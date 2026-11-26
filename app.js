(() => {
  "use strict";

  // Leaderboards live in data.json (built by tools/build_data.py) next to the page.
  const choices = document.querySelectorAll(".choice");
  choices.forEach((b) => (b.disabled = true));
  document.getElementById("dataNote").textContent = "Loading leaderboards…";
  fetch("data.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(init)
    .catch((e) => {
      document.getElementById("dataNote").textContent = `Couldn't load the leaderboards (${e.message}). Reload the page to try again.`;
    });

  function init(DATA) {
  // Expand compact rows [rank, playerIndex, display] into objects.
  DATA.categories.forEach((c) => {
    c.leaders = c.l.map(([rank, i, disp]) => ({ rank, name: DATA.players[i], disp }));
  });
  // Hole score = how far off you were, as a % of the leaderboard's length (0–100, one decimal).
  // Out of bounds (player not on the board) scores the maximum: 100.
  const OB_POINTS = 100;
  const pts = (x) => Math.round(x * 10) / 10;
  const fmtPts = (x) => (Number.isInteger(x) ? String(x) : x.toFixed(1));

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const norm = (s) =>
    s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
      .replace(/[^a-z0-9 ]/g, " ")
      .replace(/\s+/g, " ").trim();
  const shuffle = (a) => {
    a = a.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Every name that appears on any leaderboard — the autocomplete pool.
  const POOL = DATA.players.map((name) => ({ key: norm(name), name }));

  // ---------- state ----------
  let round = null; // { holes: [{cat, par, guess, strokes, ob}], idx }

  function buildRound(n) {
    const cats = DATA.categories;
    let order = [];
    while (order.length < n) {
      let next = shuffle(cats);
      // avoid the same category on back-to-back holes when the deck wraps
      if (order.length && next[0].id === order[order.length - 1].id) next.push(next.shift());
      order = order.concat(next);
    }
    return {
      idx: 0,
      holes: order.slice(0, n).map((cat) => {
        const pinEntry = cat.leaders[Math.floor(Math.random() * cat.leaders.length)];
        return { cat, par: pinEntry.rank, guess: null, strokes: null, ob: false };
      }),
    };
  }

  const total = () => pts(round.holes.reduce((s, h) => s + (h.strokes ?? 0), 0));
  const maxRank = (cat) => cat.leaders[cat.leaders.length - 1].rank;

  // ---------- screens ----------
  function show(id) {
    ["setup", "hole", "final"].forEach((s) => $(s).classList.toggle("hidden", s !== id));
    $("totalBadge").classList.toggle("hidden", id === "setup");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startRound(n) {
    round = buildRound(n);
    $("holeCount").textContent = n;
    renderHole();
    show("hole");
  }

  function renderHole() {
    const h = round.holes[round.idx];
    $("holeNum").textContent = round.idx + 1;
    $("parRank").textContent = h.par;
    $("parRank2").textContent = h.par;
    $("catName").textContent = h.cat.name;
    $("listSize").textContent = maxRank(h.cat);
    $("result").classList.add("hidden");
    $("guessForm").classList.remove("hidden");
    $("guessInput").value = "";
    $("guessInput").disabled = false;
    $("guessBtn").disabled = false;
    hideAc();
    $("totalScore").textContent = fmtPts(total());
    renderScorecard($("scorecard"), true);
    setTimeout(() => $("guessInput").focus(), 50);
  }

  // ---------- guessing ----------
  function resolveGuess(text) {
    const key = norm(text);
    if (!key) return { error: "Type a player's name." };
    const exact = POOL.find((p) => p.key === key);
    if (exact) return { name: exact.name, key };
    const sugg = suggestions(text);
    if (sugg.length === 1) return { name: sugg[0].name, key: sugg[0].key };
    if (sugg.length > 1) return { error: "Pick a player from the suggestions." };
    return { name: text.trim(), key }; // not on any leaderboard — allowed, but it's OB here
  }

  function submitGuess(text) {
    const r = resolveGuess(text);
    if (r.error) { flashInput(r.error); return; }
    const h = round.holes[round.idx];
    const hit = h.cat.leaders.find((p) => norm(p.name) === r.key);
    h.guess = r.name;
    if (hit) {
      h.guessRank = hit.rank;
      h.miss = Math.abs(hit.rank - h.par);
      h.strokes = pts((100 * h.miss) / h.cat.leaders.length);
      h.ob = false;
    } else {
      h.guessRank = null;
      h.strokes = OB_POINTS;
      h.ob = true;
    }
    renderResult(h);
  }

  function label(h) {
    if (h.ob) return ["Out of bounds", "bad"];
    const s = h.strokes;
    if (s === 0) return ["Hole in one!", "good"];
    if (s <= 1) return ["Eagle", "good"];
    if (s <= 3) return ["Birdie", "good"];
    if (s <= 7) return ["Par", ""];
    if (s <= 15) return ["Bogey", ""];
    if (s <= 30) return ["Double bogey", "bad"];
    return ["Triple bogey+", "bad"];
  }

  function renderResult(h) {
    hideAc();
    $("guessInput").disabled = true;
    $("guessBtn").disabled = true;
    $("guessForm").classList.add("hidden");

    const [txt, cls] = label(h);
    $("resultLabel").textContent = txt;
    $("resultLabel").className = "result-label " + cls;
    $("resultStrokes").textContent = fmtPts(h.strokes);

    const pinNames = h.cat.leaders.filter((p) => p.rank === h.par).map((p) => p.name);
    const atPin = pinNames.length <= 3
      ? pinNames.join(" / ")
      : `${pinNames.slice(0, 2).join(" / ")} and ${pinNames.length - 2} others tied`;
    // Short form for the scorecard and shared card.
    h.pinName = pinNames.length === 1 ? pinNames[0] : `${pinNames[0]} +${pinNames.length - 1} tied`;
    $("resultDetail").innerHTML = h.ob
      ? `<b>${esc(h.guess)}</b> isn't in the top ${maxRank(h.cat)}. The pin (#${h.par}) was ${esc(atPin)}.`
      : `<b>${esc(h.guess)}</b> is #${h.guessRank}, ${h.miss} spot${h.miss === 1 ? "" : "s"} off on a ${h.cat.leaders.length}-player list. The pin (#${h.par}) was ${esc(atPin)}.`;

    const lo = h.ob ? h.par : Math.min(h.par, h.guessRank);
    const hi = h.ob ? h.par : Math.max(h.par, h.guessRank);
    const guessKey = norm(h.guess);
    $("board").innerHTML = h.cat.leaders.map((p) => {
      const c = [];
      if (p.rank === h.par) c.push("par");
      if (!h.ob && norm(p.name) === guessKey) c.push("guess");
      if (p.rank > lo && p.rank < hi) c.push("inrange");
      return `<li class="${c.join(" ")}"><span class="rk">#${p.rank}</span><span>${esc(p.name)}</span><span class="val">${esc(p.disp)}</span></li>`;
    }).join("");

    $("nextBtn").textContent = round.idx === round.holes.length - 1 ? "Finish round →" : "Next hole →";
    $("result").classList.remove("hidden");
    $("totalScore").textContent = fmtPts(total());
    renderScorecard($("scorecard"), true);

    // scroll the board so the pin is visible
    const board = $("board");
    const pinEl = board.querySelector("li.par");
    if (pinEl) board.scrollTop = pinEl.offsetTop - board.clientHeight / 2 + pinEl.clientHeight / 2;
    $("nextBtn").focus({ preventScroll: true });
  }

  function next() {
    if (round.idx < round.holes.length - 1) { round.idx++; renderHole(); }
    else finish();
  }

  // ---------- scorecard ----------
  function renderScorecard(table, live) {
    const hs = round.holes;
    const cell = (h, i, inner, extra = "") => {
      const cur = live && i === round.idx ? " current" : "";
      return `<td class="${extra}${cur}">${inner}</td>`;
    };
    const head = `<tr><th class="row-head">Hole</th>${hs.map((_, i) => `<th>${i + 1}</th>`).join("")}<th>Tot</th></tr>`;
    const cats = `<tr class="cat-row"><td class="row-head">Stat</td>${hs.map((h, i) => cell(h, i, esc(h.cat.name.replace(/^Career /, "")))).join("")}<td></td></tr>`;
    // Player names only appear once a hole is played, so the live card never gives away the pin.
    const who = (name) => `<span class="sc-name">${esc(name)}</span>`;
    const pins = `<tr><td class="row-head">Pin</td>${hs.map((h, i) => cell(h, i, "#" + h.par + (h.strokes == null ? "" : who(h.pinName)))).join("")}<td></td></tr>`;
    const hits = `<tr><td class="row-head">Hit</td>${hs.map((h, i) => cell(h, i, h.strokes == null ? "" : (h.ob ? "OB" : "#" + h.guessRank) + who(h.guess), h.ob ? "ob" : "")).join("")}<td></td></tr>`;
    const strokes = `<tr><td class="row-head">Points</td>${hs.map((h, i) => cell(h, i, h.strokes == null ? "" : fmtPts(h.strokes), h.strokes === 0 ? "ace" : h.ob ? "ob" : "")).join("")}<td><b>${fmtPts(total())}</b></td></tr>`;
    table.innerHTML = head + cats + pins + hits + strokes;
  }

  // ---------- final ----------
  function finish() {
    const n = round.holes.length, t = total(), avg = t / n;
    $("finalScore").textContent = fmtPts(t);
    $("finalHoles").textContent = n;
    const aces = round.holes.filter((h) => h.strokes === 0).length;
    const [rank, blurb] =
      avg <= 2 ? ["Tour Pro", "You know these leaderboards cold."] :
      avg <= 5 ? ["Scratch Golfer", "Seriously impressive."] :
      avg <= 10 ? ["Club Champion", "A solid, respectable round."] :
      avg <= 20 ? ["Weekend Hacker", "Some good swings in there."] :
      ["Beer Cart Regular", "Rough day on the links."];
    let verdict = `${avg.toFixed(1)} points per hole. ${blurb}`;
    if (aces) verdict += ` ${aces} hole${aces > 1 ? "s" : ""}-in-one!`;
    $("finalRank").textContent = rank;
    $("finalVerdict").textContent = verdict;
    renderScorecard($("finalCard"), false);
    $("totalScore").textContent = fmtPts(t);
    show("final");
  }

  function shareText() {
    const icon = (h) => h.ob ? "🟥" : h.strokes === 0 ? "⛳" : h.strokes <= 3 ? "🟩" : h.strokes <= 15 ? "🟨" : "🟧";
    const holes = round.holes.map((h, i) => [
      `${i + 1}. ${h.cat.name.replace(/^Career /, "")} — ${icon(h)} ${fmtPts(h.strokes)} pts`,
      `   Pin: #${h.par} ${h.pinName}`,
      `   Hit: ${h.ob ? "OB" : "#" + h.guessRank} ${h.guess}`,
    ].join("\n"));
    return [
      `NFL Golf ⛳ ${round.holes.length} holes — ${fmtPts(total())} points (${$("finalRank").textContent})`,
      round.holes.map(icon).join(""),
      "",
      ...holes,
    ].join("\n");
  }

  // ---------- autocomplete ----------
  let acItems = [], acIndex = -1;

  function suggestions(q) {
    const key = norm(q);
    if (key.length < 2) return [];
    const qt = key.split(" ");
    const scored = [];
    for (const p of POOL) {
      const nt = p.key.split(" ");
      const tokenMatch = qt.every((t) => nt.some((w) => w.startsWith(t)));
      if (!tokenMatch && !p.key.includes(key)) continue;
      const score = p.key.startsWith(key) ? 0 : tokenMatch ? 1 : 2;
      scored.push([score, p]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name));
    return scored.slice(0, 8).map((s) => s[1]);
  }

  function renderAc() {
    const q = $("guessInput").value;
    acItems = suggestions(q);
    acIndex = acItems.length ? 0 : -1;
    const list = $("acList");
    if (!acItems.length) { hideAc(); return; }
    const k = norm(q);
    list.innerHTML = acItems.map((p, i) => {
      const at = p.name.toLowerCase().indexOf(k);
      const label = at >= 0 ? esc(p.name.slice(0, at)) + "<b>" + esc(p.name.slice(at, at + k.length)) + "</b>" + esc(p.name.slice(at + k.length)) : esc(p.name);
      return `<li role="option" data-i="${i}" class="${i === acIndex ? "active" : ""}">${label}</li>`;
    }).join("");
    list.classList.remove("hidden");
  }
  function hideAc() { $("acList").classList.add("hidden"); acItems = []; acIndex = -1; }
  function setActive(i) {
    acIndex = (i + acItems.length) % acItems.length;
    [...$("acList").children].forEach((li, j) => li.classList.toggle("active", j === acIndex));
    $("acList").children[acIndex]?.scrollIntoView({ block: "nearest" });
  }
  function pick(i) { $("guessInput").value = acItems[i].name; hideAc(); }

  function flashInput(msg) {
    const inp = $("guessInput");
    inp.setCustomValidity(msg); inp.reportValidity();
    setTimeout(() => inp.setCustomValidity(""), 1500);
  }

  // ---------- wiring ----------
  document.querySelectorAll(".choice").forEach((b) => b.addEventListener("click", () => startRound(+b.dataset.holes)));
  $("guessInput").addEventListener("input", renderAc);
  $("guessInput").addEventListener("keydown", (e) => {
    if ($("acList").classList.contains("hidden")) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive(acIndex + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive(acIndex - 1); }
    else if (e.key === "Escape") hideAc();
    else if (e.key === "Tab" && acIndex >= 0) { e.preventDefault(); pick(acIndex); }
    else if (e.key === "Enter" && acIndex >= 0 && norm($("guessInput").value) !== acItems[acIndex].key) { e.preventDefault(); pick(acIndex); }
  });
  $("guessInput").addEventListener("blur", () => setTimeout(hideAc, 150));
  $("acList").addEventListener("mousedown", (e) => {
    const li = e.target.closest("li"); if (!li) return;
    e.preventDefault(); pick(+li.dataset.i);
  });
  $("guessForm").addEventListener("submit", (e) => { e.preventDefault(); submitGuess($("guessInput").value); });
  $("nextBtn").addEventListener("click", next);
  $("againBtn").addEventListener("click", () => show("setup"));
  $("shareBtn").addEventListener("click", () => {
    const box = $("shareText");
    box.value = shareText();
    navigator.clipboard.writeText(box.value)
      .then(() => { $("shareBtn").textContent = "Copied!"; box.hidden = true; })
      .catch(() => { box.hidden = false; box.focus(); box.select(); $("shareBtn").textContent = "Select and copy below"; });
    setTimeout(() => ($("shareBtn").textContent = "Share your card"), 2000);
  });
  choices.forEach((b) => (b.disabled = false));

  $("dataNote").textContent =
    `${DATA.categories.length} stat categories · ${POOL.length.toLocaleString()} players · Regular-season career leaderboards from Pro Football Reference, as of ${DATA.asOf}.`;
  }
})();
