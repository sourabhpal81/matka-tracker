"""
chart_sources.py  —  Maps all 31 markets to their panel-chart pages across the
two source sites, and parses those pages into {date: jodi}.

Two sites are used:
  * Bombay/main markets   -> https://sattamatkadpboss.mobi
  * Andhra/regional markets -> https://dpbossss.boston

The panel-chart layout on both sites is the same dpboss template: an HTML table
whose rows each start with a "DD/MM/YYYY to DD/MM/YYYY" week range, followed by
day cells in triples (open-panna, jodi, close-panna). We read the middle 2-digit
jodi of each triple and map it to consecutive dates from the week's start.

This parser was ported from the browser extractor that was validated against the
live charts (it correctly skips closed days, e.g. Sunday for closed-Sunday
markets, and stops at the latest declared date).
"""
import re
import datetime as dt
from html.parser import HTMLParser
from urllib.request import Request, urlopen

SITE_BOMBAY = "https://sattamatkadpboss.mobi"
SITE_ANDHRA = "https://dpbossss.boston"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# market name (exactly as in matka.db) -> full panel-chart URL
MARKET_CHARTS = {
    # --- Bombay site ---
    "Kalyan":        SITE_BOMBAY + "/record/kalyan-penal-chart.php",
    "Kalyan Night":  SITE_BOMBAY + "/record/kalyan-night-penal-chart.php",
    "Main Bazaar":   SITE_BOMBAY + "/main-bazar-panel-chart.php",
    "Time Bazaar":   SITE_BOMBAY + "/time-bazar-panel-chart.php",
    "Milan Day":     SITE_BOMBAY + "/record/milan-day-penal-chart.php",
    "Milan Night":   SITE_BOMBAY + "/record/milan-night-penal-chart.php",
    "Rajdhani Day":  SITE_BOMBAY + "/record/rajdhani-day-penal-chart.php",
    "Rajdhani Night":SITE_BOMBAY + "/record/rajdhani-night-penal-chart.php",
    "Madhur Day":    SITE_BOMBAY + "/madhur-day-panel-chart.php",
    "Madhur Night":  SITE_BOMBAY + "/madhur-night-panel-chart.php",
    "Sridevi":       SITE_BOMBAY + "/record/sridevi-satta-penal-chart.php",
    "Sridevi Night": SITE_BOMBAY + "/record/sridevi-night-satta-penal-chart.php",
    # --- Andhra site ---
    "Sita Morning":      SITE_ANDHRA + "/panel-chart-record/sita-morning.php",
    "Sita Day":          SITE_ANDHRA + "/panel-chart-record/sita-day.php",
    "Sita Night":        SITE_ANDHRA + "/panel-chart-record/sita-night.php",
    "Geeta Morning":     SITE_ANDHRA + "/panel-chart-record/geeta-morning.php",
    "Star Tara Morning": SITE_ANDHRA + "/panel-chart-record/star-tara-morning.php",
    "Star Tara Day":     SITE_ANDHRA + "/panel-chart-record/star-tara-day.php",
    "Star Tara Night":   SITE_ANDHRA + "/panel-chart-record/star-tara-night.php",
    "Tulsi Morning":     SITE_ANDHRA + "/panel-chart-record/tulsi-morning.php",
    "Andra Morning":     SITE_ANDHRA + "/panel-chart-record/andhra-morning.php",
    "Andra Day":         SITE_ANDHRA + "/panel-chart-record/andhra-day.php",
    "Andra Night":       SITE_ANDHRA + "/panel-chart-record/andhra-night.php",
    "Meena Morning":     SITE_ANDHRA + "/panel-chart-record/meena-morning.php",
    "Meena Bazaar":      SITE_ANDHRA + "/panel-chart-record/meena-bazar.php",
    "Mahadevi Morning":  SITE_ANDHRA + "/panel-chart-record/mahadevi-morning.php",
    "Mahadevi":          SITE_ANDHRA + "/panel-chart-record/mahadevi.php",
    "Mahadevi Night":    SITE_ANDHRA + "/panel-chart-record/mahadevi-night.php",
    "Srilakhsmi Day":    SITE_ANDHRA + "/panel-chart-record/srilaxmi-day.php",
    "Super King":        SITE_ANDHRA + "/panel-chart-record/super-king.php",
    "Superking Night":   SITE_ANDHRA + "/panel-chart-record/super-king-night.php",
}


class _TableParser(HTMLParser):
    """Collect table rows as lists of cell-texts."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            t = data.strip()
            if t:
                self._cell.append(t)


_DATE_RANGE = re.compile(
    r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4}).{0,6}(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})"
)


def parse_panel_chart(html):
    """Return {YYYY-MM-DD: 'jodi'} parsed from a dpboss-style panel chart page."""
    p = _TableParser()
    try:
        p.feed(html)
    except Exception:
        pass
    out = {}
    for row in p.rows:
        if len(row) < 2:
            continue
        # locate the date-range cell
        di = -1
        m = None
        for i, cell in enumerate(row):
            mm = _DATE_RANGE.search(cell.replace("\n", " "))
            if mm:
                di, m = i, mm
                break
        if di < 0:
            continue
        try:
            start = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        day_cells = row[di + 1:]
        # group in triples: [open_panna, jodi, close_panna]
        for g in range(len(day_cells) // 3 + 1):
            idx = g * 3 + 1
            if idx >= len(day_cells):
                break
            digits = re.sub(r"\D", "", day_cells[idx])
            d = start + dt.timedelta(days=g)
            if len(digits) == 2:
                out[d.isoformat()] = digits
    return out


def fetch_html(url, timeout=30):
    req = Request(url, headers={"User-Agent": UA,
                                "Accept-Language": "en-US,en;q=0.9",
                                "Accept": "text/html,*/*;q=0.8"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_market(name, timeout=30):
    """Fetch + parse one market's chart. Returns {date: jodi} or raises."""
    url = MARKET_CHARTS[name]
    return parse_panel_chart(fetch_html(url, timeout=timeout))


if __name__ == "__main__":
    # quick reachability + parse smoke test for a couple of markets
    import sys
    names = sys.argv[1:] or ["Kalyan", "Sita Morning"]
    for n in names:
        try:
            data = fetch_market(n)
            last = sorted(data)[-5:]
            print(f"OK   {n}: {len(data)} days, latest -> "
                  + ", ".join(f"{d}={data[d]}" for d in last))
        except Exception as e:
            print(f"FAIL {n}: {type(e).__name__}: {e}")
