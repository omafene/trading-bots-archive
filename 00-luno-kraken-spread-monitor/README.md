# Luno ↔ Kraken spread monitor

The first project (2025-10-05): a Python/ccxt monitor comparing Luno and Kraken prices on non-NGN pairs and pushing Telegram alerts when the spread clears fees. Alert-only — no execution path.

- `luno_kraken_arbitrage_bot.py` / `luno_kraken_alert_bot.py` — near-identical; the former adds two reversed pairs.
- Per-venue rate limiting (Luno 1 req/s, Kraken ~600 ms), maker/taker fee tables, and tiered thresholds by pair class (stablecoin / major / alt) with min / good / excellent bands.

Expects a `config.json` (untracked) with `telegram_token`, `telegram_chat_id`, and a polling interval. Superseded within days by the Node.js triangular engines in `01-luno-kraken-arbitrage/`.
