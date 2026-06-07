"""
auto_update.py  —  One command that keeps matka.db up to date for all 31 markets.

Used by:
  - Windows Task Scheduler (twice daily)  -> auto_update.bat
  - The in-app "Update Now" button         -> imports run_auto_update()
  - Manual runs                            -> python auto_update.py

HOW IT WORKS
------------
For every market it reads that market's PANEL CHART (the dated history grid) from
the right source site (see chart_sources.py) and upserts the last N days into the
database. Reading dated chart values — rather than a homepage snapshot — means:
  * today's results appear only once a market has actually declared (no stale
    "yesterday's number shown as today" mistakes), and
  * any gaps from days the app was off get filled automatically.

By default it does NOT overwrite values you already have; pass --overwrite to let
it correct existing entries from the source.

USAGE
-----
    python auto_update.py               # re-sync last 12 days, all 31 markets
    python auto_update.py --days 30     # widen the window
    python auto_update.py --overwrite   # allow corrections to existing values
    python auto_update.py --quiet       # minimal output (for the scheduler)
    python auto_update.py --only "Kalyan,Sita Day"   # just these markets

Results are logged to the fetch_log table and to last_update.json.

NOTE: Web scraping may violate a site's Terms of Service. Check robots.txt / ToS
before scheduling. Usage is your responsibility.
"""
import os
import sys
import json
import argparse
import sqlite3
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

DB_PATH = os.path.join(HERE, "matka.db")
LAST_UPDATE_PATH = os.path.join(HERE, "last_update.json")

from chart_sources import MARKET_CHARTS, fetch_html, parse_panel_chart  # noqa: E402


# --------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_fetch_log():
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS fetch_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT CURRENT_TIMESTAMP, date TEXT, url TEXT,
        markets_found INTEGER, markets_saved INTEGER, status TEXT, message TEXT)""")
    conn.commit()


def get_markets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, closures FROM markets ORDER BY display_order"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_closed(closures, d):
    if not closures:
        return False
    js_dow = (d.weekday() + 1) % 7  # python Mon=0..Sun=6 -> JS Sun=0..Sat=6
    closed = {int(x) for x in str(closures).split(",") if x.strip().isdigit()}
    return js_dow in closed


def upsert(conn, market_id, date_str, jodi, overwrite=False):
    if not (len(jodi) == 2 and jodi.isdigit()):
        return "skip"
    row = conn.execute(
        "SELECT jodi FROM jodis WHERE market_id=? AND date=?", (market_id, date_str)
    ).fetchone()
    if row is None:
        conn.execute("INSERT INTO jodis (market_id, date, jodi) VALUES (?,?,?)",
                     (market_id, date_str, jodi))
        conn.execute("INSERT INTO audit_log (user, action, details) VALUES (?,?,?)",
                     ("auto_update", "add", f"mkt{market_id} {date_str}={jodi}"))
        return "new"
    if row["jodi"] != jodi and overwrite:
        conn.execute("UPDATE jodis SET jodi=? WHERE market_id=? AND date=?",
                     (jodi, market_id, date_str))
        conn.execute("INSERT INTO audit_log (user, action, details) VALUES (?,?,?)",
                     ("auto_update", "fix", f"mkt{market_id} {date_str} {row['jodi']}->{jodi}"))
        return "updated"
    return "same"


# --------------------------------------------------------------------------
def run_auto_update(mode="both", days=12, overwrite=False, quiet=False, only=None):
    """Re-sync the last `days` days for all (or `only`) markets from panel charts.

    `mode` is accepted for backward compatibility; "daily" narrows the window to
    a few recent days, anything else uses `days`.
    Returns a summary dict (keys kept stable for the app UI).
    """
    def log(*a):
        if not quiet:
            print(*a)

    ensure_fetch_log()
    started = dt.datetime.now()
    today = dt.date.today()
    if mode == "daily":
        days = min(days, 4)
    start = today - dt.timedelta(days=days)

    only_set = None
    if only:
        only_set = {s.strip() for s in only.split(",")} if isinstance(only, str) else set(only)

    markets = get_markets()
    by_name = {m["name"]: m for m in markets}

    conn = get_conn()
    per_market = []
    tot_new = tot_upd = ok = unreachable = 0

    log(f"Re-syncing {start} .. {today} for "
        f"{len(only_set) if only_set else len(MARKET_CHARTS)} markets "
        f"(overwrite={overwrite}) ...")

    for name, url in MARKET_CHARTS.items():
        if only_set and name not in only_set:
            continue
        mk = by_name.get(name)
        if not mk:
            per_market.append({"market": name, "ok": False, "err": "not in DB"})
            continue
        try:
            data = parse_panel_chart(fetch_html(url, timeout=30))
        except Exception as e:
            unreachable += 1
            per_market.append({"market": name, "ok": False, "err": f"{type(e).__name__}"})
            continue
        if not data:
            per_market.append({"market": name, "ok": False, "err": "no rows parsed"})
            continue
        ok += 1
        new = upd = 0
        d = start
        while d <= today:
            ds = d.isoformat()
            if ds in data and not is_closed(mk["closures"], d):
                r = upsert(conn, mk["id"], ds, data[ds], overwrite=overwrite)
                if r == "new":
                    new += 1
                elif r == "updated":
                    upd += 1
            d += dt.timedelta(days=1)
        tot_new += new
        tot_upd += upd
        per_market.append({"market": name, "ok": True, "new": new, "updated": upd,
                           "latest": sorted(data)[-1] if data else None})
        if new or upd:
            log(f"  {name}: +{new} new, ~{upd} fixed (latest {sorted(data)[-1]})")

    conn.commit()
    conn.close()

    status = "ok" if ok else "error"
    msg = f"{ok}/{len(MARKET_CHARTS)} markets reached, +{tot_new} new, ~{tot_upd} fixed"
    if unreachable:
        msg += f", {unreachable} unreachable"

    # fetch_log row
    try:
        c = get_conn()
        c.execute("INSERT INTO fetch_log (date,url,markets_found,markets_saved,status,message) "
                  "VALUES (?,?,?,?,?,?)",
                  (today.isoformat(), "panel-charts", ok, tot_new, status, msg[:500]))
        c.commit(); c.close()
    except Exception:
        pass

    summary = {
        "ts": started.isoformat(timespec="seconds"),
        "mode": mode, "days": days, "overwrite": overwrite,
        "total_new": tot_new, "total_updated": tot_upd,
        "markets_ok": ok, "markets_total": len(MARKET_CHARTS), "unreachable": unreachable,
        # keys kept for the app UI:
        "daily": {"status": status, "saved": tot_new, "message": msg},
        "resync": {"markets_ok": ok, "markets_total": len(MARKET_CHARTS),
                   "new": tot_new, "updated": tot_upd, "per_market": per_market},
    }
    try:
        with open(LAST_UPDATE_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        pass

    elapsed = (dt.datetime.now() - started).total_seconds()
    log(f"\nDONE in {elapsed:.1f}s  |  {msg}  |  log: last_update.json")
    return summary


def main():
    ap = argparse.ArgumentParser(description="Keep matka.db up to date from panel charts.")
    ap.add_argument("--mode", choices=["both", "daily", "resync"], default="both")
    ap.add_argument("--days", type=int, default=12)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--only", default=None, help='Comma-separated market names.')
    a = ap.parse_args()
    s = run_auto_update(mode=a.mode, days=a.days, overwrite=a.overwrite,
                        quiet=a.quiet, only=a.only)
    sys.exit(0 if s["markets_ok"] else 1)


if __name__ == "__main__":
    main()
