# Technology Stack

## Implemented

| Area | Technology | Role in this demo |
|---|---|---|
| Mobile client | Expo SDK 58, React Native 0.88, React 19, TypeScript 7 | One app supports all five role/profile modes and runs on each phone. Expo Go is the development workflow. |
| Navigation/config | Expo Router, `app.json` | File-based app entry, Camera plugin and Android cleartext LAN configuration. |
| Demo QR | Expo Camera, `react-native-qrcode-svg` | Scans/displays receiver profile IDs only; QR is not a payment credential. |
| LAN backend | Python 3.13 standard-library `ThreadingHTTPServer` | REST commands, dashboard static files and health endpoint on `0.0.0.0:8765`. No FastAPI or pip package required. |
| Database | SQLite via Python `sqlite3` | Shared users, balances, receiver scores, transactions, score history, reports and event chain. |
| Realtime | Server-Sent Events (SSE) | Browser dashboard receives backend event pushes. Mobile uses 1.8-second snapshot polling for React Native compatibility. |
| Admin session | HMAC-SHA256 signed bearer token | Expires after configured session interval and protects score/reset/manual-review API calls. |
| App audit | Python `hashlib` SHA-256 links | Orders application audit events; database file can still be modified by a privileged host user. |
| Smart contract | Solidity 0.8.28 | Local escrow creation, locked native test-chain value, score-based release/refund, expiry/manual-review and access control. |
| EVM tooling | Hardhat 2.26, `@nomicfoundation/hardhat-ethers` 3.1, ethers 6.14, solc 0.8.28 | Local JSON-RPC chain, compile/deploy/tests, and backend bridge transactions. The compiler package is pinned locally so Hardhat does not download solc during build. |
| Desktop monitor | Static HTML/CSS/JavaScript, browser Canvas and EventSource | Served by the Python backend at `/dashboard`; charting and live event UI have no external runtime/CDN dependency. |

## Why these choices

The existing Expo/React Native client and standard-library Python server were preserved. SQLite is sufficient for a single-host academic demo without a database daemon. SSE is push-based, browser-native and dependency-free; REST remains the mutation path. A small vanilla dashboard is served from the existing backend so faculty can open one LAN URL without a second dev server. Hardhat provides an isolated local chain and test accounts; ethers is the bridge interface. The choice keeps this runnable on one computer and makes the oracle boundary explicit.

Scam scores are deterministic admin-controlled values. There are no ML, dataset, training or model-serving dependencies.

## Installed tool versions observed

- Node.js `v22.17.1`, npm (through `npm.cmd`).
- Python `3.13.14`, pip `26.1.2`.
- Expo `58.0.23`, React Native `0.88.0`, React `19.3.0`.
- Hardhat `2.26.0`, ethers `6.14.0`, local solc `0.8.28`.

The first npm install hit a pre-existing peer-resolution conflict between React 19.3.0 and react-dom 19.3.1 nested through Expo's dependency tree. Hardhat packages were installed with `--legacy-peer-deps`; dependencies are present and the Android bundle and Hardhat tests pass. npm reported 24 package advisories in the installed tree (10 low, 7 moderate, 7 high); no broad `npm audit fix --force` was run because it may change Expo versions. This dependency-tree advisory remains a review item.

## Runtime boundaries

The backend binds LAN port 8765. Hardhat binds local-only `127.0.0.1:8545`. Generated deployment config/artifacts/cache and SQLite state are ignored by Git. Local chain resets erase chain state and require redeployment. No TLS or public deployment is supported.
