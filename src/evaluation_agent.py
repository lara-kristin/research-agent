"""
Evaluation Agent.

Scores each retrieved paper against each sub-question and applies a selection
threshold. Mirrors the evaluateEvidence operation on the Evaluation and
Synthesis Agent in Diagram 1.

The division of labour follows the design proposal: the model judges
relevance, which is a semantic question, and the agent decides what counts as
selected, which is an exact rule. Asking the model to decide selection would
make the rule vary between responses and leave nothing to audit.
"""

import logging

from src.llm import generate_json
from src.models import Assessment, Paper, SubQuestion

logger = logging.getLogger(__name__)

# A paper must be more relevant than not to be selected. That is the whole
# reasoning: like the record threshold, this number rests on no measurement.
# It is named here rather than buried in a condition, and the researcher can
# deselect anything at the evidence checkpoint, so it proposes rather than
# decides.
SELECTION_THRESHOLD = 0.6

ASSESSMENT_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "paper_title": {"type": "STRING"},
            "sub_question_id": {"type": "INTEGER"},
            "relevance_score": {"type": "NUMBER"},
            "reason": {"type": "STRING"},
        },
        "required": ["paper_title", "sub_question_id", "relevance_score", "reason"],
    },
}


def _assessable(papers: list[Paper]) -> list[Paper]:
    """
    Return the papers that carry an abstract.

    A record without one has no relevance signal to score. Sending it anyway
    would invite the model to judge on the title alone, and a title-only
    judgement is indistinguishable in the output from one made on a full
    abstract. Since Semantic Scholar withholds abstracts for some publishers
    rather than at random, scoring such records weakly would systematically
    favour preprints over published articles for a reason unrelated to their
    content.
    """
    return [paper for paper in papers if paper.abstract]


def _prompt(papers: list[Paper], sub_questions: list[SubQuestion]) -> str:
    """
    Build one prompt covering every paper and every sub-question.

    Batched into a single call rather than one call per pairing. Diagram 2
    shows a single assessment call, and the free-tier allowance is counted per
    request, so fourteen papers against three sub-questions is one request
    rather than forty-two.

    Papers are identified by title in both directions. The model is given no
    index to return, because a returned index cannot be checked against
    anything, whereas a title that does not match a retrieved paper is
    detectable.
    """
    questions = "\n".join(f"{sq.id}. {sq.text}" for sq in sub_questions)
    evidence = "\n\n".join(
        f"Title: {paper.title}\nAbstract: {paper.abstract}" for paper in papers
    )

    return f"""You are assessing retrieved literature for a research project.

Sub-questions:
{questions}

Papers:
{evidence}

Assess every paper against every sub-question, so produce one assessment for
each pairing. For each, give:
- paper_title: the paper's title, copied exactly as given above
- sub_question_id: the number of the sub-question
- relevance_score: 0.0 to 1.0, where 1.0 means the paper directly addresses
  that sub-question and 0.0 means it is unrelated
- reason: one short sentence justifying the score

Judge only what the abstract supports. Do not infer findings it does not
state."""


def evaluate_evidence(
    papers: list[Paper], sub_questions: list[SubQuestion], use_cache: bool = True
) -> list[Assessment]:
    """
    Score every assessable paper against every sub-question.

    Returns assessments with the selection threshold already applied. Scoring
    each pairing rather than each paper is what allows coverage to be reported
    per aspect of the research question: the point of decomposing it was that
    different aspects need different evidence, and a single score per paper
    could not show which aspect a paper serves.

    Papers without abstracts are excluded from scoring and reported. They are
    not discarded: the researcher sees them at the evidence checkpoint, where
    a human can judge a title in a way this system should not.
    """
    assessable = _assessable(papers)

    if len(assessable) < len(papers):
        logger.warning(
            "%d of %d records have no abstract and are excluded from scoring; "
            "they remain in the output for the researcher to judge",
            len(papers) - len(assessable),
            len(papers),
        )

    if not assessable:
        logger.warning("No record carries an abstract; nothing can be scored")
        return []

    logger.info(
        "Assessing %d papers against %d sub-questions in one request",
        len(assessable),
        len(sub_questions),
    )

    raw = generate_json(
        _prompt(assessable, sub_questions),
        ASSESSMENT_SCHEMA,
        "relevance assessment",
        use_cache=use_cache,
    )

    # Validated individually so one malformed assessment does not discard the
    # rest. The schema constrains shape; it cannot prevent a score outside the
    # permitted range, which the model is capable of returning and which
    # Assessment refuses.
    assessments: list[Assessment] = []
    for item in raw:
        try:
            assessments.append(Assessment.model_validate(item))
        except Exception as exc:
            logger.warning("Discarding an unusable assessment: %s", exc)

    # Titles are checked against the papers actually retrieved. A title the
    # model altered or invented cannot be matched back to a paper, and an
    # assessment of a paper that was never retrieved would put a fabricated
    # record into the brief, which is precisely the failure the design
    # proposal's validation controls exist to prevent.
    known_titles = {paper.title for paper in assessable}
    matched = [a for a in assessments if a.paper_title in known_titles]
    if len(matched) < len(assessments):
        logger.warning(
            "Discarded %d assessment(s) naming a paper that was not retrieved",
            len(assessments) - len(matched),
        )

    # The threshold is applied here rather than requested in the prompt, so
    # the rule is one line of code rather than a property of a response.
    selected = [
        a.model_copy(update={"selected": a.relevance_score >= SELECTION_THRESHOLD})
        for a in matched
    ]

    logger.info(
        "Assessment complete: %d of %d pairings at or above %.2f",
        sum(1 for a in selected if a.selected),
        len(selected),
        SELECTION_THRESHOLD,
    )
    return selected