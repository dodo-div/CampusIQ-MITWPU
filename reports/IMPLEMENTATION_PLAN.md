# Implementation plan

1. Reliability: reuse structured calendar records for exact commencement/end dates; retain validation; clarify missing qualifiers; reject unavailable calendar years and unsupported citations.
2. Performance: remove exact-event embeddings; record retrieval, generation, embedding and validation timings; version cache by corpus, application code and model.
3. Frontend: preserve Dark Editorial and PDF highlighting; configurable API base; bounded requests, retry recovery and mobile overflow fixes.
4. Validation: run existing scripts and focused regressions, backend compilation and frontend build/lint. Record actual failures and measured benchmarks.
5. Deployment preparation: explicit dependencies, safe environment examples, repeatable local setup and deployment blockers. No publication or database rebuild.
