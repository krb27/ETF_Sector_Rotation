# ETF Sector Rotation — Design Document

*Last updated: Nov 2026*

---

## 1. Overview

This project implements a **momentum-based ETF sector rotation strategy** for the Indian market using 10 NSE BeES ETFs. The strategy is systematic and rule-based: every month it ranks ETFs by their recent price momentum, holds the top 2, and moves entirely to cash when the broader market turns bearish.

The codebase is intentionally minimal — pure Python standard library for the backtest, with no heavy dependencies except `jugaad-data` for data download.

---

## 2. Strategy Logic

### 2.1 Momentum Score

Each ETF is ranked by a **weighted composite return** across three lookback windows:

```
Score = (50% × 3-month return) + (30% × 6-month return) + (20% × 12-month return)
```

Lookbacks are approximated in calendar days:
- 3M  → 63 trading days × 1.4  = ~88 calendar days
- 6M  → 126 trading days × 1.4 = ~176 calendar days
- 12M → 252 trading days × 1.4 = ~353 calendar days

### 2.2 Bear-Market Filter

Before investing, the strategy checks whether **NIFTYBEES (Nifty 50 proxy) is above its 200-day moving average**:

- **Above 200-MA (Bull)** → invest in top 2 ETFs at 50/50 equal weight
- **Below 200-MA (Bear)** → move 100% to cash (LiquidBees)

This filter prevented large drawdowns during the 2022 market correction.

### 2.3 Rebalance Schedule

| Event | Timing |
|---|---|
| Regular rebalance | 1st trading day of every month |
| Bear exit check | Same — 1st trading day |
| Re-entry after bear | Next month's 1st trading day once Nifty > 200-MA |

