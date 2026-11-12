# CampusIQ — Dark Editorial frontend

These files are designed to be copied into your existing **Vite + React** frontend. They do not modify FastAPI, ChromaDB, Gemini or the retrieval pipeline.

## Installation on Windows PowerShell

1. Stop the Vite dev server.
2. In your existing `frontend` directory, back up your files:
   ```powershell
   Copy-Item .\src\App.jsx .\src\App.backup.jsx
   if (Test-Path .\src\App.css) { Copy-Item .\src\App.css .\src\App.backup.css }
   if (Test-Path .\src\index.css) { Copy-Item .\src\index.css .\src\index.backup.css }
   ```
3. Install the icon package:
   ```powershell
   npm install lucide-react
   ```
4. Copy `src/App.jsx`, `src/App.css`, `src/index.css` from this bundle to the **existing** `frontend/src/` directory.
5. Confirm your existing `src/main.jsx` imports `./index.css` and renders `<App />` (the standard Vite React setup). Keep any existing providers or routing that your app depends on.
6. Make sure the FastAPI backend is available at http://127.0.0.1:8000 (or set `VITE_API_URL=http://127.0.0.1:8000` in `frontend/.env`).
7. Start the frontend with `npm run dev`. Open http://localhost:5173.

## Expected backend JSON

POST /api/chat: `{ "message": "..." }`

Response: `{ "answer": "...", "sources": ["..."], "citations": [{ "document": "...", "page": 2 }], "validation": { "status": "verified" }, "cached": false }`

GET /api/health: any HTTP 200 response indicates the API is available.

## Notes

- `verified` is displayed as **Dates checked against source**, because your backend's `validate_answer_dates` verifies dates, not every factual claim.
- Source chips show references, **not working PDF links**, because the backend does not expose document URLs.
- Conversation is kept **in React memory only**; it is erased on reload or new conversation. No account/login or persistent conversation history is represented.
- The UI does not call `/api/metrics`; that monitoring endpoint is reserved for local development.
- The Google Fonts import requires an internet connection. If offline, fallback system fonts will render.
- Important: The backend currently permits CORS from `http://localhost:5173`. If your frontend is opened from `http://127.0.0.1:5173` or a hosted domain, adjust backend CORS intentionally.
- For public deployment, use authentication, protect metrics, review policy/PII handling, and replace development in-memory cache and rate limiting as appropriate.
