# ShieldPay: Step-by-Step Implementation Guide

*Edge-Cloud Intelligence for Real-Time Scam Detection and Risk-Aware Digital Payments*

A build manual for turning your research paper into a working system, written so you can paste sections directly into a vibe-coding tool (Cursor, Claude Code, Windsurf, Bolt, Lovable, Replit Agent, etc.).

---

## 0. How to Use This Document

1. Work **phase by phase, in order**. Each phase has a goal, a ready-to-paste prompt, expected output, and an acceptance test.
2. Never paste the whole document into the tool at once. Paste **one phase prompt at a time**, run the acceptance test, fix, commit, then move on.
3. Always start a new coding session by pasting the **Master Context File** from Section 3. AI tools forget; this file keeps every session consistent with your paper.
4. Commit to git after every passing phase (`git commit -m "phase 3 done"`). If the AI breaks something, you can roll back.
5. Ask the tool to **write tests first or alongside code**. Vibe-coded projects fail silently without tests.

**Golden rules when vibe coding:**

- Give small, specific tasks. "Build the escrow service" is too big; "Create the `escrow_holds` table and a function `create_hold()`" is right.
- Always state the file path, the language, the inputs and outputs, and a test you expect to pass.
- After each generation, run the code yourself. Paste the full error back if it fails.
- Pin library versions in `requirements.txt` so the tool does not use outdated APIs.

---

## 1. What You Are Building (Plain Summary)

A payment-risk system with four moving parts:

| Part | What it does | Paper section |
| --- | --- | --- |
| **Edge risk engine** | Small XGBoost model on the phone gives a fast risk score (even offline) | III-C |
| **Cloud Transformer** | Reads a user's recent transaction sequence and gives a fraud probability | III-B |
| **Scam Score + decision engine** | Keeps a decaying per-user score; fuses everything into Low / Medium / High | III-D, III-E |
| **Escrow + audit** | High-risk payments are held and re-evaluated; every decision is logged with tamper-evident hashes | III-F, III-H |

Plus: signed model updates (III-G), a retraining loop (III-I), and an evaluation harness (IV-C).

### Scope Decision (Important)

You cannot hold real UPI money without being a regulated entity. So this guide builds a **complete working prototype with a simulated wallet and simulated money**. The escrow module is designed behind an interface so a bank or PSP partner's hold mechanism can replace it later. Do not describe the prototype as moving real money in your report.

---

## 2. Tech Stack (Chosen for Vibe-Coding Friendliness)

These choices are popular, well documented, and AI tools generate them reliably.

| Layer | Choice | Why |
| --- | --- | --- |
| Language (backend/ML) | Python 3.11 | Best AI-tool support |
| API framework | FastAPI + Pydantic v2 | Auto docs, typed |
| Database | PostgreSQL 16 | Ledger, escrow, audit index |
| Cache / score store | Redis 7 | Fast Scam Score reads |
| ML (edge) | XGBoost | Exportable to JSON trees |
| ML (cloud) | PyTorch 2.x | Transformer |
| Calibration/metrics | scikit-learn | Platt, isotonic, PR-AUC |
| Explainability | SHAP | Reason codes for appeals |
| Job scheduling | APScheduler (simple) or Celery + Redis | Escrow review window |
| Signing | PyNaCl (Ed25519) | Signed model bundles |
| Mobile app | Flutter (Dart) | One codebase, Android and iOS |
| Containers | Docker Compose | One-command local stack |
| Experiment tracking | MLflow (optional) | Model versions |
| Tests | pytest, Flutter test | Acceptance checks |

**Key design trick for the phone model:** do not fight with native ONNX plugins. Export the XGBoost trees to a JSON file and write a tiny tree-walker in Dart (about 40 lines). It is fast (microseconds), has no native dependencies, and is easy for an AI tool to get right.

---

## 3. Master Context File (Paste at the Start of Every Session)

Create `docs/PROJECT_CONTEXT.md` in your repo with this content, and paste it into your tool at the start of every session.

```markdown
# ShieldPay Project Context

Goal: risk-aware payment prototype with edge-cloud fraud detection.
Money is SIMULATED. Never integrate real payment rails.

## Components
- ml/: data generation, features, XGBoost edge model, Transformer, calibration, evaluation
- services/gateway: FastAPI app, the only public API
- services/scamscore: per-user Scam Score (Redis) implementing Eq.1
- services/decision: fusion of PT, PE, receiver Scam Score (Eq.2), thresholds T1,T2
- services/escrow: state machine HELD -> RELEASED | RETURNED | INVESTIGATING
- services/audit: encrypted records + SHA-256 hash chain
- mobile/: Flutter app with offline edge scoring and signed model updates

## Equations
Eq.1: S_u(t) = a*S_u(t-1)*exp(-dt/tau) + (1-a)*(w1*PT + w2*PE + w3*Ru)
Eq.2: P = wT*PT + wE*PE + wR*Sr    (online)
      offline: P = weighted PE + regional risk indicator
Bands: Low P<T1 -> APPROVE; Medium T1<=P<T2 -> VERIFY; High P>=T2 -> HOLD

## Rules
- Python 3.11, type hints, pydantic v2, pytest for every module.
- Clients never receive raw scores, only APPROVE/VERIFY/HOLD plus reason codes.
- Time-based train/val/test splits only, never random.
- Cloud call has an 80ms timeout; on timeout fall back to edge score.
- All model bundles are signed (Ed25519) with a monotonically increasing version.
- Sensitive identifiers are pseudonymised (HMAC-SHA256 with a secret salt).
- Never hardcode secrets; read from environment variables.
```

---

## 4. Repository Structure

```text
shieldpay/
  docs/
    PROJECT_CONTEXT.md
    API.md
  data/
    raw/            # downloaded datasets (gitignored)
    synthetic/      # generated UPI-style data
    processed/      # features, splits
  ml/
    datagen/        # synthetic generator
    features/       # feature pipeline
    edge/           # XGBoost train + export
    transformer/    # sequence model
    calibration/    # Platt/isotonic + thresholds
    eval/           # metrics, ablations, fairness
    artifacts/      # trained models (gitignored)
  services/
    gateway/
    scamscore/
    decision/
    escrow/
    audit/
    common/         # shared config, db, schemas
  mobile/           # Flutter app
  infra/
    docker-compose.yml
    init.sql
  tests/
  Makefile
  requirements.txt
  .env.example
  README.md
```

