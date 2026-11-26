// NFL Golf — Pro Football Reference QB wins exporter.
// Paste into the DevTools console of any pro-football-reference.com tab. Downloads pfr_qb_wins.json
// containing every table on /friv/qb-wins.htm, with each cell keyed by PFR's data-stat column name.
(async () => {
  const res = await fetch("/friv/qb-wins.htm", { credentials: "include" });
  if (!res.ok) { console.warn("QB wins page failed: HTTP " + res.status); return; }
  const html = (await res.text()).replace(/<!--|-->/g, "");
  const doc = new DOMParser().parseFromString(html, "text/html");
  const tables = [...doc.querySelectorAll("table")].map((t) => ({
    id: t.id,
    caption: t.querySelector("caption")?.textContent.trim(),
    headers: [...(t.tHead?.rows[t.tHead.rows.length - 1]?.cells || [])].map((c) => ({ stat: c.dataset.stat, text: c.textContent.trim() })),
    rows: [...t.querySelectorAll("tbody tr")].filter((tr) => !tr.classList.contains("thead")).map((tr) => {
      const o = {};
      for (const c of tr.cells) {
        o[c.dataset.stat || "_" + c.cellIndex] = c.textContent.trim();
        const a = c.querySelector('a[href*="/players/"]');
        if (a) o._playerId = a.getAttribute("href");
      }
      return o;
    }),
  }));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify({ title: doc.querySelector("h1")?.textContent.trim(), retrieved: new Date().toISOString(), tables })], { type: "application/json" }));
  a.download = "pfr_qb_wins.json";
  a.click();
  console.log("Done:", tables.map((t) => `${t.id || "table"} (${t.rows.length} rows)`).join(", "));
})();
