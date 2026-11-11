# System Architecture

## Current system topology

```text
Three sender phones ─┐       REST snapshot polling
Scammer phone ──────┼──────────────────────────────────────┐
Business phone ─────┘                                      v
                                                     Python backend
Desktop browser ── REST + SSE ──────────────────────── :8765 / 0.0.0.0
                                                     ├─ SQLite app state/audit
                                                     └─ local Node ethers bridge
                                                              │
                                                 JSON-RPC localhost:8545
                                                              v
                                                  Hardhat / Solidity escrow
```

One Expo app is opened on five devices and each device selects one of five shared profiles. All five query the same backend. The desktop dashboard is a static site served by that same backend. It reads shared state through REST, listens through SSE, and uses authenticated admin routes for score control, timeout review and reset.

## Payment flow

1. Mobile sends sender profile, receiver profile and amount to `POST /api/payments`.
2. Backend validates sender/receiver roles, amount, available simulated balance and idempotency key. It snapshots the receiver score.
3. Below 50: backend records `APPROVED` and updates sender/receiver SQLite balances. No contract escrow is created.
4. 50–80 inclusive: backend records an escrow hold and invokes `chain/bridge.cjs create` when a local contract is deployed. The bridge submits native test-chain value from the local oracle account, stores the mapped sender/receiver addresses and returns receipt hash/events. Backend stores the hash and audit event. If chain creation fails, it rolls back SQLite and returns 503.
5. Above 80: backend records `REJECTED`; sender balance is unchanged.
6. Backend publishes transaction/audit notifications by SSE. Mobile refreshes `/api/state` every 1.8 seconds; the dashboard listens for events and refreshes its snapshot.

## Score/oracle flow

Dashboard login exchanges the demo admin password for an expiring HMAC bearer token. A score change sends `POST /api/admin/score`. The backend checks token and score range, calls the oracle bridge, and asks `ShieldPayEscrow.setReceiverScore` to apply the same bands. The contract emits settlement events; bridge decodes receipt. SQLite updates score history and matching transaction state, records `SMART_CONTRACT_EVENT_RECEIVED`, then broadcasts SSE. Mobile refreshes state; dashboard updates from SSE and REST.

Only the backend has an API path that invokes the bridge. Mobile client has no private key and cannot directly call a settlement route. Hardhat JSON-RPC remains bound to `127.0.0.1:8545`; backend LAN API is on 8765.

## Timeout and reset flow

Backend timeout worker queries expired `ESCROW` rows. For chain-backed rows it calls permissionless contract `markExpired`; contract and backend move to `MANUAL_REVIEW`, retaining locked value. Authenticated admin `POST /api/admin/transactions/{id}/refund` calls oracle-only `refundAfterReview`, credits sender demo balance and records receipt. The dashboard reset first safely resolves local open holds, resets local receiver scores and demo SQLite data, and preserves local-chain logs.

## Storage and real-time details

SQLite stores users, transactions, score history, report records and audit events. Amounts are integer paise. The backend serializes writes with a process lock and SQLite constraints. SSE uses per-client bounded queues; each event carries ID/type/payload. Clients fetch a complete snapshot after reconnect rather than depending on every event being delivered. Mobile currently polls to remain compatible with Expo Go's React Native runtime.

## Trust boundaries and limitations

Phones and dashboard are clients on private LAN; the backend decides balances and scores. Admin operations have a local demo password and signed session. The backend/oracle, host, Hardhat RPC, user devices and Wi-Fi are trust dependencies. Contract transitions are auditable on the local chain but cannot validate the score source or secure the host. The local chain's dev accounts/private keys are publicly known Hardhat test keys. App balances are synthetic INR, contract value is local test ETH, and neither represents real money.
