# Crawford World Cup 2026 Sweepstake

Live leaderboard for the 10-person family World Cup 2026 sweepstake. Auto-updates every 30 minutes from Wikipedia.

## What it does

1. **Scraper** (`scripts/scrape.py`) fetches match results from Wikipedia's per-group + knockout pages, parses the `{{#invoke:football box|main}}` templates, writes `docs/results.json`.
2. **Scorer** (`scripts/score.py`) combines results × player picks × scoring rules → `docs/leaderboard.json`.
3. **Frontend** (`docs/`) is a static HTML/JS page that reads `leaderboard.json`. No build step.
4. **GitHub Action** runs steps 1–2 on a 30-minute cron and commits the JSON. GitHub Pages auto-redeploys.

## Files

```
WorldCup/
├── data/
│   ├── players.json       # 10 players × 4 teams × tier (1–4)
│   └── scoring.json       # tier → +/- per goal; penalty shootout rules
├── scripts/
│   ├── scrape.py
│   ├── score.py
│   └── requirements.txt
├── docs/                  # GitHub Pages root
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── results.json       # generated
│   └── leaderboard.json   # generated
└── .github/workflows/update.yml
```

## Scoring rules

| Tier | Goal scored | Goal conceded |
|:----:|:-----------:|:-------------:|
| 1    | +1          | −4            |
| 2    | +2          | −3            |
| 3    | +3          | −2            |
| 4    | +4          | −1            |

Plus **+3** for winning a penalty shootout, **−3** for losing one. Shootout goals don't count. Third-place playoff counts.

## Run locally

```bash
pip install -r scripts/requirements.txt
python scripts/scrape.py    # writes docs/results.json
python scripts/score.py     # writes docs/leaderboard.json
python -m http.server -d docs 8000
# open http://localhost:8000
```

## Deploy to GitHub Pages (one-time)

```bash
cd /Users/montycrawford/WorldCup
git init -b main
git add .
git commit -m "Initial sweepstake tracker"

# Create the public repo and push (requires gh auth login)
gh repo create worldcup-2026 --public --source=. --push

# Enable GitHub Pages: Settings → Pages → Source = Deploy from a branch,
# Branch = main, Folder = /docs. Save.
# (CLI shortcut, if your gh version supports pages edit:)
# gh api -X POST repos/:owner/worldcup-2026/pages -f source[branch]=main -f source[path]=/docs

# Trigger the first scheduled job manually:
gh workflow run update.yml
```

Live site: **https://monty13549.github.io/WorldCup/**

The cron runs every 30 min during the tournament. To force an immediate refresh:

```bash
gh workflow run update.yml --repo Monty13549/WorldCup
```

## Editing player picks

Edit `data/players.json`, commit, push. The next scheduled run picks it up. Field shape:

```json
{"name": "Monty", "teams": [{"team": "Netherlands", "tier": 1}, ...]}
```

`tier` is 1–4 (driving the scoring). `team` must match what Wikipedia uses — see `team_aliases` in `players.json` for the few normalisations (Turkey ↔ Türkiye, Czechia ↔ Czech Republic, etc).

## Caveats

- Scraper relies on Wikipedia's `football box` template format. Stable in practice but not contractually guaranteed; if a match goes missing, check the template parameters on that match's section.
- Penalty shootouts: parser reads `penaltyscore` parameter. Rare edge cases may miss until knockout stage starts and we can verify against a real match.
- "Mum"/"Dad" are the player names from the screenshot; rename in `players.json` if you want.
