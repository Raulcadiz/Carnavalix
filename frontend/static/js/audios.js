/* ══════════════════════════════════════════════════════════════════
   Carnavalix — Player de Audios
   HTML5 <audio> nativo + sidebar de grupos + player sticky
   ══════════════════════════════════════════════════════════════════ */

// ── Estado global ─────────────────────────────────────────────────
let _catalogo        = [];          // respuesta de /api/audio/
let _playlistActual  = [];          // tracks del grupo seleccionado
let _grupoActual     = "";          // nombre del grupo en reproducción
let _iconoActual     = "🎵";        // icono de la modalidad actual
let _trackIdx        = -1;          // índice del track en curso

const audio = document.getElementById("audioElement");
audio.volume = 0.8;

// ── Arranque ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", cargarCatalogo);

async function cargarCatalogo() {
  try {
    const data = await fetch("/api/audio/").then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
    _catalogo = data;
    document.getElementById("sidebarLoading").style.display = "none";
    renderSidebar(data);
  } catch (err) {
    const el = document.getElementById("sidebarLoading");
    if (el) el.innerHTML = `<p style="color:#888;padding:12px;font-size:12px">
      Error al cargar el catálogo de audio.</p>`;
  }
}

// ── Sidebar ───────────────────────────────────────────────────────
function renderSidebar(catalogo) {
  const nav = document.getElementById("sidebarNav");
  if (!nav) return;
  nav.innerHTML = "";

  catalogo.forEach(({ modalidad, icono, grupos }) => {
    const section = document.createElement("div");
    section.className = "sidebar-section";

    // Botón de modalidad (acordeón)
    const toggle = document.createElement("button");
    toggle.className = "sidebar-modalidad open";
    toggle.innerHTML = `
      <span>${icono} ${capitalizar(modalidad)}</span>
      <span class="sidebar-count">${grupos.length}</span>
      <span class="sidebar-modalidad-arrow">▶</span>
    `;

    // Lista de grupos
    const lista = document.createElement("ul");
    lista.className = "sidebar-grupos";

    grupos.forEach((g) => {
      const li = document.createElement("li");
      li.className = "sidebar-grupo";
      li.textContent = g.nombre;
      li.title       = g.nombre;

      li.addEventListener("click", () => {
        document.querySelectorAll(".sidebar-grupo").forEach(el => el.classList.remove("active"));
        li.classList.add("active");
        cargarGrupo(modalidad, icono, g);
      });

      lista.appendChild(li);
    });

    // Toggle acordeón
    toggle.addEventListener("click", () => {
      const abierto = lista.style.display !== "none";
      lista.style.display = abierto ? "none" : "block";
      toggle.classList.toggle("open", !abierto);
    });

    section.appendChild(toggle);
    section.appendChild(lista);
    nav.appendChild(section);
  });
}

// ── Cargar grupo en el panel principal ────────────────────────────
function cargarGrupo(modalidad, icono, grupo) {
  _playlistActual = grupo.tracks;
  _grupoActual    = grupo.nombre;
  _iconoActual    = icono;

  // Mostrar panel
  document.getElementById("tracksEmpty").style.display = "none";
  document.getElementById("tracksWrap").style.display  = "block";

  document.getElementById("tracksModalidad").textContent  = capitalizar(modalidad);
  document.getElementById("tracksGrupoNombre").textContent = grupo.nombre;
  document.getElementById("tracksCount").textContent =
    `${grupo.tracks.length} pista${grupo.tracks.length !== 1 ? "s" : ""}`;

  // Renderizar lista de pistas
  const lista = document.getElementById("trackList");
  lista.innerHTML = "";

  grupo.tracks.forEach((track, idx) => {
    const li = document.createElement("li");
    li.className = "track-item";

    const durId = `dur-${idx}`;
    li.innerHTML = `
      <span class="track-num">${String(idx + 1).padStart(2, "0")}</span>
      <span class="track-titulo">${escHtml(track.titulo)}</span>
      <span class="track-duracion" id="${durId}">—</span>
      <button class="track-play-btn" title="Reproducir">▶</button>
    `;

    li.querySelector(".track-play-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      reproducir(idx);
    });
    li.addEventListener("click", () => reproducir(idx));

    lista.appendChild(li);

    // Pre-cargar duración sin reproducir (usando un Audio temporal)
    precargarDuracion(track.url, durId);
  });

  // Botón "Reproducir todo"
  document.getElementById("btnPlayAll").onclick = () => reproducir(0);
}

