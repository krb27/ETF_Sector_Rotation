"""
NSE ETF Data Downloader
========================
Fetches 5-year daily price history for all BeES ETFs directly from NSE
using the jugaad-data library, and writes NSE-format CSV files that are
fully compatible with backtest.py.

Install dependency (one time):
    pip install jugaad-data

Usage:
    python download_data.py

Output:
    One CSV per ETF in the same folder, e.g. BANKBEES.csv, GOLDBEES.csv ...
    Columns match the NSE Security-wise Price & Volume CSV export format.
"""

import os
import time
import warnings
from datetime import date, timedelta

warnings.filterwarnings("ignore")   # suppress jugaad numpy timezone warnings

from jugaad_data.nse import stock_df

# ── ETF universe ──────────────────────────────────────────────────────────────
# All liquid NSE BeES / sector ETFs from the Quantinuous strategy
ETF_UNIVERSE = [
    "NIFTYBEES",    # Nifty 50          — also used as 200-MA filter proxy
    "BANKBEES",     # Nifty Bank
    "JUNIORBEES",   # Nifty Next 50
    "AUTOBEES",     # Nifty Auto
    "PHARMABEES",   # Nifty Pharma
    "ITBEES",       # Nifty IT
    "INFRABEES",    # Nifty Infrastructure
    "CONSUMBEES",   # Nifty India Consumption
    "GOLDBEES",     # Gold
    "SILVERBEES",   # Silver
]

# ── Date range: 5 years back from today ──────────────────────────────────────
END_DATE   = date.today()
START_DATE = END_DATE - timedelta(days=365 * 5 + 10)   # small buffer

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def fmt_date_nse(dt) -> str:
    """Return date as NSE-style string: 11-Nov-2026 (no leading zero on day)."""
    return dt.strftime("%d-%b-%Y").lstrip("0")


def write_csv(symbol: str, df) -> None:
    """Write a jugaad stock_df DataFrame to an NSE-format CSV."""
    # Sort newest → oldest
    df = df.sort_values("DATE", ascending=False).reset_index(drop=True)

    out_path = os.path.join(OUTPUT_DIR, f"{symbol}.csv")
    with open(out_path, "w", encoding="utf-8-sig", newline="\n") as f:
        # Header — exactly matching NSE column names (trailing spaces included)
        f.write(
            '"Symbol  ","Series  ","Date  ","Prev Close  ","Open Price  ",'
            '"High Price  ","Low Price  ","Last Price  ","Close Price  ",'
            '"Average Price ","Total Traded Quantity  ","Turnover \u20b9  ","No. of Trades  "\n'
        )

        for _, row in df.iterrows():
            dt       = row["DATE"]
            # jugaad returns datetime64; convert to date
            if hasattr(dt, "date"):
                dt = dt.date()

            close      = float(row["CLOSE"])
            open_      = float(row["OPEN"])
            high       = float(row["HIGH"])
            low        = float(row["LOW"])
            prev_close = float(row["PREV. CLOSE"])
            vwap       = float(row["VWAP"])
            volume     = int(row["VOLUME"])
            value      = float(row["VALUE"])        # turnover in NSE units (lakh ₹ → multiply × 1e5? actually NSE returns ₹)
            trades     = int(row["NO OF TRADES"])

            date_str = fmt_date_nse(dt)

            f.write(
                f'"{symbol}","EQ","{date_str}",'
                f'"{prev_close:,.2f}","{open_:,.2f}",'
                f'"{high:,.2f}","{low:,.2f}",'
                f'"{close:,.2f}","{close:,.2f}",'
                f'"{vwap:,.2f}","{volume:,}",'
                f'"{value:,.2f}","{trades:,}"\n'
            )


def download_symbol(symbol: str) -> bool:
    """Download 5-year history for one ETF. Returns True on success."""
    print(f"  {symbol:<15}", end=" ", flush=True)
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            df = stock_df(
                symbol=symbol,
                from_date=START_DATE,
                to_date=END_DATE,
                series="EQ",
            )
            if df is None or df.empty:
                print("SKIP — no data")
                return False
            write_csv(symbol, df)
            print(f"OK — {len(df)} rows")
            return True
        except Exception as e:
            if attempt < retries:
                wait = attempt * 3
                print(f"\n    Attempt {attempt} failed: {e}. Retrying in {wait}s ...", end="", flush=True)
                time.sleep(wait)
            else:
                print(f"FAILED — {e}")
                return False
    return False


def main():
    print(f"\nNSE ETF Data Downloader (via jugaad-data / NSE)")
    print(f"Period : {START_DATE}  →  {END_DATE}")
    print(f"ETFs   : {len(ETF_UNIVERSE)}")
    print("=" * 56)

    success, failed = [], []
    for symbol in ETF_UNIVERSE:
        ok = download_symbol(symbol)
        (success if ok else failed).append(symbol)
        time.sleep(1.5)   # polite delay between NSE requests

    print("\n" + "=" * 56)
    print(f"Done.  {len(success)} downloaded,  {len(failed)} failed.")
    if failed:
        print(f"Failed : {', '.join(failed)}")
        print("Tip    : Download manually from https://www.nseindia.com/report-detail/eq_security#")
    if success:
        print(f"\nNext step:  python backtest.py")


if __name__ == "__main__":
    main()
