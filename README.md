# CampusIQ MIT-WPU

Local document-grounded assistant: FastAPI, Gemini, ChromaDB, SentenceTransformers, React and Vite. The supplied knowledge base contains three official PDFs and an existing vector index. Preserve both; setup does not ingest documents or rebuild the database.

## Local setup (PowerShell)

Tested environment: Python 3.14.7, Node 26.13.0, npm 11.20.0. The existing `backend/.venv` and `frontend/node_modules` can be reused.

For a clean environment, run from this directory:

```powershell
py -3.14 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
Copy-Item backend/.env.example backend/.env
Set-Location frontend
npm ci
Set-Location ..
```

The lock file snapshots the installed Python environment; `backend/requirements.txt` lists direct runtime/test dependencies. A clean installation of the snapshot has not been tested. Package installation requires network access; do not overwrite an existing `.env`. Set `GEMINI_API_KEY` in `backend/.env` privately. Never place it in a Vite variable or commit it. `GEMINI_MODEL` defaults to `gemini-3.5-flash-lite`.

Start backend in one terminal:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start frontend in another:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. `/api/health` checks the HTTP service; it does not certify Gemini credentials, OCR or model readiness. Exact qualified term commencement/end dates work without Gemini credentials. Other document answers call Gemini and send the question and retrieved excerpts to Google.

The first semantic lookup may download `all-MiniLM-L6-v2` from Hugging Face. After the model is cached, set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` to avoid startup metadata network requests. Do not rebuild or delete `vector_db`.

Scanned PDF highlighting requires Tesseract English language data. Set `TESSDATA_PREFIX` to its directory when needed; the existing Windows path remains a fallback. If OCR fails, citations still open the PDF page. The existing verified commencement-cell highlight is preserved.

## Configuration and checks

`backend/.env.example` documents server settings. `frontend/.env.example` documents `VITE_API_URL`; it is public build-time configuration and must never contain secrets. Set `CORS_ORIGINS` to a comma-separated list of exact frontend origins when hosting separately.

```powershell
backend/.venv/Scripts/python.exe scripts/test_mvp_regressions.py
backend/.venv/Scripts/python.exe scripts/test_conversation_isolation.py
backend/.venv/Scripts/python.exe scripts/test_citation_reliability.py
backend/.venv/Scripts/python.exe scripts/test_query_routing.py
backend/.venv/Scripts/python.exe -m compileall -q backend/app
Set-Location frontend
npm run build
npm run lint
Set-Location ..
backend/.venv/Scripts/python.exe scripts/benchmark_performance.py
```

The benchmark expects a running API, makes Gemini calls for ordinance questions and writes `reports/performance_latest.json`. Set `CAMPUSIQ_API_URL` to test a different origin. First means first request in that benchmark, not necessarily a cold cache; each row records the actual cache flag. `/api/metrics` is restricted to loopback and includes embedding timings. Response `timings_seconds` separates retrieval, generation, date/citation validation, highlighting and claim auditing; cached responses retain the original computation timings.

See `reports/DEVELOPMENT_REPORT.md` for actual outcomes, file changes, performance and limitations.

## Deployment preparation

Build frontend with its intended public API origin (`VITE_API_URL`), serve `frontend/dist` over HTTPS, and run the backend behind a TLS reverse proxy with explicit CORS origins. Mount the existing documents and vector database on persistent storage, provision the embedding model and OCR data, and inject the Gemini key as a server secret. Do not include `.env`, virtual environments or runtime data in public artifacts.

Public deployment remains blocked on operator configuration and verification: hosting target, private secret injection, resource sizing for embeddings/OCR, model/network readiness, HTTPS, trusted proxy/client-IP configuration and access policy for document distribution. The rate limiter, cache and metrics are in-process; use one backend worker for the local MVP. Multiple workers/replicas need shared limits/cache and an explicit Chroma deployment strategy. Do not trust arbitrary forwarded IP headers. Browser/mobile interaction testing and clean-machine installation remain outstanding. Claim auditing is diagnostic, not a proof of entailment. Unknown or multiple explicit ordinance versions conservatively return no evidence rather than silently choosing another version. No site has been deployed.
