// NFL Golf — export the AFL (1960-69) and AAFC (1946-49) seasons, which PFR keeps on separate pages
// (/years/1965_AFL/...). Same output shape as pfr-export-seasons.js, keyed "1965_AFL", in one file:
// pfr_seasons_afl_aafc.json. About 112 pages, ~7 minutes.
// Paste into the DevTools console of a pro-football-reference.com tab that has passed the bot check.
// It walks seasons from FROM down to TO, fetching one page every 3.6 s (under PFR's 20-per-minute
// limit). Every 10 seasons it downloads a file named pfr_seasons_<first>-<last>.json, so a stop
// part-way loses little. If it stops, set FROM to the season it names and paste it again.
(async () => {
  const SEASONS = [
    ...Array.from({ length: 10 }, (_, i) => `${1969 - i}_AFL`),
    ...Array.from({ length: 4 }, (_, i) => `${1949 - i}_AAFC`),
  ];
  const PAGES = ["passing", "rushing", "receiving", "defense", "kicking", "punting", "returns", "scoring"];
  const GAP = 3600;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const say = (...a) => console.warn("[NFL Golf]", ...a); // PFR's scripts silence console.log
  const save = (data, name) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: "application/json" }));
    a.download = name;
    a.click();
  };

  const grab = async (year, page) => {
    const res = await fetch(`/years/${year}/${page}.htm`, { credentials: "include" });
    if (res.status === 404) return null;
    if (!res.ok) throw Object.assign(new Error("HTTP " + res.status), { fatal: true });
    const html = (await res.text()).replace(/<!--|-->/g, ""); // PFR hides some tables in comments
    const doc = new DOMParser().parseFromString(html, "text/html");
    const table = [...doc.querySelectorAll("table")]
      .filter((t) => t.querySelector('tbody a[href*="/players/"]'))
      .sort((a, b) => b.rows.length - a.rows.length)[0];
    if (!table) return null;
    const cols = [...(table.tHead?.rows[table.tHead.rows.length - 1]?.cells || [])].map((c) => c.dataset.stat);
    const rows = [], seen = new Set();
    for (const tr of table.querySelectorAll("tbody tr")) {
      if (tr.classList.contains("thead") || tr.classList.contains("partial_table")) continue;
      const link = tr.querySelector('a[href*="/players/"]');
      if (!link) continue;
      const id = link.getAttribute("href");
      if (seen.has(id)) continue; // a multi-team player's combined row comes first
      seen.add(id);
      const byStat = {};
      for (const c of tr.cells) byStat[c.dataset.stat] = c.textContent.trim();
      rows.push([id, link.textContent.trim(), ...cols.map((s) => byStat[s] ?? "")]);
    }
    return { cols, rows };
  };

  const total = SEASONS.length * PAGES.length;
  say(`Exporting ${SEASONS.length} AFL/AAFC seasons: ${total} pages, about ${Math.ceil(total * GAP / 60000)} min. Keep this tab open.`);
  const all = {};
  let done = 0;
  for (const year of SEASONS) {
    all[year] = {};
    for (const page of PAGES) {
      try {
        const t = await grab(year, page);
        if (t) all[year][page] = t;
        say(`✓ ${year} ${page}: ${t ? t.rows.length + " players" : "none"}  (${++done}/${total})`);
      } catch (e) {
        save(all, "pfr_seasons_afl_aafc_partial.json");
        say(`✗ Stopped at ${year} ${page} (${e.message}). Saved what we had as pfr_seasons_afl_aafc_partial.json.`);
        return;
      }
      await sleep(GAP);
    }
  }
  save(all, "pfr_seasons_afl_aafc.json");
  say("Saved pfr_seasons_afl_aafc.json");
  say("All done.");
})();
