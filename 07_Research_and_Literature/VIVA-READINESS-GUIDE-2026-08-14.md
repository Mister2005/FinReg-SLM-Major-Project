# FinReg-SLM — Viva/Demo Readiness Guide

**Date:** 2026-08-14
**Companion to:** `PROJECT-STATUS-REVIEW-2026-08-14.md` (the audit this guide acts on)
**Scope:** Make the project defensible for a B.Tech viva/demo — real, computed evaluation numbers and an honest, working end-to-end system. This is explicitly **not** a production-deployment guide (no hosting, CI/CD, auth, monitoring, scaling — see §5).

---

## 0. One-line summary of where you stand

The corpus, retrieval stack, RAFT training run, and Phase 4 engine are all real and wired together end-to-end. The problem is entirely in the numbers used to justify the project's two central claims — several are hardcoded placeholders or synthetic template responses that were never replaced with real computation. Fix the numbers, not the architecture.

## 0.1 One thing to check before anything else

The status review found `GROQ_API_KEY=` empty in `.env`, which is why it concluded no real frontier-model or judge calls were possible. **That's no longer true** — `.env` currently has a populated `GROQ_API_KEY` (56 chars) and four `GEMINI_API_KEY*` values. This changes the cost/benefit of Fix 3 below (real generations become possible, not just aspirational), so verify the key actually works first:

```python
import os, groq
from dotenv import load_dotenv
load_dotenv()
client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":"say ok"}], max_tokens=5)
print(r.choices[0].message.content)
```

If this returns a real response, Fix 3 Path A (below) is back on the table. If it errors (rate-limited, revoked, wrong model name), fall back to Fix 3 Path B.

---

## 1. Fix list, in priority order

### Fix 1 — Make the Phase 3 decision gates real (highest leverage)

**Problem:** `Phase 3/src/finreg3/cli.py:203-211` passes literal hardcoded floats into `evaluate_gates()`:
```python
summary = evaluator.evaluate_gates(
    a2_citation_precision=0.72, a6_citation_precision=0.88,
    a2_temporal_accuracy=0.75, a6_temporal_accuracy=0.86,
    a2_judge_score=0.75, a6_judge_score=0.82,
    forgetting_loss_pts=0.8,
)
```
`Phase 3/src/finreg3/eval/gate_phase3.py`'s `evaluate_gates()` itself is fine — it's a pure function that computes deltas and pass/fail correctly from whatever it's given. The bug is entirely that nothing computes the real numbers to feed it. Arm A6 already ran for real (`Phase 3/runs/raft-qwen2.5-7b/run_A6.json`, 300 real generations from the real merged model, with per-record `citation_precision`, `correct_temporal_version`, `abstention_classification` already computed by `runner_a6.py`). **There is no equivalent real run for Arm A2** — `Phase 2/src/finreg/eval/runner.py:78-87` hardcodes A2's response as an f-string template, so there's nothing genuine to diff A6 against.

**Fix, in order:**
1. Do **Fix 2** first (citation-precision bug) — the aggregator you write here will call that function, so fix it before trusting its output.
2. Create a real Arm A2 run. The cleanest path: generalize `Phase 3/src/finreg3/eval/runner_a6.py`'s `ArmA6Runner` to accept an arbitrary `model_dir` instead of being hardcoded to the merged RAFT model — point it at the **base** model, `unsloth/qwen2.5-1.5b-instruct-unsloth-bnb-4bit` (the same architecture pre-RAFT-tuning), using the same 4-bit NF4 loading path already written at `runner_a6.py:52-72`. Run it against the same 300-Q bench-v1 with the same retrieval index (`limit=500`, temporal filter on) and write `run_A2.json` next to `run_A6.json`.
3. Write an aggregator function (new file, e.g. `Phase 3/src/finreg3/eval/aggregate.py`) that reads a `run_*.json` and returns: mean citation precision (per the fixed Fix-2 semantics), % correct on the C3 temporal subset, the abstention confusion matrix counts, and mean judge score if you have one (see Fix 3).
4. Replace `cli.py:203-211`'s literal floats with calls to `aggregate(run_dir / "run_A2.json")` and `aggregate(run_dir / "run_A6.json")`.
5. Re-run `finreg3 eval gate` and let `reports/phase3-decision.md` regenerate with whatever the real deltas turn out to be — **accept a "no gain" or "partial gain" result if that's what the data shows.** A defensible negative result survives a viva; a fabricated +16pp win that a panelist can falsify by reading `run_A6.json` does not.

