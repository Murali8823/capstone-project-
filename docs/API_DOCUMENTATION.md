# API Documentation

## Current backend (Phases 2–5)

Base URL is `http://<host-wifi-ip>:8765`. Requests and responses are JSON except HTML/JavaScript dashboard files and the SSE event stream. Balances are simulated INR. When local chain deployment is present, an escrow has a real local Hardhat transaction hash and `escrow_backend_only:false`; without deployment it is backend-only and `escrow_backend_only:true`.

### Read endpoints

| Method and path | Behavior |
|---|---|
| `GET /` or `/dashboard` | Serves the desktop monitoring dashboard |
| `GET /dashboard.js` | Serves dashboard browser code |
| `GET /health` | Health, simulation flag, database path, realtime transport, local-chain configured/connected state, network and deployed contract address |
| `GET /api/state` | Snapshot of 5 profiles, 500 latest transactions, open escrow, dashboard totals, score history, event history, timeout and chain-configured marker |
| `GET /api/users` | Five profiles and current balances/scores |
| `GET /api/events` | Latest 200 audit events with JSON payload and hash linkage |
| `GET /api/transactions/{id}` | One transaction or 404 |
| `GET /api/stream` | SSE stream; each event is `id`, `event`, and JSON `data`. Keepalives are comments. Clients should fetch `/api/state` at connect/reconnect and after `STATE_UPDATED`. |

### Payment endpoint

`POST /api/payments` accepts `{ "sender_id":"maya", "receiver_id":"business", "amount":125.50, "scenario":"demo" }`. Only the three seeded `sender` roles may send, and only `business`/`scammer` may receive. Amount must be greater than zero, no more than INR 1,000,000, and within the simulated balance. Amounts are persisted as integer paise. Optional `Idempotency-Key` header (or body `idempotency_key`) avoids duplicate processing.

Returns HTTP 201 with `{ "id", "status", "reason", "transaction": { ... } }`. Status is determined from the receiver score snapshot: below 50 `APPROVED` (debit sender and credit receiver), 50–80 inclusive `ESCROW` (debit sender, retain equivalent simulated value in contract when deployed), and above 80 `REJECTED` (no debit, receiver receives nothing). `transaction.scam_score` remains the creation-time snapshot after an escrow is resolved. Chain creation failure returns HTTP 503 and rolls back the SQLite payment. A repeated key returns the first transaction with `duplicate:true`.

### Admin authentication and score controls

`POST /api/admin/login` with `{ "password":"..." }` returns an expiring HMAC-signed bearer token. Default demo password is `shieldpay-admin`; configure `SHIELDPAY_ADMIN_PASSWORD` and `SHIELDPAY_ADMIN_TOKEN_SECRET` for a presentation. Never use this demo default on a public service.

All following routes require `Authorization: Bearer <token>`:

| Method and path | Body | Behavior |
|---|---|---|
| `POST /api/admin/score` | `{ "receiver_id":"business", "score":35 }` | Validates whole-number score 0–100; invokes oracle contract call when deployed; saves score history and audit event. For that receiver's open escrows, below 50 releases, above 80 refunds, 50–80 leaves locked. Returns previous/new score, timestamp, actor, decision, settled transaction IDs and chain hash. Chain failure leaves backend score unchanged and returns 503. |
| `POST /api/admin/transactions/{id}/refund` | `{}` | Allowed only for an escrow in `MANUAL_REVIEW`; returns amount to sender once and marks `REFUNDED`. |
| `POST /api/admin/reset` | `{}` | Safely resolves any open contract holds, restores five seed identities/balances and clears app transactions/reports/score history, then records reset. Local-chain history remains immutable and is not erased. |

Timeout defaults to 300 seconds; set `SHIELDPAY_ESCROW_TIMEOUT_SECONDS` at backend start (minimum 10 seconds) for a shorter demo. Expiry sets contract and app state to `MANUAL_REVIEW` while keeping funds locked. An admin must review and refund using the route above. This retained-lock policy avoids auto-releasing to a risky receiver.

`POST /api/reports` with `reporter_id` and `receiver_id` preserves the prototype reporting feature. It records an audit event but does not change the admin-configured score.

### Error behavior

Malformed JSON/invalid amount/score/profile returns HTTP 400; missing or invalid admin session returns 401; unknown resources return 404; invalid timeout refund state returns 409. Error body is `{ "detail": "..." }`.

### Realtime event examples

Event names include `PAYMENT_APPROVED`, `PAYMENT_ESCROW`, `PAYMENT_REJECTED`, `SCAM_SCORE_UPDATED`, `ESCROW_RELEASED`, `ESCROW_REFUNDED`, `ESCROW_MANUAL_REVIEW`, `ESCROW_TIMEOUT_REFUNDED`, `DEMO_RESET`, and `STATE_UPDATED`. A score update event is published only after SQLite commits; clients use its notification to fetch the authoritative snapshot.

## Security and deployment boundary

This is an unauthenticated simulated-user LAN demo except admin routes. Publicly accessible browsers may read state and connect to SSE. Use trusted Private Wi-Fi, do not expose port 8765 to the public internet, and do not enter real user/payment data. Production deployment would need TLS, real identity/session controls, restrictive CORS, stronger secret management and operational controls.
