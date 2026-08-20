const $ = (id) => document.getElementById(id);
const SEEN_KEY = "msm-last-alert-ts";
let usingLocalApi = false;

function cls(v) {
  return String(v || "")
    .toLowerCase()
    .replace(/\s+/g, "_");
}

function fmt(n, d = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toFixed(d);
}

function chg(n) {
  if (n === null || n === undefined) return "";
  const s = `${n >= 0 ? "+" : ""}${fmt(n, 2)}%`;
  return `<span class="chg ${n >= 0 ? "up" : "down"}">${s}</span>`;
}

function pill(text, kind) {
  return `<span class="pill ${cls(kind || text)}">${text}</span>`;
}

function spark(values, up) {
  const w = 240, h = 36;
  if (!values || values.length < 2) return "";
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / span) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const color = up ? "#3dd68c" : "#ff5d6c";
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke="${color}" stroke-width="2" points="${pts.join(" ")}"/></svg>`;
}

function indexCard(inst) {
  const up = (inst.change_pct || 0) >= 0;
  return `<article class="idx">
    <div class="idx-top">
      <span class="sym">${inst.symbol}</span>
      ${pill(inst.regime, inst.regime)}
    </div>
    <div class="px">${fmt(inst.price, 2)} ${chg(inst.change_pct)}</div>
    ${spark(inst.spark, up)}
    <div class="meta"><span>50d ${inst.vs50_pct == null ? "—" : fmt(inst.vs50_pct, 1) + "%"}</span><span>200d ${inst.vs200_pct == null ? "—" : fmt(inst.vs200_pct, 1) + "%"}</span></div>
    <div class="meta"><span>daily ${inst.daily_structure}</span><span>weekly ${inst.weekly_structure}</span></div>
  </article>`;
}

function render(s) {
  $("clock").textContent = s.ts_label || "—";
  $("session-pill").className = "pill " + (s.rth ? "live" : "closed");
  $("session-pill").textContent = s.rth ? "RTH live" : "session closed";
  $("updated").textContent = s.ts ? `Updated ${s.ts_label}` : "";

  const score = (s.score || {}).value;
  const label = (s.score || {}).label || "—";
  $("score-value").textContent = score == null ? "—" : fmt(score, 0);
  $("score-label").className = "pill " + cls(label);
  $("score-label").textContent = label;
  $("score-bar").style.width = score == null ? "0%" : `${Math.max(4, Math.min(100, score))}%`;
  $("score-bar").style.background = score >= 70 ? "var(--green)" : score >= 45 ? "var(--amber)" : "var(--red)";

  const vol = s.volatility || {};
  $("vix-line").textContent = `VIX ${fmt(vol.vix, 2)}`;
  $("vix-sub").textContent = `${(vol.vix_bucket || "").replace("_", " ")} · ${(vol.term_state || "—")} (${fmt(vol.term_ratio, 3)})`;

  const inn = s.internals || {};
  $("breadth-line").textContent = `${inn.sectors_above_50 ?? "—"} / ${inn.sectors_total ?? 11}`;
  $("breadth-sub").textContent = `${(inn.breadth_bucket || "").replace("_", " ")} · sectors above 50 DMA`;

  const hosted = !!s.hosted;
  $("scan-btn").hidden = hosted;
  $("test-btn").hidden = hosted;
  $("notify-btn").hidden = !hosted;
  if (hosted) syncNotifyButton();
  notifyNewAlerts(s);
  if (hosted) {
    $("ntfy-topic").textContent = "ntfy alerts on (topic not published)";
    $("tailscale-line").textContent = "Cloud dashboard · GitHub Pages · PC can be off";
    $("updated").textContent = (s.ts ? `Updated ${s.ts_label}` : "") + " · refresh ~15 min in RTH";
  } else {
    const server = (s.ntfy_server || "https://ntfy.sh").replace(/\/$/, "");
    const topic = s.ntfy_topic || "—";
    $("ntfy-topic").innerHTML = `<a href="${server}/${topic}" target="_blank" rel="noopener">${topic}</a>`;
    const acc = s.access || {};
    if (acc.tailscale) {
      $("tailscale-line").innerHTML = `<a href="${acc.tailscale}">${acc.tailscale}</a>`;
    } else if (acc.tailscale_installed && acc.tailscale_state && acc.tailscale_state !== "running") {
      $("tailscale-line").textContent = `Tailscale: ${acc.tailscale_state} — log in on this PC`;
    } else if (acc.tailscale_installed) {
      $("tailscale-line").textContent = "Tailscale: installed, waiting for login";
    } else {
      $("tailscale-line").textContent = "Tailscale: not installed on this PC";
    }
  }

  $("indices").innerHTML = (s.indices || []).map(indexCard).join("") || "<p class='muted'>No index data.</p>";

  const orbs = s.opening || {};
  const orbKeys = Object.keys(orbs);
  $("opening").innerHTML = orbKeys.length
    ? orbKeys.map((sym) => {
        const o = orbs[sym];
        return `<div class="orb"><strong>${sym}</strong> ${pill(o.status, o.status === "break_up" ? "bull" : o.status === "break_down" ? "bear" : "range")}
          <div class="meta"><span>last ${fmt(o.last)}</span><span>ORH ${fmt(o.orh)} / ORL ${fmt(o.orl)}</span></div>
          <div class="meta"><span>VWAP ${o.vs_vwap}</span><span>${o.date}</span></div></div>`;
      }).join("")
    : "<p class='muted'>Opening-range appears during the US cash session.</p>";

  $("cross").innerHTML = (s.cross_asset || []).map((c) => `<article>
      <div class="idx-top"><span class="sym">${c.symbol}</span>${pill(c.regime, c.regime)}</div>
      <div class="px" style="font-size:18px">${fmt(c.price, 2)} ${chg(c.change_pct)}</div>
      <div class="meta"><span>vs50 ${c.vs50_pct == null ? "—" : fmt(c.vs50_pct, 1) + "%"}</span><span>${c.daily_structure}</span></div>
    </article>`).join("");

  $("sectors").innerHTML = (s.sectors || []).map((sec) => {
    const w = Math.min(100, Math.abs(sec.vs50_pct || 0) * 8 + 12);
    return `<div class="sector">
      <div><strong>${sec.symbol}</strong><div class="name muted">${sec.name}</div></div>
      <div class="track ${sec.above50 ? "" : "off"}"><span style="width:${w}%"></span></div>
      <div>${chg(sec.change_pct)}</div>
    </div>`;
  }).join("");

  const rels = [
    ["IWM vs SPY", inn.iwm_vs_spy_20d],
    ["RSP vs SPY", inn.rsp_vs_spy_20d],
    ["QQQ vs SPY", inn.qqq_vs_spy_20d],
    ["HYG vs TLT", inn.hyg_vs_tlt_20d],
  ];
  $("relative").innerHTML = rels.map(([name, v]) => `<div class="rel">
    <div class="idx-top"><span>${name}</span>${v == null ? "" : pill(v >= 0 ? "lead" : "lag", v >= 0 ? "bull" : "bear")}</div>
    <div class="mono">${v == null ? "—" : (v >= 0 ? "+" : "") + fmt(v, 2) + "%"} over 20 sessions</div>
  </div>`).join("");

  const hist = (s.alert_history || []).slice().reverse();
  $("alerts").innerHTML = hist.length
    ? hist.map((a) => `<article class="alert">
        <div class="sev ${a.severity}">${a.severity}<div class="muted">${(a.ts || "").replace("T", " ").slice(0, 16)}</div></div>
        <div><h3>${a.title}</h3><p class="muted">${a.body}</p></div>
      </article>`).join("")
    : "<p class='muted'>No structure changes yet. The first scan seeds a baseline; later flips show up here and on your phone.</p>";
}

function newestAlertTs(s) {
  const hist = s.alert_history || [];
  let max = "";
  for (const a of hist) {
    if (a && a.ts && a.ts > max) max = a.ts;
  }
  return max;
}

function notifyNewAlerts(s) {
  if (usingLocalApi) return;
  if (!("Notification" in window) || Notification.permission !== "granted") {
    const ts = newestAlertTs(s);
    if (ts && !localStorage.getItem(SEEN_KEY)) localStorage.setItem(SEEN_KEY, ts);
    return;
  }
  const prev = localStorage.getItem(SEEN_KEY) || "";
  const hist = (s.alert_history || []).filter((a) => a && a.ts && a.ts > prev);
  const ts = newestAlertTs(s);
  if (ts) localStorage.setItem(SEEN_KEY, ts);
  if (!prev) return;
  for (const a of hist.slice(-4)) {
    try {
      new Notification(a.title || "Market structure", {
        body: a.body || "",
        silent: true,
        tag: a.id || a.ts,
      });
    } catch (err) {
      /* ignore */
    }
  }
}

function syncNotifyButton() {
  const btn = $("notify-btn");
  if (!btn || btn.hidden) return;
  if (!("Notification" in window)) {
    btn.hidden = true;
    return;
  }
  if (Notification.permission === "granted") btn.textContent = "Desktop alerts on";
  else if (Notification.permission === "denied") btn.textContent = "Alerts blocked in browser";
  else btn.textContent = "Enable desktop alerts";
}

async function load() {
  const errors = [];
  for (const url of ["/api/snapshot", "snapshot.json"]) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`${url} ${res.status}`);
      usingLocalApi = url === "/api/snapshot";
      render(await res.json());
      return;
    } catch (err) {
      errors.push(err);
    }
  }
  throw errors[errors.length - 1] || new Error("snapshot failed");
}

$("notify-btn").addEventListener("click", async () => {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    new Notification("Market structure alerts on", {
      body: "Quiet Windows banners when structure flips. Keep this tab open.",
      silent: true,
    });
    syncNotifyButton();
    return;
  }
  const perm = await Notification.requestPermission();
  syncNotifyButton();
  if (perm === "granted") {
    new Notification("Market structure alerts on", {
      body: "Quiet Windows banners when structure flips. Keep this tab open.",
      silent: true,
    });
  }
});

$("test-btn").addEventListener("click", async () => {
  $("test-btn").disabled = true;
  $("test-btn").textContent = "Sending…";
  try {
    const res = await fetch("/api/test-notify", { method: "POST" });
    $("test-btn").textContent = res.ok ? "Sent — check ntfy / Windows" : "Send failed";
  } catch (err) {
    $("test-btn").textContent = "Send failed";
  } finally {
    setTimeout(() => {
      $("test-btn").disabled = false;
      $("test-btn").textContent = "Send test push";
    }, 2500);
  }
});

$("scan-btn").addEventListener("click", async () => {
  $("scan-btn").disabled = true;
  $("scan-btn").textContent = "Scanning…";
  try {
    await fetch("/api/scan", { method: "POST" });
    await load();
  } finally {
    $("scan-btn").disabled = false;
    $("scan-btn").textContent = "Scan now";
  }
});

load().catch((err) => {
  $("updated").textContent = "Could not load snapshot. If you just started the app, wait a few seconds.";
  console.error(err);
});
setInterval(() => load().catch(() => {}), 20000);
