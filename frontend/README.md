This is a minimal Vite + React frontend for the Base Navigator backend.

Local run:

1. cd frontend
2. npm install
3. Create a `.env` or `.env.local` with `VITE_API_BASE_URL` set to your backend URL, e.g. `http://localhost:8000` (no trailing slash)
4. npm run dev

Notes:
- The frontend reads the backend base URL from `VITE_API_BASE_URL`. No hosts are hardcoded.
- If backend endpoints return HTTP 402 (Payment Required), either disable x402 in backend dev settings or set an `INTERNAL_KEY` in the backend and provide it via request headers.
