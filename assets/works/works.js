/* works page: WALL（既定）/ RING 切替と詳細ビュー */
(() => {
  const root = document.getElementById("zw");
  if (!root) return;
  const items = JSON.parse(document.getElementById("zw-data").textContent);
  const N = items.length;
  const wallEl = document.getElementById("zw-wall");
  const ringEl = document.getElementById("zw-ring");
  const detEl = document.getElementById("zw-detail");
  const toggles = document.querySelectorAll(".zw-toggle button");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const EASE = "cubic-bezier(.2,.8,.2,1)"; // = CSS の --zw-ease

  /* ---------- 小道具 ---------- */
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clamp = (i) => Math.max(0, Math.min(N - 1, i));
  const pad = (n) => String(n).padStart(2, "0");
  const portrait = () => innerHeight > innerWidth || innerWidth <= 700;
  const label = (it) => it.status === "tba" ? "COMING SOON" : it.title;
  const link = (text, url) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : esc(text);
  /** 高さ / 幅（縦横比が分からなければ 3:4） */
  const ratio = (it) => {
    const m = (it.ar || "").match(/([\d.]+)\s*\/\s*([\d.]+)/);
    return m ? m[2] / m[1] : 4 / 3;
  };
  const tint = (it) => `color-mix(in srgb, ${it.color || "#E4E7EC"} 42%, #FFFFFF)`;
  const store = {
    get() { try { return localStorage.getItem("zw-mode"); } catch { return null; } },
    set(v) { try { localStorage.setItem("zw-mode", v); } catch { /* noop */ } },
  };

  /* 札/カードの中身（RING と詳細で使う。WALL の札は overrides/works.html） */
  function face(it, full) {
    if (it.status === "tba") {
      return `<span class="zw-card zw-card--tba"><span class="zw-mono">COMING SOON</span><span><span class="zw-light zw-card-d">${esc(it.range)}</span><span class="zw-mono">${esc(it.y)}</span></span></span>`;
    }
    if (it.img) {
      return `<img ${full ? "" : "data-"}src="${esc(full ? it.img : it.thumb)}" alt="${esc(it.alt)}" draggable="false" decoding="async">`;
    }
    return `<span class="zw-card"><span class="zw-card-t">${esc(it.title)}</span><span class="zw-light zw-card-d">${esc(it.md)}</span></span>`;
  }

  /* ---------- モード切替 ---------- */
  let mode = "wall";
  function setMode(m, updateUrl = true) {
    if (m === mode) return;
    mode = m;
    toggles.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === m)));
    wallEl.hidden = m !== "wall";
    ringEl.hidden = m !== "ring";
    if (m === "ring") ring.show(); else ring.hide();
    store.set(m);
    if (updateUrl) history.replaceState(null, "", m === "ring" ? "#ring" : location.pathname + location.search);
    scrollTo(0, 0);
  }
  toggles.forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));

  /* ---------- RING（螺旋状のリング。1周 K 枚、横スワイプで時間を移動） ---------- */
  const ring = (() => {
    let built = false, p = 0, v = 0, raf = 0, target = null, drag = null, moved = false, wheelT = 0;
    let K, step, R, pitch, cw, cards = [], els = {};
    const front = () => clamp(Math.round(p));

    function build() {
      const years = [...new Set(items.map((it) => it.y))];
      ringEl.innerHTML = `
        <div class="zw-ryear" aria-hidden="true"></div>
        <div class="zw-stage"><div class="zw-scene">${items.map((it) =>
          `<button type="button" class="zw-rc" data-i="${it.i}" aria-label="${esc(it.full)} ${esc(it.title || "COMING SOON")}">${face(it, false)}</button>`).join("")}</div></div>
        <footer class="zw-rfoot">
          <div class="zw-rcap"><span class="zw-light zw-rdate"></span><span class="zw-mono zw-rtitle"></span></div>
          <nav class="zw-years" aria-label="年へ移動">${years.map((y) => `<button type="button" data-y="${y}">${y}</button>`).join("")}</nav>
          <div class="zw-rnav"><span class="zw-mono"><span class="zw-swipe">← SWIPE →&nbsp;&nbsp;</span><span class="zw-pos"></span></span>
            <button type="button" class="zw-round" data-d="-1" aria-label="前へ">←</button>
            <button type="button" class="zw-round" data-d="1" aria-label="次へ">→</button></div>
        </footer>`;
      const $ = (sel) => ringEl.querySelector(sel);
      els = {
        year: $(".zw-ryear"), scene: $(".zw-scene"), date: $(".zw-rdate"), title: $(".zw-rtitle"), pos: $(".zw-pos"),
        years: [...ringEl.querySelectorAll(".zw-years button")],
      };
      cards = [...ringEl.querySelectorAll(".zw-rc")];

      cards.forEach((c, i) => {
        // フライヤーは元の縦横比のまま 3:4 の枠に収める
        const img = c.querySelector("img");
        if (img && items[i].ar) {
          const r = (4 / 3) / ratio(items[i]); // 枠と比べた横長さ（>1 なら枠より横長）
          img.style.width = r > 1 ? "100%" : (r * 100).toFixed(2) + "%";
          img.style.height = r > 1 ? (100 / r).toFixed(2) + "%" : "100%";
        }
        c.addEventListener("click", () => {
          if (moved) return;
          if (i === Math.round(p)) detail.open(i, c.firstElementChild, "ring"); else to(i);
        });
      });
      ringEl.querySelectorAll(".zw-round").forEach((b) => b.addEventListener("click", () => by(+b.dataset.d)));
      els.years.forEach((b) => b.addEventListener("click", () => to(items.findLastIndex((it) => it.y === b.dataset.y))));
      ringEl.addEventListener("pointerdown", down);
      ringEl.addEventListener("pointermove", move);
      ringEl.addEventListener("pointerup", up);
      ringEl.addEventListener("pointercancel", up);
      ringEl.addEventListener("wheel", wheel, { passive: false });
      addEventListener("resize", () => { if (!ringEl.hidden) { layout(); render(); } });
      const next = items.findIndex((it) => it.status !== "past");
      p = next < 0 ? N - 1 : next;
      built = true;
    }

    function layout() {
      const pt = portrait();
      K = pt ? 16 : 22;
      cw = pt ? Math.min(240, innerWidth * 0.52) : Math.min(300, Math.max(200, innerWidth * 0.2));
      cw = Math.min(cw, (ringEl.clientHeight || innerHeight) * 0.32); // ヘッダーの分だけ低いリングに収める
      const ch = cw * 4 / 3;
      step = 360 / K;
      R = (K * cw * 1.14) / (2 * Math.PI);
      pitch = ch * 0.5 / K; // 1周で半札分だけ下がる螺旋
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
        const img = c.querySelector("img[data-src]"); // 見える範囲に来たら読み込む
        if (img) { img.src = img.dataset.src; img.removeAttribute("data-src"); }
      });
      const fi = front(), f = items[fi];
      els.year.textContent = f.y;
      els.date.textContent = f.full;
      els.title.textContent = label(f);
      els.pos.textContent = `${pad(fi + 1)} / ${N}`;
      els.years.forEach((b) => b.setAttribute("aria-current", String(b.dataset.y === f.y)));
      ringEl.style.backgroundColor = tint(f);
      cards.forEach((c, i) => c.toggleAttribute("data-front", i === fi));
    }

    /** 慣性（target なし）か、target へ吸い寄せるアニメーション */
    function loop() {
      cancelAnimationFrame(raf);
      const tick = () => {
        if (drag) return;
        if (target === null) {
          p += v; v *= 0.92;
          if (p < 0 || p > N - 1) v *= 0.5;
          if (Math.abs(v) < 0.004) { v = 0; target = front(); }
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
    function to(i) { v = 0; target = clamp(i); loop(); }
    function by(d) { to(Math.round(p) + d); }

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
      const now = performance.now(), unit = cw * 1.1;
      v = -((e.clientX - drag.lx) / unit) * Math.min(2, 16 / Math.max(1, now - drag.t));
      drag.lx = e.clientX; drag.t = now;
      const np = drag.p - dx / unit;
      p = np < 0 ? np / 3 : np > N - 1 ? N - 1 + (np - (N - 1)) / 3 : np; // 端はゴムのように
      render();
    }
    function up() {
      if (!drag) return;
      drag = null; ringEl.classList.remove("is-drag"); loop();
      setTimeout(() => { moved = false; }, 0); // 直後の click を無視するため
    }
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
      to, by,
      dim(on) { ringEl.classList.toggle("is-dim", on); },
    };
  })();

  /* ---------- DETAIL ---------- */
  const detail = (() => {
    let cur = -1, from = "wall", lastFocus = null;
    const row = (k, v) => v ? `<div><dt>${k}</dt><dd>${v}</dd></div>` : "";
    const slide = (el, keyframe, opts) => { if (!reduce) el.animate([keyframe, { opacity: 1, transform: "none" }], { easing: EASE, ...opts }); };
    const focusClose = () => detEl.querySelector(".zw-close").focus({ preventScroll: true });

    function html(it) {
      const tba = it.status === "tba";
      const tickets = it.tickets.map((t) => t.url ? link(t.label || "TICKET", t.url) : esc(t.label)).join("");
      return `
        <div class="zw-dback">${it.img ? `<img src="${esc(it.thumb)}" alt="">` : ""}</div>
        <div class="zw-dfig">${face(it, true)}</div>
        <section class="zw-dpanel">
          <div class="zw-dtop"><span class="zw-mono">${pad(it.i + 1)} / ${N}</span>
            <button type="button" class="zw-close" aria-label="閉じる">✕</button></div>
          <div class="zw-dmain">
            <div><p class="zw-mono zw-dmeta">${esc(it.y)} · ${esc(it.dow)}${it.status === "upcoming" ? " · NEXT" : ""}</p>
              <h2 class="zw-ddate">${esc(it.range)}</h2></div>
            <h3 class="zw-dtitle">${esc(label(it))}</h3>
            ${tba ? "" : `<dl class="zw-dl">${row("VENUE", it.venue && link(it.venue, it.venue_url))}${row("ORGANIZER", it.organizer && link(it.organizer, it.organizer_url))}${row("TICKET", tickets)}${row("ROLE", esc(it.role))}</dl>`}
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

    /** 一覧の札の位置から拡大して出てくる */
    function flip(fromEl) {
      const fig = detEl.querySelector(".zw-dfig > *");
      if (!fig || !fromEl || reduce) return;
      const a = fromEl.getBoundingClientRect(), b = fig.getBoundingClientRect();
      if (!a.width || !b.width) return;
      const dx = a.left + a.width / 2 - (b.left + b.width / 2), dy = a.top + a.height / 2 - (b.top + b.height / 2);
      fig.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${a.width / b.width})` }, { transform: getComputedStyle(fig).transform }],
        { duration: 650, easing: EASE });
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
      slide(detEl.querySelector(".zw-dpanel"), { opacity: 0, transform: portrait() ? "translateY(40px)" : "translateX(40px)" }, { duration: 500, delay: 180, fill: "backwards" });
      if (!reduce) detEl.querySelector(".zw-dback").animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400 });
      focusClose();
    }

    function go(d) {
      const n = cur + d;
      if (n < 0 || n >= N) return;
      fill(n);
      if (from === "ring") ring.to(n);
      detEl.querySelectorAll(".zw-dfig, .zw-dmain").forEach((el) => slide(el, { opacity: 0, transform: `translateX(${d * 24}px)` }, { duration: 380 }));
      focusClose();
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

  /* ---------- WALL：並び順のまま、いちばん短い列へ順に詰める（石垣状） ---------- */
  (() => {
    const grids = [...wallEl.querySelectorAll(".zw-grid")].map((g) => ({ g, tiles: [...g.querySelectorAll(".zw-tile")] }));
    // 列数：スマホは3列、それ以外は CSS の minmax(220px, 1fr) と同じ計算（gap 8px・左右 padding 8px）
    const cols = () => innerWidth <= 600 ? 3 : Math.max(1, Math.min(5, Math.floor((wallEl.clientWidth - 16 + 8) / (220 + 8))));
    let n = 0;
    function layout() {
      const k = cols();
      if (k === n) return;
      n = k;
      grids.forEach(({ g, tiles }) => {
        const colEls = Array.from({ length: k }, () => Object.assign(document.createElement("div"), { className: "zw-col" }));
        const h = new Array(k).fill(0);
        tiles.forEach((t) => {
          let c = 0;
          for (let j = 1; j < k; j++) if (h[j] < h[c] - 0.01) c = j;
          colEls[c].appendChild(t);
          h[c] += ratio(items[+t.dataset.i]) + 0.04;
        });
        g.replaceChildren(...colEls);
        g.classList.add("is-masonry");
      });
    }
    layout();
    let rt = 0;
    addEventListener("resize", () => { cancelAnimationFrame(rt); rt = requestAnimationFrame(layout); });
    wallEl.addEventListener("click", (e) => {
      const t = e.target.closest(".zw-tile");
      if (t) detail.open(+t.dataset.i, t.querySelector("img, .zw-card"), "wall");
    });
  })();

  detEl.addEventListener("click", (e) => { if (e.target === detEl || e.target.classList.contains("zw-dback")) detail.close(); });

  document.addEventListener("keydown", (e) => {
    const d = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
    if (detail.isOpen()) {
      if (e.key === "Escape") detail.close();
      else if (d) detail.go(d);
    } else if (mode === "ring" && d) ring.by(d);
  });

  // 初期モード：#ring > 前回の選択 > WALL
  if (location.hash === "#ring" || store.get() === "ring") setMode("ring", false);
})();
