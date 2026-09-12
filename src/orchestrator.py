"""
Orchestrator: the deterministic coordinator described in the design proposal.

Not an agent. It sequences the agents and performs the checks that need no
model: deduplication, validation and storage. Keeping these here rather than
inside an agent is what the proposal means by restricting model use to
semantic tasks and leaving exact rules deterministic.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.crossref import verify
from src.evaluation_agent import evaluate_evidence
from src.interface import review_evidence, review_sub_questions
from src.models import Assessment, Brief, Decision, Paper, SubQuestion
from src.planning_agent import plan_research, reformulate_query
from src.synthesis import synthesise
from src.retrieval_agent import assess_threshold, count_usable, retrieve_evidence

# Runs write here rather than into the repository root, so output is separable
# from source. Git-ignored, with one representative run copied into evidence/
# instead: an accumulating folder of run artefacts is not source code.
OUTPUT_DIR = Path("output")

# One scope revision per run, as Diagram 3 specifies. Revision at the first
# checkpoint is unrestricted because it costs one model call; correcting after
# evidence review repeats retrieval, validation and assessment, so it is
# capped. A second rejection ends the run and recommends restarting with a
# rephrased question, which is a judgement about the question rather than
# something further searching can resolve.
MAX_SCOPE_REVISIONS = 1

logger = logging.getLogger(__name__)


def retrieve_for_plan(
    sub_questions: list[SubQuestion], limit: int = 5, use_cache: bool = True
) -> list[Paper]:
    """
    Retrieve evidence for every approved sub-question, reformulating once
    where a search falls short.

    The one-retry limit is enforced here rather than inside either agent.
    retried_once records that a retry has happened; this function is what
    reads it and declines a second, which keeps retry counting among the
    deterministic responsibilities the design proposal assigns to the
    orchestrator. Diagram 2 routes the request the same way: the Retrieval
    Agent reports an unmet threshold, and the orchestrator asks the Planning
    Agent for a new query.

    A sub-question still short after its retry is logged and its records kept.
    Diagram 3 flags insufficient coverage and proceeds rather than stopping:
    thin evidence for one aspect of a question is a finding the researcher
    should see at the evidence checkpoint, not a reason to abandon the other
    aspects.

    Retrieval refuses to run on sub-questions the researcher has not approved.
    A flag recording approval is only a control if something checks it.

    The list is updated in place where a query is reformulated, so retried_once
    reaches the caller. Without that the guard on it could never fire, and a
    later stage could not tell which aspects were searched under a query other
    than the one approved.

    No separate search budget is enforced. With the sub-question count fixed
    at three and one retry each, a run is bounded at six searches by
    construction, so the searchBudget field in Diagram 1 could never bind. If
    the count is ever made variable, that field becomes necessary.
    """
    # The checkpoint is enforced here rather than assumed. Recording approval
    # on each sub-question only helps if something reads it: without this
    # check, Human Review 1 would be enforced by the order in which functions
    # happen to be called, which is a convention rather than a control. The
    # design proposal makes researcher authority over scope a property of the
    # system, so it is checked where the consequence occurs.
    unapproved = [sq.id for sq in sub_questions if not sq.approved]
    if unapproved:
        raise ValueError(
            f"Retrieval requires approved sub-questions; {unapproved} are unapproved."
        )

    all_papers: list[Paper] = []
    thin_coverage: list[int] = []

    for index, sub_question in enumerate(sub_questions):
        papers = retrieve_evidence(sub_question, limit=limit, use_cache=use_cache)

        # Assessed once and the result held. Calling the check again in a
        # later branch would issue a second identical log line, which would
        # misrepresent the run in the record the design proposal requires for
        # post-run inspection.
        met = assess_threshold(papers)

        if not met and not sub_question.retried_once:
            sub_question = reformulate_query(sub_question, use_cache=use_cache)

            # Written back into the list the caller holds. Rebinding the loop
            # variable alone left retried_once set on a copy that was then
            # discarded, so the flag never reached the caller: the one-retry
            # guard above could not fire, and the brief could not report which
            # aspects had been searched under a reformulated query.
            sub_questions[index] = sub_question

            retried_papers = retrieve_evidence(
                sub_question, limit=limit, use_cache=use_cache
            )

            # The reformulated query is kept only if it did better, judged on
            # usable records rather than the raw count. A retry returning more
            # records but fewer abstracts is not an improvement, and comparing
            # totals would treat it as one.
            if count_usable(retried_papers) > count_usable(papers):
                papers = retried_papers
                met = assess_threshold(papers)
            else:
                logger.info(
                    "Reformulation for sub-question %d returned no more records; keeping the original result",
                    sub_question.id,
                )

        if not met:
            thin_coverage.append(sub_question.id)

        all_papers.extend(papers)

    if thin_coverage:
        logger.warning(
            "Insufficient coverage for sub-question(s) %s. This is reported rather than corrected: "
            "the researcher judges it at the evidence checkpoint",
            ", ".join(str(i) for i in thin_coverage),
        )

    logger.info(
        "Retrieval complete: %d records across %d sub-questions",
        len(all_papers),
        len(sub_questions),
    )
    return all_papers


def deduplicate_by_doi(papers: list[Paper]) -> list[Paper]:
    """
    Remove repeated records, identified by DOI.

    Records without a DOI are all retained. They cannot be compared on the
    field this function deduplicates by, and falling back to title comparison
    would risk merging two genuinely different papers whose titles resemble
    each other. That failure is worse than the one it prevents: a duplicate is
    visible in the output, whereas a paper silently discarded is not. The
    diagram specifies deduplication by DOI, so the absence of one is reported
    rather than worked around.

    The first occurrence is kept, so where the same paper arrives under two
    sub-questions the earlier retrieval survives. Order is otherwise
    preserved, which keeps a run's output comparable between executions.
    """
    seen: set[str] = set()
    unique: list[Paper] = []
    duplicates = 0

    for paper in papers:
        if paper.doi is None:
            # Retained deliberately, not overlooked. Logged so the count of
            # unverifiable records in a run is recoverable afterwards.
            logger.debug("Retaining record with no DOI: %r", paper.title)
            unique.append(paper)
            continue

        # Comparison is safe without normalising here, because Paper lowercases
        # and strips the DOI on construction. Doing it once at the boundary
        # rather than at each comparison is what makes that possible.
        if paper.doi in seen:
            duplicates += 1
            logger.debug("Duplicate DOI discarded: %s", paper.doi)
            continue

        seen.add(paper.doi)
        unique.append(paper)

    logger.info(
        "Deduplication: %d records in, %d out, %d duplicates removed",
        len(papers),
        len(unique),
        duplicates,
    )
    return unique


def validate_dois_and_metadata(papers: list[Paper]) -> list[Paper]:
    """
    Check every record against Crossref and return them with the outcome set.

    A failure to reach Crossref is deliberately not caught here. Recording it
    as an unverified result would conflate an infrastructure fault with a
    verification finding, which is the same conflation the status-code
    handling at stage 1 exists to prevent. Retryable failures have already
    been absorbed by the client, so anything reaching this point is terminal
    and the caller needs to hear about it rather than read it as evidence
    about a paper.

    Called once per paper. The ad-hoc commands used during development called
    verify twice per record, which doubled Crossref requests for no benefit.
    """
    validated = [verify(paper) for paper in papers]

    verified_count = sum(1 for paper in validated if paper.doi_verified)
    logger.info(
        "Validation: %d of %d records verified against Crossref",
        verified_count,
        len(validated),
    )
    return validated


def _paper_to_markdown(
    paper: Paper,
    summary: str | None = None,
    score: float | None = None,
    sub_question_ids: list[int] | None = None,
) -> str:
    """
    Render one paper for a human reader.

    Verification status is stated on every record rather than only on the
    unverified ones. A reader who sees nothing cannot tell whether a paper was
    checked and passed or was never checked, and the design proposal requires
    the flagged state to be visible to the researcher rather than held
    internally.

    The abstract is deliberately not reproduced here. The summary exists to
    spare the reader the abstract, and printing both made the brief largely a
    repetition of its sources while blurring which text the system produced
    and which it retrieved. Abstracts remain in the JSON, where a machine
    reader may want the source text.
    """
    heading = f"### {paper.title}" if score is None else f"### [{score:.2f}] {paper.title}"
    lines = [heading, ""]

    if paper.authors:
        lines.append(f"**Authors:** {', '.join(paper.authors)}")
    if paper.year:
        lines.append(f"**Year:** {paper.year}")

    if paper.doi:
        lines.append(f"**DOI:** {paper.doi}")
        status = "verified against Crossref" if paper.doi_verified else "not verified"
        if paper.verification_note:
            status = f"{status} ({paper.verification_note})"
        lines.append(f"**Verification:** {status}")
    else:
        lines.append("**DOI:** none in record")
        lines.append("**Verification:** not possible without a DOI")

    # Which aspects of the question this paper was selected for. Decomposing
    # the question was what made per-aspect coverage knowable, and a brief
    # that omits it discards the distinction the decomposition created.
    if sub_question_ids:
        aspects = ", ".join(str(i) for i in sub_question_ids)
        lines.append(f"**Addresses sub-question(s):** {aspects}")

    if summary:
        lines.extend(["", f"**Summary (generated from the abstract):** {summary}"])
    else:
        # Stated rather than left blank, so a missing summary is visible as an
        # absence rather than mistaken for a rendering fault.
        lines.extend(["", "_No summary was produced for this paper._"])

    return "\n".join(lines)


def _brief_to_markdown(brief: Brief, assessments: list[Assessment]) -> str:
    """
    Render the brief for a human reader.

    Ordered as a reader needs it: what was asked, what was searched across,
    what was found, then what the search could not establish. The limitations
    come last because they qualify everything above them.
    """
    out = [f"# Research brief: {brief.research_question}", ""]

    if brief.sub_questions:
        out.extend(["## Sub-questions searched", ""])
        for sub_question in brief.sub_questions:
            out.append(f"{sub_question.id}. {sub_question.text}")
            out.append(f"   - search query: `{sub_question.search_query}`")
        out.append("")

    if brief.themes:
        out.extend(["## Themes across the evidence", ""])
        out.extend(f"- {theme}" for theme in brief.themes)
        out.append("")

    if brief.gaps:
        out.extend(["## Gaps this evidence does not address", ""])
        out.extend(f"- {gap}" for gap in brief.gaps)
        out.append("")

    # Scores and sub-question attribution are carried into the output rather
    # than discarded. A brief recording which papers were selected, but not how
    # strongly or for which aspect, leaves the researcher unable to review that
    # judgement afterwards.
    best_score: dict[str, float] = {}
    aspects: dict[str, list[int]] = {}
    for assessment in assessments:
        if not assessment.selected:
            continue
        title = assessment.paper_title
        best_score[title] = max(best_score.get(title, 0.0), assessment.relevance_score)
        aspects[title] = sorted(aspects.get(title, []) + [assessment.sub_question_id])

    if brief.selected_papers:
        # Strongest first, matching the order the researcher reviewed them in.
        ordered = sorted(
            brief.selected_papers,
            key=lambda paper: best_score.get(paper.title, 0.0),
            reverse=True,
        )
        out.extend([f"## Selected papers ({len(ordered)})", ""])
        for paper in ordered:
            out.append(
                _paper_to_markdown(
                    paper,
                    brief.summaries.get(paper.title),
                    best_score.get(paper.title),
                    aspects.get(paper.title),
                )
            )
            out.append("")

    out.extend(["## Limitations of this search", ""])
    out.extend(f"- {limitation}" for limitation in brief.limitations)

    return "\n".join(out) + "\n"


def save_brief(brief: Brief, assessments: list[Assessment]) -> tuple[Path, Path]:
    """
    Write the brief to Markdown and JSON, and return both paths.

    Two formats because they serve different readers: Markdown for the
    researcher, JSON so a later run or a test can read the same record back
    without reparsing prose. The design proposal requires both.

    Named save_brief rather than save_papers because there is now a brief to
    save. The earlier name described what that function actually wrote, which
    was a list of papers; renaming it before a Brief existed would have
    misdescribed its output.

    Filenames carry a timestamp so a run cannot overwrite the record of the
    one before it, which is the same reason the log file appends.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = OUTPUT_DIR / f"brief_{stamp}.json"
    markdown_path = OUTPUT_DIR / f"brief_{stamp}.md"

    # The JSON carries every assessment, not only the selected ones. Anyone
    # reconstructing the decision needs to see what was rejected as well as
    # what was kept, and the Markdown shows only the selection.
    payload = brief.model_dump()
    payload["retrieved_at"] = stamp
    payload["assessments"] = [assessment.model_dump() for assessment in assessments]

    # encoding specified explicitly on both writes. Windows defaults to a
    # legacy code page that cannot represent the characters common in author
    # names and abstracts, so an unspecified encoding fails on real data
    # rather than on anything contrived.
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    markdown_path.write_text(_brief_to_markdown(brief, assessments), encoding="utf-8")

    logger.info(
        "Saved brief with %d paper(s) to %s and %s",
        len(brief.selected_papers),
        markdown_path,
        json_path,
    )
    return markdown_path, json_path


