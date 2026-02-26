/* ══════════════════════════════════════════════════════════════════
   CarnavalPlay — Página de inicio
   ══════════════════════════════════════════════════════════════════ */

let currentPage = 1;
let totalPages = 1;
let currentFilters = {};

// ── Arranque ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await Promise.all([
    cargarEstadisticas(),
    cargarAños(),
    cargarVideos(),
  ]);
  initFiltros();
  initTabs();
  initHero();
  initLetras();
  leerURLParams();
});

// ── Hero stats ─────────────────────────────────────────────────────
async function cargarEstadisticas() {
  try {
    const stats = await CP.get("/api/videos/estadisticas");
    const el = document.getElementById("heroStats");
    if (!el) return;
    el.innerHTML = `
      <div>
        <span class="hero-stat-num">${stats.total_videos || 0}</span>
        <span class="hero-stat-label">Vídeos</span>
      </div>
      <div>
        <span class="hero-stat-num">${stats.total_grupos || 0}</span>
        <span class="hero-stat-label">Grupos</span>
      </div>
      <div>
        <span class="hero-stat-num">${stats.con_letra || 0}</span>
        <span class="hero-stat-label">Con letra</span>
      </div>
    `;
  } catch {/* silencioso */}
}

// ── Selector de años ───────────────────────────────────────────────
async function cargarAños() {
  try {
    const años = await CP.get("/api/videos/años");
    const sel = document.getElementById("filtroAño");
    if (!sel) return;
    años.forEach(a => {
      const opt = document.createElement("option");
      opt.value = a;
      opt.textContent = a;
      sel.appendChild(opt);
    });
  } catch {/* silencioso */}
}

