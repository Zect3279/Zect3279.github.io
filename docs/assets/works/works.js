/* works page: WALL（既定）/ RING 切替と詳細ビュー */
(() => {
  const root = document.getElementById("zw");
  if (!root) return;
  const items = JSON.parse(document.getElementById("zw-data").textContent);
  const N = items.length;
  const wallEl = document.getElementById("zw-wall");
  const ringEl = document.getElementById("zw-ring");
  const detEl = document.getElementById("zw-detail");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const EASE = "cubic-bezier(.2,.8,.2,1)";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const portrait = () => innerHeight > innerWidth || innerWidth <= 700;
  const store = {
    get() { try { return localStorage.getItem("zw-mode"); } catch { return null; } },
    set(v) { try { localStorage.setItem("zw-mode", v); } catch { /* noop */ } },
  };
  const tint = (it) => `color-mix(in srgb, ${it.color || "#E4E7EC"} 42%, #FFFFFF)`;

  /* ---------- 共通：札/カードの中身 ---------- */
  function face(it, full) {
    if (it.status === "tba") {
      return `<span class="zw-card zw-card--tba"><span class="zw-mono">COMING SOON</span><span><span class="zw-serif zw-card-d">${esc(it.range)}</span><span class="zw-mono">${esc(it.y)}</span></span></span>`;
    }
    if (it.img) {
      const src = full ? it.img : it.thumb;
      return `<img ${full ? "" : 'data-'}src="${esc(src)}" alt="${esc(it.alt)}" draggable="false" decoding="async">`;
    }
    return `<span class="zw-card"><span class="zw-card-t">${esc(it.title)}</span><span class="zw-serif zw-card-d">${esc(it.md)}</span></span>`;
  }

  /* ---------- モード切替 ---------- */
  let mode = "wall";
  function setMode(m, push = true) {
    if (m === mode) return;
    mode = m;
    root.dataset.mode = m;
    root.querySelectorAll(".zw-toggle button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === m)));
    wallEl.hidden = m !== "wall";
    ringEl.hidden = m !== "ring";
    if (m === "ring") ring.show();
    else ring.hide();
    store.set(m);
    if (push) history.replaceState(null, "", m === "ring" ? "#ring" : location.pathname + location.search);
    window.scrollTo(0, 0);
  }
  root.querySelectorAll(".zw-toggle button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));

  /* ---------- RING（螺旋状のリング。1周 K 枚、横スワイプで時間を移動） ---------- */
  const ring = (() => {
    let built = false, p = 0, v = 0, raf = 0, target = null, drag = null, moved = false;
    let K, step, R, pitch, cw, ch, cards = [], els = {};
    const startIndex = () => { const k = items.findIndex((it) => it.status !== "past"); return k < 0 ? N - 1 : k; };

    function build() {
      const years = [...new Set(items.map((it) => it.y))];
      ringEl.innerHTML = `
        <div class="zw-ryear" aria-hidden="true"></div>
        <div class="zw-stage"><div class="zw-scene">${items.map((it) =>
          `<button type="button" class="zw-rc" data-i="${it.i}" aria-label="${esc(it.full)} ${esc(it.title || "COMING SOON")}">${face(it, false)}</button>`).join("")}</div></div>
        <footer class="zw-rfoot">
          <div class="zw-rcap"><span class="zw-serif zw-rdate"></span><span class="zw-mono zw-rtitle"></span></div>
          <nav class="zw-years" aria-label="年へ移動">${years.map((y) => `<button type="button" data-y="${y}">${y}</button>`).join("")}</nav>
          <div class="zw-rnav"><span class="zw-mono"><span class="zw-swipe">← SWIPE →&nbsp;&nbsp;</span><span class="zw-pos"></span></span>
            <button type="button" class="zw-round" data-d="-1" aria-label="前へ">←</button>
            <button type="button" class="zw-round" data-d="1" aria-label="次へ">→</button></div>
        </footer>`;
      els = {
        year: ringEl.querySelector(".zw-ryear"), stage: ringEl.querySelector(".zw-stage"), scene: ringEl.querySelector(".zw-scene"),
        date: ringEl.querySelector(".zw-rdate"), title: ringEl.querySelector(".zw-rtitle"), pos: ringEl.querySelector(".zw-pos"),
        years: [...ringEl.querySelectorAll(".zw-years button")],
      };
      cards = [...ringEl.querySelectorAll(".zw-rc")];
      // フライヤーは元の縦横比のまま 3:4 の枠に収める
      cards.forEach((c) => {
        const img = c.querySelector("img");
        const m = img && (items[+c.dataset.i].ar || "").match(/([\d.]+)\s*\/\s*([\d.]+)/);
        if (!m) return;
        const r = (+m[1] / +m[2]) / (3 / 4); // >1 なら横長寄り
        img.style.width = r > 1 ? "100%" : (r * 100).toFixed(2) + "%";
        img.style.height = r > 1 ? (100 / r).toFixed(2) + "%" : "100%";
      });
      cards.forEach((c) => c.addEventListener("click", () => {
        if (moved) return;
        const i = +c.dataset.i;
        if (i === Math.round(p)) detail.open(i, c.firstElementChild, "ring"); else to(i);
      }));
      ringEl.querySelectorAll(".zw-round").forEach((b) => b.addEventListener("click", () => to(Math.round(p) + +b.dataset.d)));
      els.years.forEach((b) => b.addEventListener("click", () => {
        const idx = items.map((it) => it.y).lastIndexOf(b.dataset.y);
        to(idx);
      }));
      ringEl.addEventListener("pointerdown", down);
      ringEl.addEventListener("pointermove", move);
      ringEl.addEventListener("pointerup", up);
      ringEl.addEventListener("pointercancel", up);
      ringEl.addEventListener("wheel", wheel, { passive: false });
      addEventListener("resize", () => { if (!ringEl.hidden) { layout(); render(); } });
      p = startIndex();
      built = true;
    }

    function layout() {
      const pt = portrait();
      K = pt ? 16 : 22;
      cw = pt ? Math.min(240, innerWidth * 0.52) : Math.min(300, Math.max(200, innerWidth * 0.2));
      ch = cw * 4 / 3;
      step = 360 / K;
      R = (K * cw * 1.14) / (2 * Math.PI);
      pitch = ch * 0.5 / K; // 1周で 半札分 だけ下がる螺旋
      ringEl.style.setProperty("--zw-cw", cw + "px");
      ringEl.style.setProperty("--zw-ch", ch + "px");
      ringEl.style.setProperty("--zw-persp", (pt ? 1000 : 1700) + "px");
      cards.forEach((c, i) => { c.style.transform = `translateY(${i * pitch}px) rotateY(${i * step}deg) translateZ(${R}px)`; });
    }

    function render() {
      els.scene.style.transform = `translateZ(${-R}px) rotateX(-4deg) translateY(${-p * pitch}px) rotateY(${-p * step}deg)`;
      const half = K / 2;
      cards.forEach((c, i) => {
        const d = Math.abs(i - p);
        if (d > half) { c.style.visibility = "hidden"; return; }
        c.style.visibility = "";
        c.style.pointerEvents = d < K / 4 ? "" : "none"; // 奥側の札はクリックを拾わない
        c.style.opacity = (1 - (d / half) * 0.8).toFixed(3);
        const img = c.querySelector("img[data-src]");
        if (img) { img.src = img.dataset.src; img.removeAttribute("data-src"); }
      });
      const fi = Math.max(0, Math.min(N - 1, Math.round(p)));
      const f = items[fi];
      els.year.textContent = f.y;
      els.date.textContent = f.full;
      els.title.textContent = f.status === "tba" ? "COMING SOON" : f.title;
      els.pos.textContent = `${String(fi + 1).padStart(2, "0")} / ${N}`;
      els.years.forEach((b) => b.setAttribute("aria-current", String(b.dataset.y === f.y)));
      ringEl.style.backgroundColor = tint(f);
      cards.forEach((c, i) => c.toggleAttribute("data-front", i === fi));
    }

    function loop() {
      cancelAnimationFrame(raf);
      const tick = () => {
        if (drag) return;
        if (target === null) {
          p += v; v *= 0.92;
          if (p < 0 || p > N - 1) { v *= 0.5; }
          if (Math.abs(v) < 0.004) { v = 0; target = Math.max(0, Math.min(N - 1, Math.round(p))); }
        } else {
          const d = target - p;
          p += d * (reduce ? 1 : 0.16);
          if (Math.abs(d) < 0.002) { p = target; target = null; render(); return; }
        }
        render();
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }
    function to(i) { v = 0; target = Math.max(0, Math.min(N - 1, i)); loop(); }
    function down(e) {
      if (e.target.closest(".zw-rfoot")) return;
      cancelAnimationFrame(raf); target = null; moved = false;
      drag = { x: e.clientX, p, lx: e.clientX, t: performance.now() };
      ringEl.classList.add("is-drag");
    }
    function move(e) {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      if (Math.abs(dx) > 5 && !moved) { moved = true; try { ringEl.setPointerCapture(e.pointerId); } catch { /* noop */ } }
      const now = performance.now();
      const unit = cw * 1.1;
      v = -((e.clientX - drag.lx) / unit) * Math.min(2, 16 / Math.max(1, now - drag.t));
      drag.lx = e.clientX; drag.t = now;
      let np = drag.p - dx / unit;
      if (np < 0) np = np / 3; else if (np > N - 1) np = N - 1 + (np - (N - 1)) / 3; // 端はゴムのように
      p = np; render();
    }
    function up() {
      if (!drag) return;
      drag = null; ringEl.classList.remove("is-drag"); loop();
      setTimeout(() => { moved = false; }, 0);
    }
    let wheelT = 0;
    function wheel(e) {
      if (!detEl.hidden) return;
      e.preventDefault();
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      cancelAnimationFrame(raf); target = null;
      p = Math.max(-0.3, Math.min(N - 0.7, p + d / (cw * 1.6)));
      render();
      clearTimeout(wheelT); wheelT = setTimeout(() => to(Math.round(p)), 120);
    }

    return {
      show() { if (!built) build(); layout(); render(); },
      hide() { cancelAnimationFrame(raf); },
      to, current: () => Math.round(p),
      card: (i) => cards[i],
      dim(on) { ringEl.classList.toggle("is-dim", on); },
      key(e) { if (e.key === "ArrowLeft") to(Math.round(p) - 1); if (e.key === "ArrowRight") to(Math.round(p) + 1); },
    };
  })();

  /* ---------- DETAIL ---------- */
  const detail = (() => {
    let cur = -1, from = "wall", lastFocus = null;

    function row(k, v) { return v ? `<div><dt>${k}</dt><dd>${v}</dd></div>` : ""; }
    function linkOr(text, url) { return url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : esc(text); }

    function html(it) {
      const tickets = (it.tickets || []).map((t) => t.url ? `<a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.label || "TICKET")} ↗</a>` : esc(t.label)).join("");
      const tba = it.status === "tba";
      return `
        <div class="zw-dback">${it.img ? `<img src="${esc(it.thumb)}" alt="">` : ""}</div>
        <div class="zw-dfig">${face(it, true)}</div>
        <section class="zw-dpanel">
          <div class="zw-dtop"><span class="zw-mono">${String(it.i + 1).padStart(2, "0")} / ${N}</span>
            <button type="button" class="zw-close" aria-label="閉じる">✕</button></div>
          <div class="zw-dmain">
            <div><p class="zw-mono zw-dmeta">${esc(it.y)} · ${esc(it.dow)}${it.status === "upcoming" ? " · NEXT" : ""}</p>
              <h2 class="zw-ddate">${esc(it.range)}</h2></div>
            <h3 class="zw-dtitle">${tba ? "COMING SOON" : esc(it.title)}</h3>
            ${tba ? "" : `<dl class="zw-dl">${row("VENUE", it.venue && linkOr(it.venue, it.venue_url))}${row("ORGANIZER", it.organizer && linkOr(it.organizer, it.organizer_url))}${row("TICKET", tickets)}${row("ROLE", esc(it.role))}</dl>`}
          </div>
          <div class="zw-dnav"><button type="button" data-d="-1" ${it.i === 0 ? "disabled" : ""}>← PREV</button><button type="button" data-d="1" ${it.i === N - 1 ? "disabled" : ""}>NEXT →</button></div>
        </section>`;
    }

    function fill(i) {
      cur = i;
      detEl.innerHTML = html(items[i]);
      detEl.querySelector(".zw-close").addEventListener("click", close);
      detEl.querySelectorAll(".zw-dnav button").forEach((b) => b.addEventListener("click", () => go(+b.dataset.d)));
    }

    function flip(fromEl) {
      const fig = detEl.querySelector(".zw-dfig > *");
      if (!fig || !fromEl || reduce) return;
      const a = fromEl.getBoundingClientRect(), b = fig.getBoundingClientRect();
      if (!a.width || !b.width) return;
      const dx = a.left + a.width / 2 - (b.left + b.width / 2), dy = a.top + a.height / 2 - (b.top + b.height / 2);
      const s = a.width / b.width;
      fig.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${s})` }, { transform: getComputedStyle(fig).transform === "none" ? "none" : getComputedStyle(fig).transform }],
        { duration: 650, easing: EASE });
    }
    function fadeIn() {
      if (reduce) return;
      const panel = detEl.querySelector(".zw-dpanel"), back = detEl.querySelector(".zw-dback");
      panel.animate([{ opacity: 0, transform: portrait() ? "translateY(40px)" : "translateX(40px)" }, { opacity: 1, transform: "none" }], { duration: 500, delay: 180, easing: EASE, fill: "backwards" });
      if (back) back.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400 });
    }

    function open(i, fromEl, src) {
      from = src;
      lastFocus = document.activeElement;
      fill(i);
      detEl.classList.toggle("is-ring", src === "ring");
      detEl.classList.toggle("is-wall", src !== "ring");
      detEl.hidden = false;
      root.classList.add("is-detail");
      document.documentElement.style.overflow = "hidden";
      if (src === "ring") ring.dim(true);
      flip(fromEl);
      fadeIn();
      detEl.querySelector(".zw-close").focus({ preventScroll: true });
    }

    function go(d) {
      const n = cur + d;
      if (n < 0 || n >= N) return;
      fill(n);
      if (from === "ring") { ring.to(n); }
      if (!reduce) detEl.querySelectorAll(".zw-dfig, .zw-dmain").forEach((el) => el.animate([{ opacity: 0, transform: `translateX(${d * 24}px)` }, { opacity: 1, transform: "none" }], { duration: 380, easing: EASE }));
      detEl.querySelector(".zw-close").focus({ preventScroll: true });
    }

    function close() {
      const done = () => {
        detEl.hidden = true; detEl.innerHTML = "";
        root.classList.remove("is-detail");
        document.documentElement.style.overflow = "";
        if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
      };
      if (from === "ring") ring.dim(false);
      if (reduce) return done();
      detEl.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 250, easing: "ease" }).onfinish = done;
    }

    return { open, close, go, isOpen: () => !detEl.hidden };
  })();

  /* ---------- WALL：新しい順に、いちばん短い列へ順に詰める ---------- */
  (() => {
    const grids = [...wallEl.querySelectorAll(".zw-grid")];
    const tiles = grids.map((g) => [...g.querySelectorAll(".zw-tile")]);
    const ratio = (t) => {
      const ar = (items[+t.dataset.i] || {}).ar;
      const m = ar && ar.match(/([\d.]+)\s*\/\s*([\d.]+)/);
      return m ? +m[2] / +m[1] : 4 / 3;
    };
    const cols = () => {
      if (innerWidth <= 600) return 3;
      const gap = 8, w = wallEl.clientWidth - 16;
      return Math.max(1, Math.min(5, Math.floor((w + gap) / (220 + gap))));
    };
    let n = 0;
    function layout() {
      const k = cols();
      if (k === n) return;
      n = k;
      grids.forEach((g, gi) => {
        const colEls = Array.from({ length: k }, () => Object.assign(document.createElement("div"), { className: "zw-col" }));
        const h = new Array(k).fill(0);
        tiles[gi].forEach((t) => {
          let c = 0;
          for (let j = 1; j < k; j++) if (h[j] < h[c] - 0.01) c = j;
          colEls[c].appendChild(t);
          h[c] += ratio(t) + 0.04;
        });
        g.replaceChildren(...colEls);
        g.classList.add("is-masonry");
      });
    }
    layout();
    let rt = 0;
    addEventListener("resize", () => { cancelAnimationFrame(rt); rt = requestAnimationFrame(layout); });
  })();

  wallEl.addEventListener("click", (e) => {
    const t = e.target.closest(".zw-tile");
    if (!t) return;
    detail.open(+t.dataset.i, t.querySelector("img, .zw-card"), "wall");
  });
  detEl.addEventListener("click", (e) => { if (e.target === detEl || e.target.classList.contains("zw-dback")) detail.close(); });

  document.addEventListener("keydown", (e) => {
    if (detail.isOpen()) {
      if (e.key === "Escape") detail.close();
      else if (e.key === "ArrowLeft") detail.go(-1);
      else if (e.key === "ArrowRight") detail.go(1);
    } else if (mode === "ring") ring.key(e);
  });

  // 初期モード：#ring > 前回の選択 > WALL
  const initial = location.hash === "#ring" ? "ring" : store.get() === "ring" ? "ring" : "wall";
  if (initial === "ring") setMode("ring", false);
})();
