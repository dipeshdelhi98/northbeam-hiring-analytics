# Frontend (Next.js)

Three sections over the FastAPI backend: **Overview** (headline metrics, hires by month, funnel,
pipeline on any date), **Requisitions** (filterable pipeline; click a role for its candidates and
each candidate's stage history), **Team** (per-recruiter / hiring-manager results).

## Rule

This app renders what the API returns. It may filter, sort and lay out rows; it never derives a
number. Every metric is defined in `../metrics/definitions.py`, and
`tests/test_single_definition.py::test_next_frontend_does_no_arithmetic_on_values` fails the
build if `Math.`, `parseFloat`, `.reduce(`, `toFixed`, `Intl.NumberFormat` etc. appear in `src/`.

## Run

```bash
# with the API running on :8000 (see the root README)
npm install
npm run dev        # http://localhost:3000 — proxies /api to :8000
npm run build      # static export to ./out; FastAPI then serves it at http://127.0.0.1:8000
```

`src/lib/api.ts` is the only module that calls the backend. The session token is kept in
`sessionStorage` (it dies with the tab); the theme choice in `localStorage`.
