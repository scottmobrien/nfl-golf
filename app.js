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

  // ---------- tees (game modes) ----------
  // Families: off, def, kick (placekicking + points), punt, ret (returns), gen (games, starts, AV, awards).
  // Modes with a span rebuild every board from season-by-season stats (seasons.json) for those years.
  const ALL_FAMS = ["off", "def", "kick", "punt", "ret", "gen"];
  const TEES = {
    tips: { label: "The Tips", fams: ALL_FAMS },
    champ: { label: "Championship", fams: ["off", "def", "gen"] },
    members: { label: "Members Tees", fams: ["off", "def", "kick", "ret", "gen"], from: 2000 },
    red: { label: "Red Tees" },
  };
  let SEASONS = null, seasonsLoading = null;
  const loadSeasons = () => seasonsLoading ||= fetch("seasons.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((S) => {
      SEASONS = S;
      DATA.allPlayers = DATA.players.concat(S.extraPlayers);
      POOL_ALL = DATA.allPlayers.map((name) => ({ key: norm(name), name }));
      return S;
    })
    .catch((e) => { seasonsLoading = null; throw e; });

  // Totals for every player over [from, to]: Map(playerIndex -> {"table.col": sum}).
  function totals(from, to) {
    const t = new Map();
    for (let y = from; y <= to; y++) {
      const season = SEASONS.seasons[y];
      if (!season) continue;
      for (const [table, { c, r }] of Object.entries(season)) {
        const keys = c.map((col) => table + "." + col);
        for (const row of r) {
          let o = t.get(row[0]);
          if (!o) t.set(row[0], (o = {}));
          for (let j = 0; j < keys.length; j++) if (row[j + 1]) o[keys[j]] = (o[keys[j]] || 0) + row[j + 1];
        }
      }
    }
    return t;
  }

  const add = (o, keys) => keys.reduce((s, k) => s + (o[k] || 0), 0);
  // Passing formulas need sums of attempts, completions, yards, TDs, INTs, sacks, sack yards.
  const FORMULAS = {
    rating(v) {
      const c = (x) => Math.max(0, Math.min(2.375, x));
      const a = c((v.cmp / v.att - 0.3) * 5), b = c((v.yds / v.att - 3) * 0.25);
      const d = c((v.td / v.att) * 20), e = c(2.375 - (v.int / v.att) * 25);
      return ((a + b + d + e) / 6) * 100;
    },
    aya: (v) => (v.yds + 20 * v.td - 45 * v.int) / v.att,
    nya: (v) => (v.yds - v.sky) / (v.att + v.sk),
    anya: (v) => (v.yds + 20 * v.td - 45 * v.int - v.sky) / (v.att + v.sk),
  };

  function rangeBoard(spec, tot, years) {
    // Rate stats need a minimum volume: qMin per season, up to 10 seasons (= PFR's career minimums).
    // If fewer than 60 players clear it, lower the bar to the 60th player's volume, but never below a third.
    let qMin = 1;
    if (spec.q && !spec.qFlat) {
      const full = spec.qMin * Math.min(years, 10);
      const vols = [...tot.values()].map((o) => add(o, spec.q)).sort((a, b) => b - a);
      qMin = Math.max(1, Math.min(full, Math.max(full / 3, vols[59] || 0)));
    }
    const rows = [];
    for (const [pi, o] of tot) {
      let v;
      if (spec.qFlat && add(o, spec.q) < spec.qFlat) continue;
      if (spec.sum) v = add(o, spec.sum);
      else {
        if (add(o, spec.q) < qMin) continue;
        if (spec.formula) {
          const vals = {};
          for (const [name, keys] of Object.entries(spec.k)) vals[name] = add(o, keys);
          if (!vals.att) continue;
          v = FORMULAS[spec.formula](vals);
        } else {
          const den = add(o, spec.den);
          if (!den) continue;
          v = (add(o, spec.num) / den) * (spec.mult || 1);
        }
      }
      const d = 10 ** (spec.dec || 0);
      v = Math.round(v * d) / d;
      if (v > 0 || (spec.low && v === 0 && !spec.sum)) rows.push([pi, v]);
    }
    rows.sort((a, b) => (spec.low ? a[1] - b[1] : b[1] - a[1]));
    // Rank with ties, keeping ranks up to 250.
    let ranked = [];
    for (let i = 0; i < rows.length; i++) {
      const prev = ranked[ranked.length - 1];
      const rank = prev && prev.v === rows[i][1] ? prev.rank : i + 1;
      if (rank > 250) break;
      ranked.push({ rank, pi: rows[i][0], v: rows[i][1] });
    }
    // Trim a giant tie off the bottom (e.g. dozens of trick-play passers tied at 1 completion).
    const share = 0.2;
    while (ranked.length) {
      const lastRank = ranked[ranked.length - 1].rank;
      const tail = ranked.filter((r) => r.rank === lastRank).length;
      if (tail <= share * ranked.length) break;
      ranked = ranked.slice(0, ranked.length - tail);
    }
    const biggest = Math.max(0, ...Object.values(ranked.reduce((m, r) => ((m[r.rank] = (m[r.rank] || 0) + 1), m), {})));
    // Span boards need 50+ players and no single tie covering over 20% of the list.
    if (ranked.length < 50 || biggest > share * ranked.length) return null;
    const fmt = (v) => v.toLocaleString("en-US", { minimumFractionDigits: spec.dec || 0, maximumFractionDigits: spec.dec || 0 });
    return {
      id: spec.id, name: spec.name, f: spec.f,
      leaders: ranked.map((r) => ({ rank: r.rank, name: DATA.allPlayers[r.pi], disp: spec.pct ? fmt(r.v) + "%" : fmt(r.v) + " " + spec.unit })),
    };
  }

  function boardsFor(t) {
    if (!t.from) return DATA.categories.filter((c) => t.fams.includes(c.f));
    const tot = totals(t.from, t.to);
    return SEASONS.boards.filter((b) => t.fams.includes(b.f))
      .map((b) => rangeBoard(b, tot, t.to - t.from + 1)).filter(Boolean);
  }
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
  const shuffle = (a, rnd = Math.random) => {
    a = a.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Every name that appears on any leaderboard — the autocomplete pool.
  const POOL_CAREER = DATA.players.map((name) => ({ key: norm(name), name }));
  let POOL_ALL = null, POOL = POOL_CAREER;

  // ---------- state ----------
  let round = null; // { holes: [{cat, par, guess, strokes, ob}], idx }

  // Pins on long boards lean toward the top: deep pins (#101+) are less fun to aim at.
  // Boards of 100 or fewer stay uniform. Within a band, every listed player is equally likely.
  const PIN_BANDS = [[1, 75, 0.55], [76, 100, 0.30], [101, Infinity, 0.15]];
  function pickPin(leaders, rnd, uniform) {
    const any = () => leaders[Math.floor(rnd() * leaders.length)];
    if (uniform || leaders.length <= 100) return any();
    let x = rnd();
    for (const [lo, hi, w] of PIN_BANDS) {
      if ((x -= w) < 0 || hi === Infinity) {
        const band = leaders.filter((p) => p.rank >= lo && p.rank <= hi);
        return band.length ? band[Math.floor(rnd() * band.length)] : any();
      }
    }
  }

  function buildRound(n, cats, rnd = Math.random, uniformPins = false) {
    let order = [];
    while (order.length < n) {
      let next = shuffle(cats, rnd);
      // avoid the same category on back-to-back holes when the deck wraps
      if (order.length && next[0].id === order[order.length - 1].id) next.push(next.shift());
      order = order.concat(next);
    }
    return {
      idx: 0,
      tee: currentTee,
      holes: order.slice(0, n).map((cat) => {
        const pinEntry = pickPin(cat.leaders, rnd, uniformPins);
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
    $("hardToggle").classList.toggle("hidden", id !== "setup");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // The tee in play: a TEES entry, plus from/to for span modes.
  let currentTee = null;
  function chosenTee() {
    const id = document.querySelector('input[name="tee"]:checked').value;
    const last = SEASONS ? SEASONS.years[1] : DATA.lastSeason;
    if (id === "red") {
      const fams = [...document.querySelectorAll('input[name="fam"]:checked')].flatMap((c) => c.value.split(","));
      const from = +$("yearFrom").value, to = $("yearTo").value === "present" ? last : +$("yearTo").value;
      return { id, label: TEES.red.label, fams, from, to, present: $("yearTo").value === "present" };
    }
    const t = TEES[id];
    return { id, label: t.label, fams: t.fams, from: t.from, to: t.from ? last : undefined, present: !!t.from };
  }
  const spanText = (t) => (t.from ? `${t.from}–${t.present ? "present" : t.to}` : "All time");
  const teeText = (t) => (t.challenge ? "Challenge · " : "") + (t.daily ? `The Daily 9 #${t.num} · Members Tees` : `${t.label} · ${spanText(t)}`) + (t.hard ? " · Hard mode" : "");

  // ---------- daily course ----------
  // Everyone gets the same 9 Members Tees holes each day (US Eastern date), seeded from the date.
  const DAILY_EPOCH = "2026-11-27"; // The Daily 9 #1
  const todayET = () => new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
  const dayNum = (d) => Math.round((Date.parse(d) - Date.parse(DAILY_EPOCH)) / 864e5) + 1;
  function seeded(str) {
    let h = 2166136261;
    for (const ch of str) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
    return () => { // mulberry32
      h = (h + 0x6d2b79f5) | 0;
      let t = Math.imul(h ^ (h >>> 15), 1 | h);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const dailyTee = (date) => ({
    id: "daily", daily: date, num: dayNum(date), label: "The Daily 9",
    fams: TEES.members.fams, from: TEES.members.from, to: SEASONS.years[1], present: true,
  });
  // Saved progress: {date, picks: [{name, key}], posted, name}
  const DAILY_KEY = "nflgolf.daily";
  const loadDaily = () => { try { const d = JSON.parse(localStorage.getItem(DAILY_KEY)); return d && d.date === todayET() ? d : null; } catch { return null; } };
  const saveDaily = (d) => { try { localStorage.setItem(DAILY_KEY, JSON.stringify(d)); } catch {} };

  async function startDaily() {
    const date = todayET();
    if (!SEASONS) {
      $("dailyBtn").disabled = true;
      $("dailyBtn").textContent = "Loading…";
      try { await loadSeasons(); } catch (e) { $("dailyBtn").disabled = false; renderDailyCard(`Couldn't load season stats (${e.message}). Try again.`); return; }
      $("dailyBtn").disabled = false;
    }
    const t = dailyTee(date);
    const saved = loadDaily() || { date, picks: [] };
    // Hard mode is locked in once today's round has started.
    t.hard = saved.picks.length ? !!saved.hard : $("hardMode").checked;
    saveDaily({ ...saved, hard: t.hard });
    currentTee = t;
    POOL = POOL_ALL;
    // The Daily 9 #1 launched with uniform pins; keep it so saved rounds replay the same course.
    round = buildRound(9, boardsFor(t), seeded("nfl-golf-daily:" + date), t.num <= 1);
    $("holeTee").textContent = teeText(t);
    $("reteeBtn").classList.add("hidden"); // one Daily 9 round per day
    $("holeCount").textContent = 9;
    // Replay saved swings so a refresh can't re-roll a hole.
    saved.picks.forEach((r, i) => { round.idx = i; scoreGuess(round.holes[i], r); });
    round.idx = Math.min(saved.picks.length, 8);
    if (saved.picks.length >= 9) { finish(); return; }
    renderHole();
    show("hole");
  }

  async function startRound(n) {
    const t = chosenTee();
    if (t.from && !SEASONS) {
      setChoices(false, "Loading season-by-season stats…");
      try { await loadSeasons(); } catch (e) { setChoices(true, `Couldn't load season stats (${e.message}). Try again.`); return; }
      setChoices(true);
      Object.assign(t, chosenTee());
    }
    if (t.id === "red" && !t.fams.length) { redNote("Check at least one category.", true); return; }
    if (t.id === "red" && t.from > t.to) { redNote("The starting year is after the ending year.", true); return; }
    const cats = boardsFor(t);
    if (!cats.length) { redNote("Not enough players on any leaderboard for that span. Widen the years or add categories.", true); return; }
    t.hard = $("hardMode").checked;
    currentTee = t;
    POOL = t.from ? POOL_ALL : POOL_CAREER;
    round = buildRound(n, cats);
    beginRound(t, n);
  }

  function beginRound(t, n) {
    $("holeTee").textContent = teeText(t);
    $("reteeBtn").classList.toggle("hidden", !!t.daily); // one Daily 9 round per day
    $("holeCount").textContent = n;
    renderHole();
    show("hole");
  }

  function renderHole() {
    const h = round.holes[round.idx];
    $("holeNum").textContent = round.idx + 1;
    $("parRank").textContent = h.par;
    $("parRank2").textContent = h.par;
    // Default: show the pin player's stat, e.g. "#85 (48 TD)". Hard mode hides it.
    $("pinStat").textContent = round.tee.hard ? "" : ` (${h.cat.leaders.find((p) => p.rank === h.par).disp})`;
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
    if (h.strokes != null) return;
    scoreGuess(h, r);
    if (round.tee.daily) {
      const d = loadDaily() || { date: round.tee.daily, picks: [] };
      d.picks[round.idx] = { name: r.name, key: r.key };
      saveDaily(d);
    }
    renderResult(h);
  }

  function scoreGuess(h, r) {
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
    // Pin names, for the scorecard and shared card.
    const pinNames = h.cat.leaders.filter((p) => p.rank === h.par).map((p) => p.name);
    h.pinNames = pinNames;
    h.pinName = pinNames.length === 1 ? pinNames[0] : `${pinNames[0]} +${pinNames.length - 1} tied`;
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

    const pinNames = h.pinNames;
    const atPin = pinNames.length <= 3
      ? pinNames.join(" / ")
      : `${pinNames.slice(0, 2).join(" / ")} and ${pinNames.length - 2} others tied`;
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
    const ch = round.tee.challenge;
    const rival = ch && !live
      ? `<tr class="rival-row"><td class="row-head">Rival</td>${hs.map((h, i) => cell(h, i, fmtPts(ch.s[i]), ch.s[i] < h.strokes ? "beat" : "")).join("")}<td><b>${fmtPts(pts(ch.s.reduce((a, b) => a + b, 0)))}</b></td></tr>`
      : "";
    table.innerHTML = head + cats + pins + hits + strokes + rival;
  }

  // ---------- final ----------
  function finish() {
    const n = round.holes.length, t = total(), avg = t / n;
    $("finalScore").textContent = fmtPts(t);
    $("finalHoles").textContent = n;
    $("finalTee").textContent = teeText(round.tee);
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
    $("shareText").hidden = true;
    $("dailyBoard").classList.toggle("hidden", !round.tee.daily);
    $("reteeFinalBtn").classList.toggle("hidden", !!round.tee.daily);
    $("challengeSendBtn").classList.toggle("hidden", !!round.tee.daily);
    const ch = round.tee.challenge;
    $("challengeResult").classList.toggle("hidden", !ch);
    if (ch) {
      const theirs = pts(ch.s.reduce((a, b) => a + b, 0)), diff = pts(Math.abs(theirs - t));
      ch.outcome = t < theirs ? "Won" : t > theirs ? "Lost" : "Tied";
      $("challengeResult").innerHTML = `<b>${t < theirs ? "You win!" : t > theirs ? "Your challenger wins." : "All square!"}</b> `
        + `Your challenger shot ${fmtPts(theirs)}${t === theirs ? " too" : `, you ${t < theirs ? "beat them" : "were behind"} by ${fmtPts(diff)}`}.`;
      // Done with the link: a refresh shouldn't offer the same challenge again.
      history.replaceState(null, "", location.pathname);
      $("challengeCard").classList.add("hidden");
    }
    if (round.tee.daily) renderBoardPanel();
    show("final");
  }

  function shareText() {
    const icon = (h) => h.ob ? "🟥" : h.strokes === 0 ? "⛳" : h.strokes <= 3 ? "🟩" : h.strokes <= 15 ? "🟨" : "🟧";
    if (round.tee.daily) {
      // No player names: friends may not have played today's course yet.
      return [
        `NFL Golf ⛳ The Daily 9 #${round.tee.num} — ${fmtPts(total())} points (${$("finalRank").textContent})`,
        round.holes.map(icon).join(""),
        "",
        ...round.holes.map((h, i) => `${i + 1}. ${h.cat.name} · pin #${h.par} — ${icon(h)} ${fmtPts(h.strokes)}`),
        "",
        location.origin + location.pathname,
      ].join("\n");
    }
    const holes = round.holes.map((h, i) => [
      `${i + 1}. ${h.cat.name.replace(/^Career /, "")} — ${icon(h)} ${fmtPts(h.strokes)} pts`,
      `   Pin: #${h.par} ${h.pinName}`,
      `   Hit: ${h.ob ? "OB" : "#" + h.guessRank} ${h.guess}`,
    ].join("\n"));
    return [
      `NFL Golf ⛳ ${teeText(round.tee)} · ${round.holes.length} holes — ${fmtPts(total())} points (${$("finalRank").textContent})`
        + (round.tee.challenge ? ` · ${round.tee.challenge.outcome} vs. ${fmtPts(pts(round.tee.challenge.s.reduce((a, b) => a + b, 0)))}` : ""),
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
  $("againBtn").addEventListener("click", () => { renderDailyCard(); show("setup"); });
  $("dailyBtn").addEventListener("click", startDaily);

  // Re-Tee: a fresh course with the same tee, years, categories, hole count and Hard mode.
  function reTee() {
    const t = { ...round.tee, challenge: null }, n = round.holes.length;
    if (t.daily) return;
    const played = round.holes.some((h) => h.strokes != null) && !round.holes.every((h) => h.strokes != null);
    if (played && !confirm("Start over from hole 1 with a fresh course? This round's scores will be lost.")) return;
    round = buildRound(n, boardsFor(t));
    beginRound(t, n);
  }
  $("reteeBtn").addEventListener("click", reTee);
  $("reteeFinalBtn").addEventListener("click", reTee);

  // The logo goes home too: same as ← Home during a round, a plain jump from the final screen.
  $("brandLink").addEventListener("click", (e) => {
    e.preventDefault();
    if (!$("hole").classList.contains("hidden")) $("homeBtn").click();
    else { renderDailyCard(); show("setup"); }
  });

  // Back to the home screen mid-round. The Daily 9 keeps its progress (resume from the card).
  $("homeBtn").addEventListener("click", () => {
    const played = round.holes.some((h) => h.strokes != null);
    if (!round.tee.daily && played && !confirm("Leave this round? Your scores so far will be lost.")) return;
    renderDailyCard();
    show("setup");
  });
  $("shareBtn").addEventListener("click", () => {
    const box = $("shareText");
    box.value = shareText();
    navigator.clipboard.writeText(box.value)
      .then(() => { $("shareBtn").textContent = "Copied!"; box.hidden = true; })
      .catch(() => { box.hidden = false; box.focus(); box.select(); $("shareBtn").textContent = "Select and copy below"; });
    setTimeout(() => ($("shareBtn").textContent = "Share your card"), 2000);
  });
  // ---------- challenges ----------
  // A challenge link carries the whole course: tee settings, [board id, pin] per hole, and the sender's points.
  const enc64 = (o) => btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(o))))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const dec64 = (s) => JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0))));

  function challengeLink() {
    const t = round.tee;
    const spec = {
      v: 1,
      t: { id: t.id, l: t.label, f: t.fams, from: t.from || 0, to: t.from && !t.present ? t.to : 0, hard: t.hard ? 1 : 0 },
      h: round.holes.map((h) => [h.cat.id, h.par]),
      s: round.holes.map((h) => h.strokes),
    };
    return `${location.origin}${location.pathname}?challenge=${enc64(spec)}`;
  }

  let pendingChallenge = null;
  function teeFromChallenge(c) {
    const T = c.t, last = SEASONS ? SEASONS.years[1] : DATA.lastSeason;
    return {
      id: T.id, label: T.l || (TEES[T.id] || {}).label || "NFL Golf", fams: T.f,
      from: T.from || undefined, to: T.from ? T.to || last : undefined, present: !!T.from && !T.to,
      hard: !!T.hard, challenge: c,
    };
  }
  function showChallengeCard() {
    const c = pendingChallenge;
    if (!c) return;
    const t = teeFromChallenge(c), theirs = pts(c.s.reduce((a, b) => a + b, 0));
    $("challengeWhat").textContent = `${t.label} · ${spanText(t)} · ${c.h.length} holes${t.hard ? " · Hard mode" : ""}`;
    $("challengeNote").textContent = `Your challenger shot ${fmtPts(theirs)} points. Same holes, same pins. Can you beat it?`;
    $("challengeCard").classList.remove("hidden");
  }
  async function startChallenge() {
    const c = pendingChallenge;
    if (c.t.from && !SEASONS) {
      $("challengeBtn").disabled = true;
      try { await loadSeasons(); } catch (e) { $("challengeBtn").disabled = false; $("challengeNote").textContent = `Couldn't load season stats (${e.message}). Try again.`; return; }
      $("challengeBtn").disabled = false;
    }
    const t = teeFromChallenge(c), cats = boardsFor(t);
    const holes = c.h.map(([id, par]) => {
      const cat = cats.find((x) => x.id === id);
      if (!cat) return null;
      // If the stats were refreshed since the link was made, snap to the nearest rank that still exists.
      const pin = cat.leaders.reduce((best, p) => (Math.abs(p.rank - par) < Math.abs(best.rank - par) ? p : best));
      return { cat, par: pin.rank, guess: null, strokes: null, ob: false };
    });
    if (holes.includes(null)) { $("challengeNote").textContent = "This challenge uses a leaderboard that's no longer in the game. Ask for a new link."; return; }
    currentTee = t;
    POOL = t.from ? POOL_ALL : POOL_CAREER;
    round = { idx: 0, tee: t, holes };
    beginRound(t, holes.length);
  }

  $("challengeBtn").addEventListener("click", startChallenge);
  $("challengeSendBtn").addEventListener("click", async () => {
    const url = challengeLink(), btn = $("challengeSendBtn");
    const text = `I shot ${fmtPts(total())} on NFL Golf (${teeText({ ...round.tee, challenge: null })}, ${round.holes.length} holes). Same holes, same pins. Can you beat me?`;
    if (navigator.share) {
      try { await navigator.share({ title: "NFL Golf challenge", text, url }); return; }
      catch (e) { if (e.name === "AbortError") return; }
    }
    const box = $("shareText");
    box.value = `${text}\n${url}`;
    try { await navigator.clipboard.writeText(box.value); btn.textContent = "Link copied!"; box.hidden = true; }
    catch { box.hidden = false; box.focus(); box.select(); btn.textContent = "Copy the link below"; }
    setTimeout(() => (btn.textContent = "⚔️ Challenge"), 2000);
  });

  // ---------- daily leaderboard (Supabase) ----------
  const LB = window.NFLGOLF_LEADERBOARD || {};
  const lbOn = !!(LB.url && LB.key);
  // New-style publishable keys (sb_publishable_…) go in the apikey header only; legacy anon JWTs also need Authorization.
  const lbHeaders = { apikey: LB.key, "Content-Type": "application/json", ...(/^eyJ/.test(LB.key || "") ? { Authorization: `Bearer ${LB.key}` } : {}) };
  const deviceId = (() => {
    try {
      let id = localStorage.getItem("nflgolf.device");
      if (!id) localStorage.setItem("nflgolf.device", (id = crypto.randomUUID()));
      return id;
    } catch { return crypto.randomUUID(); }
  })();
  async function lbFetch(date) {
    const q = `day=eq.${date}&select=name,score,hard,device&order=score.asc,created_at.asc&limit=5000`;
    const r = await fetch(`${LB.url}/rest/v1/daily_scores?${q}`, { headers: lbHeaders });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function lbPost(date, name, score, hard) {
    const r = await fetch(`${LB.url}/rest/v1/daily_scores`, {
      method: "POST", headers: { ...lbHeaders, Prefer: "return=minimal" },
      body: JSON.stringify({ day: date, name, score, hard: !!hard, device: deviceId }),
    });
    // 409 = this device already posted today; treat as posted.
    if (!r.ok && r.status !== 409) throw new Error("HTTP " + r.status);
  }

  const savedName = () => { try { return localStorage.getItem("nflgolf.name") || ""; } catch { return ""; } };

  async function renderBoardPanel(msg) {
    const box = $("dailyBoard"), d = loadDaily() || {};
    if (!lbOn) { box.innerHTML = `<h3>The Daily 9 leaderboard</h3><p class="fine">The leaderboard opens soon. Come back tomorrow for a new course.</p>`; return; }
    const form = d.posted ? "" : `
      <form id="postForm" class="post-form">
        <input id="postName" maxlength="20" placeholder="Your name for the leaderboard" value="${esc(d.name || savedName())}" aria-label="Your name" required />
        <button class="primary" type="submit">Post score</button>
      </form>`;
    box.innerHTML = `<h3>The Daily 9 #${dayNum(d.date || todayET())} leaderboard</h3>${form}<p class="fine" id="lbMsg">${esc(msg || "Loading…")}</p><ol class="lb-list" id="lbList"></ol>`;
    $("postForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = $("postName").value.trim().slice(0, 20);
      if (!name) return;
      const btn = $("postForm").querySelector("button");
      btn.disabled = true;
      try {
        await lbPost(round.tee.daily, name, total(), round.tee.hard);
        try { localStorage.setItem("nflgolf.name", name); } catch {}
        saveDaily({ ...(loadDaily() || { date: round.tee.daily, picks: [] }), posted: true, name });
        renderBoardPanel();
      } catch (err) { btn.disabled = false; $("lbMsg").textContent = `Couldn't post (${err.message}). Try again.`; }
    });
    try {
      const rows = await lbFetch(d.date || todayET());
      let rank = 0, prev = null;
      const ranked = rows.map((r, i) => ({ ...r, rank: prev !== null && r.score === prev ? rank : (rank = i + 1, prev = r.score, rank) }));
      const mine = ranked.find((r) => r.device === deviceId);
      $("lbMsg").textContent = !rows.length ? "No scores yet. Be the first."
        : (mine ? `You're #${mine.rank} of ${rows.length} today.` : `${rows.length} golfer${rows.length === 1 ? "" : "s"} today.`)
          + (rows.some((r) => r.hard) ? " 🔥 = Hard mode." : "");
      const top = ranked.slice(0, 25);
      if (mine && !top.includes(mine)) top.push(mine);
      $("lbList").innerHTML = top.map((r) => `<li class="${r === mine ? "me" : ""}"><span class="rk">#${r.rank}</span><span>${esc(r.name)}${r.hard ? ' <span class="hard-flag" title="Hard mode">🔥</span>' : ""}</span><span class="val">${fmtPts(+r.score)}</span></li>`).join("");
    } catch (err) { $("lbMsg").textContent = `Couldn't load the leaderboard (${err.message}).`; }
  }

  // The daily card at the top of the setup screen.
  function renderDailyCard(note) {
    const d = loadDaily(), date = todayET(), n = dayNum(date);
    const left = (() => { // time until midnight Eastern
      const now = new Date(), et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
      const mins = 24 * 60 - (et.getHours() * 60 + et.getMinutes());
      return `${Math.floor(mins / 60)}h ${mins % 60}m`;
    })();
    const done = d && d.picks.filter(Boolean).length >= 9;
    const started = d && d.picks.length && !done;
    $("dailyNum").textContent = n;
    $("dailyDate").textContent = new Date(date + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    $("dailyBtn").textContent = done ? "See your card & leaderboard" : started ? `Resume (hole ${d.picks.length + 1} of 9)` : "Play today's Daily 9";
    $("dailyNote").textContent = note || (done ? `You've played today's Daily 9. A new one tees off in ${left}.` : "Same 9 holes and pins for everyone · Members Tees (2000–present) · One round per day.");
  }

  // ---------- setup screen ----------
  const baseNote = `${DATA.categories.length} all-time stat categories · Regular-season stats from Pro Football Reference, as of ${DATA.asOf}.`;
  function setChoices(on, note) {
    choices.forEach((b) => (b.disabled = !on));
    $("dataNote").textContent = note || baseNote;
  }
  function redNote(msg, warn) {
    $("redNote").textContent = msg;
    $("redNote").classList.toggle("warn", !!warn);
    if (warn) $("redOptions").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  // Year pickers: From defaults to 1990, To defaults to "Present".
  const last = DATA.lastSeason;
  for (let y = last; y >= DATA.firstSeason; y--) {
    $("yearFrom").add(new Option(y, y));
    $("yearTo").add(new Option(y, y));
  }
  $("yearTo").add(new Option("Present", "present"), 0);
  $("yearFrom").value = "1990";
  $("yearTo").value = "present";
  // Live count of how many holes the Red Tees settings produce (needs season data).
  function updateRed() {
    const red = document.querySelector('input[name="tee"]:checked').value === "red";
    $("redOptions").classList.toggle("hidden", !red);
    if (!red) return;
    if (!SEASONS) { redNote("Loading season-by-season stats…"); loadSeasons().then(updateRed, (e) => redNote(`Couldn't load season stats (${e.message}).`, true)); return; }
    const t = chosenTee();
    if (!t.fams.length) return redNote("Check at least one category.", true);
    if (t.from > t.to) return redNote("The starting year is after the ending year.", true);
    const n = boardsFor(t).length;
    redNote(n ? `${n} leaderboard${n === 1 ? "" : "s"} in play for ${spanText(t)}.` : "No leaderboards are deep enough for that span. Widen the years or add categories.", !n);
  }
  document.querySelectorAll('input[name="tee"]').forEach((r) => r.addEventListener("change", () => {
    if (r.value === "members" || r.value === "red") loadSeasons().catch(() => {});
    updateRed();
  }));
  document.querySelectorAll('input[name="fam"], #yearFrom, #yearTo').forEach((el) => el.addEventListener("change", updateRed));
  // Hard mode toggle: remembered between visits.
  try { $("hardMode").checked = localStorage.getItem("nflgolf.hard") === "1"; } catch {}
  const tip = (open) => { $("hardTip").classList.toggle("hidden", !open); $("hardHelp").setAttribute("aria-expanded", open); };
  $("hardHelp").addEventListener("click", (e) => { e.stopPropagation(); tip($("hardTip").classList.contains("hidden")); });
  document.addEventListener("click", (e) => { if (!$("hardTip").contains(e.target)) tip(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") tip(false); });
  $("hardMode").addEventListener("change", () => { try { localStorage.setItem("nflgolf.hard", $("hardMode").checked ? "1" : "0"); } catch {} });
  setChoices(true);
  renderDailyCard();
  // Members Tees (the default) needs season stats: fetch them in the background so the first round starts fast.
  if (document.querySelector('input[name="tee"]:checked').value !== "tips") setTimeout(() => loadSeasons().catch(() => {}), 500);
  // Opened from a challenge link?
  try {
    const raw = new URLSearchParams(location.search).get("challenge");
    if (raw) {
      const c = dec64(raw);
      if (c && c.v === 1 && Array.isArray(c.h) && c.h.length && c.s.length === c.h.length) { pendingChallenge = c; showChallengeCard(); }
    }
  } catch { /* a mangled link just opens the normal home screen */ }
  }
})();
