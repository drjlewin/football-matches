import requests
from bs4 import BeautifulSoup
import sqlite3
import re
from datetime import datetime, timedelta, date

HEADERS = {"User-Agent": "Mozilla/5.0"}

URL = "https://www.live-footballontv.com"

def parse_tnt_date(label: str) -> str | None:
    """
    Convert 'Tuesday 25th November 2025' -> '2025-11-25' (ISO).
    """
    parts = label.split()
    # Expect: [Weekday, DayWithSuffix, Month, Year]
    if len(parts) < 4:
        return None

    day_with_suffix = parts[1]       # '25th'
    month_name = parts[2]            # 'November'
    year_str = parts[3]              # '2025'

    # Strip 'st', 'nd', 'rd', 'th'
    day_str = re.sub(r'(st|nd|rd|th)$', '', day_with_suffix)

    try:
        day = int(day_str)
        month = datetime.strptime(month_name, "%B").month
        year = int(year_str)
    except ValueError:
        return None

    try:
        dt = date(year, month, day)
        return dt.isoformat()
    except ValueError:
        return None
    
def split_teams(teams_text: str) -> tuple[str, str]:
    if " v " in teams_text:
        home, away = teams_text.split(" v ", 1)
    elif " vs " in teams_text:
        home, away = teams_text.split(" vs ", 1)
    else:
        # Fallback: put whole string as home_team, leave away empty
        return teams_text.strip(), ""

    return home.strip(), away.strip()
    
def parse_and_insert_tnt(html: str, cursor: sqlite3.Cursor) -> int:
    soup = BeautifulSoup(html, "html.parser")
    total = 0

    # Each big block is a fixture-group
    groups = soup.select("div.fixture-group")

    for group in groups:
        current_date_iso = None

        # Walk through direct child divs in order: anchor, fixture-date, fixture, anchor, fixture-date, ...
        for child in group.find_all("div", recursive=False):
            classes = child.get("class", []) or []

            # If it's a date line, update the current date
            if "fixture-date" in classes:
                raw_date = child.get_text(strip=True)
                current_date_iso = parse_tnt_date(raw_date) or ""
                continue

            # If it's a fixture row, use the current date
            if "fixture" in classes:
                if not current_date_iso:
                    # Safety: skip fixtures if we somehow haven't seen a date yet
                    continue

                time_div = child.find("div", class_="fixture__time")
                teams_div = child.find("div", class_="fixture__teams")
                comp_div = child.find("div", class_="fixture__competition")
                channel_div = child.find("div", class_="fixture__channel")

                if not (time_div and teams_div):
                    continue

                kickoff_time = time_div.get_text(strip=True)
                teams_text = teams_div.get_text(strip=True)

                # reuse the split_teams() helper from before
                home_team, away_team = split_teams(teams_text)

                competition = comp_div.get_text(strip=True) if comp_div else ""
                channel = channel_div.get_text(strip=True) if channel_div else ""

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO matches (date, home_team, away_team, time, competition, channel)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (current_date_iso, home_team, away_team, kickoff_time, competition, channel),
                )

                total += 1

            # ignore other child divs like <div class="anchor"> etc.

    return total


if __name__ == "__main__":
    conn = sqlite3.connect("football.db")
    cursor = conn.cursor()

    total_inserted = 0

    resp = requests.get(URL, headers=HEADERS)
    resp.raise_for_status()

    total_inserted += parse_and_insert_tnt(resp.text, cursor)

    conn.commit()
    conn.close()

    print(f"TNT scrape complete. Inserted {total_inserted} matches (new rows only).")