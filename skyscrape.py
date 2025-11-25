import requests
from bs4 import BeautifulSoup
import sqlite3
import re
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0"}

def parse_date_label(label: str) -> str | None:
    """
    Convert strings like 'Thu 4th December' -> '2025-12-04' (ISO),
    assuming the current year.
    """
    parts = label.split()
    if len(parts) < 3:
        return None

    # Example: "4th" -> "4"
    day_str = re.sub(r'(st|nd|rd|th)$', '', parts[1])
    month_name = parts[2]

    try:
        day = int(day_str)
        month = datetime.strptime(month_name, "%B").month
    except ValueError:
        return None
    
    today = datetime.today().date()
    year = today.year

    if today.month >= 8 and month < 8:
        year += 1


    try:
        dt = datetime(year, month, day).date()
        return dt.isoformat()  # 'YYYY-MM-DD'
    except ValueError:
        return None


def parse_and_insert(html: str, cursor: sqlite3.Cursor) -> int:
    soup = BeautifulSoup(html, "html.parser")
    total = 0

    # Each date heading looks like: <h3 class="text-h4 -rs-style20 box">Thu 4th December</h3>
    date_headers = soup.select("h3.text-h4.-rs-style20.box")

    for h3 in date_headers:
        raw_date_label = h3.get_text(strip=True)
        date_iso = parse_date_label(raw_date_label) or ""

        # The <div class="box"> that comes right after this h3
        box_div = h3.find_next_sibling("div", class_="box")
        if not box_div:
            continue

        # Inside that box, each div.event-group contains one match
        event_groups = box_div.select("div.event-group.-layout1")

        for group in event_groups:
            ul = group.find("ul", class_="row-table event")
            if not ul:
                continue

            lis = ul.find_all("li")
            if len(lis) < 3:
                continue

            home_team = lis[0].get_text(strip=True)
            kickoff_time = lis[1].get_text(strip=True)
            away_team = lis[2].get_text(strip=True)

            # p.event-detail inside the same group
            detail_p = group.find("p", class_="event-detail")
            competition = ""
            channel = ""

            if detail_p:
                raw = detail_p.get_text(strip=True)
                parts = raw.split(",", 1)
                competition = parts[0].strip()
                if len(parts) > 1:
                    channel = parts[1].strip()

            cursor.execute(
                """
                INSERT OR IGNORE INTO matches (date, home_team, away_team, time, competition, channel)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (date_iso, home_team, away_team, kickoff_time, competition, channel),
            )

            total += 1

    return total


# --- main scraping driver ---

conn = sqlite3.connect("football.db")
cursor = conn.cursor()


total_inserted = 0

# 1) Main page
main_url = "https://www.skysports.com/watch/football-on-sky"
resp = requests.get(main_url, headers=HEADERS)
resp.raise_for_status()
total_inserted += parse_and_insert(resp.text, cursor)

# 2) “Load more” pages – loop over a bunch of future dates
today = datetime.today().date()

for offset in range(0, 300):
    d = today + timedelta(days=offset)
    datestr = d.strftime("%Y%m%d")
    more_url = f"https://www.skysports.com/watch/liveonsky/more/football/{datestr}"

    r = requests.get(more_url, headers=HEADERS)
    if r.status_code != 200:
        continue

    total_inserted += parse_and_insert(r.text, cursor)

conn.commit()
conn.close()

print(f"Inserted {total_inserted} matches into the database.")
