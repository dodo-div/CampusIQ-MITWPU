# CampusIQ development report

Verified locally on 13 November 2026 (Asia/Calcutta). No public deployment, database rebuild, knowledge-base expansion or official-document edits were performed. This checkout has no Git metadata, so a Git diff/commit audit was unavailable.

## Bugs and behavior

- Exact qualified commencement and last-instructional-day questions use the existing structured calendar records and existing date validator. No individual answer dates are embedded in the new answer logic. Conflicting or missing records abstain; missing qualifiers request clarification.
- Semester II end returns 8 May 2027, with calendar page 2 and PDF highlight evidence. The 9 May attendance-locking date remains rejected. Exact answers bypass Gemini and embeddings and are cached.
- Explicit ordinance 2020/2022 requests now select that document before batch-based defaults. Unsupported or multiple explicit ordinance versions do not silently fall back. Applicability notices remain.
- Ordinarily retrieved ordinance evidence gains lexical fallback candidates before query expansions; expansions run when no relevant candidates remain. Complementary chunks on one page are retained, while identical passages are deduplicated.
- Citation filtering rejects fabricated explicit references and absence-only citations; separately cited factual background can remain. Bold source headings, inline source tags and empty bullets are cleaned.
- Calendar follow-ups preserve academic-year context; policy follow-ups do not rewrite explicit new calendar/hostel/fee/scholarship questions. Cache keys include resolved questions, corpus version, application code and model.
- Added per-response retrieval, generation, citation/date validation, highlighting and audit timings; aggregate embedding timings are available in loopback-only metrics.
- Dark Editorial styles and PDF links are preserved. Requests have a 90-second timeout, retry actions retain original conversation context, API base/CORS/OCR paths are configurable, and narrow-screen overflow/accessibility styling is improved.

## Measured performance

Seconds; every first request in this final benchmark was a cache miss. Baseline used the pre-edit server on port 8000; final used a separate server on port 8001 with cached embeddings in offline mode. Process/model startup and remote Gemini conditions differ, so these are observed request timings, not a controlled throughput study.

| Question | Measured before first | Before repeat | Final first | Final repeat | Final repeat cached |
|---|---:|---:|---:|---:|---|
| Semester II begins | 66.123 | 0.027 | 0.213 | 0.008 | True |
| Semester II ends | 2.172 | 2.213 | 1.470 | 0.009 | True |
| Post-examination | 1.705 | 0.003 | 9.581 | 0.008 | True |
| Digital masking | 2.060 | 0.018 | 3.797 | 0.009 | True |
| Result declaration | 2.233 | 0.017 | 3.044 | 0.008 | True |

Final average: **3.621s first / 0.008s repeated**, with 5/5 repeat-cache hits. Measured baseline: 14.859s / 0.456s and 4/5 hits. The user-supplied earlier benchmark was 4.221s / 1.903s. The measured baseline commencement request took 66.123s; it dominates that baseline average. An earlier updated run measured 2.418s / 0.012s, illustrating remote-generation variability.

### Final stage timings

| Question | Retrieval | Generation | Date validation | Citation validation | Highlighting | Claim audit |
|---|---:|---:|---:|---:|---:|---:|
| When does Semester II begin for second-year students? | 0.124772 | 0.000448 | 0.000076 | 0.006009 | 0.000133 | 0.001781 |
| When does Semester II end for second-year students? | 0.002581 | 0.000110 | 0.000057 | 0.006851 | 1.450248 | 0.000671 |
| What are post-examination activities under the 2022 ordinance? | 0.496465 | 8.990524 | 0.000027 | 0.008351 | 0.040982 | 0.031019 |
| Does the 2022 ordinance mention digital masking? | 0.007225 | 3.765803 | 0.000024 | 0.005540 | 0.007810 | 0.001237 |
| What does the 2022 ordinance say about result declaration? | 0.009417 | 3.008507 | 0.000037 | 0.004987 | 0.006569 | 0.004700 |

The calendar end request is dominated by OCR/highlighting. Ordinance latency is dominated by Gemini generation; exact dates no longer pay that cost. Embedding measurements are saved in `profile_metrics.json`. Response timings are diagnostic and retain their original computation values on cache hits.

## Actual validation

- PASS: `scripts/test_query_routing.py` (exit 0).
- PASS: `scripts/test_conversation_isolation.py` (exit 0).
- PASS: `scripts/test_real_evidence.py` (exit 0).
- PASS: `scripts/test_numeric_accuracy.py` (exit 0).
- PASS: `scripts/test_security.py` (exit 0).
- PASS: `scripts/test_routing_integration.py` (exit 0).
- PASS: `scripts/test_retrieval.py` (exit 0).
- PASS: `scripts/test_mvp_regressions.py` (exit 0).
- PASS: `scripts/test_citation_reliability.py` (exit 0).

