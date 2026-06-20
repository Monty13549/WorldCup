#!/usr/bin/env python3
"""Compute the leaderboard from scraped results + player picks.

Inputs:
  data/players.json
  data/scoring.json
  data/teams.json
  docs/results.json

Outputs:
  docs/leaderboard.json
  docs/history.json   (one snapshot per tournament date)
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYERS = ROOT / "data" / "players.json"
SCORING = ROOT / "data" / "scoring.json"
TEAMS   = ROOT / "data" / "teams.json"
RESULTS = ROOT / "docs" / "results.json"
OUT = ROOT / "docs" / "leaderboard.json"
HISTORY = ROOT / "docs" / "history.json"


def normalize(name: str, aliases: dict[str, list[str]]) -> str:
    """Map a Wikipedia-extracted team name back to the canonical name in players.json."""
    for canonical, alts in aliases.items():
        if name == canonical or name in alts:
            return canonical
    return name


def aggregate_team_stats(matches, aliases):
    """Walk matches → per-team {goals_for, goals_against, pen_wins, pen_losses, matches_played}."""
    stats: dict[str, dict] = {}
    for m in matches:
        t1 = normalize(m["team1"], aliases)
        t2 = normalize(m["team2"], aliases)
        for team, gf, ga, won_pens, lost_pens in [
            (t1, m["score1"], m["score2"],
             m["winner_pens"] == m["team1"],
             m["pens1"] is not None and m["winner_pens"] == m["team2"]),
            (t2, m["score2"], m["score1"],
             m["winner_pens"] == m["team2"],
             m["pens2"] is not None and m["winner_pens"] == m["team1"]),
        ]:
            s = stats.setdefault(team, {
                "goals_for": 0, "goals_against": 0,
                "pen_wins": 0, "pen_losses": 0, "matches_played": 0,
            })
            s["goals_for"] += gf
            s["goals_against"] += ga
            s["matches_played"] += 1
            if won_pens:
                s["pen_wins"] += 1
            if lost_pens:
                s["pen_losses"] += 1
    return stats


def compute_leaderboard(team_stats, players_doc, scoring):
    """Return a list of {player, total, teams: [...]} ranked by total desc."""
    tier_rules = scoring["tiers"]
    pen_win = scoring["penalty_shootout_win"]
    pen_loss = scoring["penalty_shootout_loss"]
    empty = {"goals_for": 0, "goals_against": 0,
             "pen_wins": 0, "pen_losses": 0, "matches_played": 0}

    leaderboard = []
    for player in players_doc["players"]:
        teams = []
        total = 0
        for pick in player["teams"]:
            tier = str(pick["tier"])
            rule = tier_rules[tier]
            stats = team_stats.get(pick["team"], empty)
            points = (
                stats["goals_for"] * rule["goal_for"]
                + stats["goals_against"] * rule["goal_against"]
                + stats["pen_wins"] * pen_win
                + stats["pen_losses"] * pen_loss
            )
            total += points
            teams.append({
                "team": pick["team"],
                "tier": int(tier),
                "bonus": bool(pick.get("bonus", False)),
                "matches_played": stats["matches_played"],
                "goals_for": stats["goals_for"],
                "goals_against": stats["goals_against"],
                "pen_wins": stats["pen_wins"],
                "pen_losses": stats["pen_losses"],
                "points": points,
            })
        leaderboard.append({"player": player["name"], "total": total, "teams": teams})
    leaderboard.sort(key=lambda x: x["total"], reverse=True)
    for i, row in enumerate(leaderboard, 1):
        row["rank"] = i
    return leaderboard


def build_history(matches, players_doc, scoring, aliases):
    """One snapshot per unique match date (end-of-day standings)."""
    dated = [m for m in matches if m.get("date")]
    unique_dates = sorted({m["date"] for m in dated})
    history = []
    for d in unique_dates:
        through = [m for m in dated if m["date"] <= d]
        team_stats = aggregate_team_stats(through, aliases)
        lb = compute_leaderboard(team_stats, players_doc, scoring)
        history.append({
            "date": d,
            "scores": {row["player"]: row["total"] for row in lb},
        })
    return history


def main() -> int:
    players_doc = json.loads(PLAYERS.read_text())
    scoring = json.loads(SCORING.read_text())
    results = json.loads(RESULTS.read_text())

    aliases = players_doc.get("team_aliases", {})

    # Current standings
    team_stats = aggregate_team_stats(results["matches"], aliases)
    leaderboard = compute_leaderboard(team_stats, players_doc, scoring)

    teams_doc = json.loads(TEAMS.read_text()) if TEAMS.exists() else {"teams": {}}
    teams_meta = teams_doc.get("teams", {})

    team_owners: dict[str, list[dict]] = {}
    for player in players_doc["players"]:
        for pick in player["teams"]:
            team_owners.setdefault(pick["team"], []).append({
                "player": player["name"],
                "bonus": bool(pick.get("bonus", False)),
            })

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    payload = {
        "updated_at": now_iso,
        "results_updated_at": results.get("updated_at"),
        "match_count": results.get("match_count"),
        "upcoming_count": results.get("upcoming_count", 0),
        "scoring": scoring,
        "teams": teams_meta,
        "team_owners": team_owners,
        "leaderboard": leaderboard,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT}")

    # History
    history = build_history(results["matches"], players_doc, scoring, aliases)
    HISTORY.write_text(json.dumps({
        "updated_at": now_iso,
        "players": [p["name"] for p in players_doc["players"]],
        "history": history,
    }, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {HISTORY} ({len(history)} day(s))")

    print()
    print(f"{'Rank':<5}{'Player':<10}{'Pts':>6}")
    for row in leaderboard:
        print(f"{row['rank']:<5}{row['player']:<10}{row['total']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
