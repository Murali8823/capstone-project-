# Academic Review Explanation

## Problem statement

Digital payments can be sent to suspicious recipients, while senders have limited time to assess risk. A payment system can reduce immediate exposure by holding uncertain transfers until a trusted risk decision is available.

## Proposed solution

ShieldPay demonstrates risk-aware simulated payment handling. Three sender profiles, a suspicious persona and a legitimate business use one shared backend. A desktop dashboard monitors activity and changes receiver scores. A deterministic policy directs each transaction to approval, escrow or rejection. A local smart contract holds test-chain value and releases/refunds based on authenticated backend oracle updates.

The scores are fixed/configurable demo inputs. Machine learning, dataset collection and model training are deliberately disabled for this phase. There is no bank, UPI, card or payment gateway integration.

## System architecture and data flow

The five mobile phones and desktop browser connect to one backend on the computer's private Wi-Fi address. Mobile screens use Expo/React Native/TypeScript and refresh shared REST state every 1.8 seconds. The dashboard is a browser page served from the Python backend; it uses REST commands and Server-Sent Events (SSE) for live updates. Python stores simulated balances, profiles, transactions, scores and audit events in SQLite.

When a sender submits a payment, backend validates the sender role, receiver, amount, available balance and current score. It stores the score snapshot and makes a deterministic decision. For an escrow, the backend calls a local ethers bridge. The bridge sends a transaction to the local Hardhat EVM and returns its transaction hash and contract events. An authenticated admin score update follows the same bridge path; the backend is the oracle because the contract cannot read the dashboard or a score source itself.

## Scam-score policy

- Score below 50: `APPROVED`; sender is debited and receiver credited immediately.
- Score 50 through 80 inclusive: `ESCROW`; sender's simulated wallet is debited and equivalent local test-chain value is locked.
- Score above 80: `REJECTED`; sender balance remains unchanged and receiver gets nothing.
- For existing escrow, a new score below 50 releases; above 80 refunds; 50–80 remains locked.
- At timeout, status becomes `MANUAL_REVIEW`; funds remain locked until authenticated admin review refunds the sender.

The contract keeps the score at creation separately from the latest oracle score. It uses state checks so release and refund cannot both occur for the same escrow.

## Why use escrow and a smart contract?

Escrow delays recipient access while the risk score is in an uncertain range. Solidity code records the hold and restricts settlement to authorized contract transitions. It emits events that can be inspected on the local chain. These properties make the decision and outcome visible for an academic demonstration.

The contract does not infer scam risk. It does not independently read the desktop or AI output. The backend oracle authenticates an admin action, submits the score update using the local Hardhat oracle account, records the receipt, and sends updated state/events to clients.

## Broader edge/cloud risk design

A full research version could combine a fast edge risk signal with a cloud signal based on broader transaction context. Those signals could produce or adjust a receiver risk score. They are not present in this demo; using a configurable score isolates and explains the payment policy without claiming model accuracy.

## Technologies and modules

- **Expo, React Native, TypeScript, Expo Router:** one mobile codebase for the five selectable profiles.
- **Python standard-library HTTP server:** LAN API, dashboard hosting, admin controls, timeout worker and SSE without a FastAPI dependency.
- **SQLite:** shared durable local state and audit records.
- **SSE plus REST:** push notifications to browser dashboard; HTTP mutations and snapshot polling.
- **Solidity, Hardhat, ethers.js:** local escrow contract, deployment, lifecycle tests and backend oracle bridge.
- **HTML, CSS, browser JavaScript/Canvas:** local desktop dashboard and charts without a separate service.

## Security benefits and limits

Backend validates amounts, balances, roles and admin mutations. HMAC bearer tokens protect dashboard score/reset/refund routes. Contract oracle checks, unique IDs and lifecycle state prevent unauthorized or duplicate terminal settlement in the demo contract. Local EVM events show the contract's activity.

The score source, Python host, admin session, oracle process, local RPC, devices and Wi-Fi remain trusted dependencies. Demo sender IDs are selected, not authenticated. The default admin password is public demo configuration. Hardhat uses publicly known test keys. Test ETH is funded by the oracle account while synthetic INR is debited by the backend; this models the lifecycle but is not a real sender bank payment. HTTP is unencrypted, so keep the demo on a trusted private LAN. Blockchain does not make the whole system unhackable.

## Major demonstration scenarios

1. **Safe payment:** set score 25%, pay, verify `APPROVED` and immediate transfer.
2. **Escrow then release:** set 65%, create escrow, change score to 35%, verify contract `RELEASED` and receiver credit.
3. **Escrow then refund:** set 65%, create escrow, change score to 90%, verify `REFUNDED` and sender credit.
4. **Timeout:** leave score at 65%, wait for expiry, verify `MANUAL_REVIEW`, then admin-refund sender.

Dashboard controls and the backend/contract paths are implemented. Backend endpoints and contract transitions passed automated/manual checks. Physical five-phone use and browser visual interactions remain to be verified in the presentation environment.

## Current status and future work

Phases 1–5 implementation and technical documentation are complete. Python compilation, TypeScript check, Android bundle export, five Hardhat contract tests, backend API scenarios, live local-chain release/refund/timeout, dashboard static routes and same-host LAN checks passed. The next validation is opening the running Expo project on five actual phones and clicking through the dashboard in a browser. Machine learning remains a future phase after this deterministic escrow demonstration is evaluated.
