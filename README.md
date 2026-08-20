# Trading Bots Archive (Oct 2025 – Feb 2026)

Eight algorithmic-trading projects built over five months, from cross-exchange crypto arbitrage alerts to a calibrated probability model for 15-minute prediction markets. Results below are as logged — losses included. Backtests and projections are labelled as such.

| # | Project | Dates | Stack | Status | Headline |
|---|---------|-------|-------|--------|----------|
| 00 | [Luno ↔ Kraken spread monitor](00-luno-kraken-spread-monitor/) | 2025-10-05 | Python, ccxt | prototype | Cross-exchange Telegram alerts; tiered thresholds by pair class |
| 01 | [Luno / Kraken triangular arbitrage](01-luno-kraken-arbitrage/) | 2025-10 → 2026-01 | Node.js, zero deps | live, paused | 3,362 opportunities, 3.8–5.9% best edge, 3/123 fills |
| 02 | [Quidax port](02-quidax-arbitrage/) | 2025-11-11/12 | Node.js | prototype | Engine retargeted in a day; flat 0.1% fee venue |
| 03 | [Systematic Trader v2](03-systematic-trader-v2/) | 2025-11 → 2026-03 | Node.js, ccxt, pm2 | paper, stopped | 415 paper trades, 29.9% WR, −$1,082 |
| 04 | [IBKR gateway (IBC)](04-ibkr-gateway-ibc/) | 2025-12 | Java, IB Gateway | abandoned | Headless IB Gateway config; never launched (X11) |
| 05 | [Kalshi endgame sweep bot](05-kalshi-endgame-bot/) | 2025-12 → 2026-02 | Python | superseded | Near-certain-outcome harvesting, Kelly sizing, Telegram control |
| 06 | [Kalshi 15-minute crypto edge bot](06-kalshi-15m-edge-bot/) | 2026-01 → 2026-04 | Python, asyncio, websockets, Flask | live, dormant | +57% live run; 7,425 skipped trades validated; 4 model generations |
| 07 | [Kalshi hybrid bot](07-kalshi-hybrid-bot/) | 2026-02 → 2026-03 | Python | paper only | 8-layer validation pipeline; 1,081-market backtest |

Supporting research notes for the 15m bot live in [`docs/`](docs/): probability model v2 recalibration, dynamic calibration, drift-triggered recalibration, and the crowd-blending fix.

## Arc

1. **Arbitrage (Oct–Nov 2025).** Started with a Python/ccxt cross-exchange alerter, moved to dependency-free Node.js triangular execution engines on Luno and Kraken, then generalised the engine to Quidax. The edge was real but under-capitalised and precision-brittle; the lasting wins were the self-learning decimal-precision cache, pre-execution spread re-validation, and layered risk rails.
2. **Systematic crypto (Nov 2025–Mar 2026).** Multi-strategy spot bot with ADX regime switching and fractional-Kelly sizing. Strong engineering, negative validated edge: momentum fired 412 of 415 trades and lost.
3. **Prediction markets (Dec 2025–Mar 2026).** Slow high-probability sweeps → high-frequency 15-minute crypto edge detection with a real calibration loop (every *skipped* trade logged and settled against the outcome) → an architectural cleanup distilling those lessons into 8 composable filters.

## What carried forward

| Technique | First appeared | Reused in |
|-----------|----------------|-----------|
| Pre-execution re-validation | Luno arbitrage | Hybrid bot spread/slippage gate |
| Layered risk rails (per-trade / daily / weekly caps) | Luno arbitrage | Every later bot |
| Fractional Kelly sizing | Systematic Trader v2 | Endgame, 15m, hybrid |
| ADX / R² regime classification | Systematic Trader v2 | 15m v4 model, hybrid regime detector |
| Telegram alerting + remote control | Spread monitor | Every later bot |
| Skipped-trade outcome tracking → calibration | Kalshi 15m | Later work |

## About the commit history

The original projects were developed outside version control. This repo's history was reconstructed in August 2026: one commit per project, with the author date set to the earliest file timestamp in that project's original working tree (and the message noting the period it was worked on). Each commit contains the project's final state, not its evolution.

## Credentials

No credentials are committed. Every bot loads keys from environment variables or an untracked config file — see each project's `.env.example`. Logs, data dumps, virtualenvs, `node_modules`, and dated backup copies were stripped from this archive; the original working trees were not under version control.

## Disclaimer

Research and personal experimentation. Nothing here is financial advice, and most of these bots lost money or never traded live.
