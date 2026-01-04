# 📊 Calibration & Outcome Analysis Summary
**Generated:** 2026-02-13 13:05

---

## ⚙️ V2 DRIFT CALIBRATION STATUS

**Calibration Mode:** Drift Detection (v2 model)
- **Drift Threshold:** 10% deviation triggers recalibration
- **Last Recalibration:** 2026-02-13 13:05:05 (~just now*)
- **Cooldown Period:** 12 hours minimum between recalibrations
- **Next Check:** Available after 2026-02-14 01:05

\* *Note: Last recalibration timestamp updated when MomentumAnalyzer initialized. This is likely from bot startup, not an actual drift-triggered recalibration event.*

**Recalibration Requirements:**
- Minimum 300 samples
- Lookback window: 1 day
- Triggers when performance drifts >10% from calibration curve

**Status:** ⏸️ IN COOLDOWN - Cannot recalibrate for 12 more hours

---

## 📈 SKIPPED TRADES OUTCOME ANALYSIS
**Period:** Feb 4-13, 2026 (100 outcomes just checked via Kalshi API)
**Total Outcomes Verified:** 7,425 skipped trades

### Overall Performance
- **Win Rate:** 36.0% (2,674 would have won / 7,425 total)
- **Theoretical P&L:** **-$174,903.00** ❌
- **Average per trade:** -$23.55

**VERDICT:** ✅ **Bot is correctly skipping unprofitable trades!**

---

## 🎯 BREAKDOWN BY SKIP REASON

### 1. **Low Edge** (2,316 trades)
- **Win Rate:** 53.0% ✅
- **Theoretical P&L:** -$42,587.50
- **Analysis:** Even with 53% win rate, average losses suggest poor risk/reward

### 2. **Low Signal** (486 trades)
- **Win Rate:** 65.6% ✅✅
- **Theoretical P&L:** -$448.00
- **Analysis:** High win rate but tiny losses suggest marginal edges that aren't worth fees

### 3. **Contrarian Bet** (2,027 trades)
- **Win Rate:** 10.0% ❌❌❌
- **Theoretical P&L:** -$84,810.00
- **Analysis:** **EXCELLENT filter!** Only 10% WR confirms contrarian filter is critical

### 4. **Low Win Prob** (2,596 trades)
- **Win Rate:** 35.7% ❌
- **Theoretical P&L:** -$47,057.50
- **Analysis:** Correctly filtered - below 65% threshold is unprofitable

---

## 💡 KEY INSIGHTS

### ✅ What's Working
1. **Contrarian Filter:** Preventing 90% losers (saves $84K in theoretical losses!)
2. **Low Win Prob Filter:** Catching sub-50% win rate trades correctly
3. **Overall Skip Logic:** Net -$175K avoided = bot is doing its job

### ⚠️ Interesting Findings
1. **Low Edge (53% WR):** Might be worth investigating *why* these still lose money
   - Possible reasons: fees, slippage, or bet sizing issues
   - Could indicate edge calculation needs refinement

2. **Low Signal (65.6% WR):** High win rate but still unprofitable
   - Suggests these are high-probability but low-edge opportunities
   - Correct to skip due to transaction costs

### 🔍 Recommendation
The skip filters are working well! The -$175K theoretical loss shows these trades *should* be skipped. However, consider:
1. **Investigating "Low Edge" skip reason** - 53% WR is decent, but still loses money
2. **Keep contrarian filter enabled** - 10% WR is catastrophic
3. **Consider analyzing the "Low Signal" trades** - 65.6% WR is high, might be worth taking with tighter edge requirements

---

## 🚀 NEXT STEPS

### Immediate
- ✅ Outcomes checked (100 markets verified via API)
- ✅ Drift calibration status verified (in cooldown)
- 📊 Data collection ongoing

### Future (After 12h Cooldown)
1. Re-run drift calibration check to see if 10% threshold is met
2. If drift detected, v2 model will auto-recalibrate from performance data
3. Monitor if recalibration improves edge detection accuracy

---

**Last Updated:** 2026-02-13 13:05 EST
