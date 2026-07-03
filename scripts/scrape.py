#!/usr/bin/env python3
"""Scrape 2026 FIFA World Cup match results from Wikipedia.

Fetches wikitext for the 12 group pages plus the knockout-stage page,
parses every {{#invoke:football box|main|...}} template, and writes
docs/results.json.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import mwparserfromhell
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "results.json"
WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WorldCupSweepstake/1.0 (https://github.com/; family sweepstake tracker)"

GROUP_PAGES = [f"2026_FIFA_World_Cup_Group_{c}" for c in "ABCDEFGHIJKL"]
KNOCKOUT_PAGES = [
    "2026_FIFA_World_Cup_round_of_32",
    "2026_FIFA_World_Cup_knockout_stage",
    "2026_FIFA_World_Cup_final",
]

# FIFA 3-letter codes → display name (matches what we use in players.json).
FIFA_CODES: dict[str, str] = {
    "MEX": "Mexico", "SUI": "Switzerland", "BRA": "Brazil", "USA": "USA",
    "GER": "Germany", "NED": "Netherlands", "BEL": "Belgium", "ESP": "Spain",
    "FRA": "France", "ARG": "Argentina", "POR": "Portugal", "ENG": "England",
    "CZE": "Czechia", "CAN": "Canada", "MAR": "Morocco", "TUR": "Turkey",
    "ECU": "Ecuador", "JPN": "Japan", "EGY": "Egypt", "URU": "Uruguay",
    "NOR": "Norway", "AUT": "Austria", "COL": "Colombia", "CRO": "Croatia",
    "KOR": "South Korea", "BIH": "Bosnia and Herzegovina", "SCO": "Scotland",
    "PAR": "Paraguay", "CIV": "Ivory Coast", "SWE": "Sweden", "IRN": "Iran",
    "KSA": "Saudi Arabia", "SEN": "Senegal", "ALG": "Algeria", "COD": "DR Congo",
    "GHA": "Ghana", "RSA": "South Africa", "QAT": "Qatar", "HAI": "Haiti",
    "AUS": "Australia", "CUW": "Curacao", "TUN": "Tunisia", "NZL": "New Zealand",
    "CPV": "Cape Verde", "IRQ": "Iraq", "JOR": "Jordan", "UZB": "Uzbekistan",
    "PAN": "Panama",
}

SCORE_RE = re.compile(r"(\d+)\s*[–—\-]\s*(\d+)")


def fetch_wikitext(page: str) -> str | None:
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
    }
    backoffs = [2, 5, 15]
    for attempt, wait in enumerate([0, *backoffs]):
        if wait:
            time.sleep(wait)
        r = requests.get(
            WIKI_API, params=params,
            headers={"User-Agent": USER_AGENT}, timeout=30,
        )
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == len(backoffs):
                r.raise_for_status()
            retry_after = r.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(min(int(retry_after), 30))
            print(f"  WARN: {page} → HTTP {r.status_code}, retrying", file=sys.stderr)
            continue
        r.raise_for_status()
        break
    data = r.json()
    if "error" in data:
        print(f"  WARN: {page} → {data['error'].get('info')}", file=sys.stderr)
        return None
    return data.get("parse", {}).get("wikitext")


def extract_country(value) -> str | None:
    """Extract country from a team1/team2 wikicode value.

    Examples:
        {{#invoke:flag|fb-rt|MEX}}     → Mexico
        {{flagicon|RSA}} [[...|South Africa]] → South Africa
    """
    text = str(value)
    # Try FIFA-code-bearing templates first
    for code in re.findall(r"\b([A-Z]{3})\b", text):
        if code in FIFA_CODES:
            return FIFA_CODES[code]
    return None


def extract_score(value) -> tuple[int | None, int | None]:
    text = str(value)
    m = SCORE_RE.search(text)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def parse_date(value) -> str | None:
    """Pull YYYY-MM-DD from a date param like {{Start date|2026|6|11}} or '11 June 2026'."""
    text = str(value)
    m = re.search(r"\{\{[Ss]tart date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # Fall back to free text dates
    for fmt in ("%d %B %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(re.sub(r"<[^>]+>", "", text).strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def stage_for_page(page: str) -> str:
    if "Group_" in page:
        return f"group_{page[-1]}"
    if "round_of_32" in page:
        return "round_of_32"
    if "knockout" in page:
        return "knockout"  # refined per-template below
    if "final" in page:
        return "final"
    return "other"


def refine_knockout_stage(wikitext: str, template_offset: int) -> str:
    """Knockout page has section headings; pick the most recent one before the template."""
    # find the last "==... ==" before this offset
    headings = list(re.finditer(r"==+\s*([^=]+?)\s*==+", wikitext[:template_offset]))
    if not headings:
        return "knockout"
    last = headings[-1].group(1).strip().lower()
    mapping = {
        "round of 32": "round_of_32",
        "round of 16": "round_of_16",
        "quarter-finals": "quarter_finals",
        "quarter finals": "quarter_finals",
        "semi-finals": "semi_finals",
        "semi finals": "semi_finals",
        "third place play-off": "third_place",
        "match for third place": "third_place",
        "third place": "third_place",
        "final": "final",
    }
    for k, v in mapping.items():
        if k in last:
            return v
    return "knockout"


def parse_page(page: str, wikitext: str) -> list[dict]:
    code = mwparserfromhell.parse(wikitext)
    matches: list[dict] = []
    for tpl in code.filter_templates():
        name = str(tpl.name).strip().lower()
        # Match either {{#invoke:football box|main}} or {{footballbox}} variants.
        if "football box" not in name and "footballbox" not in name:
            continue
        try:
            team1_raw = tpl.get("team1").value if tpl.has("team1") else ""
            team2_raw = tpl.get("team2").value if tpl.has("team2") else ""
            team1 = extract_country(team1_raw)
            team2 = extract_country(team2_raw)
            if not team1 or not team2:
                continue
            score_raw = tpl.get("score").value if tpl.has("score") else ""
            s1, s2 = extract_score(score_raw)
            completed = s1 is not None
            date = None
            if tpl.has("date"):
                date = parse_date(tpl.get("date").value)
            time = None
            if tpl.has("time"):
                # strip wikilinks/templates from the kickoff-time string
                time_str = str(tpl.get("time").value)
                time_str = re.sub(r"<[^>]+>", "", time_str)               # strip HTML tags
                time_str = re.sub(r"\[\[[^\]]*?\|([^\]]+)\]\]", r"\1", time_str)
                time_str = re.sub(r"\[\[([^\]]+)\]\]", r"\1", time_str)
                time_str = re.sub(r"\{\{[^}]+\}\}", "", time_str)
                time_str = re.sub(r"&nbsp;", " ", time_str)
                time_str = re.sub(r"\s+", " ", time_str).strip()
                time = time_str if time_str else None
            stadium = None
            if tpl.has("stadium"):
                stadium_str = str(tpl.get("stadium").value)
                # extract first wikilink display value, fallback to plain text
                m = re.search(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]", stadium_str)
                if m:
                    stadium = (m.group(2) or m.group(1)).strip()
                else:
                    stadium = re.sub(r"\{\{[^}]+\}\}", "", stadium_str).strip(" ,")
                stadium = stadium or None
            pens1 = pens2 = None
            winner_pens = None
            # Penalty shootout: usually {{#invoke:football box|main|...|aet=yes|penaltyscore=4–3|penalties1=...|penalties2=...}}
            if tpl.has("penaltyscore"):
                p1, p2 = extract_score(tpl.get("penaltyscore").value)
                pens1, pens2 = p1, p2
            elif tpl.has("penalties1") and tpl.has("penalties2"):
                # penalties1/penalties2 list the takers; penaltyscore should be present too
                pass
            if pens1 is not None and pens2 is not None:
                winner_pens = team1 if pens1 > pens2 else team2 if pens2 > pens1 else None
            stage = stage_for_page(page)
            if stage == "knockout":
                stage = refine_knockout_stage(wikitext, wikitext.find(str(tpl)))
            matches.append({
                "stage": stage,
                "date": date,
                "time": time,
                "stadium": stadium,
                "team1": team1,
                "team2": team2,
                "score1": s1,
                "score2": s2,
                "pens1": pens1,
                "pens2": pens2,
                "winner_pens": winner_pens,
                "completed": completed,
            })
        except Exception as e:
            print(f"  WARN: failed to parse a template in {page}: {e}", file=sys.stderr)
    return matches


def main() -> int:
    all_matches: list[dict] = []
    seen: set[tuple] = set()
    for page in GROUP_PAGES + KNOCKOUT_PAGES:
        print(f"Fetching {page}...")
        wt = fetch_wikitext(page)
        if not wt:
            continue
        page_matches = parse_page(page, wt)
        for m in page_matches:
            key = (m["team1"], m["team2"], m["date"])
            if key in seen:
                continue
            seen.add(key)
            all_matches.append(m)
        print(f"  → {len(page_matches)} match(es)")
        time.sleep(0.5)  # be polite to Wikipedia

    completed = [m for m in all_matches if m["completed"]]
    upcoming = [m for m in all_matches if not m["completed"]]
    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "match_count": len(completed),
        "upcoming_count": len(upcoming),
        "matches": completed,
        "upcoming": upcoming,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {OUT} ({len(all_matches)} matches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