---

## 5. Phase 0: Environment Setup (Day 1)

**Goal:** a clean repo, running Postgres and Redis, and a "hello world" API.

**Install first (manually):** Python 3.11, Docker Desktop, Git, Flutter SDK, VS Code or Cursor.

**Prompt to paste:**

```text
Create the monorepo skeleton described in docs/PROJECT_CONTEXT.md with this folder
structure: [paste Section 4 tree]. Then:

1. Create requirements.txt with pinned versions: fastapi, uvicorn[standard], pydantic>=2,
   sqlalchemy>=2, psycopg[binary], redis, pandas, numpy, scikit-learn, xgboost, torch,
   shap, pynacl, cryptography, apscheduler, pytest, httpx, faker, mlflow.
2. Create infra/docker-compose.yml with postgres:16 (db shieldpay, user shieldpay,
   password from .env) and redis:7, both with healthchecks and named volumes.
3. Create .env.example with DATABASE_URL, REDIS_URL, PSEUDONYM_SALT, AUDIT_ENC_KEY,
   MODEL_SIGNING_KEY_PATH, CLOUD_TIMEOUT_MS=80.
4. Create services/common/config.py loading settings with pydantic-settings.
5. Create services/gateway/main.py: a FastAPI app with GET /health returning {"ok": true}.
6. Create a Makefile with targets: up, down, api, test.
7. Create .gitignore (data/raw, ml/artifacts, .env, __pycache__, mobile build dirs).
```

**Acceptance test:**

- `make up` starts Postgres and Redis healthy.
- `make api` runs the server; `curl localhost:8000/health` returns `{"ok": true}`.
- `pytest` runs (even with zero tests) without import errors.

---

## 6. Phase 1: Data (Week 1-2)

### 6.1 Download Public Datasets

Download manually (Kaggle login required) and place under `data/raw/`:

- **PaySim** (mobile-money simulator, `PS_...log.csv`): good for transfer/cash-out fraud patterns.
- **IEEE-CIS Fraud Detection** (`train_transaction.csv`, `train_identity.csv`): card-not-present e-commerce fraud, rich features.

(These are two separate datasets. Cite them separately in your paper.)

Public data has **no receiver-side scam signals** and no UPI behavior, which is why you also need a synthetic generator.

### 6.2 Synthetic UPI-Style Generator (Core of Your Evaluation)

**Goal:** produce 1-3 million transactions with realistic normal behavior and labelled scam patterns, including receiver-side signals.

**Prompt to paste:**

```text
In ml/datagen/generate.py write a synthetic UPI-style transaction generator.

Entities:
- 20,000 users across 8 regions (region_id 0-7), each with: home_region, typical_amount
  (lognormal), activity_rate (txns/day, Poisson), active_hours (a 6-hour window),
  account_age_days, is_merchant (10%).
- 1,500 merchants with merchant_age_days (30% are < 60 days old, and are legitimate).
- Fraud actors: 300 mule accounts (receive many first-time payments, then fan out money
  fast) and 100 scammer accounts (receive from many victims within hours).

Generate 60 days of transactions. Columns: txn_id, timestamp, sender_id, receiver_id,
amount, sender_region, receiver_region, hour, is_new_payee (sender never paid this
receiver before), sender_txn_count_24h, receiver_unique_senders_24h, receiver_inflow_24h,
receiver_age_days, device_id, is_fraud, scam_type (none | mule | impersonation |
urgent_request | fake_merchant), reported_by_victim (True for ~40% of frauds, delayed
by 1-14 days).

Fraud injection rules:
1. Impersonation scam: victim pays a new payee an amount 3-10x their typical amount,
   often at unusual hours.
2. Mule burst: a mule receives 20+ payments from different senders in a few hours,
   then forwards 90% of it within an hour.
3. Urgent-request scam: 2-4 rapid payments from the same victim to the same new payee.
4. Fake merchant: new merchant account receives many small payments then disappears.
Overall fraud rate should be about 0.4-0.8%. Add 5% label noise (some fraud unlabeled).

Save to data/synthetic/upi_txns.parquet with a fixed random seed (CLI arg --seed).
Also write a test checking: fraud rate in range, timestamps sorted, no null sender_id.
```

**Acceptance test:** fraud rate is 0.4-0.8%; at least four scam types present; 30% of new merchants are legitimate (this is how you later test fairness for new merchants).

### 6.3 Pseudonymisation Utility

```text
In services/common/pseudonym.py write pseudonymise(value: str) -> str using
HMAC-SHA256 keyed with PSEUDONYM_SALT from environment, returning a hex digest
truncated to 16 chars. Add tests: same input gives same output; different salt gives
different output; empty string raises ValueError.
```

Use it for any identifier that enters logs or the audit store.

---

## 7. Phase 2: Feature Engineering (Week 2-3)

**Goal:** one feature pipeline used for training AND serving, so there is no train/serve skew.

### 7.1 Features to Compute

**Sender behavior (edge-computable, computed on the phone from local history):**

