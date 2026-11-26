// NFL Golf — export EVERY career leaderboard listed on pro-football-reference.com/leaders/.
// Paste into the DevTools console of a pro-football-reference.com tab that has passed the bot check.
// It reads the index, then fetches each "*_career.htm" page one every 4 seconds (under PFR's
// 20-requests-per-minute limit), keeps every column of each leaderboard row, and downloads
// pfr_all_career_leaders.json at the end. Expect several minutes; progress is logged as it goes.
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const parse = async (url) => {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const html = (await res.text()).replace(/<!--|-->/g, ""); // PFR hides some tables in comments
    return new DOMParser().parseFromString(html, "text/html");
  };

  const index = await parse("/leaders/");
  const pages = new Map();
  for (const a of index.querySelectorAll('a[href*="/leaders/"]')) {
    const path = new URL(a.getAttribute("href"), location.origin).pathname;
    if (/^\/leaders\/[a-z0-9_]+_career\.htm$/.test(path) && !pages.has(path)) pages.set(path, a.textContent.trim());
  }
  console.log(`Found ${pages.size} career leaderboards. ETA ~${Math.ceil(pages.size * 4.5 / 60)} min.`);

  const out = {}, failed = [];
  let n = 0;
  for (const [path, linkText] of pages) {
    n++;
    const key = path.replace(/^\/leaders\/|_career\.htm$/g, "");
    try {
      const doc = await parse(path);
      const table = [...doc.querySelectorAll("table")].sort((a, b) => b.rows.length - a.rows.length)[0];
      const headers = [...(table.tHead?.rows[table.tHead.rows.length - 1]?.cells || [])]
        .map((c) => ({ stat: c.dataset.stat, text: c.textContent.trim(), tip: c.getAttribute("data-tip") || "" }));
      const rows = [];
      for (const tr of table.querySelectorAll("tbody tr")) {
        const link = tr.querySelector('a[href*="/players/"]');
        if (!link) continue;
        const cells = {};
        for (const c of tr.cells) cells[c.dataset.stat || "_" + c.cellIndex] = c.textContent.trim();
        rows.push({ name: link.textContent.trim(), id: link.getAttribute("href"), cells });
      }
      out[key] = { path, linkText, title: doc.querySelector("h1")?.textContent.trim().replace(/\s+/g, " "), headers, rows };
      console.log(`✓ [${n}/${pages.size}] ${key}: ${rows.length} rows`);
    } catch (e) {
      failed.push(key);
      console.warn(`✗ [${n}/${pages.size}] ${key}: ${e.message}`);
    }
    if (n < pages.size) await sleep(4500);
  }
  out._meta = { retrieved: new Date().toISOString(), count: pages.size, failed };
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out)], { type: "application/json" }));
  a.download = "pfr_all_career_leaders.json";
  a.click();
  console.log(`Done. ${pages.size - failed.length} saved, ${failed.length} failed${failed.length ? ": " + failed.join(", ") : ""}.`);
})();
