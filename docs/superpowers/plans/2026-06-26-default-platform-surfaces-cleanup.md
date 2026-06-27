# Default Platform Surfaces Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Polymarket/trading-specific language from platform-default agent-facing docs and prompts so the default `littleman.platform` application reads like a general autonomous assistant.

**Architecture:** Keep domain-specific concepts in the Polymarket application (`docs/applications/polymarket.md`, `littleman/applications/polymarket/`) and in the optional trading skill docs. The platform-provided docs and chat prompts should be application-neutral.

**Tech Stack:** Markdown docs, Python prompt strings in `littleman/llm/prompts.py`, pytest.

## Global Constraints

- Polymarket trading must still work when `active_application = "Polymarket trading"`.
- Do not change the JSON schemas or function signatures used by the Polymarket app unless necessary.
- Every prompt/doc change must be accompanied by a test that fails before the change and passes after.
- Run the full test suite and frontend build after each task.

---

## File map

| File | Responsibility |
|------|----------------|
| `workspace/skills/probability.md` | Doc for `estimate_probability`. Must become a generic calibrated-probability guide. |
| `workspace/construct/EXPOSURE.template.md` | Template for the risk-map construct doc. Must be generic. |
| `littleman/llm/prompts.py` | Prompt templates. Clean trading-only examples from chat and maintenance prompts. |
| `tests/test_prompts.py` (new) | Assert that platform chat/maintenance prompts do not contain trading-specific assumptions. |

---

## Task 1: Make `probability.md` application-neutral

**Files:**
- Modify: `workspace/skills/probability.md`
- Test: `tests/test_skill_docs.py`

**Interfaces:**
- Consumes: registered skill name `estimate_probability`.
- Produces: doc text that explains probability estimation for any binary question.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_skill_docs.py`:

```python
def test_probability_doc_is_domain_agnostic():
    from littleman.config import settings

    text = (settings.workspace_dir / "skills" / "probability.md").read_text(encoding="utf-8")
    assert "Polymarket" not in text
    assert "bet" not in text.lower()
    assert "market price" not in text.lower() or "external reference price" in text.lower()
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py::test_probability_doc_is_domain_agnostic -v`
Expected: FAIL.

- [ ] **Step 3: Rewrite `probability.md` generically**

Replace the file with:

```markdown
# probability — Calibrated Probability Estimation

## Purpose
Produce a calibrated numeric probability for a binary question using the
`estimate_probability` skill. Use it whenever you need to act under uncertainty.

## The anti-anchoring discipline
**Form your own estimate from evidence BEFORE looking at any external reference price or consensus.**
The skill asks for `evidence_summary` first, then lets you note an external reference (if any) for
comparison. Do not let that reference leak into your evidence.

## Key parameters
- `market_id` (str, required): a stable identifier for the question or market you are estimating
- `evidence_summary` (str, required): your synthesized evidence, NOT including an external reference price
- `market_title` (str): human-readable question name
- `resolution_criteria` (str): exact wording of what makes the question resolve YES
- `market_price` (float, optional): an external reference probability or price (0–1) — provided AFTER evidence
- `comparable_base_rates` (str, optional): similar historical events and their frequencies

## Return shape
```json
{
  "estimated_probability": 0.71,
  "confidence": "MEDIUM",
  "key_uncertainties": ["Fed statement timing", "CPI print"],
  "reasoning": "...",
  "edge": 0.09,
  "market_id": "..."
}
```

## Edge threshold (when a reference price exists)
- `edge` = estimated_probability − reference_price
- Only act if |edge| ≥ config.min_edge_pct (default 3%) AND confidence ≥ MEDIUM
- LOW confidence → PASS regardless of edge (the estimate is unreliable)

## Building a good evidence_summary
Good: "Three recent polls show candidate X at 54-58% in PA. Historical base rate for
      incumbents with this polling lead at this stage: 71%. No major scandals in past 30d."
Bad:  "The consensus is at 0.62 which seems low given recent news."

## Confidence calibration
- HIGH: Strong recent data, clear resolution criteria, well-understood domain
- MEDIUM: Some uncertainty, ambiguous signals, or limited evidence
- LOW: Speculative, breaking news, high domain uncertainty → do not act

