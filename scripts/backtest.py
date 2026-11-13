"""
ETF Sector Rotation Backtester
Strategy rules (from Quantinuous.net):
  - Universe  : Any NSE ETF CSVs placed in same folder
  - Ranking   : Momentum score = 50% * 3M return + 30% * 6M return + 20% * 12M return
  - Hold      : Top 2 ETFs at 50/50  (or Top 3 at 33/33/33)
  - Rebalance : First trading day of every month
  - Filter    : If Nifty50 < 200-day MA → 100% cash (LiquidBees)
Outputs:
  - results.json  (used by the HTML UI)
"""

import csv
import json
import math
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────────
ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT_DIR, "data")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")
NIFTY_FILE = os.path.join(DATA_DIR, "NIFTYBEES.csv")   # used as Nifty50 proxy for 200-MA filter
INITIAL_CAPITAL = 500_000          # ₹5,00,000
TOP_N     = 2                      # 2 = top-2 model,  3 = top-3 model
MOMENTUM_WEIGHTS = {
    63:  0.50,   # ~3 months  (63 trading days)
    126: 0.30,   # ~6 months
    252: 0.20,   # ~12 months
}
MA_PERIOD = 200                    # bear-market filter

# ── CSV Parsing ────────────────────────────────────────────────────────────────
def parse_number(s: str) -> float:
    """Remove commas and whitespace, return float."""
    return float(s.replace(",", "").strip())

def load_csv(path: str) -> dict:
    """Returns {date: close_price} sorted oldest→newest."""
    prices = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # strip BOM / whitespace from keys
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

def get_etf_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]

# ── Discover all ETF CSVs ──────────────────────────────────────────────────────
def discover_etfs() -> list:
    etfs = []
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".csv") and fname not in ("NIFTYBEES.csv",):
            etfs.append(os.path.join(DATA_DIR, fname))
    # Always include NIFTYBEES as a tradeable ETF too
    nifty_path = NIFTY_FILE
    if os.path.exists(nifty_path):
        etfs.append(nifty_path)
    return etfs

# ── Momentum Score ─────────────────────────────────────────────────────────────
def momentum_score(prices: dict, ref_date: datetime) -> float | None:
    """Weighted momentum score relative to ref_date."""
    dates = sorted(prices.keys())
    # find the latest date <= ref_date
    past = [d for d in dates if d <= ref_date]
    if not past:
        return None
    current_date = past[-1]
    current_price = prices[current_date]

    score = 0.0
    for lookback_days, weight in MOMENTUM_WEIGHTS.items():
        target = ref_date - timedelta(days=lookback_days * 1.4)  # calendar-day approx
        candidates = [d for d in dates if d <= target]
        if not candidates:
            return None
        past_price = prices[candidates[-1]]
        ret = (current_price - past_price) / past_price
        score += weight * ret
    return score

# ── 200-day MA filter ──────────────────────────────────────────────────────────
def is_above_200ma(nifty_prices: dict, ref_date: datetime) -> bool:
    dates = sorted(nifty_prices.keys())
    past  = [d for d in dates if d <= ref_date]
    if len(past) < MA_PERIOD:
        return True  # not enough data → assume bullish
    current_price = nifty_prices[past[-1]]
    ma200 = sum(nifty_prices[d] for d in past[-MA_PERIOD:]) / MA_PERIOD
    return current_price > ma200

# ── Monthly rebalance dates ────────────────────────────────────────────────────
def get_monthly_first_trading_days(all_dates: list) -> list:
    """Return the first trading day of each calendar month."""
    seen = set()
    result = []
    for d in sorted(all_dates):
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result