**Verify:** hand-check 5–10 records — read the raw generation, count citations yourself, compare to what the aggregator reports for that qid. `phase3-decision.md`'s numbers should match your manual spot-check.

---

### Fix 2 — Citation-precision zero-citation bug

**Problem:** `Phase 3/src/finreg3/eval/citation_precision.py:70`:
```python
precision = valid_count / max(total, 1) if total > 0 else 1.0
```
A response with **zero** citations scores a perfect `1.0`. Per the status review, 58.7% of the 300 real A6 responses contain no citations at all — those all get scored as flawless, which is how an aggregate of 80% got reported when the real precision among the 124 responses that actually cited something was 51.6%.

**Fix:** change the `else` branch. Two reasonable options:
- Minimal: `precision = valid_count / total if total > 0 else 0.0` — a no-citation response scores 0.
- More informative for a viva: keep 0-citation responses **out of** the precision average entirely, and report a separate "citation coverage" stat (fraction of responses that cited anything). This distinguishes "cited the wrong thing" from "didn't cite at all," which are different failure modes worth naming separately when you present this.

Either is a small, contained change — but it changes what every downstream number in Fix 1's aggregator means, so land it first.

**Verify:** recompute aggregate precision on the existing `run_A6.json` after the fix. It should land near the review's manually-derived 51.6% (computed over cited responses), not 80%.

---

### Fix 3 — Phase 2 real generations + real judge, or explicit reframe

**Problem:** `Phase 2/src/finreg/eval/runner.py:78-87` hardcodes A2/A4's response as an f-string (`"As of {as_of}, compliance requirement applies under [...]"`), so A2 and A4 are guaranteed to score identically by construction — the reported "no detected difference" wasn't discovered, it was baked in. `Phase 2/src/finreg/eval/judge.py:33` falls back to a keyword-overlap heuristic when no Groq key is present; per §0.1, that key situation may have changed — verify before assuming this is still blocked.

**Two paths, pick based on remaining time before the viva:**

- **Path A (do it for real).** Now that a Groq key is present and verified working (§0.1), wire A0–A5 to real model calls: A0/A5 already have Groq-call code in `runner.py:63-77`, it just needs the verified key; A2/A4 need the same local-inference treatment as Fix 1's real A2 run (reuse the generalized runner). Let `judge.py`'s real Groq path run instead of the heuristic fallback. Before trusting judge scores, re-validate `validate_against_human_labels()` — this needs a `sample_100_evals` set of human-scored answers; check whether that data already exists anywhere in `Phase 2/data/`, and if not, budget time to hand-label ~100 (or a smaller pilot, e.g. 30, and note the smaller validation sample honestly).
- **Path B (reframe, much faster).** Explicitly relabel Phase 2 in the final report as "harness/infrastructure validation," not an empirical result, and drop the "no detected difference" (G1) claim — say instead that G1 was not empirically tested because A2/A4 generation was not wired to a real model in this phase.

