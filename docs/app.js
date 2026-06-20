"use strict";

// Country → flag emoji map for all 48 WC 2026 teams
const FLAGS = {
  "Mexico": "🇲🇽", "Switzerland": "🇨🇭", "Brazil": "🇧🇷", "USA": "🇺🇸",
  "Germany": "🇩🇪", "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Spain": "🇪🇸",
  "France": "🇫🇷", "Argentina": "🇦🇷", "Portugal": "🇵🇹", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  "Czechia": "🇨🇿", "Canada": "🇨🇦", "Morocco": "🇲🇦", "Turkey": "🇹🇷",
  "Ecuador": "🇪🇨", "Japan": "🇯🇵", "Egypt": "🇪🇬", "Uruguay": "🇺🇾",
  "Norway": "🇳🇴", "Austria": "🇦🇹", "Colombia": "🇨🇴", "Croatia": "🇭🇷",
  "South Korea": "🇰🇷", "Bosnia and Herzegovina": "🇧🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  "Paraguay": "🇵🇾", "Ivory Coast": "🇨🇮", "Sweden": "🇸🇪", "Iran": "🇮🇷",
  "Saudi Arabia": "🇸🇦", "Senegal": "🇸🇳", "Algeria": "🇩🇿", "DR Congo": "🇨🇩",
  "Ghana": "🇬🇭", "South Africa": "🇿🇦", "Qatar": "🇶🇦", "Haiti": "🇭🇹",
  "Australia": "🇦🇺", "Curacao": "🇨🇼", "Tunisia": "🇹🇳", "New Zealand": "🇳🇿",
  "Cape Verde": "🇨🇻", "Iraq": "🇮🇶", "Jordan": "🇯🇴", "Uzbekistan": "🇺🇿",
  "Panama": "🇵🇦",
};

const flag = (team) => FLAGS[team] || "⚽";

// Stable colour per player (works on dark bg)
const PLAYER_COLORS = {
  "Alec":   "#ef4444",
  "Dad":    "#f97316",
  "Henry":  "#eab308",
  "Jemima": "#84cc16",
  "Jess":   "#10b981",
  "Jodie":  "#06b6d4",
  "Meg":    "#3b82f6",
  "Monty":  "#8b5cf6",
  "Mum":    "#f5b800",
  "Sam":    "#ec4899",
};
const colorFor = (p) => PLAYER_COLORS[p] || "#9ca3af";

async function load() {
  const lb = await fetch("leaderboard.json", { cache: "no-store" }).then(r => r.json());
  const rs = await fetch("results.json",     { cache: "no-store" }).then(r => r.json());
  let hist = null;
  try {
    hist = await fetch("history.json", { cache: "no-store" }).then(r => r.ok ? r.json() : null);
  } catch (e) { hist = null; }
  render(lb, rs, hist);
}

const fmtPts = (n) => (n > 0 ? `+${n}` : `${n}`);
const ptsClass = (n) => (n > 0 ? "points-pos" : n < 0 ? "points-neg" : "");

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
}
function fmtUpdated(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
function medal(rank) {
  const cls = rank <= 3 ? `medal-${rank}` : "medal-x";
  const txt = rank <= 3 ? (rank === 1 ? "🏆" : rank === 2 ? "2" : "3") : rank;
  return `<span class="medal ${cls}">${txt}</span>`;
}

function renderHistoryChart(hist, leaderboard) {
  const meta = document.getElementById("history-meta");
  if (!hist || !hist.history || hist.history.length === 0) {
    meta.textContent = "no history yet";
    return;
  }
  const labels = hist.history.map(e => e.date);
  // Order datasets by current rank so the leader's line stacks on top in tooltips
  const orderedPlayers = leaderboard.map(r => r.player);
  const datasets = orderedPlayers.map(player => ({
    label: player,
    data: hist.history.map(e => e.scores[player] ?? null),
    borderColor: colorFor(player),
    backgroundColor: colorFor(player) + "33",
    borderWidth: 2,
    pointRadius: 2,
    pointHoverRadius: 5,
    tension: 0.25,
    spanGaps: true,
  }));
  meta.textContent = `${hist.history.length} day(s)`;

  const ctx = document.getElementById("history-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (window._historyChart) window._historyChart.destroy();
  window._historyChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#ecf2ee",
            usePointStyle: true,
            pointStyle: "circle",
            padding: 10,
            font: { size: 11 },
          },
        },
        tooltip: {
          backgroundColor: "rgba(20,48,40,0.95)",
          borderColor: "rgba(245,184,0,0.4)",
          borderWidth: 1,
          titleColor: "#ffe680",
          bodyColor: "#ecf2ee",
          padding: 10,
          itemSort: (a, b) => b.parsed.y - a.parsed.y,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y > 0 ? "+" : ""}${ctx.parsed.y}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: "#8aa39a",
            callback: (val, idx) => {
              const iso = labels[idx];
              if (!iso) return "";
              const d = new Date(iso + "T00:00:00Z");
              return d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
            },
          },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
        y: {
          ticks: { color: "#8aa39a" },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
      },
    },
  });
}

