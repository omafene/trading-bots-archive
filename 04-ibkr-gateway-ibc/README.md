# IBKR gateway groundwork (IBC)

Config and logs for a headless Interactive Brokers Gateway deployment via [IBC](https://github.com/IbcAlpha/IBC) v3.17, paper-trading mode, intended as the base for an equities strategy (Dec 2025).

Never launched: logs end in `java.awt.AWTError: Can't connect to X11 window server` — no virtual framebuffer was set up. Dropped in favour of the prediction-market bots.

`config.ini` has `IbLoginId` / `IbPassword` blanked; fill them locally and keep the file untracked.