## Common mistakes
- Letting an external reference pollute your evidence_summary (anchoring)
- Using LOW-confidence estimates to justify action
- Ignoring resolution_criteria wording — "before Dec 31" ≠ "by end of year"
- Not including base rates when they exist (neglects reference class)
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py::test_probability_doc_is_domain_agnostic -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workspace/skills/probability.md tests/test_skill_docs.py
git commit -m "docs: make probability skill doc application-neutral"
```

---

## Task 2: Make the EXPOSURE template application-neutral

**Files:**
- Modify: `workspace/construct/EXPOSURE.template.md`

- [ ] **Step 1: Rewrite the template**

```markdown
# EXPOSURE.md — risk map

_Rendered from the world model each wake. Read-only; do not edit — your changes are overwritten._

No exposure data yet. If the active application tracks risk (balances, open positions, exposure by
category, drawdown, circuit-breaker status), this document is populated automatically from your
world model at the end of each wake. Read it during the directive/strategy step to size new risk
against what you already hold.
```

- [ ] **Step 2: Add a regression test**

Add to `tests/test_skill_docs.py`:

```python
def test_exposure_template_is_domain_agnostic():
    from littleman.config import settings

    text = (settings.workspace_dir / "construct" / "EXPOSURE.template.md").read_text(encoding="utf-8")
    assert "Polymarket" not in text
```

- [ ] **Step 3: Run the test and confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py::test_exposure_template_is_domain_agnostic -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add workspace/construct/EXPOSURE.template.md tests/test_skill_docs.py
git commit -m "docs: make EXPOSURE template application-neutral"
```

---

## Task 3: Clean platform chat and maintenance prompts

**Files:**
- Modify: `littleman/llm/prompts.py`
- Create: `tests/test_prompts.py`

**Interfaces:**
- Consumes: prompt strings used by chat suggestions, calendar maintenance, self maintenance.
- Produces: prompt strings with no hard-coded trading identity.

- [ ] **Step 1: Write the failing test**

Create `tests/test_prompts.py`:

```python
from littleman.llm import prompts


def test_chat_suggestions_do_not_assume_trading():
    assert "prediction-market trading agent" not in prompts.CHAT_SUGGESTIONS_SYSTEM


def test_calendar_maintenance_is_domain_agnostic():
    assert "open positions" not in prompts.CALENDAR_MAINTAIN_SYSTEM.lower()
    assert "watched market" not in prompts.CALENDAR_MAINTAIN_SYSTEM.lower()


def test_self_maintenance_is_domain_agnostic():
    assert "market," not in prompts.SELF_MAINTAIN_SYSTEM.lower()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_prompts.py -v`
Expected: FAIL.

- [ ] **Step 3: Update the prompt strings**

In `littleman/llm/prompts.py`:

1. `CALENDAR_MAINTAIN_SYSTEM` line 80:
   Replace:
   ```
   - Keep open positions and watched market closes current and accurate.
   ```
   with:
   ```
   - Keep time-bound commitments, deadlines, and tracked events current and accurate.
   ```

2. `SELF_MAINTAIN_SYSTEM` line 97:
   Replace:
   ```
   Be specific: cite the market, outcome, or failure that produced the learning, with the date.
   ```
   with:
   ```
   Be specific: cite the outcome or failure that produced the learning, with the date.
   ```

3. `CHAT_SUGGESTIONS_SYSTEM` line 459:
   Replace:
   ```
   Make them specific to the conversation and to littleman (a prediction-market trading agent), not generic.
   ```
   with:
   ```
   Make them specific to the conversation and to littleman (an autonomous assistant), not generic.
   ```

4. `HYPOTHESES_MAINTAIN_SYSTEM` line 304 example:
   Replace:
   ```
   - 2026-07-01T14:00:00Z | 0.75 | BTC closes above $80k today | Coinbase 24h close > $80,000
   ```
   with:
   ```
   - 2026-07-01T14:00:00Z | 0.75 | the release ships on time | CI passes and tag is pushed
   ```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add littleman/llm/prompts.py tests/test_prompts.py
git commit -m "refactor: remove trading-only language from platform prompts"
```

---

## Task 4: Full verification

- [ ] **Run the full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q`
Expected: all tests pass.

- [ ] **Run the frontend build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

---

## Spec coverage self-check

| Requirement | Task |
|---|---|
| `probability.md` does not assume Polymarket/betting | Task 1 |
| `EXPOSURE.template.md` does not assume a trading app | Task 2 |
| Chat suggestions do not frame agent as a trading bot | Task 3 |
| Maintenance prompts do not mention open positions/markets | Task 3 |
| Regression tests prevent re-drifting | Tasks 1–3 |

No placeholders remain in the plan; every step names an exact file and command.
