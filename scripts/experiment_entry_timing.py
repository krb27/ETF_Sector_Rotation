"""
Entry Timing Experiment
=======================
Does entering mid-month hurt or help vs the standard first-of-month rule?

Tests 3 strategies on identical ETF universe & signals:
  A) 1st trading day of month  (original strategy)
  B) ~10th trading day of month (mid-month entry)
  C) Last trading day of month  (end-of-month entry)

All three use the SAME momentum ranking and 200-MA signal computed on
the rebalance date itself — only the *execution day* differs.
"""

import csv, os
from datetime import datetime, timedelta

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT_DIR, "data")
NIFTY_FILE = os.path.join(DATA_DIR, "NIFTYBEES.csv")
INITIAL_CAPITAL = 500_000
TOP_N     = 2
MOMENTUM_WEIGHTS = {63: 0.50, 126: 0.30, 252: 0.20}
MA_PERIOD = 200

# ── Helpers (copied from backtest.py) ─────────────────────────────────────────
def parse_number(s):
    return float(s.replace(",", "").strip())

def load_csv(path):
    prices = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {k.strip(): v.strip() for k, v in row.items()}
            try:
                date_str = cleaned.get("Date", "")
                close    = cleaned.get("Close Price", "")
                if not date_str or not close:
                    continue
                date = datetime.strptime(date_str.strip(), "%d-%b-%Y")
                prices[date] = parse_number(close)
            except (ValueError, KeyError):
                continue
    return dict(sorted(prices.items()))

def discover_etfs():
    etfs = []
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".csv") and fname != "NIFTYBEES.csv":
            etfs.append(os.path.join(DATA_DIR, fname))
    if os.path.exists(NIFTY_FILE):
        etfs.append(NIFTY_FILE)
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
        score += weight * (current_price - prices[candidates[-1]]) / prices[candidates[-1]]
    return score

def is_above_200ma(nifty_prices, ref_date):
    dates = sorted(nifty_prices.keys())
    past  = [d for d in dates if d <= ref_date]
    if len(past) < MA_PERIOD:
        return True
    return nifty_prices[past[-1]] > sum(nifty_prices[d] for d in past[-MA_PERIOD:]) / MA_PERIOD

def closest_trading_day(all_dates_set, target):
    """Return the nearest available trading day on or after target."""
    d = target
    for _ in range(15):
        if d in all_dates_set:
            return d
        d += timedelta(days=1)
    return None

# ── Build rebalance date sets for each strategy ────────────────────────────────
def get_rebalance_dates(all_dates, strategy):
    """
    strategy: 'first' | 'mid' | 'last'
    Returns list of (signal_date, execution_date) tuples.
    signal_date  = date the ranking is computed on (always 1st trading day)
    execution_date = date we actually buy/sell
    """
    all_set = set(all_dates)
    # group trading days by (year, month)
    by_month = {}
    for d in sorted(all_dates):
        key = (d.year, d.month)
        by_month.setdefault(key, []).append(d)

    result = []
    for key in sorted(by_month):
        days = by_month[key]
        signal_date = days[0]   # always rank on 1st trading day

        if strategy == "first":
            exec_date = days[0]
        elif strategy == "mid":
            # ~10th calendar day of the month
            year, month = key
            target = datetime(year, month, 10)
            exec_date = closest_trading_day(all_set, target)
        elif strategy == "last":
            exec_date = days[-1]

        if exec_date is not None:
            result.append((signal_date, exec_date))
    return result

