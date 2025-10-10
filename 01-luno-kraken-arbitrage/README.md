# Luno / Kraken triangular arbitrage

Dependency-free Node.js engines that scan order books for triangular loops and execute (or paper-trade) them.

- `luno-arbitrage.js` — main engine (~1,860 lines). NGN/ZAR/USDT bases, e.g. `NGN → ALGO → XBT → NGN`.
- `kraken-arbitrage.js` — Kraken sibling over USD/USDC/USDT paths, HMAC-SHA512 signing.
- `*-test.js`, `check-*.js` — API, balance, order-book and Telegram harnesses.
- `luno-working-decimals.json` — learned per-pair volume precision.

## Techniques
- Adaptive decimal-precision cache: parses exchange rejection messages to learn accepted precision per pair.
- Order-book depth gating and a second spread check immediately before execution.
- Risk rails: per-trade cap, daily trade cap, daily loss cap, balance reserves. Paper-trade mode.

## Results (Oct 2025 – Jan 2026)
3,362 opportunities logged; best net edges 3.8–5.9%. 123 execution attempts, 3 filled — 65 failed on NGN balance, the rest on min-volume rules or widened spreads. Kraken: 33 attempts, 0 fills (account never funded). Known bug: `Gross Profit: Infinity%` on one-sided books (divide by zero before filtering).

## Run
```
cp .env.example .env   # fill in keys
node -r dotenv/config luno-arbitrage.js   # or export the vars and run plain `node`
```
`autoTrade` defaults to `false` in `CONFIG`.