- `amount`, `log_amount`
- `amount_ratio_to_typical` = amount / sender's median of last 30 payments
- `sender_txn_count_1h`, `sender_txn_count_24h`
- `is_new_payee` (never paid this receiver before)
- `payee_txn_count_by_sender`
- `hour_of_day` (sin and cos encoded), `is_unusual_hour` (outside sender's usual window)
- `time_since_last_txn_seconds` (log)
- `receiver_region_matches_sender` (bool)
- `regional_risk` (lookup from the region risk table)

**Receiver-side (cloud only):**

- `receiver_unique_senders_24h`
- `receiver_inflow_24h`
- `receiver_age_days`
- `receiver_fraud_report_count`
- `receiver_scam_score` (from Scam Score service)

### 7.2 Leakage Warning

Every feature must be computed **using only data before the transaction timestamp**. Use rolling windows with `closed="left"`. The most common vibe-coding mistake is a rolling window that accidentally includes the current row or future rows, which gives unrealistic 99% scores.

**Prompt to paste:**

```text
In ml/features/pipeline.py implement build_features(df) -> DataFrame that computes the
features listed in docs/PROJECT_CONTEXT.md and Section 7.1 of the guide, from the
synthetic dataframe sorted by timestamp.

Requirements:
- Use only information strictly BEFORE each transaction's timestamp (no leakage).
  Use groupby + rolling with closed='left' or an incremental loop with dictionaries.
- Provide two feature lists: EDGE_FEATURES (sender-side only) and CLOUD_FEATURES
  (edge + receiver-side).
- Provide time_split(df, train_frac=0.7, val_frac=0.15) that splits CHRONOLOGICALLY.
- Write tests: (1) a handcrafted 6-row dataframe where expected feature values are
  known; (2) a leakage test that shuffles future rows and asserts features of earlier
  rows are unchanged.
- Save processed splits to data/processed/{train,val,test}.parquet.
```

**Acceptance test:** the leakage test passes; train/val/test date ranges do not overlap; class balance is reported for each split.

### 7.3 Region Risk Table

```text
In ml/features/region_risk.py compute a region risk table from the TRAIN split only:
for each region_id, risk = smoothed fraud rate of transactions received by that region
(Laplace smoothing with a global prior, strength 200). Save as
ml/artifacts/region_risk.json {region_id: risk, "_global": global_rate, "_version": 1}.
Add a test that unseen regions fall back to the global rate.
```

---

## 8. Phase 3: Models (Week 3-7)

### 8.1 Baselines First

Before building anything fancy, train Logistic Regression, Random Forest and plain XGBoost on `CLOUD_FEATURES`. These are your comparison rows in the paper, and they tell you if your data is learnable at all.

```text
In ml/eval/baselines.py train LogisticRegression (class_weight balanced, scaled
features), RandomForest (300 trees, class_weight balanced_subsample) and XGBoost on
data/processed/train.parquet using CLOUD_FEATURES. Evaluate on val and test:
PR-AUC (average_precision_score), recall at FPR=1% and FPR=0.1%, F1 at the best
threshold on val. Write results to ml/artifacts/baseline_results.json and print a
markdown table. Use scale_pos_weight for XGBoost. Add a sanity test that PR-AUC is
greater than the fraud base rate.
```

**Acceptance test:** PR-AUC clearly beats the base rate on the test split. If it is above 0.99, suspect leakage and revisit Phase 2.

### 8.2 Edge Model (XGBoost, Small)

**Goal:** a tiny model that uses only `EDGE_FEATURES`, trains fast, and exports to JSON for the phone.

```text
In ml/edge/train_edge.py:
1. Train XGBoost using ONLY EDGE_FEATURES + regional_risk. Constrain size:
   n_estimators<=80, max_depth<=4, learning_rate 0.1, subsample 0.8, early stopping
   on the val split using aucpr.
2. Report model size in KB, and inference latency per prediction (p50, p95) on CPU.
3. Export the booster trees to ml/artifacts/edge_model.json in this schema:
   {"version": int, "features": [names in order], "base_score": float,
    "trees": [ nested node dicts: {"f": feature_index, "t": threshold,
    "l": left_node, "r": right_node} or {"leaf": value} ]}
   (xgboost: use booster.get_dump(dump_format='json') and convert).
4. Write ml/edge/predict_json.py implementing a pure-Python tree walker that reads
   the JSON and returns sigmoid(base_margin + sum(leaf values)).
5. Add a test: for 1,000 random test rows, the JSON walker output equals
   xgboost predict_proba within 1e-5.
```

This test is critical. The Dart implementation on the phone must also match it (see Phase 8).

### 8.3 Cloud Transformer (Sequence Model)

**Goal:** read a user's last N transactions and output a fraud probability for the newest one.

**Input design (each transaction becomes one token):**

- Numeric vector: `log_amount`, `amount_ratio_to_typical`, `log_time_gap`, `hour_sin`, `hour_cos`, `is_new_payee`, `receiver_region_matches_sender`, `receiver_unique_senders_24h` (log), `receiver_age_days` (log)
- Categorical: `receiver_region` (embedding), `sender_region` (embedding)
- Sequence length N = 32 (pad shorter histories with a mask)
- Label: `is_fraud` of the **last** transaction in the window

```text
In ml/transformer/model.py and train.py build a PyTorch model:
- Dataset: for every transaction, build a window of that sender's previous 31
  transactions plus the current one (left-padded, with an attention mask), using only
  the numeric + categorical features above. Build windows with no future leakage.
- Model: Linear(num_features -> 64) + region embeddings (dim 8, concatenated) ->
  learned positional embedding -> 2 TransformerEncoder layers (d_model 64, 4 heads,
  ff 128, dropout 0.1, batch_first=True) -> take the LAST token representation ->
  MLP -> 1 logit.
- Loss: BCEWithLogits with pos_weight = (neg/pos) clipped to 50. Optimiser AdamW
  lr 1e-3, 8-15 epochs, early stopping on val PR-AUC. Use a WeightedRandomSampler
  or downsample negatives 10:1 per epoch if training is slow.
- Save best weights to ml/artifacts/transformer.pt and export to ONNX at
  ml/artifacts/transformer.onnx (dynamic batch axis). Verify ONNX output matches
  PyTorch within 1e-4 in a test.
- Report PR-AUC and recall@1%FPR on val and test, and CPU latency for batch size 1.
Provide a --small flag to train on a 200k-row subsample for quick debugging.
```

**Tips if the AI tool struggles:**

- Start with a 2-layer MLP over the last 8 transactions to confirm the pipeline works, then swap in the Transformer.
- If it overfits, lower the layer count or add dropout. If the data is tiny, the Transformer may not beat XGBoost; that is a legitimate result to report honestly.

### 8.4 Calibration and Threshold Selection

Raw model outputs are not true probabilities. Calibration makes `P` meaningful, and thresholds are chosen from cost, as your paper specifies.

```text
In ml/calibration/calibrate.py:
1. Fit both Platt scaling (LogisticRegression on logit scores) and isotonic regression
   on VAL predictions of the fused score P. Pick the one with the lower Brier score,
   save as ml/artifacts/calibrator.pkl, and report a reliability curve (10 bins).
2. Implement choose_thresholds(y_true, p, cost_missed_fraud, cost_hold, cost_verify)
   that grid-searches T1<T2 on the VAL set to minimise expected cost:
     cost = C_miss * (fraud with action APPROVE)
          + C_verify * (non-fraud with action VERIFY)
          + C_hold * (non-fraud with action HOLD)
          + 0.3*C_miss * (fraud with action VERIFY)   # step-up catches some fraud
   Use defaults C_miss=100, C_verify=1, C_hold=5 (configurable).
3. Save ml/artifacts/thresholds.json {"T1":..., "T2":..., "version":1}.
4. Test: thresholds satisfy 0<T1<T2<1; when C_miss is raised, T1 decreases or stays.
```

Fit calibration and thresholds on **validation**, report on **test**. Never tune on test.

---

## 9. Phase 4: Scam Score Service (Week 6-8)

**Goal:** implement Eq. (1) exactly, with per-user state in Redis.

`S_u(t) = alpha * S_u(t-1) * exp(-dt/tau) + (1-alpha) * (w1*PT + w2*PE + w3*Ru)`

**Suggested defaults:** `alpha = 0.7`, `tau = 7 days (604800 s)`, `w1 = 0.5, w2 = 0.2, w3 = 0.3`, regional prior `S0` = region risk from `region_risk.json`.

**Redis keys:**

- `ss:{user}` as a hash: `score`, `last_ts`, `report_count`, `verified_reports`
- `reporters:{user}` as a set of reporter IDs (for corroboration)

```text
In services/scamscore/scoring.py implement:

def update_score(redis, user_id, pt, pe, ru, now_ts, region_prior) -> float
  - If no state exists, initialise S_prev = region_prior (NOT zero).
  - dt = now_ts - last_ts; apply Eq.1; clamp to [0,1]; store atomically with a Lua
    script or WATCH/MULTI so concurrent updates cannot lose writes.

def get_score(redis, user_id, now_ts, region_prior) -> float
  - Return the stored score with decay applied to now (read-only, do not write).

def submit_report(redis, reporter_id, target_id, reporter_reliability) -> dict
  - Reports only affect Ru after corroboration: require >=3 distinct reporters
    OR one reporter with reliability >= 0.8. Weight each report by reliability.
  - Rate limit: a reporter may file at most 5 reports per day.
  - Returns {"accepted": bool, "ru": float, "reason": str}.

Tests with fakeredis: (1) new user starts at the regional prior; (2) score decays
toward 0 with no events (check after 1 tau it is ~37% of the start); (3) repeated
high PT raises the score monotonically; (4) a single low-reliability report does not
change Ru; (5) three distinct reporters do; (6) the 6th report in a day is rejected.
```

**Acceptance test:** all six tests pass. Also manually verify recovery: set a high score, wait (simulate time) and confirm it falls, which demonstrates your "score recovers when behaviour improves" claim.

---

## 10. Phase 5: Decision Engine and Gateway API (Week 7-10)

### 10.1 Fusion (Eq. 2)

`P = wT*PT + wE*PE + wR*Sr` when online; when offline, use `PE` with the regional risk indicator. Calibrate, then apply thresholds.

```text
In services/decision/engine.py implement:

class Decision(BaseModel): action: Literal['APPROVE','VERIFY','HOLD'];
  reason_codes: list[str]; latency_ms: float; mode: Literal['online','offline']

def decide(pe, pt_or_none, receiver_score, region_risk, thresholds, calibrator,
           weights={'T':0.5,'E':0.25,'R':0.25}) -> tuple[Decision, float]
  - If pt_or_none is None -> mode offline: P = 0.7*pe + 0.3*region_risk.
  - Else online using Eq.2. Always calibrate P, then compare with T1, T2.
  - Return the decision and the calibrated P (P is stored internally, NEVER returned
    to clients).

Tests: low inputs -> APPROVE; mid -> VERIFY; high -> HOLD; offline path works with
pt None; boundary values P==T1 -> VERIFY and P==T2 -> HOLD.
```

### 10.2 Reason Codes (Explainability and Appeals)

```text
In services/decision/explain.py use SHAP TreeExplainer on the edge XGBoost model to
return the top 3 features pushing risk up for a given transaction, mapped to
human-readable codes:
  is_new_payee -> NEW_PAYEE
  amount_ratio_to_typical -> UNUSUAL_AMOUNT
  is_unusual_hour -> UNUSUAL_TIME
  receiver_unique_senders_24h -> RECEIVER_MANY_SENDERS
  receiver_age_days -> NEW_RECEIVER_ACCOUNT
  receiver_scam_score -> RECEIVER_FLAGGED
  sender_txn_count_1h -> RAPID_PAYMENTS
Precompute the explainer once at startup. Cache results per request id.
```

### 10.3 Gateway Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/payments/score` | Score a payment; returns decision + reason codes (no raw scores) |
| `POST /v1/payments/{id}/verify` | Submit step-up verification result for a VERIFY payment |
| `GET /v1/payments/{id}` | Status (APPROVED, PENDING\_VERIFY, HELD, RELEASED, RETURNED, INVESTIGATING) |
| `POST /v1/reports` | Report a suspected scam account |
| `POST /v1/appeals` | Appeal a hold, with a 48h response SLA |
| `GET /v1/updates/latest` | Latest signed model/risk bundle manifest |
| `GET /health` | Liveness |

```text
In services/gateway/ implement the endpoints above with FastAPI and pydantic schemas.

POST /v1/payments/score request: {payment_id (uuid), sender_id, receiver_id, amount,
timestamp, edge_pe (float, from the phone), edge_features (dict), device_id}.
Flow:
 1. Validate and pseudonymise ids for logging.
 2. Load receiver Scam Score (get_score) and receiver-side features from Redis/Postgres.
 3. Call the Transformer (in-process ONNX runtime) inside asyncio.wait_for with a
    timeout of CLOUD_TIMEOUT_MS; on timeout/error use pt=None (offline mode) and
    record fallback=True.
 4. decide() -> action. Persist the payment row (status per action) in Postgres.
 5. If HOLD, call escrow.create_hold(). Update the sender/receiver Scam Scores with
    update_score(). Write an audit event (Phase 8).
 6. Return {payment_id, action, reason_codes, status}. NEVER include probabilities.

Add rate limiting: max 30 score requests/min per sender (Redis token bucket), 429
on excess. Add an API key header check for service-to-service calls. Auto-generate
docs/API.md from the OpenAPI schema.

Tests with httpx.AsyncClient: APPROVE, VERIFY and HOLD paths; timeout fallback path
(mock slow transformer) still returns within 200ms; rate limit returns 429; response
JSON contains no key named 'score', 'probability' or 'p'.
```

**Acceptance test:** end-to-end, one `curl` scoring request returns a decision in under 200 ms locally, the fallback test passes, and the no-raw-scores test passes.

---

## 11. Phase 6: Simulated Wallet, Ledger and Escrow (Week 7-10)

### 11.1 Database Schema

```sql
CREATE TABLE accounts (
  id UUID PRIMARY KEY,
  user_ref TEXT UNIQUE NOT NULL,        -- pseudonymised id
  balance_paise BIGINT NOT NULL DEFAULT 0 CHECK (balance_paise >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payments (
  id UUID PRIMARY KEY,
  sender_id UUID REFERENCES accounts(id),
  receiver_id UUID REFERENCES accounts(id),
  amount_paise BIGINT NOT NULL CHECK (amount_paise > 0),
  action TEXT NOT NULL,                 -- APPROVE | VERIFY | HOLD
  status TEXT NOT NULL,                 -- see state machine
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ledger_entries (
  id BIGSERIAL PRIMARY KEY,
  payment_id UUID REFERENCES payments(id),
  account_id UUID,                      -- NULL allowed only for escrow pool
  pool TEXT,                            -- 'ESCROW' or NULL
  delta_paise BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE escrow_holds (
  payment_id UUID PRIMARY KEY REFERENCES payments(id),
  state TEXT NOT NULL,                  -- HELD|RELEASED|RETURNED|INVESTIGATING
  review_deadline TIMESTAMPTZ NOT NULL,
  last_p_bucket TEXT,                   -- low/medium/high at last re-eval
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Invariant to test forever:** the sum of all `delta_paise` in `ledger_entries` is always zero (double-entry). Every transfer writes two rows: debit one side, credit the other.

### 11.2 Escrow State Machine

```text
PENDING -> APPROVED                       (low risk, immediate transfer)
PENDING -> PENDING_VERIFY -> APPROVED     (medium risk, after step-up OK)
PENDING_VERIFY -> CANCELLED               (step-up failed or abandoned)
PENDING -> HELD                           (high risk; sender debited, pool credited)
HELD -> RELEASED   (re-eval P < T1, or P in medium + step-up passed)
HELD -> RETURNED   (fraud confirmed)
HELD -> INVESTIGATING  (unresolved at review_deadline)
INVESTIGATING -> RELEASED | RETURNED (manual outcome)
```

```text
In services/escrow/ implement with SQLAlchemy 2 and Postgres transactions:

- create_hold(payment_id): in ONE DB transaction, debit sender, credit ESCROW pool
  (two ledger rows), insert escrow_holds with review_deadline = now + THOLD (default
  48h, configurable; tests use seconds). Use SELECT ... FOR UPDATE on the account row.
- reevaluate(payment_id): recompute P using the latest receiver Scam Score and any
  new evidence; P<T1 -> release(); T1<=P<T2 -> request step-up then release();
  P>=T2 -> stay HELD. Record last_p_bucket.
- release(payment_id), return_funds(payment_id), escalate(payment_id): each validates
  the current state (illegal transitions raise InvalidTransition), moves money via
  double-entry rows, updates state and writes an audit event.
- A scheduler (APScheduler, every 60s) that (a) re-evaluates all HELD rows, (b)
  escalates holds past review_deadline to INVESTIGATING.
- Abstract class EscrowBackend with methods hold/release/return_funds so a real
  bank partner can replace SimulatedEscrow later.

Tests: balance never negative; ledger sums to zero after every operation; illegal
transition raises; concurrent create_hold calls on an account with insufficient funds
do not overdraw (use threads); deadline escalation works with a 2-second window;
idempotency: calling release twice does not move money twice.
```

**Acceptance test:** all tests above pass, especially double-spend and idempotency. These are the failures that vibe-coded wallets most often have.

---

## 12. Phase 7: Audit Store and Signed Model Updates (Week 10-12)

*Note: earlier sections say "write an audit event (Phase 8)". Build the audit module here, in Phase 7, before wiring it into the gateway and escrow.*

### 12.1 Tamper-Evident Audit Log (Replaces Raw IPFS)

Your paper flags that IPFS conflicts with erasure rights and regulation. The defensible design is: **store encrypted records in your own database, and publish only hashes** into a hash chain (optionally anchored to IPFS or a permissioned log). Deleting a record's encrypted payload (erasure) then does not break the chain.

```sql
CREATE TABLE audit_log (
  seq BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,            -- SCORED, HELD, RELEASED, RETURNED, REPORT, APPEAL, MODEL_UPDATE
  payment_id UUID,
  payload_enc BYTEA,                   -- AES-GCM ciphertext (nullable after erasure)
  payload_hash TEXT NOT NULL,          -- sha256 of canonical plaintext JSON
  prev_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL,           -- sha256(prev_hash || payload_hash || event_type || seq)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON audit_log(payment_id);
```

```text
In services/audit/ implement:

- append(event_type, payment_id, payload: dict) -> record_hash:
  1. canonical = json.dumps(payload, sort_keys=True, separators=(',',':')).
  2. payload_hash = sha256(canonical).
  3. Encrypt canonical with AES-256-GCM (cryptography library), key from AUDIT_ENC_KEY
     (32 bytes base64), random 12-byte nonce prepended to the ciphertext.
  4. In ONE transaction: lock the last row (SELECT ... ORDER BY seq DESC LIMIT 1 FOR
     UPDATE), take its record_hash as prev_hash (genesis = 64 zeros), compute
     record_hash, insert.
- read(payment_id) decrypts and returns events (authorised callers only).
- verify_chain(start=1, end=None) -> {valid: bool, first_bad_seq: int|None} that
  recomputes every record_hash and checks prev_hash linkage.
- erase(payment_id): set payload_enc = NULL for that payment (right to erasure) while
  keeping hashes; verify_chain must still pass.
- daily_anchor(): compute a Merkle root of that day's record_hashes and store it in
  an anchors table (optionally pin to IPFS; note in docs that this is optional).
- NEVER log raw ids; use pseudonymised ids inside payloads.

Tests: append 100 events then verify_chain is valid; tamper with one payload_hash in
the DB then verify_chain returns that seq; erase a payment then chain still valid and
read returns no payload; wrong key fails decryption; concurrent appends keep a
contiguous valid chain.
```

**Acceptance test:** the tamper test detects the exact modified row, and erasure does not break verification.

### 12.2 Signed Model and Risk-Table Bundles (Paper III-G)

**Bundle contents:** `edge_model.json`, `region_risk.json`, `thresholds.json`, and a `manifest.json`.

```json
{
  "version": 7,
  "created_at": "2026-11-05T10:00:00Z",
  "min_app_version": "1.0.0",
  "files": {
    "edge_model.json": "<sha256 hex>",
    "region_risk.json": "<sha256 hex>",
    "thresholds.json": "<sha256 hex>"
  },
  "signature": "<base64 Ed25519 signature over the canonical manifest WITHOUT the signature field>"
}
```

```text
In services/updates/ implement:

- tools/gen_keys.py: generate an Ed25519 keypair with PyNaCl. Print the public key
  (base64) for embedding in the mobile app; save the private key to the path in
  MODEL_SIGNING_KEY_PATH with chmod 600. NEVER commit the private key.
- build_bundle(artifact_dir, version) -> writes manifest.json with sha256 of each file
  and an Ed25519 signature over canonical JSON (sort_keys, no spaces) of the manifest
  without 'signature'.
- verify_bundle(manifest, files, public_key, current_version) -> raises on any of:
  bad signature, hash mismatch for any file, version <= current_version (rollback).
- GET /v1/updates/latest returns the manifest and file URLs (static files).

Tests: valid bundle passes; flipping one byte in edge_model.json fails; editing the
manifest version fails (signature breaks); version equal or lower than current is
rejected as rollback; verification with the wrong public key fails.
```

**Acceptance test:** the five tests pass. Also write the exact same test cases in Dart in Phase 8, because the phone is the component that must enforce them.

---

## 13. Phase 8: Flutter Mobile App with Offline Edge Scoring (Week 8-12)

**Goal:** a demo app with login (mock), balance, send-money screen, offline risk scoring, step-up verification, status screen for held payments, and report-scam button.

### 13.1 Screens

1. **Home:** balance, recent payments, a connectivity indicator (online/offline).
2. **Send:** payee ID, amount, Send button.
3. **Result:** shows the decision outcome: Sent, Verify (step-up), or Held for review with reason codes in plain language, plus an "Appeal" button.
4. **Verify:** PIN or biometric (use `local_auth`) for medium risk.
5. **Held payments:** list with state and review deadline.
6. **Report:** report a payee as scam.
7. **Settings (debug):** show model version, toggle "simulate offline", force update check.

### 13.2 Local Edge Scoring in Dart

The tree walker must match the Python walker exactly. Keep it short:

```dart
class EdgeModel {
  final List<String> features;
  final double baseMargin;       // logit(base_score) exported by Python
  final List<dynamic> trees;
  EdgeModel(this.features, this.baseMargin, this.trees);

  double predict(List<double> x) {
    var margin = baseMargin;
    for (final tree in trees) {
      var n = tree as Map<String, dynamic>;
      while (!n.containsKey('leaf')) {
        final v = x[n['f'] as int];
        n = (v.isNaN || v < (n['t'] as num)) ? n['l'] : n['r'];  // match XGBoost: yes-branch is x < t
      }
      margin += (n['leaf'] as num).toDouble();
    }
    return 1.0 / (1.0 + math.exp(-margin));
  }
}
```

(Handle XGBoost's default direction for missing values consistently with the Python exporter; simplest is to impute missing values to 0 in both places so the issue never arises.)

```text
In mobile/ create a Flutter app (Android first) with this structure:
 lib/main.dart, lib/screens/*.dart, lib/services/edge_model.dart,
 lib/services/local_history.dart, lib/services/api_client.dart,
 lib/services/update_manager.dart, lib/services/risk_features.dart

local_history.dart: store the last 100 sent payments in sqflite (payee, amount,
 timestamp). risk_features.dart: compute the SAME EDGE_FEATURES as the Python
 pipeline from local history (amount_ratio_to_typical = amount / median of last 30,
 is_new_payee, sender_txn_count_1h/24h, hour sin/cos, is_unusual_hour, time since last
 txn, regional_risk from region_risk.json). Provide a golden-file test: a JSON file of
 50 input rows with expected feature vectors and expected edge probabilities produced
 by Python; the Dart test must match to 1e-5.

send flow:
 1. Compute features and edge probability pe locally (works fully offline).
 2. Try POST /v1/payments/score with a 150ms total timeout.
 3. If the server answers, follow its action (APPROVE/VERIFY/HOLD).
 4. If offline or timeout, decide locally: pe_adj = 0.7*pe + 0.3*regional_risk, then
    compare to the cached thresholds. Offline APPROVE is allowed; offline HOLD is
    queued locally and sent to the server on reconnect (payment stays pending). Mark
    offline decisions with a badge in the UI.
 5. VERIFY triggers local_auth; on success POST /v1/payments/{id}/verify.
 Show only action and plain-language reason codes, never numeric scores.
```

### 13.3 Secure Update Manager in Dart

```text
In lib/services/update_manager.dart:
- Embed the Ed25519 PUBLIC key as a constant (base64).
- On app start and every 6 hours online: GET /v1/updates/latest. If version > stored
  version, download all files, verify (a) manifest signature using the cryptography or
  pinenacl package over canonical JSON (sorted keys, no spaces), (b) sha256 of each
  file, (c) version strictly greater than the current one.
- If verification passes, atomically swap in the new files (write to temp dir, then
  rename) and update the stored version. If it fails, keep the previous trusted bundle,
  log an AUDIT-style local event, and show a 'Update rejected' notice in the debug
  screen. Never fall back to unsigned data.
Dart tests mirroring the five Python tests in Section 12.2, using a test keypair.
```

### 13.4 Device Attestation (Optional for Prototype)

On Android, call the **Play Integrity API** and send the integrity token with each scoring request; the gateway verifies it with Google's server API. For a student prototype, implement a stub `verify_attestation()` behind a feature flag and describe the real integration in the report.

**Acceptance test:** in airplane mode a payment is scored in under 10 ms locally; Dart golden test matches Python; a tampered bundle is rejected on the device.

---

## 14. Phase 9: Feedback Loop and Retraining (Week 12-14)

**The label problem (paper III-I):** held payments never get a clean outcome, and confirmed labels take weeks. Without care, your model learns from its own decisions.

### 14.1 Mitigations to Implement

1. **Random release sample:** release 2-5% of medium-risk payments (and a smaller fraction of high-risk in a simulation-only mode) without extra friction, and observe outcomes. Tag these rows `exploration=true`.
2. **Delayed labels:** keep a `label_status` column (`pending`, `confirmed_fraud`, `confirmed_legit`). Train only on rows older than the label-delay window (for example 14 days) or with confirmed status.
3. **Inverse propensity weights:** weight exploration rows by `1/sampling_rate` so they stand in for the blocked traffic.
4. **Never treat a model's own HOLD as ground truth fraud.**

```text
In ml/retrain/retrain.py implement a pipeline:
 1. Pull labelled rows from Postgres (label_status != 'pending' and age > 14 days).
 2. Apply weights: exploration rows get weight 1/sample_rate, others 1.
 3. Retrain edge XGBoost and the Transformer using the same code as Phase 3, with the
    time-based split.
 4. Gate: only promote the new model if PR-AUC on the validation split and recall@1%FPR
    are >= the current production model's values (read from MLflow or a metrics.json),
    AND the FPR gap across regions does not worsen by more than 0.5 points.
 5. If it passes: recalibrate, re-choose thresholds, bump the version, build and sign a
    new bundle (Section 12.2), publish it, and write a MODEL_UPDATE audit event.
 6. If it fails: keep the old model and write a MODEL_UPDATE_REJECTED audit event.
Provide a CLI: python -m ml.retrain.retrain --dry-run and a nightly cron entry.
Test with a small synthetic dataset where a deliberately worse model is rejected.
```

### 14.2 Drift Monitoring

Log weekly: feature means vs training means (population stability index per feature), average score by action band, and hold rate. Alert (print a warning for the prototype) if any PSI exceeds 0.25.

---

## 15. Phase 10: Evaluation Harness (Week 13-16)

This phase produces the numbers and figures for your paper's results section.

### 15.1 Experiments

| Experiment | What to compare | Metrics |
| --- | --- | --- |
| E1 Baselines | LogReg, RF, XGBoost, LSTM, Transformer | PR-AUC, recall@1%FPR, recall@0.1%FPR, F1 |
| E2 Ablation | Edge-only vs Cloud-only vs Hybrid | Same metrics + p50/p95 latency |
| E3 Offline degradation | Hybrid with network off vs on | Recall@FPR drop, % decisions made offline |
| E4 Cost | Expected loss at chosen T1, T2 vs single-threshold | Expected cost, hold rate, verify rate |
| E5 Fairness | FPR by region and by merchant age bucket (<60 days vs older) | FPR gap, HOLD rate gap |
| E6 Escrow | Outcomes of HELD payments | % released, returned, investigating, median time to resolve |
| E7 Edge footprint | Model size, memory, CPU time on a low-end phone or emulator | KB, MB, ms |
| E8 Audit | Append latency, verify\_chain time for 1M rows, retrieval time vs plain DB | ms, seconds |
| E9 Security tests | Tampered bundle, rollback, replay, probing (rate limit) | Pass/fail table |

```text
In ml/eval/run_all.py implement the experiments above on the TEST split (chronological),
writing results to ml/artifacts/results/*.json and figures to ml/artifacts/figures/*.png
(matplotlib, no seaborn): precision-recall curves for all models on one plot, a latency
box plot for edge-only/cloud-only/hybrid, a bar chart of FPR by region and merchant age,
and a reliability curve. Latency experiments must call the real gateway over HTTP using
locust or a simple asyncio client with 1,000 requests, reporting p50/p95/p99 and the
percentage under 200 ms. Include 95% bootstrap confidence intervals (1,000 resamples)
for PR-AUC and recall@FPR. Output a results.md with all tables in markdown.
```

### 15.2 Shadow Mode (Realistic Deployment Test)

Replay the test split through the gateway in timestamp order with `SHADOW_MODE=true`. The system scores and logs but never holds funds. Compare would-have-held transactions to actual labels. This is the standard first step before any real-world pilot.

### 15.3 Honest-Reporting Checklist

- Report that synthetic data results may not transfer to real traffic (your paper already says this).
- If the Transformer does not beat XGBoost, say so; the hybrid's value then is latency and offline operation.
- Report CIs, not single numbers. State seeds used.
- Do not tune anything on the test split.

---

## 16. Security and Threat-Model Tests (Paper IV-A)

| Threat | Defense to implement | Test |
| --- | --- | --- |
| Model probing | Rate limit, only action returned, Transformer server-side | Fire 1,000 requests; confirm 429s and no scores in responses |
| Fake updates / rollback | Ed25519 signed, versioned bundles | Tamper and downgrade tests (Phase 7/8) |
| Tampered device | Play Integrity attestation (stub in prototype) | Request without token rejected when flag on |
| False-report attacks | Corroboration (3 reporters or reliable reporter), reporter reliability, daily cap | Phase 4 tests |
| Fake-account trust farming | Rate-limited trust gain: cap score decrease per day (for example max 0.05/day) | Unit test |
| Replay of scoring requests | Payment UUID uniqueness plus timestamp window of 2 minutes | Replay returns 409 |
| Audit tampering | Hash chain, verify\_chain | Phase 7 tests |
| Data exposure | AES-GCM at rest, pseudonymised ids, secrets in env only, TLS | Secret scan (gitleaks) in CI |

Also run: `pip-audit` for dependency vulnerabilities, `bandit -r services` for Python security issues, and `gitleaks detect` for committed secrets.

---

## 17. Deployment (Demo Level)

1. **Local demo:** `docker compose up` runs Postgres, Redis, gateway and scheduler. Load the trained artifacts from a mounted `ml/artifacts` volume.
2. **Cloud demo:** deploy the gateway container to Render, Railway or Fly.io; use managed Postgres and Redis. Put it behind HTTPS. Set environment variables from the platform secrets panel.
3. **Mobile:** build an APK with `flutter build apk --release` and point `api_client.dart` at the deployed URL via a build-time `--dart-define=API_URL=...`.
4. **CI:** a GitHub Actions workflow that runs `pytest`, `bandit`, `pip-audit`, `flutter test`, on every push.
5. **Docs:** keep `README.md` with a one-command quickstart, an architecture diagram, and API docs from `/docs`.

---

## 18. 16-Week Plan for a Four-Person Team

| Weeks | Person A (ML) | Person B (Backend) | Person C (Mobile) | Person D (Security/Eval) |
| --- | --- | --- | --- | --- |
| 1-2 | Synthetic data generator, baselines | Repo, Docker, DB schema | Flutter skeleton, screens | Threat model, test plan |
| 3-5 | Features, edge XGBoost, export | Gateway skeleton, Redis | Local history + features in Dart | Pseudonymisation, key mgmt |
| 5-8 | Transformer, calibration, thresholds | Scam Score service, decision engine | Dart tree walker + golden tests | Audit hash chain |
| 8-11 | Explainability (SHAP), fairness slices | Escrow ledger + scheduler | Send flow, offline mode, step-up | Signed bundles (Py + Dart) |
| 11-13 | Retraining pipeline | Rate limits, appeals, reports | Update manager, held-payment UI | Security test suite |
| 13-16 | Experiments E1-E5 | Latency tests E2, E6, E8 | Edge footprint E7, demo build | E9, report writing, shadow mode |

If you are solo or in a pair, drop in this order: Transformer (keep XGBoost cloud model), IPFS anchoring, Play Integrity, then iOS.

---

## 19. Troubleshooting Vibe-Coding Failures

| Symptom | Likely cause | Fix prompt |
| --- | --- | --- |
| Model scores 99%+ PR-AUC | Feature leakage or random split | "Audit build\_features for any use of the current or future rows; add the leakage test and re-run." |
| Dart and Python predictions differ | Threshold comparison direction or missing-value handling | "Print the first 5 trees and one traversal path in both languages for the same input and align them." |
| Balance goes negative or money duplicated | Missing row locks or no idempotency | "Wrap in a transaction with SELECT FOR UPDATE and add an idempotency key per operation; add the concurrency test." |
| Gateway slower than 200 ms | Model loaded per request, sync I/O | "Load ONNX session and explainer once at startup; make Redis calls async; profile with py-spy." |
| Tool rewrites working files | Prompts too broad | "Only modify files X and Y. Do not touch other files. Show a diff before applying." |
| Tool invents library APIs | Outdated knowledge | "Use only the versions in requirements.txt; check docs for the installed version before using an API." |
| Tests pass but app is wrong | Tests too shallow | "List the acceptance criteria from the guide and add a test for each." |
| Context lost between sessions | No shared memory | Paste docs/PROJECT\_CONTEXT.md first, then say which phase you are on. |

---

## 20. One-Shot Kickoff Prompt (For Agentic Tools)

If your tool is an autonomous agent (Claude Code, Cursor Agent, Replit Agent), start with this, then feed it one phase at a time:

```text
You are building ShieldPay, a risk-aware simulated payment system described in
docs/PROJECT_CONTEXT.md. Work strictly in phases. Do not start a phase until I say
"Start Phase N". For each phase: (1) restate the acceptance tests, (2) write tests
first, (3) implement, (4) run the tests and fix failures, (5) summarise what changed
and any assumptions, (6) stop and wait. Never use real payment APIs or real personal
data. Never commit secrets. Prefer small, readable functions with type hints. If a
requirement is ambiguous, state your assumption and continue; do not ask more than
one question at a time.
```

---

## 21. Final Completion Checklist

- [ ] Synthetic data generator and leakage-tested feature pipeline
- [ ] Baselines, edge XGBoost (JSON export matches), Transformer (ONNX matches)
- [ ] Calibration and cost-based thresholds on the validation split
- [ ] Scam Score service (Eq. 1) with regional prior, decay and corroborated reports
- [ ] Decision engine (Eq. 2) with online/offline modes and reason codes
- [ ] Gateway API with rate limits, timeout fallback and no raw scores in responses
- [ ] Double-entry ledger and escrow state machine, with double-spend and idempotency tests
- [ ] Audit hash chain with erasure support
- [ ] Signed, versioned, rollback-protected bundles verified on the phone
- [ ] Flutter app working offline with golden-test parity
- [ ] Retraining pipeline with delayed-label handling and promotion gate
- [ ] Evaluation experiments E1-E9 with confidence intervals and fairness slices
- [ ] Security test suite, dependency and secret scans, CI pipeline
- [ ] README, API docs, architecture diagram, and shadow-mode demo

**Before any real-money pilot:** get legal review of RBI and NPCI rules on holding funds, DPDP Act obligations and data localisation, and integrate through a licensed bank or PSP partner.
