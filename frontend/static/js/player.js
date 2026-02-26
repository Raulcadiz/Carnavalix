/* ══════════════════════════════════════════════════════════════════
   CarnavalPlay — Player
   ══════════════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", async () => {
  const ytId = window.YOUTUBE_ID;
  if (!ytId) return;

  await Promise.all([
    cargarInfoVideo(ytId),
    cargarLetras(ytId),
    cargarRelacionados(ytId),
  ]);

  initEstrellas();
  initFavorito(ytId);
  initCompartir(ytId);
  initToggleLetras();
});

// ── Info del vídeo ─────────────────────────────────────────────────
async function cargarInfoVideo(ytId) {
  try {
    // Buscar por youtube_id
    const data = await CP.get(`/api/videos/?q=${ytId}&per_page=1`);
    const video = data.videos?.[0];
    if (!video) return;

    document.title = `${video.titulo} · CarnavalPlay`;
    document.getElementById("playerTitulo").textContent = video.titulo;
    document.getElementById("metaAño").textContent = video.año || "";
    document.getElementById("metaModalidad").textContent = video.modalidad || "";
    document.getElementById("metaFase").textContent = video.fase || "";
    document.getElementById("metaGrupo").textContent = video.grupo_nombre || "";

    // Rating
    const starsEl = document.getElementById("starsInput");
    starsEl.dataset.videoId = video.id;
    document.getElementById("ratingMedia").textContent =
      video.total_votos > 0
        ? `${video.puntuacion_media} / 5 (${video.total_votos} votos)`
        : "Sin votos aún";

    // Odysee
    if (video.odysee_url) {
      const panel = document.getElementById("playerOdysee");
      panel.style.display = "block";
      document.getElementById("odyseeLink").href = video.odysee_url;
    }
  } catch (e) {
    console.warn("Error cargando info vídeo:", e);
  }
}

// ── Letras ─────────────────────────────────────────────────────────
async function cargarLetras(ytId) {
  try {
    // Primero necesitamos el ID interno del vídeo
    const data = await CP.get(`/api/videos/?q=${ytId}&per_page=1`);
    const video = data.videos?.[0];
    if (!video) return;

    const letras = await CP.get(`/api/letras/por-video/${video.id}`);
    if (!letras.length) return;

    renderLetras(letras);
  } catch (e) {
    console.warn("Error cargando letras:", e);
  }
}

function renderLetras(letras) {
  const body = document.getElementById("letrasBody");
  const tabsEl = document.getElementById("letrasTabs");
  if (!body) return;

  body.innerHTML = "";
  tabsEl.innerHTML = "";

  // Agrupar por tipo_pieza
  const grupos = {};
  letras.forEach(l => {
    const tipo = l.tipo_pieza || "Letra";
    if (!grupos[tipo]) grupos[tipo] = [];
    grupos[tipo].push(l);
  });

  const tipos = Object.keys(grupos);
  tipos.forEach((tipo, i) => {
    // Tab
    const tab = document.createElement("button");
    tab.className = `letra-tab${i === 0 ? " active" : ""}`;
    tab.textContent = tipo.charAt(0).toUpperCase() + tipo.slice(1);
    tab.dataset.tipo = tipo;
    tab.addEventListener("click", () => {
      document.querySelectorAll(".letra-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".letra-pieza").forEach(p => {
        p.style.display = p.dataset.tipo === tipo ? "block" : "none";
      });
    });
    tabsEl.appendChild(tab);

    // Contenido
    grupos[tipo].forEach(l => {
      const div = document.createElement("div");
      div.className = "letra-pieza";
      div.dataset.tipo = tipo;
      div.style.display = i === 0 ? "block" : "none";
      div.innerHTML = `
        <div class="letra-pieza-titulo">${l.tipo_pieza || "Letra"}</div>
        <div class="letra-pieza-texto">${escapeHtml(l.contenido)}</div>
      `;
      body.appendChild(div);
    });
  });
}

function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ── Vídeos relacionados ────────────────────────────────────────────
async function cargarRelacionados(ytId) {
  try {
    const data = await CP.get(`/api/videos/?q=${ytId}&per_page=1`);
    const video = data.videos?.[0];
    if (!video) return;

    const rel = await CP.get(
      `/api/videos/?modalidad=${video.modalidad || ""}&per_page=8&page=1`
    );

    const grid = document.getElementById("relacionadosGrid");
    if (!grid) return;
    grid.innerHTML = "";

    rel.videos
      .filter(v => v.youtube_id !== ytId)
      .slice(0, 6)
      .forEach(v => {
        const a = document.createElement("a");
        a.href = `/player/${v.youtube_id}`;
        a.className = "card";
        a.innerHTML = `
          <div class="card-thumb" style="aspect-ratio:16/9">
            <img class="card-img" src="${v.thumbnail}" alt="${escapeHtml(v.titulo)}" loading="lazy"/>
            <div class="card-overlay"><span class="card-play">▶</span></div>
            <span class="card-tipo">${v.modalidad || ""}</span>
          </div>
          <div class="card-info">
            <h3 class="card-titulo">${escapeHtml(v.titulo)}</h3>
            <div class="card-meta">
              <span>${v.año || ""}</span>
              <span>${v.fase || ""}</span>
            </div>
          </div>
        `;
        grid.appendChild(a);
      });
  } catch (e) {
    console.warn("Error relacionados:", e);
  }
}

// ── Sistema de estrellas ───────────────────────────────────────────
function initEstrellas() {
  const container = document.getElementById("starsInput");
  if (!container) return;
  const stars = container.querySelectorAll(".star");

  stars.forEach(star => {
    star.addEventListener("mouseenter", () => {
      const val = +star.dataset.val;
      stars.forEach(s => s.classList.toggle("active", +s.dataset.val <= val));
    });
    star.addEventListener("mouseleave", () => {
      stars.forEach(s => s.classList.remove("active"));
    });
    star.addEventListener("click", async () => {
      const val = +star.dataset.val;
      const videoId = container.dataset.videoId;
      if (!videoId) return;
      try {
        const res = await CP.post("/api/votos/", { video_id: +videoId, valor: val });
        document.getElementById("ratingMedia").textContent =
          `${res.puntuacion_media} / 5 (${res.total_votos} votos)`;
        stars.forEach(s => s.classList.toggle("active", +s.dataset.val <= val));
      } catch {
        console.warn("Error al votar");
      }
    });
  });
}

// ── Favorito (localStorage) ────────────────────────────────────────
function initFavorito(ytId) {
  const btn = document.getElementById("btnFav");
  if (!btn) return;
  const key = `fav_${ytId}`;
  const isFav = localStorage.getItem(key) === "1";
  btn.textContent = isFav ? "♥" : "♡";
  btn.style.color = isFav ? "#e74c3c" : "";

  btn.addEventListener("click", () => {
    const nuevo = localStorage.getItem(key) !== "1";
    localStorage.setItem(key, nuevo ? "1" : "0");
    btn.textContent = nuevo ? "♥" : "♡";
    btn.style.color = nuevo ? "#e74c3c" : "";
  });
}

// ── Compartir ──────────────────────────────────────────────────────
function initCompartir(ytId) {
  document.getElementById("btnShare")?.addEventListener("click", async () => {
    const url = window.location.href;
    if (navigator.share) {
      await navigator.share({ title: document.title, url });
    } else {
      await navigator.clipboard.writeText(url);
      alert("¡Enlace copiado!");
    }
  });
}

// ── Toggle panel letras ────────────────────────────────────────────
function initToggleLetras() {
  document.getElementById("btnToggleLetras")?.addEventListener("click", () => {
    const panel = document.getElementById("playerLetrasPanel");
    panel.style.display = panel.style.display === "none" ? "" : "none";
  });
}
