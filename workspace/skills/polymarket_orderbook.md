# polymarket_orderbook — CLOB Orderbook Reader

## Purpose
Read the live Central Limit Order Book for a Polymarket market to understand
current liquidity, bid/ask spread, and real executable prices.

## When to use
- After identifying a market via polymarket_scan that looks promising
- Before sizing a position — the orderbook tells you real fill cost, not mid-price
- When checking if a position is large enough to move the market (slippage risk)

## Key parameters
- `market_id` (str): the Polymarket market ID (from scan results)
- `side` (str, optional): "YES" | "NO" | "BOTH" — defaults to BOTH
- `depth` (int, optional): number of levels to return, default 5

## Return shape
```json
{
  "bids": [{"price": 0.61, "size": 450.0}, ...],
  "asks": [{"price": 0.63, "size": 220.0}, ...],
  "mid": 0.62,
  "spread": 0.02,
  "best_bid": 0.61,
  "best_ask": 0.63
}
```

## Interpreting the orderbook
- `mid` = (best_bid + best_ask) / 2 — the fair value implied by market makers
- `spread` < 0.02 = liquid; > 0.05 = illiquid, widen your edge threshold
- Check `size` at best levels — if total depth < your bet size, expect worse fill
- Slippage estimate: walk the book to see average fill price for your intended size

## Common mistakes
- Using `yes_price` from scan as your fill price — always check the ask level for buys
- Ignoring spread: a 3¢ spread needs 3¢+ edge just to break even
- Not accounting for slippage when sizing positions above $50
- Betting into a market where the top-of-book size is smaller than your bet