// ── Reproducir track ──────────────────────────────────────────────
function reproducir(idx) {
  if (idx < 0 || idx >= _playlistActual.length) return;
  _trackIdx = idx;
  const track = _playlistActual[idx];

  audio.src = track.url;
  audio.play().catch(err => console.warn("[Audio] play() bloqueado:", err));

  // Panel inferior
  document.getElementById("playerTitulo").textContent = track.titulo;
  document.getElementById("playerGrupo").textContent  = _grupoActual;
  document.getElementById("playerEmoji").textContent  = _iconoActual;
  document.getElementById("audioPlayer").style.display = "flex";
  document.getElementById("btnPlayPause").textContent  = "⏸";

  // Resaltar track activo en la lista
  document.querySelectorAll(".track-item").forEach((el, i) => {
    const jugando = i === idx;
    el.classList.toggle("playing", jugando);
    const btn = el.querySelector(".track-play-btn");
    if (btn) btn.textContent = jugando ? "⏸" : "▶";
  });
}

// ── Controles del player ──────────────────────────────────────────
document.getElementById("btnPlayPause")?.addEventListener("click", () => {
  if (audio.paused) {
    audio.play();
    document.getElementById("btnPlayPause").textContent = "⏸";
  } else {
    audio.pause();
    document.getElementById("btnPlayPause").textContent = "▶";
  }
});

document.getElementById("btnNext")?.addEventListener("click", () => {
  if (_trackIdx < _playlistActual.length - 1) reproducir(_trackIdx + 1);
});

document.getElementById("btnPrev")?.addEventListener("click", () => {
  // Si llevamos más de 3 segundos, reiniciar; si no, ir al anterior
  if (audio.currentTime > 3) {
    audio.currentTime = 0;
  } else if (_trackIdx > 0) {
    reproducir(_trackIdx - 1);
  }
});

// Auto-siguiente al terminar
audio.addEventListener("ended", () => {
  if (_trackIdx < _playlistActual.length - 1) {
    reproducir(_trackIdx + 1);
  } else {
    document.getElementById("btnPlayPause").textContent = "▶";
    document.querySelectorAll(".track-item").forEach(el => {
      el.classList.remove("playing");
      const btn = el.querySelector(".track-play-btn");
      if (btn) btn.textContent = "▶";
    });
  }
});

// ── Progreso ──────────────────────────────────────────────────────
audio.addEventListener("timeupdate", () => {
  if (!audio.duration || isNaN(audio.duration)) return;
  const pct = (audio.currentTime / audio.duration) * 100;
  const fill = document.getElementById("progressFill");
  if (fill) fill.style.width = `${pct}%`;
  const ct = document.getElementById("playerCurrentTime");
  if (ct) ct.textContent = formatTime(audio.currentTime);
});

audio.addEventListener("loadedmetadata", () => {
  const dur = document.getElementById("playerDuration");
  if (dur) dur.textContent = formatTime(audio.duration);
  // Actualizar duración en la lista
  const durEl = document.getElementById(`dur-${_trackIdx}`);
  if (durEl) durEl.textContent = formatTime(audio.duration);
});

// Clic en barra para seek
document.getElementById("progressBar")?.addEventListener("click", (e) => {
  const bar  = e.currentTarget;
  const rect = bar.getBoundingClientRect();
  const ratio = (e.clientX - rect.left) / rect.width;
  if (audio.duration) audio.currentTime = ratio * audio.duration;
});

// Volumen
document.getElementById("playerVolume")?.addEventListener("input", (e) => {
  audio.volume = parseFloat(e.target.value);
});

// ── Helpers ───────────────────────────────────────────────────────
function formatTime(secs) {
  if (!secs || isNaN(secs) || !isFinite(secs)) return "0:00";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function capitalizar(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function escHtml(s) {
  return (s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Carga un Audio temporal sólo para leer la duración y actualizarla en la lista.
 * No reproduce nada.
 */
function precargarDuracion(url, elementId) {
  const tmp = new Audio();
  tmp.preload = "metadata";
  tmp.addEventListener("loadedmetadata", () => {
    const el = document.getElementById(elementId);
    if (el) el.textContent = formatTime(tmp.duration);
    tmp.src = ""; // liberar
  });
  tmp.src = url;
}
