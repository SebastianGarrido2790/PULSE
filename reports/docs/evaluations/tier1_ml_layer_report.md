# The Tier 1 ML Layer: How It Works

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)
**Component:** Phase 3 — Tier 1 ML Layer
**Status:** Complete, validated (ADR-005 Amendment 2)

---

## 1. What Tier 1 Actually Does

Every downstream computation in PULSE — leverage, escalation, tactical output — ultimately depends on one number: `p`, the probability a server wins the next point. The Markov solver turns `p` into leverage through exact, closed-form probability theory. It cannot invent `p` itself; something has to estimate it from history first.

That's the entire job of Tier 1. It does not compute leverage, does not decide anything, and does not touch the solver's math. It supplies one honest input and one honest diagnostic:

1. **A point-win probability estimate**, with a transparent account of how much data backs it.
2. **A pressure-adjusted deviation estimate**, describing whether a specific player performs differently than usual when a point matters more.

Both outputs carry their own confidence pedigree rather than presenting a single confident-looking number — consistent with the project's Sufficiency Gate: PULSE does not emit a signal it cannot statistically support.

---

## 2. Component 1: The Point-Win Classifier

### What it is — and isn't

Despite the name, this is not a trained machine-learning classifier in the usual sense. It's a **Hierarchical Empirical Stratum Estimator** — a structured lookup table of historical serve-win rates, aggregated at four levels of specificity.

This was a deliberate design choice (ADR-005 Amendment 1), not a simplification. A parametric model like logistic regression, given enough player-specific detail to be useful, converges toward something very close to this table anyway — the direct approach is more transparent about exactly how much data supports each estimate, and resolves in constant time, comfortably inside the sub-second latency budget for live monitoring.

### How it resolves a probability

Given a point about to be served — this player, on this surface, first or second serve — the estimator looks for the most specific historical data available, and only falls back to something coarser when the specific data is too thin to trust:

| Tier                       | Looks up                                                             | Falls back when                                                    |
| -------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **0 — Exact Stratum**      | This exact player, on this exact surface, on this exact serve number | Fewer than 10 historical points in that combination                |
| **1 — Player Overall**     | This player's rate across all surfaces and both serve numbers        | Fewer than 20 historical points for the player overall             |
| **2 — Surface Population** | The average rate for _all_ players on this surface and serve number  | Fewer than 50 historical points for that surface/serve combination |
| **3 — Global Default**     | A fixed population-average serve-win rate (0.62)                     | Always available — the floor that can never fail                   |

Every prediction reports which tier it resolved at. This matters operationally: a probability backed by thousands of points on Tier 0 deserves more trust than one that had to fall back to Tier 2, and everything downstream can see the difference rather than treating both as equally certain.

### Output

For any `(player, surface, serve number)` query: a probability `p_hat`, the observation count `N` behind it, and the `fallback_tier` it resolved at.

---

## 3. Component 2: The Pressure Deviation Model

### What it measures

Some players may perform differently under high-stakes points than their overall average suggests — better, worse, or no differently at all. The Pressure Deviation Model is built to detect a _real_ effect while actively resisting the temptation to call ordinary variance a "clutch gene" or a "choke" when a player simply hasn't played enough high-pressure points yet to know.

Every point is bucketed by its computed leverage — how much that single point matters to the match outcome — into one of three bands:

| Bucket       | Leverage Range | Meaning                                       |
| ------------ | -------------- | --------------------------------------------- |
| **Routine**  | `[0.00, 0.10)` | Below the escalation threshold; ordinary play |
| **Elevated** | `[0.10, 0.25)` | Meaningfully consequential points             |
| **Critical** | `[0.25, 1.00]` | Decisive, high-stakes points                  |

### How the shrinkage works

For a player with only a handful of high-leverage points on record, their raw win rate in that bucket is statistically unreliable — a player who happens to have won 3 of 4 critical points so far doesn't necessarily have a 75% critical-point win rate. The model handles this with **Empirical-Bayes shrinkage**: each player's estimate is pulled toward a population-typical rate for that leverage bucket, with the strength of the pull determined by how much data that specific player actually has. A player with hundreds of high-leverage points barely moves from their raw rate; a player with three barely moves from the population baseline.

