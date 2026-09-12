"""
Synthesis.

Produces the summaries, themes and gaps that make up the research brief.
Together with relevance assessment this is the Evaluation and Synthesis Agent
of Diagram 1: synthesis consumes the evaluation output, so keeping them as one
agent avoids a handoff while human approval still separates the two phases.

Synthesis draws only on papers the researcher approved, and only on their
abstracts. Nothing else is available to it: the system never retrieves full
text, so a claim about a paper's methods or findings beyond what its abstract
states would be unsupported.
"""

import logging

from src.llm import generate_json
from src.models import Assessment, Brief, Paper, SubQuestion

logger = logging.getLogger(__name__)

SYNTHESIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summaries": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "paper_title": {"type": "STRING"},
                    "summary": {"type": "STRING"},
                },
                "required": ["paper_title", "summary"],
            },
        },
        "themes": {"type": "ARRAY", "items": {"type": "STRING"}},
        "gaps": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summaries", "themes", "gaps"],
}


def _prompt(question: str, sub_questions: list[SubQuestion], papers: list[Paper]) -> str:
    """
    Build one prompt covering summaries, themes and gaps.

    Batched into a single request. Themes and gaps require reading across the
    papers, so the model needs all of them in context regardless; asking
    separately would send the same abstracts twice and spend two requests from
    a daily allowance.

    The instruction to ground every statement in the abstracts is the only
    control available here. Unlike relevance scores, a summary cannot be
    checked against anything the system holds, so the brief states plainly
    that summaries derive from abstracts alone.
    """
    questions = "\n".join(f"{sq.id}. {sq.text}" for sq in sub_questions)
    evidence = "\n\n".join(
        f"Title: {paper.title}\nAbstract: {paper.abstract}" for paper in papers
    )

    return f"""You are preparing a research brief from literature a researcher has approved.

Research question: {question}

Sub-questions:
{questions}

Approved papers:
{evidence}

Produce:
- summaries: one entry per paper, with paper_title copied exactly as given
  above and a two to three sentence summary of what that paper contributes to
  the research question
- themes: three to five themes recurring across these papers
- gaps: two to four aspects of the research question this set of papers does
  not address

State only what the abstracts support. Do not infer findings, methods or
conclusions they do not state, and do not draw on knowledge of these papers
from outside the abstracts given."""


def _limitations(
    papers: list[Paper],
    all_retrieved: list[Paper],
    assessments: list[Assessment],
    sub_questions: list[SubQuestion],
) -> list[str]:
    """
    State the limitations of this run from what it recorded.

    Assembled deterministically rather than asked of the model. The system
    knows which records it could not verify and which carried no abstract;
    a model asked the same question would produce plausible limitations rather
    than the ones that actually applied, which is the unfaithful-summarisation
    failure the design proposal guards against.
    """
    limitations = [
        "Summaries derive from abstracts alone. Full texts were not retrieved, "
        "so methods, results and limitations reported only in the body of a "
        "paper are not represented here.",
        "One literature source was searched. Records held only by other "
        "indexes will not appear.",
    ]

    # A retry was attempted for these aspects because the approved query
    # returned too little. The limitation reports that a reformulation
    # occurred, not that its results were used: the reformulated query is kept
    # only when it retrieved more, so asserting that the evidence came from it
    # would be false whenever the original result was retained. The query
    # shown for each sub-question above is always the one that produced the
    # evidence beneath it.
    reformulated = [sq.id for sq in sub_questions if sq.retried_once]
    if reformulated:
        ids = ", ".join(str(i) for i in reformulated)
        limitations.append(
            f"The approved query for sub-question(s) {ids} returned too few "
            "usable records, so a reformulated query was tried. The query "
            "listed for each sub-question above is the one whose results were "
            "retained, and coverage of those aspects is thinner than of the "
            "others."
        )

    unverified = [p for p in papers if not p.doi_verified]
    if unverified:
        limitations.append(
            f"{len(unverified)} of {len(papers)} selected papers could not be "
            "independently verified against Crossref. Most are preprints "
            "registered with a different agency rather than doubtful records; "
            "each paper states its own reason."
        )

    no_abstract = [p for p in all_retrieved if not p.abstract]
    if no_abstract:
        limitations.append(
            f"{len(no_abstract)} retrieved record(s) carried no abstract and "
            "were excluded from relevance scoring, so they were never "
            "candidates for selection regardless of their content."
        )

    if assessments:
        scores = {round(a.relevance_score, 2) for a in assessments}
        if len(scores) <= 5:
            limitations.append(
                "Relevance scores took only a few distinct values across this "
                "run, so they are better read as coarse bands than as fine "
                "measurements."
            )

    return limitations


def synthesise(
    question: str,
    sub_questions: list[SubQuestion],
    approved: list[Paper],
    all_retrieved: list[Paper],
    assessments: list[Assessment],
    use_cache: bool = True,
) -> Brief:
    """
    Assemble the research brief from the approved evidence.

    Returns a Brief even when nothing was approved: an empty brief that states
    its own limitations is a more honest output than no file at all, and the
    researcher who approved nothing still has a record of what was searched.
    """
    if not approved:
        logger.warning("No approved papers; producing a brief with no evidence")
        return Brief(
            research_question=question,
            sub_questions=sub_questions,
            limitations=_limitations([], all_retrieved, assessments, sub_questions)
            + ["No paper was approved, so this brief reports the search rather than its findings."],
        )

    logger.info("Synthesising a brief from %d approved paper(s)", len(approved))

    raw = generate_json(
        _prompt(question, sub_questions, approved),
        SYNTHESIS_SCHEMA,
        "synthesis",
        use_cache=use_cache,
    )

    # Summaries are matched back to approved papers by title, as assessments
    # are. A summary naming a paper that was not approved would place text
    # about an unapproved record in the brief, which is the same fabrication
    # risk the assessment stage checks for.
    approved_titles = {paper.title for paper in approved}
    summaries = {
        item["paper_title"]: item["summary"]
        for item in raw.get("summaries", [])
        if item.get("paper_title") in approved_titles
    }

    missing = approved_titles - summaries.keys()
    if missing:
        # Reported rather than filled in. A paper appearing in the brief with
        # no summary is visibly incomplete; one given a placeholder summary
        # would read as though it had been assessed.
        logger.warning("No summary returned for %d approved paper(s)", len(missing))

    brief = Brief(
        research_question=question,
        sub_questions=sub_questions,
        selected_papers=approved,
        summaries=summaries,
        themes=raw.get("themes", []),
        gaps=raw.get("gaps", []),
        limitations=_limitations(approved, all_retrieved, assessments, sub_questions),
    )

    logger.info(
        "Brief assembled: %d summaries, %d themes, %d gaps, %d limitations",
        len(brief.summaries),
        len(brief.themes),
        len(brief.gaps),
        len(brief.limitations),
    )
    return brief