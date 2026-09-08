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

from src.models import Decision, SubQuestion

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

    # An empty reason would send the agent to regenerate with nothing to work
    # from, producing another decomposition by chance rather than by
    # correction. Asked again rather than accepted.
    feedback = ""
    while not feedback:
        feedback = input("What should change? ").strip()
        if not feedback:
            print("A revision needs a reason. Describe what to change.")

    logger.info("Researcher requested revision: %r", feedback)
    return decision, feedback