The population baseline itself — the "prior" — isn't guessed. It's fit directly from the data (Method of Moments) separately for each of the three buckets, using every player with enough of their own data to contribute reliably. If a bucket doesn't have enough players to fit a trustworthy prior, the model falls back to a fixed, weak default prior rather than fitting something unstable — the same sufficiency-gate philosophy applied one layer up.

### Output

For each player, in each leverage bucket: a shrunk performance estimate, the deviation from that player's own baseline rate, a 90% credible interval around that deviation, and an `is_prior_estimated` flag showing whether the bucket's prior came from real data or the safe fallback.

---

## 4. Validation Results

### Point-Win Classifier

![Point-Win Classifier Calibration Curve](../../../artifacts/models/point_win_classifier/calibration_curve.png)

The left panel (uniform, equal-_width_ bins) looks distorted at low predicted probabilities — but that's an artifact of bin construction, not a modeling problem: predicted probabilities below ~0.45 are rare, so a handful of thin, noisy strata get stretched across a wide bin. The right panel (quantile, equal-_population_ bins — ~11,000 points each) shows the honest picture: the model tracks the diagonal closely across the full range.

| Metric                               | Result         | Target | Status                           |
| ------------------------------------ | -------------- | ------ | -------------------------------- |
| **Mean Absolute Calibration Error**  | 0.65%          | ≤ 1.5% | ✅ Primary exit gate             |
| **Holdout ROC-AUC**                  | 0.6339         | ≥ 0.55 | ✅ Non-blocking sanity trip-wire |
| **Tier 0 resolution rate (holdout)** | 99.97%         | —      | High-confidence coverage         |
| **Holdout sample size**              | 109,496 points | —      | 20% of 547,478 total             |

**Why calibration, not AUC, is the pass/fail gate:** the Markov solver amplifies small probability errors through a nested, win-by-two structure — calibration accuracy is what keeps the solver's leverage output trustworthy, not how well the model ranks players against each other. AUC is retained only as a sanity check: if it ever collapsed toward 0.50, that would signal something structurally broken (a data join failure, for instance), independent of calibration quality. 0.6339 is not a weak result read in isolation — because the estimator is already the fully saturated model for its three input features and is very well calibrated, this number is close to the actual ceiling achievable on this feature set, not a shortfall to be optimized away.

### Pressure Deviation Model

| Bucket   | Leverage Range | Prior α | Prior β | Players Contributing | Prior Source  |
| -------- | -------------- | ------- | ------- | -------------------- | ------------- |
| Routine  | [0.00, 0.10)   | 23.88   | 15.40   | 471                  | Fit from data |
| Elevated | [0.10, 0.25)   | 14.95   | 11.67   | 270                  | Fit from data |
| Critical | [0.25, 1.00]   | 14.73   | 7.15    | 130                  | Fit from data |

**Empirical credible-interval coverage:** 93.75% (375 of 400 evaluated high-leverage player-bucket combinations) against a 90% target — the 90% credible intervals are behaving as advertised on held-out data, not just in theory.

### Full Suite

41/41 tests passing · 0 ruff errors · 0 pyright errors · all modules under the 1,000-line ceiling · full pipeline reproducible via `dvc repro`.

---

## 5. Known Limitations, Stated Plainly

- **The Critical bucket is data-thin by construction** (130 players). Its prior is real but rests on the smallest sample of the three, and most players' own Critical-bucket estimates will lean heavily on that population prior rather than their individual history.
- **The feature set was deliberately narrow** (player, surface, serve number only) to avoid circularity with the solver's own score-state logic. This caps achievable AUC — a known and accepted trade-off, not an oversight.
- **Grass-court strata are the sparsest by surface** (10.2% of all points), so Tier 0 resolution for grass-specific queries is more likely to fall back to Tier 2 than hard or clay.

---

## 6. What This Enables

With Tier 1 producing calibrated, confidence-aware `p` estimates and player-specific pressure deviations, Phase 4 can build the event-driven orchestration layer on top of a foundation that already knows — and reports — exactly how much it knows.
