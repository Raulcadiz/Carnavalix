/* ══════════════════════════════════════════════════════════════════
   CarnavalPlay — Script global
   ══════════════════════════════════════════════════════════════════ */

// ── Navbar scroll ──────────────────────────────────────────────────
(function () {
  const nav = document.getElementById("navbar");
  if (!nav) return;
  window.addEventListener("scroll", () => {
    nav.classList.toggle("scrolled", window.scrollY > 20);
  }, { passive: true });
})();

// ── Barra de búsqueda ──────────────────────────────────────────────
(function () {
  const btn = document.getElementById("btnBuscar");
  const bar = document.getElementById("searchBar");
  const inp = document.getElementById("searchInput");
  if (!btn || !bar) return;

  btn.addEventListener("click", () => {
    bar.classList.toggle("open");
    if (bar.classList.contains("open")) inp?.focus();
  });

  inp?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && inp.value.trim()) {
      window.location.href = `/?q=${encodeURIComponent(inp.value.trim())}`;
    }
    if (e.key === "Escape") bar.classList.remove("open");
  });
})();

// ── Botón aleatorio (navbar) ───────────────────────────────────────
document.getElementById("btnShuffle")?.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/videos/aleatorio");
    if (!res.ok) return;
    const v = await res.json();
    window.location.href = `/player/${v.youtube_id}`;
  } catch {
    console.warn("No se pudo obtener vídeo aleatorio.");
  }
});

// ── Utilidades globales ────────────────────────────────────────────
window.CP = {
  /** Formatea segundos a "1h 23m" */
  formatDur(seg) {
    if (!seg) return "";
    const h = Math.floor(seg / 3600);
    const m = Math.floor((seg % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  },

  /** Estrellas a partir de puntuación media */
  estrellas(media, total) {
    const llenas = Math.round(media);
    const str = "★".repeat(llenas) + "☆".repeat(5 - llenas);
    return total ? `${str} (${total})` : "Sin votos";
  },

  /** Fetch con manejo de error básico */
  async get(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
};
