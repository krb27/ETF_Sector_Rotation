"""
MA Period Experiment — compare 200 DMA vs 50 DMA (and any others)
Reuses all logic from backtest.py WITHOUT modifying it.
Outputs: experiment_results.json  (loaded by experiment.html)
"""

import csv
import json
import os
from datetime import datetime, timedelta

# ── Same helpers as backtest.py (copied, not imported, to keep backtest.py untouched) ──

ROOT_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR        = os.path.join(ROOT_DIR, "data")
RESULTS_DIR     = os.path.join(ROOT_DIR, "results")
NIFTY_FILE      = os.path.join(DATA_DIR, "NIFTYBEES.csv")
INITIAL_CAPITAL = 500_000
TOP_N           = 2
MOMENTUM_WEIGHTS = {63: 0.50, 126: 0.30, 252: 0.20}

MA_PERIODS_TO_TEST = [50, 100, 200]   # experiment with all three

def parse_number(s):
    return float(s.replace(",", "").strip())

def load_csv(path):
    prices = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {k.strip(): v.strip() for k, v in row.items()}
            try:
                date = datetime.strptime(cleaned["Date"].strip(), "%d-%b-%Y")
                prices[date] = parse_number(cleaned["Close Price"])
            except (ValueError, KeyError):
                continue
    return dict(sorted(prices.items()))

def get_etf_name(path):
    return os.path.splitext(os.path.basename(path))[0]

def discover_etfs():
    etfs = []
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".csv"):
            etfs.append(os.path.join(DATA_DIR, fname))
    return etfs

def momentum_score(prices, ref_date):
    dates = sorted(prices.keys())
    past  = [d for d in dates if d <= ref_date]
    if not past:
        return None
    current_price = prices[past[-1]]
    score = 0.0
    for lookback_days, weight in MOMENTUM_WEIGHTS.items():
        target     = ref_date - timedelta(days=lookback_days * 1.4)
        candidates = [d for d in dates if d <= target]
        if not candidates:
            return None
        score += weight * ((current_price - prices[candidates[-1]]) / prices[candidates[-1]])
    return score

def is_above_ma(nifty_prices, ref_date, ma_period):
    dates = sorted(nifty_prices.keys())
    past  = [d for d in dates if d <= ref_date]
    if len(past) < ma_period:
        return True
    current_price = nifty_prices[past[-1]]
    ma = sum(nifty_prices[d] for d in past[-ma_period:]) / ma_period
    return current_price > ma

def get_monthly_first_days(all_dates):
    seen, result = set(), []
    for d in sorted(all_dates):
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result

def run_single(nifty_prices, etf_data, ma_period):
    all_dates       = sorted(set(d for p in etf_data.values() for d in p))
    rebalance_dates = get_monthly_first_days(all_dates)
    start_date      = all_dates[0] + timedelta(days=365)
    rebalance_dates = [d for d in rebalance_dates if d >= start_date]

    capital, cash, holdings = float(INITIAL_CAPITAL), float(INITIAL_CAPITAL), {}

    # Nifty BnH baseline
    nifty_ts        = sorted(nifty_prices.keys())
    nifty_past_base = [d for d in nifty_ts if d <= rebalance_dates[0]]
    nifty_base      = nifty_prices[nifty_past_base[-1]]

    portfolio_values = []
    cash_months = 0
    whipsaws    = 0
    prev_in_cash = False
    prev_selected = set()

    for rb_date in rebalance_dates:
        scores = {etf: momentum_score(prices, rb_date)
                  for etf, prices in etf_data.items()
                  if momentum_score(prices, rb_date) is not None}
        ranked   = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        bull     = is_above_ma(nifty_prices, rb_date, ma_period)
        selected = [e for e, _ in ranked[:TOP_N]] if bull else []

        # count whipsaws: flipped from cash→invested or invested→cash vs previous month
        if (not bull) != prev_in_cash:
            whipsaws += 1
        prev_in_cash = not bull

        if not bull:
            cash_months += 1

        # liquidate
        for etf, shares in holdings.items():
            p    = etf_data[etf]
            past = [d for d in sorted(p) if d <= rb_date]
            if past:
                cash += shares * p[past[-1]]
        holdings = {}

        if selected:
            alloc = cash / len(selected)
            for etf in selected:
                p    = etf_data[etf]
                past = [d for d in sorted(p) if d <= rb_date]
                if past:
                    price   = p[past[-1]]
                    shares  = alloc / price
                    holdings[etf] = shares
                    cash   -= shares * price

        port_val = cash + sum(
            holdings[e] * etf_data[e][[d for d in sorted(etf_data[e]) if d <= rb_date][-1]]
            for e in holdings
            if [d for d in sorted(etf_data[e]) if d <= rb_date]
        )

        nifty_past   = [d for d in nifty_ts if d <= rb_date]
        nifty_val    = INITIAL_CAPITAL * (nifty_prices[nifty_past[-1]] / nifty_base) if nifty_past else INITIAL_CAPITAL

        portfolio_values.append({
            "date":      rb_date.strftime("%Y-%m-%d"),
            "value":     round(port_val, 2),
            "nifty_bnh": round(nifty_val, 2),
            "in_cash":   not bull,
        })

    final_val  = portfolio_values[-1]["value"] if portfolio_values else INITIAL_CAPITAL
    n_years    = len(rebalance_dates) / 12
    cagr       = ((final_val / INITIAL_CAPITAL) ** (1 / n_years) - 1) * 100

    peak, max_dd = INITIAL_CAPITAL, 0
    for pv in portfolio_values:
        if pv["value"] > peak:
            peak = pv["value"]
        dd = (peak - pv["value"]) / peak * 100
        if dd > max_dd:
            max_dd = dd

    nifty_final = portfolio_values[-1]["nifty_bnh"] if portfolio_values else INITIAL_CAPITAL
    nifty_cagr  = ((nifty_final / INITIAL_CAPITAL) ** (1 / n_years) - 1) * 100

    return {
        "ma_period":       ma_period,
        "cagr":            round(cagr, 2),
        "final_value":     round(final_val, 2),
        "max_drawdown":    round(max_dd, 2),
        "nifty_cagr":      round(nifty_cagr, 2),
        "nifty_final":     round(nifty_final, 2),
        "cash_months":     cash_months,
        "total_months":    len(rebalance_dates),
        "whipsaws":        max(0, whipsaws - 1),   # subtract initial entry
        "portfolio_values": portfolio_values,
    }

def main():
    nifty_prices = load_csv(NIFTY_FILE)
    etf_paths    = discover_etfs()
    etf_data     = {get_etf_name(p): load_csv(p) for p in etf_paths if load_csv(p)}

    results = []
    for ma in MA_PERIODS_TO_TEST:
        r = run_single(nifty_prices, etf_data, ma)
        results.append(r)
        print(f"MA-{ma:>3}: CAGR={r['cagr']:>6.1f}%  Final=Rs.{r['final_value']:>10,.0f}  "
              f"MaxDD={r['max_drawdown']:>5.1f}%  CashMonths={r['cash_months']:>2}  Whipsaws={r['whipsaws']}")

    out = {"experiments": results, "initial_capital": INITIAL_CAPITAL}
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "experiment_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\n[OK] experiment_results.json written")

if __name__ == "__main__":
    main()
