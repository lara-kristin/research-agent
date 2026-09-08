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
from src.models import Paper, SubQuestion
from src.planning_agent import reformulate_query
from src.retrieval_agent import assess_threshold, retrieve_evidence

# Runs write here rather than into the repository root, so output is separable
# from source. Git-ignored, with one representative run copied into evidence/
# instead: an accumulating folder of run artefacts is not source code.
OUTPUT_DIR = Path("output")

logger = logging.getLogger(__name__)


def retrieve_for_plan(
    sub_questions: list[SubQuestion], limit: int = 5
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

    No separate search budget is enforced. With the sub-question count fixed
    at three and one retry each, a run is bounded at six searches by
    construction, so the searchBudget field in Diagram 1 could never bind. If
    the count is ever made variable, that field becomes necessary.
    """
    all_papers: list[Paper] = []
    thin_coverage: list[int] = []

    for sub_question in sub_questions:
        papers = retrieve_evidence(sub_question, limit=limit)

        # Assessed once and the result held. Calling the check again in a
        # later branch would issue a second identical log line, which would
        # misrepresent the run in the record the design proposal requires for
        # post-run inspection.
        met = assess_threshold(papers)

        if not met and not sub_question.retried_once:
            sub_question = reformulate_query(sub_question)
            retried_papers = retrieve_evidence(sub_question, limit=limit)

            # The reformulated query is kept only if it did better. A broader
            # query can return less than the original, and silently accepting
            # the second result would discard evidence already retrieved.
            if len(retried_papers) > len(papers):
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


def _paper_to_markdown(paper: Paper) -> str:
    """
    Render one paper for a human reader.

    Verification status is stated on every record rather than only on the
    unverified ones. A reader who sees nothing cannot tell whether a paper was
    checked and passed or was never checked, and the design proposal requires
    the flagged state to be visible to the researcher rather than held
    internally.
    """
    lines = [f"### {paper.title}", ""]

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

    # Absence is stated rather than left blank. Semantic Scholar does not
    # return abstracts for every publisher, and a record with no abstract has
    # no relevance signal for the Evaluation Agent to score at stage 4. A
    # silently missing abstract would leave that indistinguishable from one
    # that was simply not rendered.
    if paper.abstract:
        lines.extend(["", paper.abstract])
    else:
        lines.extend(["", "_No abstract available from this source._"])

    return "\n".join(lines)


def save_papers(papers: list[Paper], query: str) -> tuple[Path, Path]:
    """
    Write the retrieved papers to Markdown and JSON, and return both paths.

    Two formats because they serve different readers: Markdown for the
    researcher, JSON so a later run or a test can read the same records back
    without reparsing prose. The design proposal requires both.

    Named save_papers rather than save_brief because a brief, as Diagram 1
    defines it, carries a research question, sub-questions, summaries, themes
    and gaps. None of those exist before stage 3, and a function claiming to
    save a brief while saving a list of papers would misdescribe its output.
    This is extended to the full Brief at stage 6, once there is one.

    Filenames carry a timestamp so a run cannot overwrite the record of the
    one before it, which is the same reason the log file appends.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = OUTPUT_DIR / f"papers_{stamp}.json"
    markdown_path = OUTPUT_DIR / f"papers_{stamp}.md"

    # encoding specified explicitly on both writes. Windows defaults to a
    # legacy code page that cannot represent the characters common in author
    # names and abstracts, so an unspecified encoding fails on real data
    # rather than on anything contrived.
    json_path.write_text(
        json.dumps(
            {
                "query": query,
                "retrieved_at": stamp,
                "count": len(papers),
                # model_dump rather than a hand-built dictionary, so a field
                # added to Paper appears in the output without a second edit.
                "papers": [paper.model_dump() for paper in papers],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    verified = sum(1 for paper in papers if paper.doi_verified)
    header = [
        f"# Retrieved papers: {query}",
        "",
        f"{len(papers)} records, {verified} verified against Crossref.",
        "",
    ]
    # Records joined by a blank line. A heading immediately following the
    # previous record's last line renders in most parsers but is fragile and
    # unreadable as plain text, which matters because the researcher may open
    # this file in an editor rather than a renderer.
    body = "\n\n".join(_paper_to_markdown(paper) for paper in papers)
    markdown_path.write_text("\n".join(header) + "\n" + body + "\n", encoding="utf-8")

    logger.info("Saved %d records to %s and %s", len(papers), markdown_path, json_path)
    return markdown_path, json_path