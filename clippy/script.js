/* Clippy frontend — search lyrics, highlight a span, cut the mp3.
   All the real work goes through the local helper (see clippy.py). */

// Where's the helper? If this very page is served BY the helper, same-origin
// works. Otherwise (hosted on notprsn.github.io, or opened as a file) fall back
// to the local helper on 127.0.0.1:8765. Resolved once, at boot.
const LOCAL_HELPER = "http://127.0.0.1:8765";
let API = LOCAL_HELPER;

async function resolveAPI() {
  try {
    const r = await fetch("/health", { cache: "no-store" });
    if (r.ok) {
      API = ""; // served by the helper -> same origin
      return;
    }
  } catch {
    /* not served by a helper; use the local one */
  }
  API = LOCAL_HELPER;
}

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, txt) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
};
const fmt = (s) => {
  s = Math.max(0, Math.round(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

// ---- state ----
let track = null; // { trackName, artistName, duration, lines: [{time,text}] }
let selStart = null; // index into track.lines
let selEnd = null;

// ---- helper health ----
async function checkHelper() {
  const pill = $("#helper");
  try {
    const r = await fetch(`${API}/health`, { cache: "no-store" });
    if (!r.ok) throw new Error();
    pill.className = "helper helper--online";
    pill.querySelector(".txt").textContent = "helper online";
    $("#setupCard").classList.add("hidden");
    return true;
  } catch {
    pill.className = "helper helper--offline";
    pill.querySelector(".txt").textContent = "helper offline";
    $("#setupCard").classList.remove("hidden");
    return false;
  }
}

function offlineNote() {
  const box = el("div", "offline-note");
  box.innerHTML =
    "Your local helper isn't running. Open your downloaded <code>clippy</code> folder " +
    "and run its launcher, then search again. <a href=\"#setupCard\">Need the setup steps?</a>";
  return box;
}

function showPlatformInstructions() {
  const platform = (
    navigator.userAgentData?.platform ||
    navigator.platform ||
    ""
  ).toLowerCase();
  const action = $("#launcherAction");
  const help = $("#launcherHelp");

  if (platform.includes("win")) {
    action.textContent = "Double-click start-clippy.bat";
    help.textContent = "Windows may ask whether to allow the script. Choose Run.";
  } else if (platform.includes("mac")) {
    action.textContent = "Double-click start-clippy.command";
    help.textContent = "A Terminal window will open and finish the setup for you.";
  } else if (platform.includes("linux")) {
    action.textContent = "Run bash start-clippy.sh";
    help.textContent = "Open a terminal in the clippy folder, paste that command, and press Enter.";
  }
}

// ---- search ----
$("#searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (!q) return;
  const results = $("#results");
  results.innerHTML = "";
  results.appendChild(el("div", "empty", "searching…"));

  if (!(await checkHelper())) {
    results.innerHTML = "";
    results.appendChild(offlineNote());
    return;
  }

  try {
    const r = await fetch(`${API}/lyrics?q=${encodeURIComponent(q)}`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "search failed");
    renderResults(data.results || []);
  } catch (err) {
    results.innerHTML = "";
    results.appendChild(el("div", "empty", "couldn't search: " + err.message));
  }
});

function renderResults(list) {
  const results = $("#results");
  results.innerHTML = "";
  if (!list.length) {
    results.appendChild(
      el("div", "empty", "no songs with synced lyrics found — try a different spelling.")
    );
    return;
  }
  list.slice(0, 8).forEach((item) => {
    const row = el("div", "result");
    row.appendChild(el("span", "r-title", item.trackName || "—"));
    row.appendChild(el("span", "r-artist", item.artistName || ""));
    if (item.duration) row.appendChild(el("span", "r-dur", fmt(item.duration)));
    row.addEventListener("click", () => {
      document.querySelectorAll(".result").forEach((r) => r.classList.remove("active"));
      row.classList.add("active");
      loadTrack(item);
    });
    results.appendChild(row);
  });
}

// ---- LRC parsing ----
function parseLRC(lrc) {
  const lines = [];
  const tagRe = /\[(\d{1,2}):(\d{1,2}(?:[.:]\d{1,3})?)\]/g;
  for (const raw of lrc.split("\n")) {
    const stamps = [];
    let m;
    tagRe.lastIndex = 0;
    while ((m = tagRe.exec(raw)) !== null) {
      const min = parseInt(m[1], 10);
      const sec = parseFloat(m[2].replace(":", "."));
      stamps.push(min * 60 + sec);
    }
    if (!stamps.length) continue; // skip [ar:], [ti:], blank metadata
    const text = raw.replace(tagRe, "").trim();
    for (const t of stamps) lines.push({ time: t, text });
  }
  lines.sort((a, b) => a.time - b.time);
  return lines;
}

// ---- load a track ----
function loadTrack(item) {
  const lines = parseLRC(item.syncedLyrics || "");
  if (!lines.length) return;
  track = {
    trackName: item.trackName,
    artistName: item.artistName,
    duration: item.duration || lines[lines.length - 1].time + 8,
    lines,
  };
  selStart = selEnd = null;

  $("#nowPicking").innerHTML = "";
  $("#nowPicking").appendChild(document.createTextNode(item.trackName || ""));
  $("#nowPicking").appendChild(el("small", null, item.artistName || ""));

  renderLyrics();
  $("#pickSection").classList.remove("hidden");
  $("#cutSection").classList.remove("hidden");
  $("#output").classList.add("hidden");
  $("#output").innerHTML = "";
  updateSelection();
  $("#pickSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderLyrics() {
  const box = $("#lyrics");
  box.innerHTML = "";
  track.lines.forEach((ln, i) => {
    const row = el("div", "lyric-line" + (ln.text ? "" : " instrumental"));
    row.dataset.i = i;
    row.appendChild(el("span", "ts", fmt(ln.time)));
    row.appendChild(el("span", "tx", ln.text || "♪ ♪ ♪"));
    row.addEventListener("click", () => pickLine(i));
    box.appendChild(row);
  });
}

// two-click range: first click sets start, second sets end, third restarts
function pickLine(i) {
  if (selStart === null || selEnd !== null) {
    selStart = i;
    selEnd = null;
  } else {
    if (i < selStart) {
      selEnd = selStart;
      selStart = i;
    } else {
      selEnd = i;
    }
  }
  paintSelection();
  updateSelection();
}

function paintSelection() {
  const lo = selStart;
  const hi = selEnd === null ? selStart : selEnd;
  document.querySelectorAll(".lyric-line").forEach((row) => {
    const i = +row.dataset.i;
    row.classList.toggle("sel", lo !== null && i >= lo && i <= hi);
    row.classList.toggle("endpoint", i === selStart || (selEnd !== null && i === selEnd));
  });
}

function selectionTimes() {
  if (selStart === null) return null;
  const lo = selStart;
  const hi = selEnd === null ? selStart : selEnd;
  const start = track.lines[lo].time;
  const end = hi + 1 < track.lines.length ? track.lines[hi + 1].time : track.duration;
  return { start, end };
}

function updateSelection() {
  const t = selectionTimes();
  const info = $("#selInfo");
  const btn = $("#cutBtn");
  if (!t) {
    info.textContent = "nothing selected yet";
    btn.disabled = true;
    return;
  }
  const len = t.end - t.start;
  info.innerHTML = `selected <b>${fmt(t.start)} → ${fmt(t.end)}</b> · ${len.toFixed(1)}s`;
  btn.disabled = len <= 0;
}

// ---- cut it ----
$("#cutBtn").addEventListener("click", async () => {
  const t = selectionTimes();
  if (!t || !track) return;
  const out = $("#output");
  out.classList.remove("hidden");
  out.innerHTML = "";
  const status = el("div", "status");
  status.appendChild(el("span", "spinner"));
  status.appendChild(el("span", null, "grabbing audio + cutting… (first clip of a song downloads it; later ones are instant)"));
  out.appendChild(status);

  if (!(await checkHelper())) {
    out.innerHTML = "";
    out.appendChild(offlineNote());
    return;
  }

  try {
    const body = {
      title: track.trackName,
      artist: track.artistName,
      duration: track.duration,
      start: t.start,
      end: t.end,
      fade: $("#fade").checked,
      url: $("#ytUrl").value.trim() || undefined,
    };
    const r = await fetch(`${API}/clip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      let msg = "cut failed";
      try {
        msg = (await r.json()).error || msg;
      } catch {}
      throw new Error(msg);
    }
    const fname =
      r.headers.get("X-Clippy-Filename") ||
      `${track.artistName} - ${track.trackName}.mp3`;
    const blob = await r.blob();
    const urlObj = URL.createObjectURL(blob);

    out.innerHTML = "";
    const audio = el("audio");
    audio.controls = true;
    audio.src = urlObj;
    out.appendChild(audio);
    const dl = el("a", "dl", "⬇  download mp3");
    dl.href = urlObj;
    dl.download = fname;
    out.appendChild(dl);
    out.appendChild(el("span", "fname", fname));
  } catch (err) {
    out.innerHTML = "";
    const s = el("div", "status err");
    s.textContent = "😕  " + err.message;
    out.appendChild(s);
  }
});

// boot
(async () => {
  showPlatformInstructions();
  await resolveAPI();
  checkHelper();
})();
