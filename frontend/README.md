This is the Next.js intelligence terminal for Base Navigator.

Local run:

1. cd frontend
2. npm install
3. Create a `.env` or `.env.local` with `NEXT_PUBLIC_API_BASE_URL` set to your backend URL, e.g. `http://localhost:8000` (no trailing slash)
4. npm run dev

Notes:
- The frontend reads precomputed feed APIs only: `/api/signals`, `/api/governance`, `/api/grants`, and `/health`.
- The premium route is surfaced as a product-ready API path, but payment flow is not implemented in this frontend phase.
