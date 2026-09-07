"""
Stage 1: retrieve papers from the Semantic Scholar Academic Graph API.

This stage deliberately contains no LLM call. Retrieval and its failure modes
are proven first, so that later LLM-dependent stages are built onto a
foundation already known to work.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Read from .env rather than the source: the repository is public, and a
# committed credential persists in Git history even after removal.
load_dotenv()
api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

# requests deletes None-valued headers in merge_setting() before preparing the
# request, so a missing key raises nothing: the call goes out unauthenticated,
# into a pool shared with all other unauthenticated users, and can be throttled
# for reasons unrelated to this client. An invalid key returns a 403 and names
# the problem; an absent one does not.
if not api_key:
    print("SEMANTIC_SCHOLAR_API_KEY not found. Check .env exists and the name matches.")
    sys.exit(1)

url = "https://api.semanticscholar.org/graph/v1/paper/search"

# Only the fields needed for this connectivity test are requested; smaller
# responses reduce load on a shared public API. externalIds is required
# because the DOI is nested inside it rather than returned at the top level.
# From stage 3 abstracts and authors join the same call, since retrieving them
# afterwards would add requests under a limit shared across all endpoints.
params = {
    "query": "multi-agent systems",
    "limit": 3,
    "fields": "title,year,externalIds",
}

# A header rather than a URL parameter, so the key stays out of the request
# line, and therefore out of browser history and standard access logs.
headers = {"x-api-key": api_key}

# requests applies no timeout by default, so a stalled connection would hang
# indefinitely with no output. RequestException is the parent of timeouts, DNS
# failures and refused connections, so one clause covers every case where no
# response arrived at all, which is distinct from one that arrived refused.
try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
except requests.RequestException as exc:
    print(f"Request could not be completed: {exc}")
    sys.exit(1)

# Checked before the body is read. The 429 and 500 encountered during
# development both returned valid JSON without a "data" key, so reading
# results directly reported KeyError: 'data' rather than the actual failure.
if response.status_code != 200:
    print(f"Request failed: {response.status_code} - {response.text}")
    sys.exit(1)

# A 200 whose body will not parse is a separate failure from one whose JSON
# lacks an expected key, and neither is a retrieval result.
try:
    data = response.json()
except requests.exceptions.JSONDecodeError:
    print("Request succeeded but the response body was not valid JSON.")
    sys.exit(1)

# Four states are kept apart: no response, a refused response, a response that
# cannot be read as expected, and a readable one whose result set may be empty.
# Only the last is a retrieval outcome. Collapsing the others into it would
# have the Retrieval Agent reformulate a sound query after an infrastructure
# fault. Every search response carries "total", so its absence means the body
# is not a search result at all.
if "total" not in data:
    print("Request succeeded but the response was not a search result.")
    sys.exit(1)

# On zero matches the API omits "data" entirely rather than returning an empty
# list, confirmed by inspecting a live response to a query with no matches. An
# absent "data" is therefore a normal empty result, not a malformed body.
papers = data.get("data", [])

# {"data": null} is valid JSON and would otherwise pass as a zero-result
# search. Not observed from this endpoint, but the distinction above holds
# only if the shape is checked. Pydantic supersedes this check at stage 2.
if not isinstance(papers, list):
    print("Request succeeded but the 'data' field was not a list.")
    sys.exit(1)

# An empty result set is a successful request, so this exits 0. It justifies
# query reformulation by the Retrieval Agent, whereas a refusal justifies a retry.
if not papers:
    print("Request succeeded but returned no matching papers.")
    sys.exit(0)

for paper in papers:
    print(paper["title"])