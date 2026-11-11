# Blockchain and Escrow

## Phase 4 implementation status

The project now contains `contracts/ShieldPayEscrow.sol`, a local Hardhat network, deployment script and ethers-based backend bridge. The latest verification deployment used local chain ID 31337 at `0x59b670e9fA9D0A427751Af201D676719a970857b`; an earlier deployment used `0x5FbDB2315678afecb367f032d93F642f64180aa3`. Generated `backend/chain_config.json` is authoritative. Addresses are ephemeral: restarting Hardhat clears chain state and requires a fresh deploy. No public chain or payment rail is used.

## Contract state and methods

- `createEscrow` is oracle-only. It requires a unique nonzero transaction ID, positive `msg.value`, nonzero distinct sender/receiver addresses, a future expiry and initial score in inclusive 50–80. It stores sender/receiver demo IDs and addresses, amount, immutable score-at-creation, current score, timestamps and `LOCKED` state. The sent native local-chain value stays in the contract.
- `setReceiverScore` is oracle-only and validates 0–100. It updates the latest receiver score and loops that receiver's open holds while preserving each transaction's original score snapshot. Score below 50 marks `RELEASED` and sends to the receiver. Score above 80 marks `REFUNDED` and sends to sender. Scores 50–80 leave the hold open. Checks-effects-interactions and reverting transfers prevent silently inconsistent terminal states.
- `markExpired` is permissionless but only works on an open escrow after its expiry. It changes status to `MANUAL_REVIEW`; funds remain locked.
- `refundAfterReview` is oracle-only, requires `MANUAL_REVIEW`, and pays sender once.
- `statusOf` reads the enum status. Events record creation, score update, release, refund and review.

The enums are `NONE`, `LOCKED`, `MANUAL_REVIEW`, `RELEASED`, and `REFUNDED`. Unique IDs, role checks and status guards prevent duplicate creation and double terminal settlement.

## Oracle and backend integration

The desktop admin logs in to the backend and sends an authenticated score update. The backend checks the token and input, calls `node chain/bridge.cjs score ...`, and the bridge uses ethers to submit from local Hardhat account 0 (the configured oracle). The backend then applies the same outcome to its SQLite transaction and stores receipt hash/events. Escrow creation and timeout/refund use the same bridge. Mobile clients do not hold a key or have any contract state-changing endpoint.

Local demo currency uses a conversion of 1 INR = 10^12 wei. The Hardhat oracle account supplies the contract value; sender simulated INR balances are debited by the backend. The contract pays the mapped local business/sender addresses at settlement. This makes a real EVM value transfer and event visible, while the funds remain test-chain currency. It does not represent a real sender bank transfer.

The local ethers bridge is invoked as a child process, not exposed as another LAN service. Its JSON-RPC endpoint defaults to `http://127.0.0.1:8545`. The deployment script writes generated address/ABI to ignored `backend/chain_config.json`. The bridge maps demo IDs to unlocked Hardhat accounts #1–#5 and account #0 is the oracle. Hardhat prints publicly known development private keys; they are unsafe for any real network.

## Timeout and reset policy

Expiry is configured through `SHIELDPAY_ESCROW_TIMEOUT_SECONDS` (300 default, minimum 10 for demos). Backend worker calls `markExpired`, stores the event, and leaves funds locked. Authenticated admin review refunds the sender through `refundAfterReview`. Reset first moves receiver scores through a risk-high value to safely refund open contract holds, restores demo receiver scores, then clears the application database history. Local-chain history is not erased; it is immutable for the life of that local chain.

## Verified contract tests and live integration

`npx.cmd hardhat test` passed five tests: oracle-only access, score 65 escrow then 49 release, 80 then 81 refund, inclusive 50/80 holds then timeout review/manual refund, invalid score bands/duplicate ID/double-refund checks. `npx.cmd hardhat compile` compiled Solidity 0.8.28 locally.

Live backend → local-EVM API testing verified actual contract states `LOCKED`, `RELEASED`, `REFUNDED`, and `MANUAL_REVIEW`, corresponding backend states and returned transaction hashes. It also exercised reset and a fresh post-reset escrow/release. Test hashes are in the developer command output but are transient local-chain artifacts; deployment address and results are in `DEVELOPMENT_PROGRESS.md`.

## Security boundary

The contract enforces coded transitions and local event history. The backend/oracle key, demo admin session, Hardhat JSON-RPC host, devices and Wi-Fi remain trust dependencies. Hash-linked SQLite events are not an external immutable ledger. Local Hardhat values are synthetic. The system is not unhackable and must not be connected to a public chain or real user funds.