def _plan_with_review(
    question: str, feedback: str | None = None, use_cache: bool = True
) -> list[SubQuestion]:
    """
    Decompose the question and revise until the researcher approves.

    The loop is here rather than in the Planning Agent or the interface,
    because Diagram 2 places it in the orchestrator's control flow: the agent
    produces a plan, the interface collects a verdict, and neither decides
    whether to go round again.

    Uncapped by design. The design proposal leaves revision at this checkpoint
    unrestricted and caps only the later one, on the grounds that correcting
    here costs a single model call. Each iteration is a human choosing to
    revise, so there is no runaway to guard against.

    Approval is recorded on the sub-questions themselves rather than implied
    by returning from this function, and retrieval refuses any that lack it.
    """
    while True:
        sub_questions = plan_research(question, feedback, use_cache=use_cache)
        decision, feedback = review_sub_questions(sub_questions)

        if decision is Decision.APPROVE:
            return [sq.model_copy(update={"approved": True}) for sq in sub_questions]


def run_research(
    question: str, limit: int = 5, use_cache: bool = True
) -> tuple[Brief, list[Assessment]] | None:
    """
    Run the whole sequence and return the assembled brief, or None if the
    researcher rejected the scope and no revision remains.

    The sequence lives here rather than in the entry point because the design
    proposal makes the orchestrator the central coordinator, and Diagram 1
    places both review presentations on it. The entry point parses arguments,
    configures logging and translates the outcome into an exit code.

    The outer loop is the scope revision cycle. A rejection returns to
    decomposition carrying the researcher's reason, so the second attempt is a
    correction rather than another guess, and everything downstream is redone
    because a changed plan invalidates the evidence gathered under the old
    one.
    """
    scope_revisions = 0
    feedback: str | None = None

    while True:
        sub_questions = _plan_with_review(question, feedback, use_cache=use_cache)

        papers = retrieve_for_plan(sub_questions, limit=limit, use_cache=use_cache)
        if not papers:
            logger.info("No matching papers for any sub-question.")
            return Brief(research_question=question, sub_questions=sub_questions), []

        papers = deduplicate_by_doi(papers)
        papers = validate_dois_and_metadata(papers)
        assessments = evaluate_evidence(papers, sub_questions, use_cache=use_cache)

        decision, kept_titles, feedback = review_evidence(assessments, papers)

        if decision is not Decision.REJECT_SCOPE:
            # Filtered by title rather than by index, so the set the
            # researcher approved is the set that reaches synthesis even if
            # the ordering changes.
            approved = [paper for paper in papers if paper.title in kept_titles]
            logger.info("Proceeding with %d approved paper(s)", len(approved))

            brief = synthesise(
                question,
                sub_questions,
                approved,
                papers,
                assessments,
                use_cache=use_cache,
            )
            return brief, assessments

        if scope_revisions >= MAX_SCOPE_REVISIONS:
            logger.warning(
                "Scope rejected twice. Stopping: a question that survives one "
                "revision and is still wrong needs rephrasing rather than "
                "further searching"
            )
            return None

        scope_revisions += 1
        logger.info(
            "Scope revision %d of %d, returning to decomposition",
            scope_revisions,
            MAX_SCOPE_REVISIONS,
        )