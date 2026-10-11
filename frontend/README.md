# Frontend

The review screen for [Document Extraction Copilot](../README.md): upload an invoice (or pick a sample), see the page next to the extracted fields, fix what is wrong, and export the corrected values. Angular 22, signals, no UI library.

```bash
npm ci
npx ng serve                      # http://localhost:4200, talks to the API on :8000 (CORS is enabled for it)
npx ng test --watch=false         # 74 tests (vitest + jsdom)
npx ng build --configuration production
```

Angular 22 needs Node 22.22+ or 24. In Docker the build uses Node 24 (`Dockerfile`), so no local Node is required for the full stack.

## Where things are (`src/app/`)

| file | what it does |
|---|---|
| `invoice-form.ts` | form state as text, conversion to an invoice, immutable edits, change tracking, CSV. Pure, the most heavily tested file |
| `review-store.ts` | the state of one document under review: debounced, cancellable re-validation, merged client and server issues |
| `api-client.ts` | typed `fetch` client; readable error messages; a cancelled request is not reported as a failure |
| `app.ts`, `upload-panel.*`, `page-viewer.ts`, `review-panel.*`, `field.ts` | the screens |
| `dom.ts` | focusing the field an issue points at, file downloads |

In production the app calls `/api/v1` on its own origin and `nginx.conf` proxies it to the backend; under `ng serve` it calls `http://localhost:8000/api/v1` directly.
