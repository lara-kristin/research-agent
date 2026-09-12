"""
Gemini API client.

The one place that knows this provider's endpoint, request shape, response
nesting and failure modes. Agents call generate_json and receive parsed data,
so a change of provider is confined to this module in the same way a change of
literature source is confined to semantic_scholar.py.
"""

import json
import logging
import os

from dotenv import load_dotenv

from src.clients import gemini_limiter, post

logger = logging.getLogger(__name__)

# Pinned to an exact version rather than an alias such as gemini-flash-latest,
# so that recorded evidence keeps describing the system a reader runs.
#
# The lite variant: the project's free-tier allowance is 500 requests per day
# against 20 for gemini-3.6-flash, and 15 per minute against 5. Decomposition,
# query reformulation, relevance scoring and synthesis do not require the
# strongest available model, so capability that is not needed is traded for
# runs that are. Output quality between the two was not compared; the change
# was made for quota reasons.
MODEL = "gemini-3.5-flash-lite"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")


class MissingAPIKeyError(Exception):
    """Raised when no Gemini API key is configured."""


class LLMResponseError(Exception):
    """
    Raised when a request succeeded but produced no usable answer.

    Distinct from a transport or HTTP failure, which the client layer already
    handles, and distinct from a well-formed answer the caller dislikes. This
    covers the cases where the model returned nothing to parse: a response
    carrying no candidate, or one cut short before its JSON was complete.
    """


def generate_json(
    prompt: str, schema: dict, purpose: str = "request", use_cache: bool = True
) -> object:
    """
    Send a prompt and return the parsed JSON the model produced.

    The schema is enforced by the API rather than requested in the prompt.
    Asking politely for JSON worked in every trial run, but the design
    proposal names unreliable structured output as the principal technical
    risk, and a constraint the provider applies holds for questions that have
    not been tried. Pydantic still validates the result afterwards: the schema
    governs shape, not whether the content makes sense.
    """
    if not API_KEY:
        raise MissingAPIKeyError(
            "GEMINI_API_KEY not found. Check .env exists and the name matches."
        )

    logger.info("LLM %s: sending prompt of %d characters", purpose, len(prompt))

    response = post(
        URL,
        gemini_limiter,
        headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        },
        use_cache=use_cache,
    )

    # Retryable statuses are raised by the client layer before reaching here.
    # What remains is success or a terminal refusal, such as an invalid key.
    response.raise_for_status()

    body = response.json()

    # A successful request can still carry no candidate, for instance when the
    # prompt is refused. Reading into the nesting blindly would surface that as
    # an IndexError naming nothing useful, which is the failure the stage 1
    # remediation was about.
    candidates = body.get("candidates") or []
    if not candidates:
        raise LLMResponseError(f"No candidate returned. Response keys: {list(body)}")

    candidate = candidates[0]

    # A truncated answer is not a parsing problem, and reporting it as one
    # would send the caller looking in the wrong place. MAX_TOKENS means the
    # answer was cut off mid-structure and the request needs to be smaller.
    if candidate.get("finishReason") == "MAX_TOKENS":
        raise LLMResponseError("Response truncated before the JSON was complete.")

    try:
        text = candidate["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise LLMResponseError(f"Unexpected response shape: {exc}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # The raw text is included because a schema-constrained response that
        # will not parse is a finding about the provider, not a routine error,
        # and it cannot be investigated from the exception alone.
        raise LLMResponseError(f"Schema-constrained output did not parse: {exc}") from exc