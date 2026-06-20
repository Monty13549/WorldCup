#!/usr/bin/env python3
"""Compute the leaderboard from scraped results + player picks.

Inputs:
  data/players.json
  data/scoring.json
  docs/results.json

Output:
  docs/leaderboard.json
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


def normalize(name: str, aliases: dict[str, list[str]]) -> str:
    """Map a Wikipedia-extracted team name back to the canonical name in players.json."""
    for canonical, alts in aliases.items():
        if name == canonical or name in alts:
            return canonical
    return name


def main() -> int:
    players_doc = json.loads(PLAYERS.read_text())
    scoring = json.loads(SCORING.read_text())
    results = json.loads(RESULTS.read_text())

    aliases = players_doc.get("team_aliases", {})
    tier_rules = scoring["tiers"]
    pen_win = scoring["penalty_shootout_win"]
    pen_loss = scoring["penalty_shootout_loss"]

    # Per-team aggregates from results
    team_stats: dict[str, dict] = {}
    for m in results["matches"]:
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
            s = team_stats.setdefault(team, {
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

    # Build leaderboard
    leaderboard = []
    for player in players_doc["players"]:
        teams = []
        total = 0
        for pick in player["teams"]:
            tier = str(pick["tier"])
            rule = tier_rules[tier]
            stats = team_stats.get(pick["team"], {
                "goals_for": 0, "goals_against": 0,
                "pen_wins": 0, "pen_losses": 0, "matches_played": 0,
            })
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
        leaderboard.append({
            "player": player["name"],
            "total": total,
            "teams": teams,
        })

    leaderboard.sort(key=lambda x: x["total"], reverse=True)
    for i, row in enumerate(leaderboard, 1):
        row["rank"] = i

    teams_doc = json.loads(TEAMS.read_text()) if TEAMS.exists() else {"teams": {}}
    teams_meta = teams_doc.get("teams", {})

    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "results_updated_at": results.get("updated_at"),
        "match_count": results.get("match_count"),
        "upcoming_count": results.get("upcoming_count", 0),
        "scoring": scoring,
        "teams": teams_meta,
        "leaderboard": leaderboard,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT}")
    print()
    print(f"{'Rank':<5}{'Player':<10}{'Pts':>6}")
    for row in leaderboard:
        print(f"{row['rank']:<5}{row['player']:<10}{row['total']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
