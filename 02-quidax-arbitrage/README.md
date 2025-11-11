# Quidax arbitrage port

The Luno engine retargeted to Quidax (uniform 0.1% fee on all pairs), with a 1.5% profit threshold justified by the flat fee. Built 2025-11-11/12; paper mode only, never run in anger.

- `quidax-arbitrage.js` — engine (mirrors the Luno architecture: signing, liquidity check, paper-trade simulation, execution, stats).
- `test-quidax.js`, `diagnose-quidax.js` — API probes.
- `test-busha.js` — pass/fail suite probing Busha Pro as a possible next venue.

Credentials via `.env` (see `.env.example`).
