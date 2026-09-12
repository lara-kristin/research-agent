# Research Agent

An agent-based system that helps a researcher begin a literature search. It
decomposes a research question into sub-questions, retrieves scholarly
literature for each, validates what it finds against an independent source,
assesses relevance, and assembles a research brief.

It is intended for the start of a search rather than the end of one: the
output is a structured set of candidate papers with summaries, themes, gaps
and stated limitations, not a finished review.

Built for the Intelligent Agents module, MSc Artificial Intelligence,
University of Essex Online, as the individual implementation of a group design
proposal.

## How it works

Three agents, coordinated by a deterministic orchestrator that is not itself
an agent:

- **Planning Agent** decomposes the research question into three
  sub-questions, each with its own keyword search query, and reformulates a
  query when retrieval returns too little.
- **Retrieval Agent** searches Semantic Scholar for each sub-question and
  judges whether the result meets a configured threshold of usable records.
- **Evaluation and Synthesis Agent** scores each paper against each
  sub-question, and summarises the approved papers into a brief.

The orchestrator sequences them and performs every check that needs no model:
deduplication by DOI, validation against Crossref, threshold and retry
counting, and storage. Model use is confined to semantic judgements.

Two human review points bound the process. The researcher approves or revises
the sub-questions before anything is searched, and approves, refines or
rejects the selected evidence before anything is synthesised. Revision at the
first point is unlimited; scope rejection after the second is capped at one
per run.

## Requirements

Python 3.11 or later, as specified in the design proposal. Developed and
tested on Python 3.14.

Dependencies are pinned in `requirements.txt`:

| Package | Role |
|---|---|
| `requests` | HTTP calls to all three external services |
| `python-dotenv` | loads API keys from `.env` rather than the source |
| `pydantic` | validates model output and API responses against declared shapes |
| `tenacity` | retry with exponential backoff |
| `pytest` | test runner |

API keys are needed for Semantic Scholar and Google Gemini. Both are free.
Crossref needs no key, though a contact address is requested.

The free tiers impose limits that shape how the system behaves. Semantic
Scholar allows one request per second across its endpoints and returns 429
frequently regardless; the Gemini free tier allowed 15 requests per minute and
500 per day for the pinned model at the time of writing. Both figures are
worth checking against the providers, since they change. A single run uses
between two and six model requests depending on how often a query is
reformulated.

## Installation

```bash
git clone https://github.com/lara-kristin/research-agent.git
cd research-agent
python -m venv .venv
```

Activate the environment:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS and Linux
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create a file named `.env` in the project root:

```
SEMANTIC_SCHOLAR_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
CROSSREF_CONTACT_EMAIL=your.email@example.com
```

A Semantic Scholar key can be requested at
https://www.semanticscholar.org/product/api, and a Gemini key created at
https://aistudio.google.com. The Crossref contact address is optional: it
identifies the caller and grants access to a more reliably provisioned pool of
servers.

`.env` is excluded from version control and should not be committed.

## Running

```bash
python -m src.main "What are the failure modes of LLM-based multi-agent systems?"
```

Options:

| Option | Meaning |
|---|---|
| `--limit N` | maximum records retrieved per sub-question (default 5) |
| `--no-cache` | issue every request live, bypassing the response cache |

The run pauses twice for input. At the first checkpoint, type `approve` or
`revise`. At the second, type `approve`, `refine` or `reject`; refining asks
for the row numbers to remove.

## Output

Each run writes a timestamped brief to `output/` in two formats. The Markdown
is for the researcher. The JSON holds the same brief plus every relevance
assessment, including those that were not selected, so a decision can be
reconstructed afterwards.

Every run also appends to `run.log`, which records each request, each retry,
each validation outcome and each decision. Cached responses are logged as
such, so a cached run and a live run are distinguishable.

`output/`, `run.log` and `cache/` are excluded from version control.

## Caching

Responses are cached on disk for 24 hours to conserve the Gemini free tier's
daily request allowance, which cannot be relieved by pacing. Use `--no-cache`
when current results matter; a bypassed request still refreshes what is
stored.

## Tests

```bash
pytest
```

The suite runs without network access. External calls are replaced with
recorded or constructed responses, so it is deterministic and remains
available while a service is rate limiting. It also covers conditions the live
services do not produce on demand, such as a malformed response body or an
exhausted daily quota.

## Scope and limitations

- Abstracts only. Full texts are not retrieved, so anything reported only in
  the body of a paper is not represented.
- One literature source. Records held only by other indexes will not appear.
- Validation reaches Crossref-registered records. Preprints registered with
  other agencies, notably arXiv, are identified as such rather than verified,
  and a large share of results in some fields are preprints.
- Relevance scores are coarse bands rather than fine measurements.
- Each brief states the limitations that applied to its own run.

## Acknowledgements

This project uses the following external services. None is affiliated with it.

- **Semantic Scholar Academic Graph API**, the literature source, provided by
  the Allen Institute for AI. Kinney, R. et al. (2023) 'The Semantic Scholar
  Open Data Platform', *arXiv*. Available at:
  https://doi.org/10.48550/arXiv.2301.10140
- **Crossref REST API**, used to verify DOIs and their metadata independently
  of the source they were retrieved from. https://www.crossref.org
- **Google Gemini API**, the language model used for question decomposition,
  query reformulation, relevance assessment and summarisation. Pinned to
  `gemini-3.5-flash-lite` rather than an alias such as `gemini-flash-latest`,
  so that a later run describes the same system. The lite variant was chosen
  for its free-tier allowance, 500 requests per day against 20 for
  `gemini-3.6-flash`; the semantic tasks here do not require the strongest
  available model. Output quality between the two was not compared.
- **httpbin.org**, used to produce deterministic HTTP error responses when
  testing retry behaviour. Not used at runtime.

Free-tier Gemini requests may be used by the provider to improve their
products. No confidential material is sent: prompts contain the research
question and publicly available abstracts.