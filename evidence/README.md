# Evidence of Execution

Stage 1: retrieval from the Semantic Scholar Academic Graph API.

| File | What it demonstrates |
|---|---|
| 01_stage1_failure_500_server_error.png | Server-side fault, revealed after diagnostic printing was added |
| 02_stage1_failure_429_key_loaded.png | Rate-limit response despite the key loading correctly from .env, eliminating local configuration as the cause |
| 03_stage1_retrieval_success.png | Three papers retrieved with status-code validation in place. No change was made to the request itself between this run and the failures above; the key becoming active is the likely explanation |
| 04_stage1_error_handling_verified.png | Status-code check verified by deliberately invalidating the API key. The resulting 403 is reported directly rather than surfacing as an unrelated KeyError |