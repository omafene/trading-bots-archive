# Kalshi 15-minute crypto edge bot

Intraday edge detection on Kalshi's 15-minute up/down crypto markets (`KX{SYMBOL}15M`). Final config traded ETH, SOL, XRP (BTC dropped at 47% WR). Jan – Apr 2026; dormant and revivable.

## Architecture
`edge_bot.py` orchestrates: `kalshi_client.py`, `kalshi_ws_feed.py` (private WS for fills, backoff reconnect), `binance_price_feed.py`, `spot_price_feed.py` (CF Benchmarks), `order_book_feed*.py`, `market_scanner_15m.py`, `momentum_analyzer*.py`, `edge_detector_advanced.py` (core multi-factor model), `position_manager_15m.py`, `risk_manager.py`, `calibration_engine.py`, `negative_edge_tracker.py`, `outcome_checker.py`, `dashboard.py` (Flask), `telegram_notifier.py`. Backtesting in `backtest_v3*.py` / `backtester.py`. Run under pm2 via `ecosystem.config.js`.

## Probability model generations
- **v1** momentum — audited 28–36% overconfident; could emit p > 1.0.
- **v2** calibrated — reduced factor bonuses + piecewise-linear calibration curve.
- **v3** mean-reversion step function.
- **v4** — σ-normalised distance thresholds, R²-scaled regime-aware reversion penalty, rolling sub-15m multi-timeframe windows.

## Research loop
- Negative-edge tracker: every skipped trade logged and later settled against the real outcome.
- Dynamic calibration from skipped-trade outcomes, separate UP/DOWN curves (54% vs 91% WR asymmetry).
- Drift-triggered recalibration: |actual − predicted WR| > 10%, 300-sample minimum, 12 h cooldown.
- Crowd blending kept for DOWN trends (85.8% WR), disabled for UP (dragged to 53.8%).

## Results
Feb 2026 live run $155 → $243 (+57%). 7,425 skipped trades validated at 36% WR; contrarian filter caught 2,027 at 10% WR. Calibration study on 2,581 trades moved the WR target from 37% to 55%+. v3 backtest over 833 markets: 50% WR, +$4.67/trade, 2.2% participation (thin volume). An execution-failure incident (19/19 orders failed) was fixed to a 17% fill rate.

Design notes: `COMPLETE_V3_SETUP.md`, `CALIBRATION_SYSTEM.md`, `EXECUTIVE_SUMMARY_V2.md`, `CRITICAL_FINDINGS_V2.md`, `BUGFIXES.md`, plus `../docs/`.

## Run
Config in `config_15m.yaml`; secrets via `.env` (`KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) loaded by `config_loader.py`.
