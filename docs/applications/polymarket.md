# Application: Polymarket Trading — Integration Plan

This is the implementation plan for live Polymarket trading, the flagship **application** that
runs on the littleman platform. Read/scan skills already work against the public Gamma/CLOB
endpoints; this plan covers the missing piece: **authenticated order signing and placement**.

## 1. How Polymarket's API is structured

Three surfaces (see [Polymarket docs](https://docs.polymarket.com/)):

| Surface | Base | Auth | Use |
|---|---|---|---|
| **Gamma** | `https://gamma-api.polymarket.com` | none | market discovery, metadata, resolution criteria |
| **CLOB** | `https://clob.polymarket.com` | L1 + L2 for writes | order book, prices, place/cancel orders, positions |
| **Data API** | `https://data-api.polymarket.com` | none | historical trades, holders |

All contracts run on **Polygon PoS (chain id 137)**; gas is ~$0.002/tx.

### Collateral is pUSD, not USDC.e (2026-04-28 exchange upgrade)

Since the April 2026 exchange upgrade, the trading collateral is **pUSD** (Polymarket USD), an
ERC-20 backed 1:1 by USDC, contract `0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB` (6 decimals).
The spendable betting balance is the wallet's **pUSD** balance — reading USDC.e gives 0 even
for a funded account. `skills/polymarket_client.py` reads pUSD. Depositing USDC wraps to pUSD
1:1 via the CollateralOnramp; unwrapping is fee-free.

Funding a wallet needs **pUSD** for orders and **POL** for gas (EOA / signature type 0 only).

Our existing `skills/polymarket.py` already uses Gamma + CLOB read endpoints (`scan_markets`,
`get_market`, `get_orderbook`, `check_resolution`) — no auth needed. Those stay.

## 2. Authentication — the part we must build

Two layers ([auth reference](https://docs.polymarket.com/api-reference/authentication)):

- **L1 (wallet)** — an EIP-712 signature with the wallet private key. Used once to *create or
  derive* API credentials. Headers: `POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`,
  `POLY_NONCE`.
- **L2 (API key)** — `apiKey` / `secret` / `passphrase` derived from L1, used for every trading
  request as HMAC-SHA256 signed headers: `POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`,
  `POLY_API_KEY`, `POLY_PASSPHRASE`.

**Critical:** even with valid L2 headers, *every order must additionally be signed* by the
wallet key. There is no "API-key-only" trading.

**Signature types** (pick by wallet):

| Type | Value | Wallet |
|---|---|---|
| EOA | 0 | raw private key (MetaMask-style) |
| POLY_PROXY | 1 | Magic/email login |
| GNOSIS_SAFE | 2 | existing Safe |
| POLY_1271 | 3 | new API users with a deposit/funder wallet |

For a fresh programmatic account, Polymarket recommends **deposit wallet + `POLY_1271` (type 3)**
with a `funder` address.

## 3. SDK choice

The quickstart targets the **v2** clients (the original `py-clob-client` is archived):

- **Python:** `pip install py-clob-client-v2`
- TypeScript: `@polymarket/clob-client-v2 viem` · Rust: `polymarket_client_sdk_v2`

Flow (from the quickstart):
```python
# 1. temp client with the signing key → derive L1→L2 creds
api_creds = temp_client.create_or_derive_api_key()
# 2. full client with signer + creds → create_order / post_order
```

**Signing wallet vs funder address:** the *signing wallet* (its private key) derives credentials
and authorises orders; the *funder address* holds the pUSD + POL. The address you configure for
reads (`POLYMARKET_WALLET_ADDRESS`) is the **funder** that holds the balance. For signing we will
additionally need the signing wallet's key and the right `signature_type`.

The SDK wraps order signing + CTF interactions, so we do not hand-roll EIP-712.

## 4. Pre-trade requirements (one-time, per wallet)

Before any order, the CLOB checks: valid EIP-712 sig, sufficient **USDC.e** balance, approved
**allowances** for the exchange contracts, and valid L2 creds. EOA wallets must approve USDC +
Conditional Tokens for three exchange contracts:

```
0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
0xC5d563A36AE78145C45a50134d48A1215220f80a
0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296
```

(Magic/email wallets handle this automatically.) We expose this as a one-time
`approve_allowances` setup step, surfaced in the UI as a connection requirement.

## 5. Order types

`GTC` (rests on book), `GTD` (time-bound), `FOK` (fill-or-kill), `FAK` (fill-and-kill). The
agent's executor will default to:
- **`FOK` market order** for "take the price now" decisions (size in USDC), and
- **`GTC` limit order** when the agent wants a specific price with `max_price`.

## 6. How this maps onto our architecture

The platform pieces already exist; we slot the live client into the **execution layer** behind
the **risk governor** (nothing changes about sizing or gating — ADR 0001 stands).

| Step | Where | Change |
|---|---|---|
| Wallet config | `config.py` | add `polymarket_signature_type`, `polymarket_funder` (have key/address) |
| Live client | new `skills/polymarket_client.py` | wrap `py-sdk`: init, derive creds, sign+post orders, cancel, positions, balances |
| `place_bet` | `tasks/executor._execute_bet` | replace the "intent recorded, NOT_EXECUTED" stub with a real `post_order` **after** the risk governor ALLOWs; persist the returned `order_id`/`tx` |
| Resolution | `skills/polymarket.check_resolution` | already reads Gamma; add CLOB `get_trades`/positions reconciliation |
| Ground-truth balance | `meta/world_model` | on session start, reconcile wallet/positions from CLOB (the chain is source of truth, not our DB — matches the meta doc) |
| Connection check | `/api/agent/status` | `polymarket_wallet.ok` already reads `POLYMARKET_WALLET_ADDRESS`; extend to verify creds derive + allowances approved |

## 7. Safety sequencing (do not skip)

1. **Read-only first** (done): scans/prices/resolution against public endpoints.
2. **Testnet / tiny size**: wire the client, derive creds, place a **single minimum-size FOK**
   order manually from the UI, confirm fill + position + balance reconcile.
3. **Risk-gated auto**: only then let `_execute_bet` post real orders, still serial and
   governor-gated, still behind the autonomous toggle (default OFF).
4. **Circuit breaker** already halts on drawdown; keep it authoritative.

## 8. Open questions

- `py-sdk` vs `py-clob-client-v2` maturity for `POLY_1271` (there are known proxy-binding
  issues in v2 — track before committing to a signature type).
- Whether to custody via a deposit wallet (type 3) or an EOA (type 0). EOA is simpler to
  reason about for a solo operator; deposit wallet is Polymarket's recommended path.
- Slippage controls on `FOK` market orders vs `GTC` limit with `max_price` — prefer limit
  orders with an explicit cap for predictable cost.
