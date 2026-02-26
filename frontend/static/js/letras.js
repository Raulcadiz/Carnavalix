/* ══════════════════════════════════════════════════════════════════
   Carnavalix — Página de Letras
   Visor de letras del Carnaval de Cádiz. Llama a /api/letras/
   ══════════════════════════════════════════════════════════════════ */

let letrasPage    = 1;
let letrasPages   = 1;
let letrasFilters = {};

document.addEventListener("DOMContentLoaded", () => {
  cargarAños();
  cargarLetras();
  initControles();
});

// ── Años disponibles ──────────────────────────────────────────────
async function cargarAños() {
  try {
    const años = await fetch("/api/videos/años").then(r => r.json());
    const sel  = document.getElementById("letrasAño");
    if (!sel) return;
    años.forEach(a => {
      const opt = document.createElement("option");
      opt.value = a; opt.textContent = a;
      sel.appendChild(opt);
    });
  } catch {/* silencioso */}
}

// ── Controles ─────────────────────────────────────────────────────
function initControles() {
  document.getElementById("btnBuscarLetras")?.addEventListener("click", aplicarFiltros);
  document.getElementById("letrasQ")?.addEventListener("keydown", e => {
    if (e.key === "Enter") aplicarFiltros();
  });
  document.getElementById("btnLetrasAnterior")?.addEventListener("click", () => {
    if (letrasPage > 1) cargarLetras(letrasFilters, letrasPage - 1);
  });
  document.getElementById("btnLetrasSiguiente")?.addEventListener("click", () => {
    if (letrasPage < letrasPages) cargarLetras(letrasFilters, letrasPage + 1);
  });
  document.getElementById("btnCerrarLetra")?.addEventListener("click", cerrarModal);
  document.getElementById("letraModal")?.addEventListener("click", e => {
    if (e.target === document.getElementById("letraModal")) cerrarModal();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") cerrarModal();
  });
}

function aplicarFiltros() {
  letrasFilters = {};
  const q    = document.getElementById("letrasQ")?.value.trim();
  const año  = document.getElementById("letrasAño")?.value;
  const tipo = document.getElementById("letrasTipo")?.value;
  if (q)    letrasFilters.q          = q;
  if (año)  letrasFilters.año        = año;
  if (tipo) letrasFilters.tipo_pieza = tipo;
  cargarLetras(letrasFilters, 1);
}

// ── Carga de letras ───────────────────────────────────────────────
async function cargarLetras(filtros = {}, page = 1) {
  const grid = document.getElementById("gridLetras");
  if (!grid) return;
  grid.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Buscando letras...</p></div>`;

  const params = new URLSearchParams({ page, per_page: 24, ...filtros });
  try {
    const res  = await fetch(`/api/letras/?${params}`);
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    letrasPages = data.pages || 1;
    letrasPage  = page;
    renderLetras(data.letras || []);
    actualizarPaginacion();
  } catch {
    grid.innerHTML = `<div class="loading-state"><p>Error al cargar letras.<br>
      <small>Comprueba que el servidor está activo.</small></p></div>`;
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
          Importa letras desde el
          <a href="/admin" style="color:var(--gold)">panel de admin</a>
          → pestaña Letras.
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

    const preview = (l.contenido || "").trim().substring(0, 140);
    card.querySelector(".letra-card-preview").textContent =
      preview ? (preview + (l.contenido?.length > 140 ? "…" : "")) : "(sin contenido)";

    card.querySelector(".btn-ver-letra").addEventListener("click", () => abrirModal(l));
    grid.appendChild(card);
  });
}

function actualizarPaginacion() {
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

// ── Modal ─────────────────────────────────────────────────────────
function abrirModal(l) {
  document.getElementById("letraModalTipo").textContent   = (l.tipo_pieza || "").toUpperCase();
  document.getElementById("letraModalAño").textContent    = l.año || "";
  document.getElementById("letraModalTitulo").textContent = l.titulo || "Sin título";
  document.getElementById("letraModalGrupo").textContent  = l.grupo_nombre || "";

  const contenidoEl = document.getElementById("letraModalContenido");
  if (contenidoEl) {
    contenidoEl.innerHTML = (l.contenido || "(Sin contenido)")
      .split("\n")
      .map(line => line.trim() ? `<p>${escHtml(line)}</p>` : "<br>")
      .join("");
  }

  document.getElementById("letraModal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function cerrarModal() {
  const modal = document.getElementById("letraModal");
  if (modal) modal.style.display = "none";
  document.body.style.overflow = "";
}

function escHtml(s) {
  return (s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
