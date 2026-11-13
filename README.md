# ETF Sector Rotation — NSE BeES Strategy

A momentum-based ETF sector rotation backtest for the Indian market, using 10 NSE BeES ETFs.
Based on the strategy described at [Quantinuous.net](https://quantinuous.net).

> **Disclaimer:** Not SEBI-registered investment advice. For educational purposes only.

---

## Strategy Rules

| Parameter | Value |
|---|---|
| Universe | 10 NSE BeES ETFs (see below) |
| Ranking | 50% × 3M return + 30% × 6M return + 20% × 12M return |
| Hold | Top 2 ETFs at 50/50 equal weight |
| Rebalance | 1st trading day of every month |
| Bear filter | Nifty50 < 200-day MA → 100% cash (LiquidBees) |

---

## ETF Universe

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

## Project Structure

```
ETF_Sector_Rotation/
├── data/                        ← ETF price CSVs (NSE format)
│   ├── NIFTYBEES.csv
│   ├── BANKBEES.csv
│   └── ...  (10 ETFs total)
├── scripts/
│   ├── download_data.py         ← Fetch fresh 5-year NSE data via jugaad-data
│   ├── backtest.py              ← Main backtest → writes results/results.json
│   ├── experiment_entry_timing.py  ← Compare 1st vs mid vs end-of-month entry
│   └── experiment_ma.py         ← Compare 50/100/200-day MA filter periods
├── results/
│   ├── results.json             ← Backtest output (loaded by dashboard)
│   └── experiment_results.json  ← MA experiment output
├── dashboard/
│   └── index.html               ← Interactive results dashboard
├── docs/
│   ├── DESIGN.md                ← Architecture, data flow & design decisions
│   ├── SESSION_NOTES.md         ← Detailed session notes & findings
│   └── etf_rotation.pdf         ← Reference material
└── README.md
```

---

## How to Run

### 1. Install dependency (one time)
```bash
pip install jugaad-data
```

### 2. Refresh ETF data (run monthly)
```bash
python scripts/download_data.py
```

### 3. Run the backtest
```bash
python scripts/backtest.py
```

### 4. View the interactive dashboard

Start a local web server from the **project root folder**:

```bash
python -m http.server 8080
```

Then open in your browser:
```
http://localhost:8080/dashboard/index.html
```

Click **"Load results.json"** and select `results/results.json`.

**To use a different port** (if 8080 is busy):
```bash
python -m http.server 9090
# then open: http://localhost:9090/dashboard/index.html
```

**To stop the server:** press `Ctrl + C` in the terminal.

> **Tip:** If `localhost` refuses to connect, try `http://127.0.0.1:8080/dashboard/index.html` instead.

### 5. Run experiments (optional)
```bash
# Entry timing experiment (1st vs mid vs end-of-month)
python scripts/experiment_entry_timing.py

# MA period experiment (50 / 100 / 200-day filter)
python scripts/experiment_ma.py
```

> **Windows tip:** To avoid ₹ symbol encoding errors in PowerShell, run:
> `$env:PYTHONIOENCODING="utf-8"` before any script, or add it to your profile.

---

## Backtest Results (as of Nov 2026)

| Metric | Value |
|---|---|
| Strategy CAGR | **25.5%** |
| Final Value | ₹12,42,124 (started ₹5,00,000) |
| Max Drawdown | 13.0% |
| Nifty B&H CAGR | 6.7% |
| Period | Dec 2022 – Nov 2026 (48 months) |

### Entry Timing Experiment

| Strategy | CAGR | Final Value | Max Drawdown |
|---|---|---|---|
| 1st trading day | 25.5% | ₹12,42,124 | 13.0% |
| ~10th day (mid-month) ✅ | **29.1%** | ₹13,91,069 | **11.5%** |
| Last trading day | 30.8% | ₹14,61,963 | 20.4% |

**Conclusion:** Mid-month entry (~10th) gives +3.6% better CAGR and lower drawdown vs 1st of month.

---

## Current Signal (11 Nov 2026)

🟢 **BULL — Nifty above 200-MA** (₹288.22 vs 200-MA ₹272.55, +5.8% gap)

**Action: INVEST — Top 2 ETFs: PHARMABEES (+14.55%) + BANKBEES (+8.92%)**

Allocation: 50% PHARMABEES / 50% BANKBEES

Next check: **1 Dec 2026**