function render(data, results, hist) {
  document.getElementById("meta").textContent =
    `${data.match_count} matches played · last updated ${fmtUpdated(data.updated_at)}`;

  // Leaderboard
  const tbody = document.querySelector("#leaderboard tbody");
  tbody.innerHTML = data.leaderboard.map(row => {
    const played = row.teams.reduce((a, t) => a + (t.matches_played > 0 ? 1 : 0), 0);
    return `
      <tr>
        <td class="pos">${medal(row.rank)}</td>
        <td class="player">${row.player}</td>
        <td class="num points ${ptsClass(row.total)}">${fmtPts(row.total)}</td>
        <td class="num">${played}/${row.teams.length}</td>
      </tr>`;
  }).join("");

  // Per-player cards
  const players = document.getElementById("players");
  players.innerHTML = data.leaderboard.map(row => {
    const teamRows = row.teams.map(t => `
      <tr>
        <td><span class="flag">${flag(t.team)}</span><span class="tier tier-${t.tier}">T${t.tier}</span> ${t.team}${t.bonus ? ' <span class="bonus-tag">BONUS</span>' : ''}</td>
        <td class="num">${t.matches_played}</td>
        <td class="num">${t.goals_for}</td>
        <td class="num">${t.goals_against}</td>
        <td class="num">${t.pen_wins ? "+" + t.pen_wins : "—"}</td>
        <td class="num">${t.pen_losses ? "-" + t.pen_losses : "—"}</td>
        <td class="num ${ptsClass(t.points)}"><strong>${fmtPts(t.points)}</strong></td>
      </tr>`).join("");
    return `
      <details class="player-card" ${row.rank === 1 ? "open" : ""}>
        <summary>
          <div class="left">${medal(row.rank)} <span class="name">${row.player}</span></div>
          <span class="total ${ptsClass(row.total)}">${fmtPts(row.total)}</span>
        </summary>
        <div class="team-table">
          <table>
            <thead><tr><th>Team</th><th class="num">MP</th><th class="num">GF</th><th class="num">GA</th><th class="num">P+</th><th class="num">P-</th><th class="num">Pts</th></tr></thead>
            <tbody>${teamRows}</tbody>
          </table>
        </div>
      </details>`;
  }).join("");

  // Recent results
  const ul = document.getElementById("results");
  const recent = [...(results.matches || [])]
    .sort((a, b) => (b.date || "").localeCompare(a.date || ""))
    .slice(0, 12);
  ul.innerHTML = recent.map(m => {
    const hasPens = m.pens1 != null && m.pens2 != null;
    const pens = hasPens ? `<span class="pens">(${m.pens1}–${m.pens2} pens)</span>` : "";
    return `
      <li class="${hasPens ? "pens-w" : ""}">
        <span class="date">${fmtDate(m.date)}</span>
        <span class="t1">${m.team1} <span class="flag">${flag(m.team1)}</span></span>
        <span class="score">${m.score1}–${m.score2}</span>
        <span class="t2"><span class="flag">${flag(m.team2)}</span> ${m.team2}${pens}</span>
      </li>`;
  }).join("");

  // Upcoming matches
  const upUl = document.getElementById("upcoming");
  const upMeta = document.getElementById("upcoming-meta");
  const teamsMeta = data.teams || {};
  const owners = data.team_owners || {};
  const oddsLabel = (team) => {
    const o = teamsMeta[team]?.odds;
    return o != null ? `<span class="odds">${o}/1</span>` : "";
  };
  const ownersLabel = (team) => {
    const list = owners[team] || [];
    if (list.length === 0) return `<span class="owner-line muted">unowned</span>`;
    return `<span class="owner-line">${list.map(o => o.player).join(", ")}</span>`;
  };
  const upcomingAll = [...(results.upcoming || [])].sort((a, b) =>
    ((a.date || "9999") + (a.time || "")).localeCompare((b.date || "9999") + (b.time || ""))
  );
  upMeta.textContent = `${upcomingAll.length} fixtures left`;
  const next = upcomingAll.slice(0, 10);
  upUl.innerHTML = next.length === 0
    ? `<li class="empty">No upcoming fixtures parsed yet.</li>`
    : next.map(m => `
      <li class="upcoming-row">
        <span class="date">${fmtDate(m.date)}${m.time ? " · " + m.time : ""}</span>
        <span class="t1">
          <span class="team-name">${m.team1} <span class="flag">${flag(m.team1)}</span> ${oddsLabel(m.team1)}</span>
          <span class="owners">${ownersLabel(m.team1)}</span>
        </span>
        <span class="vs">vs</span>
        <span class="t2">
          <span class="team-name"><span class="flag">${flag(m.team2)}</span> ${m.team2} ${oddsLabel(m.team2)}</span>
          <span class="owners">${ownersLabel(m.team2)}</span>
        </span>
        ${m.stadium ? `<span class="stadium">@ ${m.stadium}</span>` : ""}
      </li>`).join("");

  // Rules table
  const rulesBody = document.querySelector("#rules tbody");
  rulesBody.innerHTML = [1, 2, 3, 4].map(tier => {
    const r = data.scoring.tiers[tier];
    return `
      <tr>
        <td><span class="tier tier-${tier}">T${tier}</span></td>
        <td class="num points-pos">+${r.goal_for}</td>
        <td class="num points-neg">${r.goal_against}</td>
      </tr>`;
  }).join("");

  const notes = [...(data.scoring.notes || [])];
  notes.push(`Penalty shootout: win = +${data.scoring.penalty_shootout_win}, loss = ${data.scoring.penalty_shootout_loss}.`);
  document.getElementById("rules-notes").innerHTML = notes.map(n => `· ${n}`).join("<br>");

  renderHistoryChart(hist, data.leaderboard);
}

load().catch(err => {
  document.getElementById("meta").textContent = "Error loading data: " + err.message;
});
