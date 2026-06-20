"use strict";

async function load() {
  const res = await fetch("leaderboard.json", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load leaderboard.json");
  const data = await res.json();
  const results = await fetch("results.json", { cache: "no-store" }).then(r => r.json());
  render(data, results);
}

function fmtPts(n) {
  return n > 0 ? `+${n}` : `${n}`;
}

function ptsClass(n) {
  if (n > 0) return "points-pos";
  if (n < 0) return "points-neg";
  return "";
}

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

function render(data, results) {
  // Meta line
  const meta = document.getElementById("meta");
  meta.textContent = `Last updated ${fmtUpdated(data.updated_at)} · ${data.match_count} matches played`;

  // Leaderboard
  const tbody = document.querySelector("#leaderboard tbody");
  tbody.innerHTML = "";
  for (const row of data.leaderboard) {
    const teamsPlayed = row.teams.reduce((a, t) => a + (t.matches_played > 0 ? 1 : 0), 0);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.rank}</td>
      <td>${row.player}</td>
      <td class="num points ${ptsClass(row.total)}">${fmtPts(row.total)}</td>
      <td class="num">${teamsPlayed}/${row.teams.length}</td>
    `;
    tbody.appendChild(tr);
  }

  // Per-player breakdown
  const players = document.getElementById("players");
  players.innerHTML = "";
  for (const row of data.leaderboard) {
    const det = document.createElement("details");
    det.className = "player-card";
    det.open = row.rank === 1;
    const teamRows = row.teams.map(t => `
      <tr>
        <td><span class="tier tier-${t.tier}">T${t.tier}</span> ${t.team}</td>
        <td class="num">${t.matches_played}</td>
        <td class="num">${t.goals_for}</td>
        <td class="num">${t.goals_against}</td>
        <td class="num">${t.pen_wins ? "+" + t.pen_wins : "—"}</td>
        <td class="num">${t.pen_losses ? "-" + t.pen_losses : "—"}</td>
        <td class="num ${ptsClass(t.points)}"><strong>${fmtPts(t.points)}</strong></td>
      </tr>`).join("");
    det.innerHTML = `
      <summary>
        <span><strong>#${row.rank}</strong> · <span class="name">${row.player}</span></span>
        <span class="total ${ptsClass(row.total)}">${fmtPts(row.total)}</span>
      </summary>
      <div class="team-table">
        <table>
          <thead><tr><th>Team</th><th class="num">MP</th><th class="num">GF</th><th class="num">GA</th><th class="num">P+</th><th class="num">P-</th><th class="num">Pts</th></tr></thead>
          <tbody>${teamRows}</tbody>
        </table>
      </div>
    `;
    players.appendChild(det);
  }

  // Recent results
  const ul = document.getElementById("results");
  ul.innerHTML = "";
  const recent = [...(results.matches || [])]
    .sort((a, b) => (b.date || "").localeCompare(a.date || ""))
    .slice(0, 12);
  for (const m of recent) {
    const pens = (m.pens1 != null && m.pens2 != null)
      ? `<span class="pens">(${m.pens1}–${m.pens2} pens)</span>` : "";
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="date">${fmtDate(m.date)}</span>
      <span class="t1">${m.team1}</span>
      <span class="score">${m.score1}–${m.score2}</span>
      <span class="t2">${m.team2} ${pens}</span>
    `;
    ul.appendChild(li);
  }

  // Rules table
  const rulesBody = document.querySelector("#rules tbody");
  rulesBody.innerHTML = "";
  for (const tier of [1, 2, 3, 4]) {
    const r = data.scoring.tiers[tier];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="tier tier-${tier}">T${tier}</span></td>
      <td class="num points-pos">+${r.goal_for}</td>
      <td class="num points-neg">${r.goal_against}</td>
    `;
    rulesBody.appendChild(tr);
  }
  const notes = data.scoring.notes || [];
  notes.push(`Penalty shootout: win = +${data.scoring.penalty_shootout_win}, loss = ${data.scoring.penalty_shootout_loss}.`);
  document.getElementById("rules-notes").innerHTML = notes.map(n => `· ${n}`).join("<br>");
}

load().catch(err => {
  document.getElementById("meta").textContent = "Error loading data: " + err.message;
});
