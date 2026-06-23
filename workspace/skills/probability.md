# probability — Calibrated Probability Estimation

## Purpose
Produce a calibrated numeric probability for a binary market resolution using
the `estimate_probability` skill. This is the analytical core of every bet decision.

## The anti-anchoring discipline
**Form your own estimate from evidence BEFORE looking at market price.**
The skill enforces this by asking for evidence_summary first, then noting the market price
at the end for edge calculation. Do not mention the market price in your evidence summary.

## Key parameters
- `market_id` (str, required): the Polymarket market ID
- `evidence_summary` (str, required): your synthesized evidence, NOT including market price
- `market_title` (str): human-readable market name
- `resolution_criteria` (str): exact wording of what makes it resolve YES
- `market_price` (float): current YES price (0–1) — provided AFTER evidence
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

## Edge threshold
- `edge` = estimated_probability − market_price
- Only bet if |edge| ≥ config.min_edge_pct (default 3%) AND confidence ≥ MEDIUM
- LOW confidence → PASS regardless of edge (the estimate is unreliable)

## Building a good evidence_summary
Good: "Three recent polls show candidate X at 54-58% in PA. Historical base rate for
      incumbents with this polling lead at this stage: 71%. No major scandals in past 30d."
Bad:  "Market is at 0.62 which seems low given recent news."

## Confidence calibration
- HIGH: Strong recent data, clear resolution criteria, well-understood domain
- MEDIUM: Some uncertainty, ambiguous signals, or limited evidence
- LOW: Speculative, breaking news, high domain uncertainty → skip the bet

## Common mistakes
- Letting the market price pollute your evidence_summary (anchoring)
- Using LOW-confidence estimates to justify bets
- Ignoring resolution_criteria wording — "before Dec 31" ≠ "by end of year"
- Not including base rates when they exist (neglects reference class)