// ── Carga de vídeos ────────────────────────────────────────────────
async function cargarVideos(filtros = {}, page = 1) {
  const grid = document.getElementById("gridVideos");
  grid.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Cargando el Carnaval...</p></div>`;

  const params = new URLSearchParams({ page, per_page: 24, ...filtros });
  try {
    const data = await CP.get(`/api/videos/?${params}`);
    totalPages = data.pages || 1;
    currentPage = page;
    renderGrid(data.videos || []);
    actualizarPaginacion();
  } catch {
    grid.innerHTML = `<div class="loading-state"><p>Error al cargar. Comprueba que el servidor está activo.</p></div>`;
  }
}

// ── Render de cards ────────────────────────────────────────────────
function renderGrid(videos) {
  const grid = document.getElementById("gridVideos");
  const tpl = document.getElementById("cardTemplate");

  if (!videos.length) {
    grid.innerHTML = `<div class="loading-state"><p>No se encontraron vídeos con estos filtros.</p></div>`;
    return;
  }

  grid.innerHTML = "";
  videos.forEach(v => {
    const card = tpl.content.cloneNode(true);

    card.querySelector(".card-link").href = `/player/${v.youtube_id}`;
    card.querySelector(".card-img").src = v.thumbnail || "/static/img/placeholder.jpg";
    card.querySelector(".card-img").alt = v.titulo;
    card.querySelector(".card-titulo").textContent = v.titulo;
    card.querySelector(".card-duracion").textContent = CP.formatDur(v.duracion);
    card.querySelector(".card-tipo").textContent = v.modalidad || "COAC";
    card.querySelector(".card-año").textContent = v.año || "";
    card.querySelector(".card-fase").textContent = v.fase || "";

    const letraBadge = card.querySelector(".card-letra-badge");
    if (v.tiene_letra) letraBadge.style.display = "inline-block";

    const ratingEl = card.querySelector(".card-estrellas");
    const votosEl = card.querySelector(".card-votos");
    if (v.total_votos > 0) {
      const llenas = Math.round(v.puntuacion_media || 0);
      ratingEl.textContent = "★".repeat(llenas) + "☆".repeat(5 - llenas);
      votosEl.textContent = `(${v.total_votos})`;
    } else {
      ratingEl.textContent = "";
      votosEl.textContent = "";
    }

    grid.appendChild(card);
  });
}

// ── Paginación ─────────────────────────────────────────────────────
function actualizarPaginacion() {
  const wrap = document.getElementById("paginacion");
  const info = document.getElementById("infoPagina");
  if (!wrap) return;
  wrap.style.display = totalPages > 1 ? "flex" : "none";
  if (info) info.textContent = `Página ${currentPage} de ${totalPages}`;
  document.getElementById("btnAnterior").disabled = currentPage <= 1;
  document.getElementById("btnSiguiente").disabled = currentPage >= totalPages;
}

document.getElementById("btnAnterior")?.addEventListener("click", () => {
  if (currentPage > 1) cargarVideos(currentFilters, currentPage - 1);
});
document.getElementById("btnSiguiente")?.addEventListener("click", () => {
  if (currentPage < totalPages) cargarVideos(currentFilters, currentPage + 1);
});

// ── Filtros ────────────────────────────────────────────────────────
function initFiltros() {
  document.getElementById("btnAplicarFiltros")?.addEventListener("click", aplicarFiltros);
  document.getElementById("btnLimpiarFiltros")?.addEventListener("click", () => {
    document.getElementById("filtroAño").value = "";
    document.getElementById("filtroModalidad").value = "";
    document.getElementById("filtroFase").value = "";
    currentFilters = {};
    cargarVideos();
  });
}

function aplicarFiltros() {
  const año = document.getElementById("filtroAño")?.value;
  const modalidad = document.getElementById("filtroModalidad")?.value;
  const fase = document.getElementById("filtroFase")?.value;
  const q = document.getElementById("searchInput")?.value.trim();

  currentFilters = {};
  if (año) currentFilters.año = año;
  if (modalidad) currentFilters.modalidad = modalidad;
  if (fase) currentFilters.fase = fase;
  if (q) currentFilters.q = q;

  cargarVideos(currentFilters, 1);
}

// ── Tabs ───────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const tipo = tab.dataset.tab;

      const catalogo       = document.getElementById("catalogo");
      const catalogoLetras = document.getElementById("catalogoLetras");

      if (tipo === "letras") {
        if (catalogo)       catalogo.style.display       = "none";
        if (catalogoLetras) catalogoLetras.style.display = "block";
        cargarLetras();
      } else {
        if (catalogo)       catalogo.style.display       = "block";
        if (catalogoLetras) catalogoLetras.style.display = "none";

        if (tipo === "destacados") cargarVideos({ destacados: true });
        else if (tipo === "recientes") cargarVideos({});
        else if (tipo === "ranking") cargarRanking();
        else if (tipo === "callejeras") cargarVideos({ tipo: "callejera" });
      }
    });
  });
}

async function cargarRanking() {
  const grid = document.getElementById("gridVideos");
  grid.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
  try {
    const videos = await CP.get("/api/votos/ranking?min_votos=1&limit=24");
    renderGrid(videos);
  } catch {
    grid.innerHTML = `<div class="loading-state"><p>Sin datos de ranking aún.</p></div>`;
  }
}

// ── Hero botones ───────────────────────────────────────────────────
function initHero() {
  document.getElementById("heroPlay")?.addEventListener("click", () => {
    document.getElementById("filtros")?.scrollIntoView({ behavior: "smooth" });
  });
  document.getElementById("heroAleatorio")?.addEventListener("click", async () => {
    const res = await CP.get("/api/videos/aleatorio");
    if (res?.youtube_id) window.location.href = `/player/${res.youtube_id}`;
  });
}

// ── Leer params de URL ─────────────────────────────────────────────
function leerURLParams() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");
  const tipo = params.get("tipo");
  const modalidad = params.get("modalidad");
  const año = params.get("año");

  if (q) {
    document.getElementById("searchInput").value = q;
    currentFilters.q = q;
  }
  if (tipo) currentFilters.tipo = tipo;
  if (modalidad) currentFilters.modalidad = modalidad;
  if (año) currentFilters.año = año;

  if (Object.keys(currentFilters).length) cargarVideos(currentFilters);
}

// ════════════════════════════════════════════════════════════════════
// LETRAS — visor de canciones del Carnaval
// ════════════════════════════════════════════════════════════════════
let letrasPage    = 1;
let letrasPages   = 1;
let letrasFilters = {};

function initLetras() {
  // Búsqueda y filtros
  document.getElementById("btnBuscarLetras")?.addEventListener("click", () => {
    letrasFilters = {};
    const q    = document.getElementById("letrasQ")?.value.trim();
    const año  = document.getElementById("letrasAño")?.value;
    const tipo = document.getElementById("letrasTipo")?.value;
    if (q)    letrasFilters.q          = q;
    if (año)  letrasFilters.año        = año;
    if (tipo) letrasFilters.tipo_pieza = tipo;
    cargarLetras(letrasFilters, 1);
  });
  document.getElementById("letrasQ")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("btnBuscarLetras")?.click();
  });

  // Paginación
  document.getElementById("btnLetrasAnterior")?.addEventListener("click", () => {
    if (letrasPage > 1) cargarLetras(letrasFilters, letrasPage - 1);
  });
  document.getElementById("btnLetrasSiguiente")?.addEventListener("click", () => {
    if (letrasPage < letrasPages) cargarLetras(letrasFilters, letrasPage + 1);
  });

  // Modal cerrar: botón y clic en overlay
  document.getElementById("btnCerrarLetra")?.addEventListener("click", cerrarLetraModal);
  document.getElementById("letraModal")?.addEventListener("click", (e) => {
    if (e.target === document.getElementById("letraModal")) cerrarLetraModal();
  });
  // ESC para cerrar
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") cerrarLetraModal();
  });

  // Poblar años con los mismos del catálogo de vídeos
  cargarAñosLetras();
}

async function cargarAñosLetras() {
  try {
    const años = await CP.get("/api/videos/años");
    const sel  = document.getElementById("letrasAño");
    if (!sel) return;
    años.forEach(a => {
      const opt = document.createElement("option");
      opt.value = a; opt.textContent = a;
      sel.appendChild(opt);
    });
  } catch {/* silencioso */}
}

async function cargarLetras(filtros = {}, page = 1) {
  const grid = document.getElementById("gridLetras");
  if (!grid) return;
  grid.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Buscando letras...</p></div>`;

  const params = new URLSearchParams({ page, per_page: 20, ...filtros });
  try {
    const data = await CP.get(`/api/letras/?${params}`);
    letrasPages = data.pages || 1;
    letrasPage  = page;
    renderLetras(data.letras || []);
    actualizarPaginacionLetras();
  } catch {
    grid.innerHTML = `<div class="loading-state"><p>Error al cargar letras. Comprueba que el servidor está activo.</p></div>`;
  }
}

