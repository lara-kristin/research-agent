"""
Planning Agent.

Decomposes a research question into sub-questions and the search queries that
will retrieve evidence for them, and reformulates a query when retrieval falls
short. Model use is confined to those semantic judgements; the sequencing,
counting and validation around them stay deterministic, which is the division
the design proposal draws.
"""

import logging

from src.llm import generate_json
from src.models import SubQuestion

logger = logging.getLogger(__name__)

# The class diagram permits 3..5; the implementation fixes the count at the
# lower bound of that range. Each sub-question is a separate search against a
# key limited to one request per second, and an unmet threshold adds a
# reformulated retry, so five sub-questions can mean ten requests in one run.
# Three keeps a run to a length that completes reliably on this quota. A fixed
# count also makes a run's cost predictable, which a variable one would not.
SUB_QUESTION_COUNT = 3

# The schema is enforced by the provider, so the prompt does not need to ask
# for JSON or forbid code fences. It describes the task only.
PLAN_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "text": {"type": "STRING"},
            "search_query": {"type": "STRING"},
        },
        "required": ["id", "text", "search_query"],
    },
}

QUERY_SCHEMA = {
    "type": "OBJECT",
    "properties": {"search_query": {"type": "STRING"}},
    "required": ["search_query"],
}


def _plan_prompt(question: str, feedback: str | None = None) -> str:
    """
    Build the decomposition prompt.

    The distinction between text and search_query is stated explicitly,
    because a model given no guidance tends to return the sub-question itself
    as the query, and a natural-language question performs poorly against a
    keyword search endpoint.
    """
    prompt = f"""You are planning an academic literature search.

Research question: {question}

Decompose it into exactly {SUB_QUESTION_COUNT} sub-questions that together
cover the main aspects of the research question. Number them from 1.

For each sub-question provide:
- text: the sub-question as a researcher would phrase it
- search_query: three to six keywords for an academic search API, not a
  sentence and not a question"""

    if feedback:
        prompt += f"""

The researcher reviewed a previous decomposition and asked for changes:
{feedback}

Produce a new decomposition addressing that feedback."""

    return prompt


def plan_research(
    question: str, feedback: str | None = None, use_cache: bool = True
) -> list[SubQuestion]:
    """
    Decompose a research question into sub-questions with search queries.

    The same function serves the first plan and any revision, with feedback
    distinguishing them. Diagram 2 shows revision returning to the same agent
    rather than to a separate path, and revisions at this checkpoint are
    unrestricted, so no attempt count is tracked here.

    The provider constrains the shape of the response; Pydantic validates it
    afterwards and the count is checked here. Shape, content and quantity are
    three different claims, and the schema only guarantees the first.
    """
    logger.info(
        "Planning %s for: %r",
        "revision" if feedback else "decomposition",
        question,
    )

    raw = generate_json(
        _plan_prompt(question, feedback), PLAN_SCHEMA, "decomposition", use_cache=use_cache
    )

    sub_questions = [SubQuestion.model_validate(item) for item in raw]

    # The schema cannot express "exactly three", so the count is checked here.
    # Logged rather than raised: a plan of two or four is still usable, and the
    # researcher reviews it before anything is searched. Failing the run would
    # discard a usable plan over a condition the human checkpoint already
    # covers.
    if len(sub_questions) != SUB_QUESTION_COUNT:
        logger.warning(
            "Expected %d sub-questions, received %d",
            SUB_QUESTION_COUNT,
            len(sub_questions),
        )

    for sub_question in sub_questions:
        logger.info("  %d. %s [query: %s]", sub_question.id, sub_question.text, sub_question.search_query)

    return sub_questions


def reformulate_query(sub_question: SubQuestion, use_cache: bool = True) -> SubQuestion:
    """
    Produce a different search query for a sub-question that returned too
    little.

    Returns a copy with the new query and retried_once set. The flag records
    that a retry has happened; it does not prevent another. Calling this twice
    would issue two requests, because enforcing the one-retry limit is a
    workflow rule and the design proposal assigns workflow rules to the
    orchestrator. The orchestrator checks the flag before calling, which keeps
    retry counting deterministic rather than depending on an agent to police
    a limit on itself.
    """
    prompt = f"""An academic search returned too few results.

Sub-question: {sub_question.text}
Query used: {sub_question.search_query}

Provide one different search query for the same sub-question. Broaden the
terms or use alternative vocabulary. Three to six keywords, not a sentence."""

    raw = generate_json(prompt, QUERY_SCHEMA, "query reformulation", use_cache=use_cache)
    new_query = raw["search_query"]

    logger.info(
        "Reformulated query for sub-question %d: %r -> %r",
        sub_question.id,
        sub_question.search_query,
        new_query,
    )

    return sub_question.model_copy(
        update={"search_query": new_query, "retried_once": True}
    )