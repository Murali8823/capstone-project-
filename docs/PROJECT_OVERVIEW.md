# ShieldPay Project Overview

## Purpose

ShieldPay is an academic local-network demonstration of risk-aware simulated payments. Three sender phones, a scammer persona phone, a business receiver phone and a desktop dashboard share one backend. A deterministic receiver scam score controls payment approval, escrow or rejection. The local smart contract demonstrates escrow state transitions and audit events. No real money or payment rails are connected.

## Current delivered implementation

- Expo/React Native/TypeScript app with five selectable profiles and role-specific sender, business and scammer views.
- Python standard-library backend bound to `0.0.0.0:8765`, SQLite persistence, REST API, SSE event stream, authenticated admin score changes, idempotent payment creation and timeout review/refund.
- Receiver score defaults: business 65%, scammer 95%; senders Maya, Arjun and Riya have separate balances.
- Exact policy: below 50 approves; 50 through 80 inclusive escrows; above 80 rejects without sender debit.
- Hardhat local EVM and Solidity escrow; backend uses ethers bridge as the oracle and stores transaction hashes/events.
- Browser dashboard served at `/dashboard`, with overview, score control/history, tables, countdowns, event feed, charts, reset and scenario actions.
- Scores are deterministic manual demo settings. ML/data collection/model training are explicitly out of scope.

## Data flow

Mobile sends a payment request to the backend. The backend validates role, balance and receiver score, then updates SQLite. For ESCROW, the backend asks the local ethers bridge to deposit corresponding local test-chain value into `ShieldPayEscrow`; the returned hash and events are recorded. Score controls are admin-authenticated. The oracle updates the contract, which releases/refunds/retains escrow and emits events. The backend records matching app state and broadcasts SSE notifications. Mobile refreshes snapshots every 1.8 seconds; dashboard uses SSE and periodic snapshot refresh.

## Technology decisions

The existing Expo app and Python standard-library HTTP server were preserved. SQLite is enough for one host. SSE delivers live dashboard notifications without a new Python dependency. The dashboard is a static page served from the backend so no additional web server is needed. Solidity/Hardhat/ethers are isolated to the local blockchain demonstration. More detail is in `TECH_STACK.md` and `SYSTEM_ARCHITECTURE.md`.

## Phase status

| Phase | Status |
|---|---|
| 1. Repository analysis and architecture | Complete |
| 2. Shared backend and demo data | Complete; manual API scenarios passed |
| 3. Five mobile role views | Implemented; TypeScript and Android bundle passed; physical five-phone testing remains |
| 4. Smart contract escrow | Contract tests and live local-chain API scenarios passed |
| 5. Desktop dashboard | Implemented and served over loopback/LAN; browser visual interaction review remains |
| 6. End-to-end integration | Partial: backend/chain and LAN interface verified; no physical phones/browser automation available |
| 7. Final documentation/review | In progress; finish runbooks and verification record after remaining available checks |

See `DEVELOPMENT_PROGRESS.md` for exact commands, outputs, limitations and known issues. Do not describe physical phone interoperability or browser visual testing as verified until actually exercised.
