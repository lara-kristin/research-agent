"""
Stage 1: retrieve papers from the Semantic Scholar Academic Graph API.

Build order note: this stage deliberately contains no LLM call. Retrieval
and its failure modes are proven first, so that later LLM-dependent stages
are added onto a foundation already known to work.
"""

import os
import requests
from dotenv import load_dotenv

# The API key is read from .env rather than written in the source, so it is
# never committed to version control. .env is listed in .gitignore.
load_dotenv()
api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

url = "https://api.semanticscholar.org/graph/v1/paper/search"

# Only the fields needed downstream are requested. Smaller responses reduce
# load on Semantic Scholar's infrastructure, as their licence asks.
# externalIds is required because the DOI is nested inside it, not returned
# as a top-level field.
params = {
    "query": "multi-agent systems",
    "limit": 3,
    "fields": "title,year,externalIds",
}

# Sent as a header rather than a URL parameter so the key does not appear in
# server logs or browser history.
headers = {"x-api-key": api_key}

response = requests.get(url, params=params, headers=headers)

# The response is checked before its contents are read. A 429 (rate limited)
# or 500 (server fault) still returns valid JSON, but without a "data" key —
# so reading results directly would raise a confusing KeyError instead of
# reporting the actual problem. Both failures were encountered during
# development, which is why this check exists at stage 1 rather than later.
if response.status_code != 200:
    print(f"Request failed: {response.status_code} - {response.text}")
    exit(1)

data = response.json()

# Results arrive nested under "data" rather than at the top level.
for paper in data["data"]:
    print(paper["title"])