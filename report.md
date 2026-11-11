# ShieldPay — Technical Report and Demo Runbook

## Project summary

ShieldPay demonstrates risk-aware simulated payments. Five mobile role views and one desktop dashboard use one backend. The receiver's configurable deterministic scam score decides whether payment is approved, escrowed or rejected. Escrow is enforced by a Solidity contract deployed on a local Hardhat EVM. No ML model, real payment rail or real user data is used.

## Components and data flow

```text
Expo/React Native clients ── REST polling ──┐
                                             ├─ Python backend :8765 ── SQLite
Desktop dashboard ── REST + SSE ────────────┘            │
                                                        ethers bridge
                                                            │ localhost JSON-RPC
                                                            v
                                                  Hardhat + Solidity escrow
```

The backend is the source of truth for demo balances and score policy. It stores user and transaction data in SQLite, enforces admin actions with an expiring HMAC bearer token, and publishes event notifications over SSE. Mobile uses 1.8-second API polling for compatibility. The dashboard uses browser EventSource and refreshes full state after reconnect. When a receiver score changes, the backend acts as authenticated oracle and submits the local-chain transaction. Contract receipt hashes and events are stored in the app audit stream.

## Five demo profiles

| Profile | Role | Starting simulated balance | Starting receiver score |
|---|---|---:|---:|
| Maya Shah | Sender A | ₹12,500 | — |
| Arjun Rao | Sender B | ₹8,900 | — |
| Riya Sen | Sender C | ₹15,300 | — |
| Suspicious Profile | Scammer persona | ₹0 | 95% |
| Northstar Gadgets | Business receiver | ₹0 | 65% |

The three senders can all pay the business. Every phone selects a role in the same Expo app; the backend state is shared.

## Scam-score policy

| Receiver score | Result | Balance handling |
|---|---|---|
| 0–49% | `APPROVED` | Debit sender and credit receiver immediately |
| 50–80% | `ESCROW` | Debit sender; lock equivalent test value in contract |
| 81–100% | `REJECTED` | Leave sender balance unchanged; do not credit receiver |

The transaction retains the score snapshot from creation. The receiver's later score is recorded separately. Open escrow releases below 50, refunds above 80, and remains locked for 50–80. Timeout enters `MANUAL_REVIEW`; funds remain locked until an authenticated admin refunds sender.

## Start-up commands (Windows PowerShell)

First run `ipconfig`; use the current IPv4 address under the Wi-Fi adapter. Replace `192.168.1.19` in the following example when DHCP changes it.

**Terminal 1 — local blockchain:**

```powershell
npm.cmd run chain:node
```

**Terminal 2 — compile/deploy contract:**

```powershell
npm.cmd run chain:compile
npm.cmd run chain:deploy
```

**Terminal 3 — backend:**

```powershell
py -3 backend/server.py
```

Short timeout variant (minimum 10 seconds):

```powershell
$env:SHIELDPAY_ESCROW_TIMEOUT_SECONDS = '10'
py -3 backend/server.py
```

Optional admin password override before backend startup:

```powershell
$env:SHIELDPAY_ADMIN_PASSWORD = 'choose-a-demo-password'
$env:SHIELDPAY_ADMIN_TOKEN_SECRET = 'choose-a-long-random-demo-secret'
py -3 backend/server.py
```

**Terminal 4 — Expo development app:**

```powershell
$env:EXPO_PUBLIC_API_URL = 'http://192.168.1.19:8765'
npx.cmd expo start --lan
```

Open the Expo QR on five Android phones using Expo Go. Assign one distinct profile per phone. Open the desktop at `http://192.168.1.19:8765/dashboard` and log in with the configured admin password (default `shieldpay-admin`).

## Live demo walkthrough

1. **Safe payment:** dashboard Scenario A sets business to 25% and submits a payment; inspect `APPROVED` and immediate receiver credit.
2. **Release:** Scenario B creates escrow at 65%; set score to 35%; inspect contract `RELEASED`, transaction hash and business credit.
3. **Refund:** Scenario C creates escrow at 65%; set score to 90%; inspect `REFUNDED`, sender credit and no business credit.
4. **Timeout:** Scenario D creates escrow at 65%; wait for countdown; inspect `MANUAL_REVIEW`; click **Review and refund sender** and verify final refund.
5. Reset Demo restores app profiles/balances and receiver scores. It safely resolves active contract holds but leaves on-chain history intact.

The scammer persona has a 95% score, so new payments to it are rejected. Use it to demonstrate the high-risk path.

## Validation performed

- Python `py -3 -m py_compile backend\server.py`: passed.
- Backend API: 49/50/80/81 boundary decisions; admin 401; idempotency; release/refund; SSE; timeout/manual-review refund: passed.
- Hardhat contract: five tests passed, including oracle access, score bands, duplicate/double settlement and timeout review/refund.
- Live API-to-Hardhat: confirmed contract states `LOCKED`, `RELEASED`, `REFUNDED`, and `MANUAL_REVIEW`, receipt hashes and chain-aware reset.
- TypeScript `npx.cmd tsc --noEmit`: passed.
- Expo `npx.cmd expo export --platform android`: passed, 1465 modules bundled.
- Dashboard JS `node --check`: passed; `/dashboard`, `/dashboard.js`, `/health` returned HTTP 200 through loopback and current host Wi-Fi IPv4.
- Expo Metro `/status`: HTTP 200 from loopback and current Wi-Fi IPv4.

Five physical phones and a separate browser session were not available in this environment. The backend and Expo servers were running during final verification, but actual phone camera/Expo Go behavior and dashboard visual interaction still need live review.

## Security notes and limitations

- Hardhat uses fake local ETH and well-known dev keys; never use those keys outside local Hardhat.
- App balances are synthetic INR; contract value is funded by the local oracle account and does not represent the sender's real wallet.
- User selection is not authentication. Only admin operations use a bearer token.
- Backend is plain HTTP on the private LAN. Hardhat RPC stays on `127.0.0.1:8545`; do not expose either port publicly.
- Blockchain protects only coded local contract transitions. Backend, oracle, admin password, local host, devices and Wi-Fi remain trust dependencies.
- A local chain restart erases the contract deployment; redeploy and restart backend. Dashboard reset clears application history but not local chain logs.

## Documentation index

Detailed architecture, file-by-file explanation, API, network setup, blockchain, security, scenarios, development progress and faculty presentation notes are in `docs/`.
