"""
Researcher interface: the boundary where the human reviews and decides.

Mirrors the ResearcherInterface boundary class in Diagram 1. Kept in its own
module so the checkpoints are visible as a distinct concern rather than
scattered through the orchestrator, and so the run sequence can be tested
without a terminal by substituting this module's functions.

This is the one place that uses print rather than logging. The log is a record
written for later inspection; these lines are a conversation with someone
sitting at the terminal now. Sending prompts through the logger would stamp
them with a timestamp and a module name, and mix questions to the researcher
into the same stream as the system's own account of itself.
"""

import logging

from src.models import Assessment, Decision, Paper, SubQuestion

logger = logging.getLogger(__name__)


def _ask(prompt: str, valid: dict[str, Decision]) -> Decision:
    """
    Read a choice, re-asking until it is one of the offered options.

    Re-asking rather than exiting on a mistyped answer: an unrecognised key
    press is not a reason to discard a plan the researcher has not yet
    rejected, and this checkpoint may have already cost several LLM calls.
    """
    options = "/".join(valid)
    while True:
        answer = input(f"{prompt} [{options}]: ").strip().lower()
        if answer in valid:
            return valid[answer]
        print(f"Please answer with one of: {options}")


def _require_reason(prompt: str) -> str:
    """
    Read a non-empty reason, asking again until one is given.

    An empty reason would send the Planning Agent to regenerate with nothing
    to work from, producing a different decomposition by chance rather than by
    correction. Used at both checkpoints, since a revision and a scope
    rejection both depend on the researcher saying what was wrong.
    """
    while True:
        reason = input(prompt).strip()
        if reason:
            return reason
        print("A reason is needed. Describe what should change.")


def review_sub_questions(sub_questions: list[SubQuestion]) -> tuple[Decision, str | None]:
    """
    Present the decomposition and return the researcher's decision.

    Returns the decision together with any feedback, since a revision is
    meaningless without the reason for it. Diagram 2 shows only approval or
    revision at this checkpoint: scope rejection belongs to the evidence
    review, once there is evidence to judge the scope against.

    Both the sub-question and the query it will search are shown. The
    researcher is approving what gets sent to the literature API, not only how
    the question was phrased, and those are different things.
    """
    print("\n" + "=" * 70)
    print("HUMAN REVIEW 1 — Sub-question review")
    print("=" * 70)
    print("\nThe research question was decomposed into:\n")

    for sub_question in sub_questions:
        print(f"  {sub_question.id}. {sub_question.text}")
        print(f"     search query: {sub_question.search_query}\n")

    print("Nothing has been searched yet.\n")

    decision = _ask(
        "Approve this decomposition, or ask for a revision?",
        {"approve": Decision.APPROVE, "revise": Decision.REVISE},
    )

    if decision is Decision.APPROVE:
        # Logged as well as printed: the decision is part of the account of
        # the run, whereas the prompts above are not.
        logger.info("Researcher approved %d sub-questions", len(sub_questions))
        return decision, None

    feedback = _require_reason("What should change? ")
    logger.info("Researcher requested revision: %r", feedback)
    return decision, feedback


def _selected_papers(
    assessments: list[Assessment], papers: list[Paper]
) -> list[tuple[Paper, float, list[int]]]:
    """
    Reduce per-pairing assessments to one row per selected paper.

    A paper is scored once per sub-question, so a paper relevant to two
    aspects appears twice in the assessments. The researcher is deciding
    whether to keep a paper, not a pairing, so the rows are collapsed: the
    highest score is shown, together with which sub-questions it was selected
    for. Showing the pairings unreduced would ask the researcher to deselect
    the same paper twice.
    """
    best: dict[str, tuple[float, list[int]]] = {}
    for assessment in assessments:
        if not assessment.selected:
            continue
        score, ids = best.get(assessment.paper_title, (0.0, []))
        best[assessment.paper_title] = (
            max(score, assessment.relevance_score),
            sorted(ids + [assessment.sub_question_id]),
        )

    by_title = {paper.title: paper for paper in papers}
    rows = [
        (by_title[title], score, ids)
        for title, (score, ids) in best.items()
        if title in by_title
    ]
    # Highest scoring first, so the researcher reads the strongest evidence
    # before deciding.
    return sorted(rows, key=lambda row: row[1], reverse=True)


