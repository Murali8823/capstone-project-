# Security Analysis

## Controls currently implemented

- Backend validates sender/receiver roles, distinct identities, amount precision/range, available simulated balance and whole-number receiver score.
- Score bands are enforced server-side; clients cannot decide transaction state.
- Admin login creates an expiring HMAC-SHA256 bearer token. Score update, reset and manual timeout refund validate the token.
- Transaction idempotency keys and SQLite constraints prevent duplicate request keys and invalid balances/scores.
- Escrow status transitions are guarded in backend and Solidity. Contract only permits oracle creation/score update/refund, unique transaction IDs and one terminal state. Timeout can only mark review after expiry and does not auto-release funds.
- Backend uses a local ethers bridge, not mobile wallet keys. Hardhat RPC binds to loopback.
- All accounts and balances are synthetic. `.env`, SQLite files, Hardhat artifacts and generated local contract config are ignored by Git.

## Known limitations

- Demo sender identities are selected by ID and are not authenticated. Anyone on the LAN can impersonate a sender profile.
- Default admin password (`shieldpay-admin`) and HMAC token secret are demo-only. Override for presentations and never expose the backend publicly.
- HTTP and Expo cleartext are used for the trusted classroom LAN; there is no TLS. CORS and state/SSE read access are broad to support local browser/mobile clients.
- Hardhat prints public development private keys and bridge uses unlocked local accounts. These must never be used on a public chain. Local chain is resettable and its value is fake.
- App SQLite/audit files can be modified by a privileged host user. SHA-256 hash linkage is educational, not externally anchored or tamper-proof.
- Admin score is a configured deterministic value, not AI/model output. No real scam classifier or calibration exists.
- The contract locks equivalent test ETH funded by the local oracle account while backend debits simulated INR. It does not pull funds from a real sender wallet or payment rail.
- An RPC failure can temporarily leave an operation uncommitted; backend returns 503, and admins/operators must restore chain connectivity before retrying. Receipt reconciliation is currently synchronous, not a production event-indexing service.
- npm reported 24 dependency advisories in its installed tree (10 low, 7 moderate, 7 high) after adding Hardhat with `--legacy-peer-deps`; no force-upgrade was run because of Expo compatibility risk.

## Security claim boundary

The smart contract enforces coded transition rules and records local EVM events. It does not make the complete application unhackable, prove score correctness, secure backend credentials, protect devices/Wi-Fi, or provide legal/payment compliance. There is no banking integration, real money, or public-chain deployment.