- Final focused MVP suite: **14 tests passed**, including wrong attendance date, exact answer without model/embeddings, cache isolation, conflicting records, missing evidence, clarification, versions, follow-ups, citation integrity, Markdown cleanup and document endpoint checks.
- Backend and scripts compileall: passed. Two existing script docstrings emit Python invalid-escape SyntaxWarnings (`benchmark_rag.py`, `test_real_evidence.py`); these are documentation strings, not runtime failures.
- Frontend production build: passed (Vite 8.3.6). Frontend lint: passed. Initial lint failed on an unused variable in archived `App.backup.jsx`; backup JSX is now explicitly outside active-source lint scope.
- Initial routing script: 6/8 because it assumed unspecified exams meant term-end exams. Those expectations now preserve broad exam intent and the script asserts its final 8/8 result.
- Existing live claim script: 8 cases completed without request errors, saved in `claim_accuracy_results.json`; this is a manual-review smoke report, not an automated accuracy score. It exposed an absence-only citation and bold source heading; both now have passing regressions. A final live missing-deadline check returned zero citations (`absence_citation_smoke.json`).
- Source audit found no literal Google API-key prefixes in scanned backend/frontend/scripts source. No `.env` values were printed. Environment examples contain no secrets; `.env` variants are ignored. This is a scoped audit, not a full-history secret scan.
- The three PDFs have a checksum inventory in `document_checksums.json`; no pre-edit hashes were captured, so this inventory is for future integrity checks rather than independent before/after proof.

## Files changed or added

Backend:
- `backend/app/main.py`
- `backend/app/rag/retriever.py`
- `backend/app/rag/answer_validator.py`
- `backend/app/rag/citation_focus.py`
- `backend/app/rag/version_policy.py`
- `backend/app/ai/gemini.py`
- `backend/app/cache/cache_version.py`
- `backend/app/memory/conversation.py`
- `backend/app/memory/policy_followup.py`
- `backend/app/monitoring/metrics.py`
- `backend/app/citation_evidence.py`
- `backend/app/pdf_highlighter.py`
- `backend/.env.example`, `backend/requirements.txt`, `backend/requirements-lock.txt`

Frontend:
- `frontend/src/App.jsx`, `frontend/src/App.css`
- `frontend/src/components/SourceCitation.jsx` (API base configuration)
- `frontend/eslint.config.js`, `frontend/.env.example`

Scripts/documentation:
- `scripts/benchmark_performance.py`
- `scripts/test_query_routing.py`
- `scripts/test_claim_accuracy.py`
- `scripts/test_mvp_regressions.py`
- `README.md`, `.gitignore`
- `reports/IMPLEMENTATION_PLAN.md`, this report and JSON validation/performance/audit artifacts.

Builds also regenerated ignored `frontend/dist` and Python bytecode. Original documents and indexed records were not edited by this work. Chroma was opened through its existing client; no collection deletion, rebuild or ingestion command was run.

## Remaining limitations and deployment assessment

Suitable for continued local MVP use after restarting the existing backend. Public deployment is **not yet verified**. Setup/run/build/configuration instructions are in the root README; no new packages were installed during this task. Existing dependencies were reused and their versions snapshotted.

- Browser/mobile interaction and visual QA were not run; responsiveness and error recovery were checked through source/build validation.
- A clean-machine dependency installation was not run. Python lock is a snapshot of the existing environment, including transitive packages, rather than a minimized cross-platform lock.
- Gemini calls remain network-dependent and variable. The lexical claim auditor can flag an otherwise date-verified structured answer; it remains a non-blocking diagnostic, not proof of truth or a reason to bypass date validation.
- Scanned PDF OCR can add latency and requires English Tesseract data. Failed OCR safely falls back to a page link. The original verified commencement-cell coordinate shortcut is retained for compatibility.
- Complex cross-version comparisons conservatively abstain. Do not infer a student?s legal ordinance applicability from the retrieval policy.
- Cache, limiter and metrics are per-process; multi-worker/replica deployment needs shared controls and a deliberate Chroma deployment strategy.
- Hosting target, TLS/reverse proxy, trusted client-IP policy, persistent storage, model/OCR provisioning, server secret injection, CORS/API origins and document distribution permissions remain operator setup items. `/api/health` is liveness, not a readiness guarantee.
- Original port 8000/5173 processes were left under user control. Restart the existing backend to load the edited source. Temporary port 8001 verification service is stopped after validation.

No deployment or destructive action was performed.