Mid-month entry (~10th calendar day) was also tested and showed +3.6% better CAGR with lower drawdown — see `experiment_entry_timing.py`.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA LAYER                           │
│                                                             │
│   NSE / jugaad-data  ──→  download_data.py  ──→  data/*.csv │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                       COMPUTE LAYER                         │
│                                                             │
│   backtest.py               ──→  results/results.json       │
│   experiment_entry_timing.py──→  (console output only)      │
│   experiment_ma.py          ──→  results/experiment_results.json │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│                                                             │
│   python -m http.server  ──→  dashboard/index.html          │
│                               (loads results/*.json)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. File Reference

| File | Layer | Purpose |
|---|---|---|
| `scripts/download_data.py` | Data | Fetches 5-year NSE price history for all 10 ETFs |
| `scripts/backtest.py` | Compute | Runs the full month-by-month backtest simulation |
| `scripts/experiment_entry_timing.py` | Compute | Compares entry on day 1 / day ~10 / last day of month |
| `scripts/experiment_ma.py` | Compute | Compares 50-day / 100-day / 200-day MA bear filter |
| `data/*.csv` | Data | NSE-format price CSVs, one per ETF |
| `results/results.json` | Output | Full backtest output — portfolio values, signals, log |
| `results/experiment_results.json` | Output | MA experiment output |
| `dashboard/index.html` | UI | Interactive dashboard — served via HTTP, loads JSON |
| `docs/SESSION_NOTES.md` | Docs | Detailed findings and session log |
| `docs/DESIGN.md` | Docs | This file |
| `README.md` | Docs | Quick-start guide |

---

## 5. Data Flow

### 5.1 CSV Format

Each CSV uses the NSE Security-wise Price & Volume export format:

```
"Symbol  ","Series  ","Date  ","Prev Close  ","Open Price  ",
"High Price  ","Low Price  ","Last Price  ","Close Price  ",
"Average Price ","Total Traded Quantity  ","Turnover ₹  ","No. of Trades  "
```

Dates are in `DD-Mon-YYYY` format (e.g. `11-Nov-2026`). The backtest only uses `Date` and `Close Price` columns.

### 5.2 results.json Schema

```json
{
  "summary": {
    "initial_capital": 500000,
    "final_value": 1242124,
    "cagr": 25.5,
    "max_drawdown": 13.0,
    "nifty_final": 534876,
    "nifty_cagr": 6.7,
    "n_months": 48,
    "top_n": 2
  },
  "current_signal": {
    "date": "11 Nov 2026",
    "bull_market": true,
    "nifty_price": 288.22,
    "nifty_200ma": 272.55,
    "ranked": [{"etf": "PHARMABEES", "score": 14.55}, ...],
    "recommended": ["PHARMABEES", "BANKBEES"],
    "action": "INVEST"
  },
  "portfolio_values": [
    {"date": "2022-12-01", "value": 500000, "nifty_bnh": 500000, "in_cash": false},
    ...
  ],
  "rebalance_log": [
    {
      "date": "01 Dec 2022",
      "bull_market": true,
      "nifty_vs_200ma": 3.2,
      "scores": {"PHARMABEES": 14.55, ...},
      "selected": ["PHARMABEES", "BANKBEES"],
      "added": ["PHARMABEES"],
      "removed": [],
      "trades": [{"etf": "PHARMABEES", "action": "BUY", "price": 25.10, "shares": 9960.16, "value": 250000}],
      "portfolio_value": 500000,
      "nifty_bnh": 500000
    },
    ...
  ]
}
```

---

## 6. Key Design Decisions

### No external backtest framework
Using `pandas`, `zipline`, or `backtrader` was deliberately avoided to keep the project dependency-free and readable. The simulation loop is ~80 lines of plain Python.

### NIFTYBEES as Nifty proxy
The strategy uses NIFTYBEES (the ETF) rather than the Nifty 50 index itself. This keeps the data source consistent (all from the same NSE CSV format) and means the 200-MA is computed on the actual tradeable instrument.

### Fractional shares
The simulation allows fractional shares (e.g. `9960.16 units`) to avoid the distortion of integer-rounding on a small capital base. In live trading, round down to nearest whole unit.

### Equal-weight (50/50)
Capital is split equally by **value**, not by number of units. For large price differences (e.g. PHARMABEES ₹29 vs BANKBEES ₹636), this means very different share counts — noted with a warning in SESSION_NOTES.

### Results JSON over database
A single flat JSON file keeps the dashboard dependency-free (no server-side database, no API). The dashboard reads the file directly via a file picker. Acceptable for a single-user tool at this scale.

---

## 7. Running the Dashboard

The dashboard (`dashboard/index.html`) is a single self-contained HTML file — no build step, no npm, no frameworks. It runs entirely in the browser and loads data via a file picker.

### Starting the server

```bash
# From project root
python -m http.server 8080
```

Open: `http://localhost:8080/dashboard/index.html`

**If port 8080 is busy:**
```bash
python -m http.server 9090
# Open: http://localhost:9090/dashboard/index.html
```

**If `localhost` refuses to connect:**
- Make sure the server is running (you should see `Serving HTTP on :: port 8080` in your terminal)
- Try `http://127.0.0.1:8080/dashboard/index.html`
- Keep the terminal window open — closing it stops the server

**To stop the server:** `Ctrl + C` in the terminal.

> **Windows / PowerShell note:** To avoid ₹ symbol encoding errors when running Python scripts, prepend:
> ```powershell
> $env:PYTHONIOENCODING="utf-8"; python scripts/backtest.py
> ```

---

## 8. Extending the Project

| What | Where to change |
|---|---|
| Add a new ETF | Download its CSV into `data/`, re-run `backtest.py` |
| Change to Top-3 holding | Set `TOP_N = 3` in `scripts/backtest.py` |
| Change MA period | Set `MA_PERIOD = 100` in `scripts/backtest.py` |
| Change momentum weights | Edit `MOMENTUM_WEIGHTS` dict in `scripts/backtest.py` |
| Change starting capital | Set `INITIAL_CAPITAL` in `scripts/backtest.py` |
| Add a signal checker script | See TODO in `docs/SESSION_NOTES.md` |

---

*Disclaimer: Not SEBI-registered investment advice. For educational purposes only.*