# ── Core simulation ────────────────────────────────────────────────────────────
def simulate(nifty_prices, etf_data, rebalance_pairs, label):
    all_dates = sorted(set(d for p in etf_data.values() for d in p))
    start_date = all_dates[0] + timedelta(days=365)
    rebalance_pairs = [(s, e) for s, e in rebalance_pairs if s >= start_date]

    capital   = float(INITIAL_CAPITAL)
    holdings  = {}
    cash      = capital
    pv_list   = []
    peak      = capital
    max_dd    = 0.0

    first_exec = rebalance_pairs[0][1]
    nifty_base = nifty_prices[min(d for d in nifty_prices if d >= first_exec)]

    for signal_date, exec_date in rebalance_pairs:
        # Value holdings at execution price
        port_value = cash
        for etf, shares in holdings.items():
            past = [d for d in sorted(etf_data[etf]) if d <= exec_date]
            if past:
                port_value += shares * etf_data[etf][past[-1]]

        # Score on SIGNAL date (1st of month always)
        scores = {}
        for etf, prices in etf_data.items():
            s = momentum_score(prices, signal_date)
            if s is not None:
                scores[etf] = s

        bull     = is_above_200ma(nifty_prices, signal_date)
        ranked   = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = [e for e, _ in ranked[:TOP_N]] if bull else []

        # Liquidate at exec_date price
        for etf, shares in holdings.items():
            past = [d for d in sorted(etf_data[etf]) if d <= exec_date]
            if past:
                cash += shares * etf_data[etf][past[-1]]
        holdings = {}

        if selected:
            alloc = cash / len(selected)
            for etf in selected:
                past = [d for d in sorted(etf_data[etf]) if d <= exec_date]
                if past:
                    price  = etf_data[etf][past[-1]]
                    shares = alloc / price
                    holdings[etf] = shares
                    cash -= shares * price

        # Portfolio value after rebalance
        port_value = cash
        for etf, shares in holdings.items():
            past = [d for d in sorted(etf_data[etf]) if d <= exec_date]
            if past:
                port_value += shares * etf_data[etf][past[-1]]

        # Nifty BnH
        nifty_past = [d for d in sorted(nifty_prices) if d <= exec_date]
        nifty_val  = INITIAL_CAPITAL * (nifty_prices[nifty_past[-1]] / nifty_base) if nifty_past else INITIAL_CAPITAL

        pv_list.append({"date": exec_date, "value": port_value, "nifty": nifty_val})

        if port_value > peak:
            peak = port_value
        dd = (peak - port_value) / peak * 100
        if dd > max_dd:
            max_dd = dd

    final  = pv_list[-1]["value"] if pv_list else INITIAL_CAPITAL
    n_years = len(rebalance_pairs) / 12
    cagr   = ((final / INITIAL_CAPITAL) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Year-by-year returns
    by_year = {}
    for pv in pv_list:
        y = pv["date"].year
        by_year.setdefault(y, []).append(pv["value"])

    year_returns = {}
    prev_val = INITIAL_CAPITAL
    for y in sorted(by_year):
        end_val = by_year[y][-1]
        year_returns[y] = (end_val / prev_val - 1) * 100
        prev_val = end_val

    return {
        "label":        label,
        "cagr":         round(cagr, 2),
        "final_value":  round(final, 0),
        "max_drawdown": round(max_dd, 2),
        "year_returns": {y: round(r, 1) for y, r in year_returns.items()},
        "n_months":     len(rebalance_pairs),
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    nifty_prices = load_csv(NIFTY_FILE)
    etf_data = {}
    for path in discover_etfs():
        name = os.path.splitext(os.path.basename(path))[0]
        data = load_csv(path)
        if data:
            etf_data[name] = data

    all_dates = sorted(set(d for p in etf_data.values() for d in p))

    results = []
    for strategy, label in [
        ("first", "A) 1st trading day  (original)"),
        ("mid",   "B) ~10th calendar day (mid-month)"),
        ("last",  "C) Last trading day  (end-of-month)"),
    ]:
        pairs = get_rebalance_dates(all_dates, strategy)
        r     = simulate(nifty_prices, etf_data, pairs, label)
        results.append(r)

    # ── Print comparison table ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  ENTRY TIMING EXPERIMENT — Does mid-month entry change results?")
    print("=" * 70)
    print(f"  {'Strategy':<40} {'CAGR':>7}  {'Final ₹':>12}  {'Max DD':>7}  {'Months':>7}")
    print("  " + "-" * 68)
    for r in results:
        print(f"  {r['label']:<40} {r['cagr']:>6.1f}%  {r['final_value']:>12,.0f}  {r['max_drawdown']:>6.1f}%  {r['n_months']:>7}")

    print()
    print("  Year-by-year comparison:")
    years = sorted(results[0]["year_returns"].keys())
    print(f"  {'Year':<6}", end="")
    for r in results:
        print(f"  {'A' if 'A)' in r['label'] else 'B' if 'B)' in r['label'] else 'C':>10}", end="")
    print()
    print("  " + "-" * 42)
    for y in years:
        print(f"  {y:<6}", end="")
        for r in results:
            val = r["year_returns"].get(y, 0)
            tag = "✅" if val > 0 else "🔴"
            print(f"  {tag}{val:>7.1f}%", end="")
        print()

    print()
    print("  Verdict:")
    a, b, c = results
    diff_ab = b["cagr"] - a["cagr"]
    diff_ac = c["cagr"] - a["cagr"]
    print(f"  Mid-month vs 1st:    {diff_ab:+.2f}% CAGR  |  DD diff: {b['max_drawdown'] - a['max_drawdown']:+.1f}%")
    print(f"  End-of-month vs 1st: {diff_ac:+.2f}% CAGR  |  DD diff: {c['max_drawdown'] - a['max_drawdown']:+.1f}%")
    best = max(results, key=lambda x: x["cagr"])
    print(f"\n  Best entry: {best['label'].strip()}  ({best['cagr']}% CAGR)")
    print("=" * 70)

if __name__ == "__main__":
    main()
