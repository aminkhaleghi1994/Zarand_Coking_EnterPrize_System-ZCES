# Contract: BFF Proxy Layer

**Scope**: Frontend `src/app/api/**` route handlers · Rule: the browser talks ONLY to
these handlers; it never calls the backend directly and never sees raw tokens.

## `GET /api/health` (Phase 1)

1. Server-side handler fetches `${BACKEND_API_BASE_URL}/healthz` (backend base URL from
   frontend environment only — never inlined).
2. Success: JSON re-validated (Zod) against the health contract and returned as-is
   (HTTP 200) with caching disabled.
3. Backend unreachable / non-JSON / timeout (≤ 5s): HTTP 502 with the standard error
   envelope — `{code: "INTERNAL_ERROR", message, details?, trace_id}`; a fresh trace id
   is minted by the route if the backend never supplied one.
4. The same mapping logic lives in `src/lib/api.ts` so every future BFF route (auth,
   resources, SSE) inherits it.

## General rules (all future BFF routes)

- Input from the browser is validated before proxying; backend errors are passed through
  in the standard envelope (codes stay stable across the boundary).
- Cookies set by the BFF are HttpOnly; browser code reads identity via `/api` endpoints,
  never from document cookies.
- Backend URLs exist only in frontend server configuration
  (`BACKEND_API_BASE_URL` in `.env.local`, mirrored by `.env.example`).
