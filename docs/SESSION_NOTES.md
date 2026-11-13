# ETF Sector Rotation — Session Notes
*Last updated: 12 Nov 2026*

---

## What we built today

| File | Purpose |
|---|---|
| `download_data.py` | Auto-downloads 5-year NSE data for all 10 BeES ETFs via `jugaad-data` |
| `backtest.py` | Runs the full momentum backtest, outputs `results.json` |
| `experiment_entry_timing.py` | Compares 1st vs mid vs end-of-month entry timing |
| `index.html` | Interactive dashboard — load `results.json` to view |
| `SESSION_NOTES.md` | This file |

---

## How to run

```bash
# 1. Refresh ETF data (run monthly)
python download_data.py

# 2. Run backtest
python backtest.py

# 3. Open dashboard
python -m http.server 8080
# then open: http://localhost:8080/index.html
# click "Load results.json"
```

---

## ETF Universe (10 ETFs)

| Symbol | Tracks |
|---|---|
| NIFTYBEES | Nifty 50 — also used as 200-MA filter proxy |
| BANKBEES | Nifty Bank |
| JUNIORBEES | Nifty Next 50 |
| AUTOBEES | Nifty Auto |
| PHARMABEES | Nifty Pharma |
| ITBEES | Nifty IT |
| INFRABEES | Nifty Infrastructure |
| CONSUMBEES | Nifty India Consumption |
| GOLDBEES | Gold |
| SILVERBEES | Silver |

---

## Current Backtest Results (as of 12 Nov 2026)

| Metric | Value |
|---|---|
| Strategy CAGR | **25.5%** |
| Final Value | ₹12,42,124 (started ₹5,00,000) |
| Max Drawdown | 13.0% |
| Nifty B&H CAGR | 6.7% |
| Backtest period | Dec 2022 – Nov 2026 (48 months) |

---

## Current Signal (11 Nov 2026)

| | |
|---|---|
| Market | 🟢 BULL — Nifty above 200-MA |
| Nifty price | ₹288.22 |
| 200-day MA | ₹272.55 |
| Gap | +5.8% above (exit triggers if Nifty falls below 200-MA) |
| **Action** | **INVEST** |
| **Top 2 ETFs** | **PHARMABEES (#1, +14.55%) + BANKBEES (#2, +8.92%)** |
| Allocation | 50% PHARMABEES / 50% BANKBEES |

### Full ranking
| Rank | ETF | Momentum Score |
|---|---|---|
| 1 | PHARMABEES | +14.55% |
| 2 | BANKBEES | +8.92% |
| 3 | NIFTYBEES | +3.74% |
| 4 | JUNIORBEES | +2.96% |
| 5 | ITBEES | +2.01% |
| 6 | AUTOBEES | +1.86% |
| 7 | INFRABEES | +0.87% |
| 8 | CONSUMBEES | +0.84% |
| 9 | GOLDBEES | -7.03% |
| 10 | SILVERBEES | -17.66% |

---

## Last Prices (11 Nov 2026)

| ETF | Close | Day Range | VWAP |
|---|---|---|---|
| PHARMABEES | ₹29.54 | ₹29.33 – ₹30.27 | ₹29.47 |
| BANKBEES | ₹636.41 | ₹624 – ₹637.43 | ₹634.45 |

> ⚠️ **50/50 by value** = ~215 PHARMABEES for every 10 BANKBEES (price difference is large)

---

## Entry Timing Experiment Results

| Strategy | CAGR | Final Value | Max Drawdown |
|---|---|---|---|
| 1st trading day (original) | 25.5% | ₹12,42,124 | 13.0% |
| ~10th day (mid-month) ✅ | **29.1%** | ₹13,91,069 | **11.5%** |
| Last trading day | 30.8% | ₹14,61,963 | 20.4% |

**Conclusion:** Mid-month entry (~10th) showed +3.6% better CAGR AND lower drawdown vs 1st of month.  
Caveat: Only 48 months of data — small sample.

---

## Exit Rule

> **If NIFTY50 (NIFTYBEES) closes BELOW its 200-day MA on the 1st trading day of any month → EXIT all positions, park in cash (LiquidBees)**

- Check: **1st trading day of every month**
- Current exit trigger price: ~₹272.55 (moves slightly each month)
- Next check: **1 Dec 2026**

---

## TODO — Next Session

- [ ] Build `check_signal.py` — monthly signal checker that:
  - Fetches fresh data via `jugaad-data`
  - Computes current 200-MA and momentum scores
  - Prints plain-English verdict: 🟢 HOLD / 🔄 REBALANCE / 🔴 EXIT
  - Shows what changed vs last month
  - Optional: send desktop notification or email alert

---

## Strategy Rules (quick reference)

```
Universe  : 10 NSE BeES ETFs (see table above)
Ranking   : 50% × 3M return + 30% × 6M return + 20% × 12M return
Hold      : Top 2 ETFs at 50/50 equal weight
Rebalance : 1st trading day of every month (mid-month also works per experiment)
Bear filter: Nifty50 < 200-day MA → 100% cash (LiquidBees)
Capital   : Any amount (backtest used ₹5,00,000)
```

---

*Disclaimer: Not SEBI-registered investment advice. For educational purposes only.*
