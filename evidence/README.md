# Evidence of Execution

Stage 1: retrieval from the Semantic Scholar Academic Graph API.

Screenshots evidence the behaviour of the live API. Failure modes the live
service does not produce, such as a malformed response body, an absent
`total` field or a `data` field of the wrong type, are evidenced by unit
tests at stage 2 rather than by contrived captures.

| File | What it demonstrates |
|---|---|
| 01_stage1_failure_500_server_error.png | Superseded implementation: a server fault ends in `KeyError: 'data'` rather than being handled. The status and message are visible only because of a temporary diagnostic print added during investigation |
| 02_stage1_failure_429_key_loaded.png | The same defect as 01, on a rate-limit response. The key loads from `.env`, eliminating local configuration as the cause |
| 03_stage1_retrieval_success.png | Three papers retrieved from the live API and titles printed |
| 04_stage1_error_handling_verified.png | Status-code check verified by deliberately invalidating the key. The 403 is reported directly rather than as an unrelated `KeyError`. Confirms that an invalid key is refused rather than throttled, which is what establishes the 429 in 02 as a genuine rate limit rather than a rejected credential |
| 05_stage1_error_handling_live_429.png | The same check as 04, handling a live rate-limit response, followed by a successful retry. Intermittent 429s are a normal condition of this API rather than a one-off fault |
| 06_stage1_missing_api_key_guard.png | An absent key is reported as a configuration fault and exits 1, rather than proceeding as an unauthenticated request |
| 07_stage1_zero_results_success.png | A query with no matches is reported as a successful request and exits 0, distinguishing an empty result set from a failed one |
| 08_stage1_transport_failure.png | A live read timeout. The request opens but no response arrives within the configured limit, and it is reported as a transport failure rather than as an HTTP error response |
| 09_stage2_retry_absorbs_live_429s.png | Three paced requests take 13.4 seconds rather than the 2 required by pacing alone. Failures occurred and were absorbed by exponential backoff, so the caller received 200 in each case. Demonstrates that throttling at the stated rate limit is insufficient on its own and that retry is required alongside it. The failures are inferred from elapsed time rather than shown, since retry output was not yet logged |
| 10_stage2_retry_and_backoff_logged.png | Retry and exponential backoff observed directly against a test endpoint returning 500 on every request. Three failed attempts are logged with waits of 1s, 2s and 4s before the run gives up, showing the doubling interval and the attempt limit |
| 11_stage2_live_429_absorbed_by_backoff.png | Two consecutive live 429 responses during a single search, each logged with the service's own message and absorbed by exponential backoff at 1s and 2s. The search returns three records to the caller. Throttling at the stated rate limit paced the requests and was still insufficient on its own, which is why retry is implemented as a separate mechanism |
| 12_stage2_crossref_validation_and_preprints.png | Crossref validation across three retrieved records. One journal DOI is verified; two arXiv DOIs are identified as preprints registered with DataCite rather than Crossref, and each carries the reason on the record rather than only an unverified flag. Each DOI appears twice because the ad-hoc command used for this capture calls verify twice per paper; the orchestrator calls it once |
| 13_stage2_deduplication_by_doi.png | Deduplication across three constructed records. Two DOIs differing only in case are treated as one paper, confirming that normalisation on construction is what makes comparison reliable, and a record with no DOI is retained rather than discarded. Three records in, two out |
| 14_stage2_pipeline_search_dedupe_validate.png | Search, deduplication and Crossref validation chained as the orchestrator sequences them, over five live records. One of five verified: three are arXiv preprints and one carries no DOI at all. Each DOI is checked once. Shows both the pipeline working and the practical reach of validating against a single registration agency |
| 15_stage2_pipeline_with_storage.png | The complete stage 2 pipeline in one run: search, deduplication, Crossref validation, and saving to timestamped Markdown and JSON. Five records, one verified, both output paths reported |