# ── Main Backtest ──────────────────────────────────────────────────────────────
def run_backtest():
    # Load Nifty for 200-MA filter
    nifty_prices = load_csv(NIFTY_FILE)

    # Load all ETFs
    etf_paths = discover_etfs()
    etf_data  = {}
    for path in etf_paths:
        name = get_etf_name(path)
        data = load_csv(path)
        if data:
            etf_data[name] = data

    # Union of all trading dates
    all_dates = sorted(set(d for prices in etf_data.values() for d in prices))
    rebalance_dates = get_monthly_first_trading_days(all_dates)

    # Determine backtest window (need at least 12M of data)
    start_date = all_dates[0] + timedelta(days=365)
    rebalance_dates = [d for d in rebalance_dates if d >= start_date]

    # ── Portfolio simulation ───────────────────────────────────────────────────
    capital    = float(INITIAL_CAPITAL)
    holdings   = {}   # {etf_name: shares}
    cash       = capital
    in_cash    = False

    portfolio_values = []   # [{date, value, holdings, scores, in_cash}]
    rebalance_log    = []   # detailed log for UI

    # Nifty buy-and-hold baseline
    first_nifty_date = min(d for d in nifty_prices if d >= rebalance_dates[0])
    nifty_base_price = nifty_prices[first_nifty_date]
    nifty_bnh_values = []

    prev_holdings = {}

    for i, rb_date in enumerate(rebalance_dates):
        # 1. Compute current portfolio value
        port_value = cash
        for etf, shares in holdings.items():
            prices = etf_data.get(etf, {})
            past = [d for d in sorted(prices) if d <= rb_date]
            if past:
                port_value += shares * prices[past[-1]]

        # 2. Compute momentum scores
        scores = {}
        for etf, prices in etf_data.items():
            s = momentum_score(prices, rb_date)
            if s is not None:
                scores[etf] = round(s * 100, 2)   # as percentage

        # 3. Bear-market filter
        bull = is_above_200ma(nifty_prices, rb_date)

        # 4. Rank & select
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = [etf for etf, _ in ranked[:TOP_N]] if bull else []

        # 5. Execute rebalance
        # Liquidate all current holdings
        for etf, shares in holdings.items():
            prices = etf_data.get(etf, {})
            past = [d for d in sorted(prices) if d <= rb_date]
            if past:
                cash += shares * prices[past[-1]]
        holdings = {}

        trades = []
        if selected:
            alloc = cash / len(selected)
            for etf in selected:
                prices = etf_data[etf]
                past = [d for d in sorted(prices) if d <= rb_date]
                if past:
                    price = prices[past[-1]]
                    shares = alloc / price
                    holdings[etf] = shares
                    cash -= shares * price
                    trades.append({
                        "etf": etf,
                        "action": "BUY",
                        "price": round(price, 2),
                        "shares": round(shares, 4),
                        "value": round(alloc, 2)
                    })
            in_cash = False
        else:
            in_cash = True
            trades.append({"etf": "CASH/LIQUIDBEES", "action": "PARK", "price": 1, "shares": cash, "value": round(cash, 2)})

        # Recompute portfolio value after rebalance
        port_value = cash
        for etf, shares in holdings.items():
            prices = etf_data[etf]
            past = [d for d in sorted(prices) if d <= rb_date]
            if past:
                port_value += shares * prices[past[-1]]

        # Nifty BnH value
        nifty_past = [d for d in sorted(nifty_prices) if d <= rb_date]
        nifty_curr = nifty_prices[nifty_past[-1]] if nifty_past else nifty_base_price
        nifty_value = INITIAL_CAPITAL * (nifty_curr / nifty_base_price)

        portfolio_values.append({
            "date": rb_date.strftime("%Y-%m-%d"),
            "value": round(port_value, 2),
            "nifty_bnh": round(nifty_value, 2),
            "in_cash": in_cash
        })

        # Determine changes vs prev month
        added   = [e for e in selected if e not in prev_holdings]
        removed = [e for e in prev_holdings if e not in selected]

        rebalance_log.append({
            "date": rb_date.strftime("%d %b %Y"),
            "bull_market": bull,
            "nifty_vs_200ma": round(
                (nifty_prices.get(nifty_past[-1] if nifty_past else rb_date, 0) /
                 (sum(nifty_prices[d] for d in sorted(nifty_prices)[-MA_PERIOD:]) / MA_PERIOD) - 1) * 100
                if len(nifty_prices) >= MA_PERIOD else 0, 2
            ),
            "scores": {etf: score for etf, score in ranked},
            "selected": selected,
            "added": added,
            "removed": removed,
            "trades": trades,
            "portfolio_value": round(port_value, 2),
            "nifty_bnh": round(nifty_value, 2),
        })

        prev_holdings = set(selected)

    # ── Summary metrics ────────────────────────────────────────────────────────
    final_value = portfolio_values[-1]["value"] if portfolio_values else INITIAL_CAPITAL
    n_years = len(rebalance_dates) / 12
    cagr = ((final_value / INITIAL_CAPITAL) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Max drawdown
    peak = INITIAL_CAPITAL
    max_dd = 0
    for pv in portfolio_values:
        v = pv["value"]
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Nifty CAGR
    nifty_final = portfolio_values[-1]["nifty_bnh"] if portfolio_values else INITIAL_CAPITAL
    nifty_cagr = ((nifty_final / INITIAL_CAPITAL) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Latest scores (today's ranking)
    latest_date = all_dates[-1]
    latest_scores = {}
    for etf, prices in etf_data.items():
        s = momentum_score(prices, latest_date)
        if s is not None:
            latest_scores[etf] = round(s * 100, 2)
    latest_ranked = sorted(latest_scores.items(), key=lambda x: x[1], reverse=True)
    latest_bull = is_above_200ma(nifty_prices, latest_date)

    # Nifty 200MA current value
    nifty_dates = sorted(nifty_prices.keys())
    nifty_curr_price = nifty_prices[nifty_dates[-1]]
    nifty_200ma = sum(nifty_prices[d] for d in nifty_dates[-MA_PERIOD:]) / MA_PERIOD

    output = {
        "summary": {
            "initial_capital": INITIAL_CAPITAL,
            "final_value": round(final_value, 2),
            "cagr": round(cagr, 2),
            "max_drawdown": round(max_dd, 2),
            "nifty_final": round(nifty_final, 2),
            "nifty_cagr": round(nifty_cagr, 2),
            "n_months": len(rebalance_dates),
            "top_n": TOP_N,
        },
        "current_signal": {
            "date": latest_date.strftime("%d %b %Y"),
            "bull_market": latest_bull,
            "nifty_price": round(nifty_curr_price, 2),
            "nifty_200ma": round(nifty_200ma, 2),
            "ranked": [{"etf": e, "score": s} for e, s in latest_ranked],
            "recommended": [e for e, _ in latest_ranked[:TOP_N]] if latest_bull else [],
            "action": "INVEST" if latest_bull else "MOVE TO CASH",
        },
        "portfolio_values": portfolio_values,
        "rebalance_log": rebalance_log,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[OK] Backtest complete -> results.json")
    print(f"   CAGR          : {cagr:.1f}%")
    print(f"   Final Value   : ₹{final_value:,.0f}")
    print(f"   Max Drawdown  : {max_dd:.1f}%")
    print(f"   Nifty CAGR    : {nifty_cagr:.1f}%")
    print(f"\nCurrent Signal ({latest_date.strftime('%d %b %Y')}):")
    print(f"   Market        : {'BULL (Above 200-MA)' if latest_bull else 'BEAR (Below 200-MA)'}")
    print(f"   Nifty Price   : ₹{nifty_curr_price:.2f}  |  200-MA: ₹{nifty_200ma:.2f}")
    print(f"   Top {TOP_N} ETFs    : {', '.join([e for e,_ in latest_ranked[:TOP_N]])}")
    for etf, score in latest_ranked:
        marker = "<< HOLD" if etf in [e for e,_ in latest_ranked[:TOP_N]] and latest_bull else ""
        print(f"   {etf:<15} score: {score:>8.2f}%  {marker}")

if __name__ == "__main__":
    run_backtest()