function renderLetras(letras) {
  const grid = document.getElementById("gridLetras");
  const tpl  = document.getElementById("letraTemplate");
  if (!grid || !tpl) return;

  if (!letras.length) {
    grid.innerHTML = `
      <div class="loading-state">
        <p>No hay letras disponibles.<br>
        <small style="color:var(--text-muted)">
          Importa letras desde el <a href="/admin" style="color:var(--gold)">panel de admin</a> → pestaña Letras.
        </small></p>
      </div>`;
    return;
  }

  grid.innerHTML = "";
  letras.forEach(l => {
    const card = tpl.content.cloneNode(true);
    card.querySelector(".letra-card-tipo").textContent  = (l.tipo_pieza || "LETRA").toUpperCase();
    card.querySelector(".letra-card-año").textContent   = l.año || "";
    card.querySelector(".letra-card-titulo").textContent = l.titulo || "Sin título";
    card.querySelector(".letra-card-grupo").textContent  = l.grupo_nombre || "";

    const preview = (l.contenido || "").trim().substring(0, 130);
    card.querySelector(".letra-card-preview").textContent = preview
      ? preview + (l.contenido?.length > 130 ? "…" : "")
      : "(sin contenido)";

    card.querySelector(".btn-ver-letra").addEventListener("click", () => abrirLetra(l));
    grid.appendChild(card);
  });
}

function actualizarPaginacionLetras() {
  const wrap = document.getElementById("paginacionLetras");
  const info = document.getElementById("infoLetrasPagina");
  if (!wrap) return;
  wrap.style.display = letrasPages > 1 ? "flex" : "none";
  if (info) info.textContent = `Página ${letrasPage} de ${letrasPages}`;
  const btnA = document.getElementById("btnLetrasAnterior");
  const btnS = document.getElementById("btnLetrasSiguiente");
  if (btnA) btnA.disabled = letrasPage <= 1;
  if (btnS) btnS.disabled = letrasPage >= letrasPages;
}

// ── Modal: letra completa ───────────────────────────────────────────
function abrirLetra(l) {
  document.getElementById("letraModalTipo").textContent   = (l.tipo_pieza || "").toUpperCase();
  document.getElementById("letraModalAño").textContent    = l.año || "";
  document.getElementById("letraModalTitulo").textContent = l.titulo || "Sin título";
  document.getElementById("letraModalGrupo").textContent  = l.grupo_nombre || "";

  // Formatear contenido: saltos de línea → párrafos
  const contenidoEl = document.getElementById("letraModalContenido");
  if (contenidoEl) {
    const lineas = (l.contenido || "(Sin contenido)").split("\n");
    contenidoEl.innerHTML = lineas
      .map(line => line.trim() ? `<p>${_escHtml(line)}</p>` : `<br>`)
      .join("");
  }

  document.getElementById("letraModal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function cerrarLetraModal() {
  const modal = document.getElementById("letraModal");
  if (modal) modal.style.display = "none";
  document.body.style.overflow = "";
}

function _escHtml(s) {
  return (s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