def _parse_deselection(answer: str, count: int) -> list[int] | None:
    """
    Read a comma-separated list of row numbers, or None if it cannot be read.

    Returns None rather than raising or guessing. A researcher who mistypes a
    number should be asked again: silently ignoring an unrecognised entry
    would keep a paper they meant to remove, and the mistake would not be
    visible in the output.
    """
    chosen = []
    for part in answer.replace(" ", "").split(","):
        if not part.isdigit():
            return None
        index = int(part)
        if not 1 <= index <= count:
            return None
        chosen.append(index)
    return chosen


def review_evidence(
    assessments: list[Assessment], papers: list[Paper]
) -> tuple[Decision, list[str], str | None]:
    """
    Present the selected evidence and return the researcher's decision.

    Returns the decision, the titles to keep, and any feedback. A refinement
    is expressed as a result rather than as an instruction the caller must
    interpret. On approval the list is what the agent proposed; on scope
    rejection it is empty and the feedback carries the reason, which the
    Planning Agent needs in order to revise rather than merely regenerate.

    All three outcomes from Diagram 2 are offered here, unlike the first
    checkpoint: scope can only be rejected once there is evidence to judge the
    scope against.

    Papers excluded from scoring are listed separately. They carry no abstract,
    so the system has no basis to assess them, but a researcher can recognise a
    paper from its title in a way this system should not attempt.
    """
    rows = _selected_papers(assessments, papers)
    unscored = [paper for paper in papers if not paper.abstract]

    print("\n" + "=" * 70)
    print("HUMAN REVIEW 2 — Evidence review")
    print("=" * 70)

    if rows:
        print(f"\n{len(rows)} paper(s) selected from {len(papers)} retrieved:\n")
        for number, (paper, score, ids) in enumerate(rows, start=1):
            aspects = ", ".join(str(i) for i in ids)
            print(f"  {number}. [{score:.2f}] {paper.title}")
            print(f"     addresses sub-question(s) {aspects}")
            verification = (
                "verified" if paper.doi_verified else paper.verification_note or "unverified"
            )
            print(f"     {verification}\n")
    else:
        print("\nNo paper met the selection threshold.\n")

    if unscored:
        print(f"{len(unscored)} record(s) could not be scored, having no abstract:\n")
        for paper in unscored:
            print(f"  - {paper.title}")
        print()

    decision = _ask(
        "Approve this evidence, refine the selection, or reject the scope?",
        {
            "approve": Decision.APPROVE,
            "refine": Decision.REFINE,
            "reject": Decision.REJECT_SCOPE,
        },
    )

    if decision is Decision.APPROVE:
        titles = [paper.title for paper, _, _ in rows]
        logger.info("Researcher approved %d selected paper(s)", len(titles))
        return decision, titles, None

    if decision is Decision.REJECT_SCOPE:
        # No titles returned. A scope rejection is a judgement that the
        # question was wrong, so the evidence gathered under it is not a
        # partial answer to be salvaged.
        feedback = _require_reason("Why is the scope wrong? ")
        logger.info("Researcher rejected the scope: %r", feedback)
        return decision, [], feedback

    if not rows:
        # Nothing to refine, so the request cannot be honoured. Treated as a
        # scope rejection rather than an approval of an empty set, since
        # approving nothing would produce a brief with no evidence in it.
        logger.info("Refinement requested with no selected papers; treating as scope rejection")
        feedback = _require_reason("Nothing was selected. What should change? ")
        return Decision.REJECT_SCOPE, [], feedback

    while True:
        answer = input("Which numbers should be removed? (or 'none'): ").strip().lower()
        if answer in ("none", ""):
            drop: list[int] = []
            break
        parsed = _parse_deselection(answer, len(rows))
        if parsed is not None:
            drop = parsed
            break
        print(f"Enter numbers between 1 and {len(rows)}, separated by commas.")

    kept = [
        paper.title
        for number, (paper, _, _) in enumerate(rows, start=1)
        if number not in drop
    ]
    logger.info(
        "Researcher refined the selection: %d kept, %d removed", len(kept), len(drop)
    )
    return decision, kept, None