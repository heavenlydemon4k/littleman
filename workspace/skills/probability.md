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
