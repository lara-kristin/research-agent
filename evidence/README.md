# Evidence of Execution

Stage 1: retrieval from the Semantic Scholar Academic Graph API.

| File | What it demonstrates |
|---|---|
| 01_stage1_failure_500_server_error.png | Original implementation: a server fault surfaces as KeyError: 'data', reporting nothing about the HTTP status or the reason |
| 02_stage1_failure_429_key_loaded.png | The same defect on a rate-limit response. The key loads correctly from .env, eliminating local configuration as the cause |
| 03_stage1_retrieval_success.png | Three papers retrieved with status-code validation in place |
| 04_stage1_error_handling_verified.png | Status-code check verified by deliberately invalidating the API key. The resulting 403 is reported directly rather than surfacing as an unrelated KeyError |
| 05_stage1_error_handling_live_429.png | The same check handling a genuine rate-limit response during normal use, followed by a successful retry. Intermittent 429s are a normal condition of this API rather than a one-off fault |