Given the priority order in §2, recommend attempting Path A only after Fix 1 and Fix 2 are done (they reuse the same real-inference machinery you'll build for the real A2 run). If time runs out, Path B is a legitimate, honest fallback — better than presenting synthetic numbers as empirical.

**Verify:** either `run_A0.json` through `run_A5.json` show genuine per-arm variation in the raw generations (not `A2 == A4` by construction), or the final report's Phase 2 section explicitly says "infrastructure validation, not an empirical comparison."

---

### Fix 4 — Forgetting harness: real or dropped

**Problem:** `Phase 2/src/finreg/train/forgetting.py:16-31` returns literal hardcoded dicts, one of them behind a comment reading `# Simulated fine-tuned checkpoint measurement`. Gate G2's "0.6-point loss, Acceptable" is not a measurement of anything.

**Fix — pick one:**
- **(a) Real, small-scale.** Run a modest subset (50–100 questions each) of MMLU and ARC-C against both the base 1.5B model and the merged RAFT model — a full `lm-eval-harness` run isn't necessary for a viva-level directional claim, a lightweight custom script scoring multiple-choice accuracy is enough. Replace the hardcoded dict with the real computed scores.
- **(b) Drop it.** Remove the G2/G7 forgetting-cost claims from the final report and state plainly that capability forgetting was out of scope for this phase, given the 8GB VRAM / time budget. This is a legitimate scope limitation, not a weakness, as long as it's stated rather than papered over.

Given the RTX 5060 8GB target and likely limited time before the viva, (b) may be the more realistic choice; (a) is stronger if you have a spare afternoon.

**Verify:** no code path that feeds a claimed report number still contains the word "Simulated" or a hardcoded constant.

---

### Fix 5 — Metadata reconciliation (7B → 1.5B, regulator scope)

**Confirmed still present in the current repo:**
- `Phase 3/runs/raft-qwen2.5-7b/raft_train_manifest.json:6` — `"model_id": "Qwen/Qwen2.5-7B-Instruct"` — wrong; the actually-trained and merged model is `unsloth/qwen2.5-1.5b-instruct-unsloth-bnb-4bit` (confirmed via the merged model's own `config.json` architecture dims).
- `Phase 4/reports/final-project-report.md:9` (abstract) claims coverage across "RBI, SEBI, and IRDAI" — but `Phase 2/data/index/dense_chunks.json` and `freeze_manifest.json` show every indexed chunk from Phase 2 onward is RBI-only. Line 12 of the same report does correctly say "1.5B model," so the two claims within the report currently contradict each other.

**Fix:**
1. Update `raft_train_manifest.json`'s `model_id` field to the real base model id. This is a metadata correction only — no re-run needed, the weights on disk are already the real 1.5B ones.
2. Correct `final-project-report.md`'s abstract to say RBI-only (matching what §4.6 of the status review confirms is actually indexed), unless you deliberately re-index a multi-regulator slice before the viva by pointing `build_index_from_db()` at a larger/unfiltered document set — a bigger lift, only worth it if you have time and want the broader scope claim to be true rather than corrected.
3. Optional: rename the `raft-qwen2.5-7b` directory to `raft-qwen2.5-1.5b` for consistency. This touches `DEFAULT_RUNS_DIR` in `cli.py` and any report text referencing the path (e.g. `final-project-report.md:54`). Skip if time-constrained — a metadata-field fix plus a footnote ("directory name is historical") is sufficient for a viva.

**Verify:** grep the whole repo for `7B`, `7b`, and `IRDAI` — zero remaining stale claims outside of explanatory footnotes.

---

## 2. Order of operations

Given the dependencies above, do them in this order:

1. **Fix 2** (citation-precision bug) — ~5 minutes, no dependencies, everything else's numbers depend on this being correct.
2. **Fix 5** (metadata reconciliation) — cheap, independent, do whenever there's a spare 20 minutes.
3. **Fix 1** (real A2 run + real gate aggregation) — the big one; needs Fix 2 done first. This is the single highest-leverage item — it's what turns the Phase 3 decision record from asserted to computed.
4. **Fix 4** (forgetting harness) — independent, can run in parallel with Fix 1's GPU time if you have the VRAM headroom, otherwise sequence after.
5. **Fix 3** (Phase 2 real generations/judge, or reframe) — most expensive if doing Path A; decide early based on remaining time, since it reuses machinery built in Fix 1.

---

## 3. Pre-viva verification checklist

- [ ] `pytest` across Phase 1–4 all green (the 2 known OCR failures are environment-only — missing Tesseract binary — either install it or be ready to explain that in one sentence)
- [ ] `finreg3 eval gate` regenerates `phase3-decision.md` from a real aggregator reading `run_A2.json`/`run_A6.json` — no literal floats remain in `cli.py`
- [ ] Manually spot-checked 5–10 records against the aggregator's reported numbers
- [ ] `final-project-report.md`'s abstract, model-identity, and regulator-scope claims match what's actually in the repo (re-grep after Fix 5)
- [ ] Phase 4 FastAPI demo run live end-to-end with a couple of fresh queries during rehearsal — not just relying on the one passing integration test
- [ ] You can state clearly, for every headline number in the report, whether it's a real measurement or an explicitly scoped-out limitation — a labeled limitation is stronger in a viva than an unlabeled fabricated number

---

## 4. Explicitly out of scope

Per the viva/demo target (not production deployment): no cloud hosting, no CI/CD pipeline, no containerization, no monitoring/observability, no auth/rate-limiting, no horizontal scaling. None of that is needed to defend this project — skip it and spend the time on §1 instead.
