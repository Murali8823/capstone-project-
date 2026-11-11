# Demonstration Scenarios

## Dashboard controls

Open `/dashboard`, sign in with the configured admin password, choose Maya/Arjun/Riya and an amount, then use the scenario cards. A sets score and payment automatically. B/C/D create an escrow at 65%; use the score slider afterward for B/C. Scenario D waits for the configured timeout and exposes manual review/refund in Escrow Monitoring. Reset restores seeded demo state; on-chain history remains.

## Scenario A — Safe payment

1. Click **Run safe payment** (score 25%).
2. Backend approves and immediately moves simulated value from sender to business.
3. Verify `APPROVED`, updated balances, dashboard totals and event feed.

## Scenario B — Escrow then release

1. Click **Create escrow** on B (score 65%).
2. Verify sender balance decreased, business did not receive funds, escrow card appears, and a local contract hash exists.
3. Set business score to 35% and click Apply score.
4. Verify contract/backend `RELEASED`, business balance increase, hash/event feed and all mobile sender/receiver views.

## Scenario C — Escrow then refund

1. Click **Create escrow** on C (score 65%).
2. Set business score to 90% and apply.
3. Verify contract/backend `REFUNDED`, sender balance restoration and no business credit.

## Scenario D — Timeout review

1. Start backend with `SHIELDPAY_ESCROW_TIMEOUT_SECONDS=10` (default is 300).
2. Click **Start timeout demo** at score 65% and keep the score in the middle band.
3. Watch countdown reach zero; contract/backend enter `MANUAL_REVIEW` while funds remain locked.
4. Click **Review and refund sender** in Escrow Monitoring.
5. Verify `REFUNDED`, restored sender balance, contract event and audit history.

## Backend/contract verification record

Phase 2 API checks verified 25%, boundaries 49/50/80/81, idempotency, admin authorization, release at 35%, refund at 90%, SSE and timeout review/refund. Phase 4 live local-chain checks verified real contract states and receipt hashes for locked, released, refunded and manual-review records, plus chain-aware reset.

The four backend/contract paths are tested. Dashboard routes/resources and mobile bundle compile. A real browser interaction session and five physical phones were not available, so phone-to-phone visual synchronization should still be demonstrated manually in Phase 6.
