"""
export_feed.py  —  Turn matka.db into a compact feed.json for the Android app.

The app reads this single JSON file (served from Firebase / any host) and renders
everything offline: today's board, the Sum 10-14 grouping, the Digit 0-9 totals,
per-market panel/jodi history, and predictions.

Run:
    python export_feed.py                # writes feed.json next to matka.db
    python export_feed.py --days 180     # limit history per market (default: all)
    python export_feed.py --out feed.json

The Sum-Group algorithm matches the app exactly:
    sum_group(AB) = (A + B) % 5 + 10   ->  always 10..14
Colors: 10=blue 11=green 12=yellow 13=orange 14=red
"""
import os
import json
import sqlite3
import argparse
import datetime as dt
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "matka.db")

SUM_COLORS = {10: "#4FC3F7", 11: "#66BB6A", 12: "#FDD835", 13: "#FF9800", 14: "#EF5350"}


def sum_group(j):
    return (int(j[0]) + int(j[1])) % 5 + 10


# ---- predictions (pure-python port of app.py predict_from) ----
def predict_from(rows):
    """rows: list of (date, jodi) sorted by date. Returns dict or None."""
    if len(rows) < 5:
        return None
    jodis = [r[1] for r in rows]
    jt = defaultdict(Counter)
    st = defaultdict(Counter)
    for i in range(len(jodis) - 1):
        cur, nxt = jodis[i], jodis[i + 1]
        jt[cur][nxt] += 1
        st[sum_group(cur)][sum_group(nxt)] += 1
    last_jodi = jodis[-1]
    last_sum = sum_group(last_jodi)
    recent = jodis[-60:]
    sum_freq = Counter(sum_group(j) for j in recent)
    digit_freq = Counter()
    for j in recent:
        digit_freq[int(j[0])] += 1
        digit_freq[int(j[1])] += 1
    # weekday boost (based on the next day's weekday)
    next_wd = (dt.date.fromisoformat(rows[-1][0]) + dt.timedelta(days=1)).weekday()
    weekday_freq = Counter()
    for d, j in rows[-180:]:
        if dt.date.fromisoformat(d).weekday() == next_wd:
            weekday_freq[sum_group(j)] += 1
    mn = jt.get(last_jodi, Counter())
    smn = st.get(last_sum, Counter())
    scores = {}
    for n in range(100):
        j = f"{n:02d}"
        sg = sum_group(j)
        s = 0.0
        s += 3.0 * (mn.get(j, 0) / (sum(mn.values()) or 1))
        s += 1.5 * (smn.get(sg, 0) / (sum(smn.values()) or 1))
        s += 1.0 * (sum_freq.get(sg, 0) / (sum(sum_freq.values()) or 1))
        s += 0.5 * ((digit_freq.get(int(j[0]), 0) + digit_freq.get(int(j[1]), 0)) /
                    (sum(digit_freq.values()) or 1))
        if weekday_freq:
            s += 1.0 * (weekday_freq.get(sg, 0) / (sum(weekday_freq.values()) or 1))
        scores[j] = round(s, 4)
    top = sorted(scores.items(), key=lambda x: -x[1])[:10]
    return {
        "top": [[j, sc] for j, sc in top],
        "last_jodi": last_jodi, "last_sum": last_sum,
        "sum_freq": dict(sum_freq),
        "digit_freq": dict(digit_freq.most_common(10)),
    }


def backtest(rows, window=60):
    """Walk-forward honesty check: for each recent day, predict from the days
    BEFORE it, then compare to what actually came. Returns real hit rates.
    rows: list of (date, jodi) sorted by date."""
    if len(rows) < 15:
        return None
    start = max(6, len(rows) - window)
    tested = top1 = top5 = top10 = sumhit = 0
    for i in range(start, len(rows)):
        p = predict_from(rows[:i])
        if not p:
            continue
        actual = rows[i][1]
        tops = [x[0] for x in p["top"]]
        tested += 1
        if tops and actual == tops[0]:
            top1 += 1
        if actual in tops[:5]:
            top5 += 1
        if actual in tops[:10]:
            top10 += 1
        if tops and sum_group(actual) == sum_group(tops[0]):
            sumhit += 1
    if tested == 0:
        return None
    def pct(x):
        return round(100.0 * x / tested, 1)
    return {
        "tested": tested,
        "top1_pct": pct(top1), "top5_pct": pct(top5), "top10_pct": pct(top10),
        "sum_pct": pct(sumhit),
        # what blind chance would score, for honest comparison:
        "rand_top1": 1.0, "rand_top5": 5.0, "rand_top10": 10.0, "rand_sum": 20.0,
    }


def month_analysis(rows, month):
    """rows for one market; month 'YYYY-MM'. Returns sum_counts, digit_counts, total."""
    sc = {10: 0, 11: 0, 12: 0, 13: 0, 14: 0}
    dc = [0] * 10
    total = 0
    for d, j in rows:
        if d.startswith(month):
            sc[sum_group(j)] += 1
            dc[int(j[0])] += 1
            dc[int(j[1])] += 1
            total += 1
    return {"sum_counts": sc, "digit_counts": dc, "total": total}


def build_feed(days=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    markets = conn.execute(
        "SELECT id, name, display_order, closures FROM markets ORDER BY display_order"
    ).fetchall()
    today = dt.date.today().isoformat()
    cur_month = today[:7]
    cutoff = None
    if days:
        cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()

    feed_markets = []
    latest_overall = ""
    for m in markets:
        q = "SELECT date, jodi FROM jodis WHERE market_id=?"
        p = [m["id"]]
        if cutoff:
            q += " AND date>=?"
            p.append(cutoff)
        q += " ORDER BY date"
        rows = [(r["date"], r["jodi"]) for r in conn.execute(q, p).fetchall()]
        if rows:
            latest_overall = max(latest_overall, rows[-1][0])
        results = {d: j for d, j in rows}
        feed_markets.append({
            "name": m["name"],
            "order": m["display_order"],
            "closures": m["closures"] or "",
            "results": results,
            "today": results.get(today),
            "latest_date": rows[-1][0] if rows else None,
            "latest_jodi": rows[-1][1] if rows else None,
            "month": {"label": cur_month, **month_analysis(rows, cur_month)},
            "predict": predict_from(rows),
            "backtest": backtest(rows),
        })
    conn.close()
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "today": today,
        "latest_date": latest_overall,
        "sum_colors": SUM_COLORS,
        "market_count": len(feed_markets),
        "markets": feed_markets,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None,
                    help="History days per market (default: all).")
    ap.add_argument("--out", default=os.path.join(HERE, "feed.json"))
    a = ap.parse_args()
    feed = build_feed(days=a.days)
    payload = json.dumps(feed, separators=(",", ":"), ensure_ascii=False)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(payload)
    # Also emit feed.js (window.__FEED__) so the app can render with no server
    # (e.g. opened via file:// on a phone) and then refresh live when online.
    js_path = os.path.join(os.path.dirname(a.out) or ".", "feed.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.__FEED__=" + payload + ";")
    size = os.path.getsize(a.out)
    print(f"Wrote {a.out}  ({size/1024:.1f} KB)  + feed.js")
    print(f"  markets: {feed['market_count']}, latest date: {feed['latest_date']}")
    print(f"  generated: {feed['generated_at']}")


if __name__ == "__main__":
    main()
