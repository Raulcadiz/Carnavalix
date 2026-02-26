/* ══════════════════════════════════════════════════════════════════
   CarnavalPlay — Panel de administración
   ══════════════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  cargarEstadisticas();
});

// ── Tabs ───────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll(".admin-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".admin-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`panel-${btn.dataset.panel}`)?.classList.add("active");
    });
  });

  // Botones de acción
  document.getElementById("btnLanzarScraper")?.addEventListener("click", lanzarScraper);
  document.getElementById("btnAñadirVideo")?.addEventListener("click", añadirVideoManual);
  document.getElementById("btnImportarLetras")?.addEventListener("click", importarLetras);
  document.getElementById("btnEnriquecerLetras")?.addEventListener("click", enriquecerLetras);
  document.getElementById("btnDetenerImport")?.addEventListener("click", detenerImportacion);
  document.getElementById("btnSincronizarOdysee")?.addEventListener("click", sincronizarOdysee);
  document.getElementById("btnLiveSiguiente")?.addEventListener("click", liveSiguiente);
  document.getElementById("btnLiveProgramar")?.addEventListener("click", liveProgramar);

  // Modo scraper: mostrar/ocultar sección según radio
  document.querySelectorAll("input[name='scraperModo']").forEach(radio => {
    radio.addEventListener("change", () => {
      const modo = document.querySelector("input[name='scraperModo']:checked")?.value;
      document.getElementById("scraperSeccionBusqueda").style.display = modo === "busqueda" ? "" : "none";
      document.getElementById("scraperSeccionCanal").style.display = modo === "canal" ? "" : "none";
    });
  });

  // Cargar estado live al abrir el panel
  document.querySelector("[data-panel='live']")?.addEventListener("click", cargarEstadoLive);
}

// ── Estadísticas ───────────────────────────────────────────────────
async function cargarEstadisticas() {
  try {
    const stats = await CP.get("/admin/estadisticas");
    document.getElementById("statVideos").textContent = stats.videos ?? "-";
    document.getElementById("statLetras").textContent = stats.letras ?? "-";
    document.getElementById("statGrupos").textContent = stats.grupos ?? "-";
    document.getElementById("statConLetra").textContent = stats.videos_con_letra ?? "-";
  } catch {/* silencioso */}
}

// ── Scraper ────────────────────────────────────────────────────────
async function lanzarScraper() {
  const modo = document.querySelector("input[name='scraperModo']:checked")?.value || "busqueda";

  let body = {};

  if (modo === "canal") {
    const channelUrl = document.getElementById("scraperCanalUrl").value.trim();
    if (!channelUrl) return alert("Introduce la URL del canal de YouTube");
    const maxVideos = parseInt(document.getElementById("scraperMaxVideos").value) || 200;
    body = { channel_url: channelUrl, max_videos: maxVideos };
    log("scraperLog", `📺 Scrapeando canal: ${channelUrl} (máx. ${maxVideos} vídeos)...`);
  } else {
    const años = document.getElementById("scraperAños").value
      .split(",").map(a => parseInt(a.trim())).filter(Boolean);
    const modalidades = [...document.querySelectorAll(".checkbox-group input:checked")]
      .map(cb => cb.value);
    const forzarYtdlp = document.getElementById("scraperForzarYtdlp")?.checked || false;
    body = { años, modalidades, forzar_ytdlp: forzarYtdlp };
    const modoStr = forzarYtdlp ? "yt-dlp (sin cuota)" : "YouTube API v3";
    log("scraperLog", `🔍 Lanzando scraper por búsqueda (${modoStr})... puede tardar varios minutos`);
  }

  try {
    const res = await fetch("/admin/scraper/youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      log("scraperLog", `❌ Error ${res.status}: ${data.error || data.mensaje || "Error desconocido"}`);
    } else {
      log("scraperLog", `✅ ${data.mensaje}`);
    }
  } catch (e) {
    log("scraperLog", `❌ Error de conexión con el servidor: ${e.message}`);
  }
}

// ── Añadir vídeo manual ────────────────────────────────────────────
async function añadirVideoManual() {
  const ytId = document.getElementById("manualYtId").value.trim();
  if (!ytId) return alert("Introduce el YouTube ID");

  log("videoLog", `Obteniendo metadata de ${ytId}...`);
  try {
    const res = await CP.post("/admin/video", {
      youtube_id: ytId,
      año: +document.getElementById("manualAño").value || null,
      modalidad: document.getElementById("manualModalidad").value || null,
      fase: document.getElementById("manualFase").value || null,
      grupo_nombre: document.getElementById("manualGrupo").value.trim() || null,
      destacado: document.getElementById("manualDestacado").checked,
    });
    log("videoLog", `✅ Vídeo añadido (ID interno: ${res.id})`);
    cargarEstadisticas();
  } catch (e) {
    log("videoLog", `❌ Error: ${e.message}`);
  }
}

// ── Importar letras desde API ───────────────────────────────────────
let _progresoInterval = null;

async function importarLetras() {
  const body = {
    anio: +document.getElementById("letrasAnio")?.value || null,
    modalidad: document.getElementById("letrasModalidad")?.value || null,
    calidad_min: +document.getElementById("letrasCalidad")?.value || 0,
    limite: +document.getElementById("letrasLimite")?.value || 20000,
  };

  log("letrasLog", "🚀 Iniciando importación desde g3v3r.pythonanywhere.com...");
  try {
    const res = await fetch("/api/letras/importar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      log("letrasLog", `❌ ${data.error || "Error al iniciar"}`);
      return;
    }
    log("letrasLog", `✅ ${data.mensaje}`);
    iniciarPollingProgreso();
  } catch (e) {
    log("letrasLog", `❌ Error de conexión: ${e.message}`);
  }
}

async function enriquecerLetras() {
  const limite = +document.getElementById("enriquecerLimite")?.value || 200;
  log("letrasLog", `📝 Iniciando descarga de contenidos (${limite} letras)...`);
  try {
    const res = await fetch("/api/letras/enriquecer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limite }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      log("letrasLog", `❌ ${data.error}`);
      return;
    }
    log("letrasLog", `✅ ${data.mensaje}`);
    iniciarPollingProgreso();
  } catch (e) {
    log("letrasLog", `❌ Error: ${e.message}`);
  }
}

function detenerImportacion() {
  // El proceso se detiene en el backend cuando "activo" se pone a false
  // Simplemente dejamos de actualizar el progreso
  clearInterval(_progresoInterval);
  _progresoInterval = null;
  document.getElementById("progresoWrap").style.display = "none";
  document.getElementById("btnDetenerImport").style.display = "none";
  log("letrasLog", "⏹ Proceso detenido manualmente.");
}

function iniciarPollingProgreso() {
  const wrap = document.getElementById("progresoWrap");
  const btnStop = document.getElementById("btnDetenerImport");
  if (wrap) wrap.style.display = "block";
  if (btnStop) btnStop.style.display = "inline-block";

  if (_progresoInterval) clearInterval(_progresoInterval);

  _progresoInterval = setInterval(async () => {
    try {
      const estado = await CP.get("/api/letras/progreso");
      actualizarBarraProgreso(estado);

      if (!estado.activo) {
        clearInterval(_progresoInterval);
        _progresoInterval = null;
        if (btnStop) btnStop.style.display = "none";
        log("letrasLog", estado.mensaje || "Proceso finalizado.");
        cargarEstadisticas();
      }
    } catch {
      clearInterval(_progresoInterval);
    }
  }, 2000);
}

function actualizarBarraProgreso(estado) {
  const fase = document.getElementById("progresoFase");
  const nums = document.getElementById("progresoNums");
  const fill = document.getElementById("progresoFill");
  const msg = document.getElementById("progresoMsg");

  const total = estado.total || 1;
  const importadas = estado.importadas || 0;
  const pct = Math.min(100, Math.round((importadas / total) * 100));

  if (fase) fase.textContent = estado.fase === "enriquecimiento" ? "📝 Descargando contenidos" : "📥 Importando metadata";
  if (nums) nums.textContent = `${importadas.toLocaleString()} / ${total.toLocaleString()} (${pct}%)`;
  if (fill) fill.style.width = `${pct}%`;
  if (msg) msg.textContent = estado.mensaje || "";
}

// ── Odysee ─────────────────────────────────────────────────────────
async function sincronizarOdysee() {
  const limite = +document.getElementById("odyseeLimit").value || 10;
  log("odyseeLog", `Sincronizando ${limite} vídeos con Odysee...`);
  try {
    const res = await fetch("/admin/odysee/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limite }),
    });
    const data = await res.json();
    log("odyseeLog", data.ok ? "✅ Sincronización iniciada en segundo plano." : `❌ ${data.error}`);
  } catch {
    log("odyseeLog", "❌ Error de conexión con Odysee.");
  }
}

// ── Live 24/7 ──────────────────────────────────────────────────────
async function cargarEstadoLive() {
  try {
    const res = await fetch("/live/estado");
    if (!res.ok) {
      document.getElementById("liveTitulo").textContent = "Sin vídeo activo";
      document.getElementById("liveYtId").textContent = "Añade vídeos al catálogo y usa 'Siguiente'";
      document.getElementById("liveDot").style.background = "#888";
      return;
    }
    const d = await res.json();
    document.getElementById("liveTitulo").textContent = d.titulo || d.youtube_id;
    document.getElementById("liveYtId").textContent = `ID: ${d.youtube_id}  |  ${d.canal_fuente || ""}  |  ${Math.floor(d.segundos_transcurridos / 60)}min ${d.segundos_transcurridos % 60}s transcurridos`;
    document.getElementById("liveDot").style.background = "#2ecc71";
  } catch {
    document.getElementById("liveTitulo").textContent = "Error al cargar estado";
    document.getElementById("liveDot").style.background = "#e74c3c";
  }
}

async function liveSiguiente() {
  log("liveLog", "⏭ Avanzando al siguiente vídeo...");
  try {
    const res = await fetch("/live/siguiente", { method: "POST" });
    const d = await res.json();
    if (d.ok) {
      log("liveLog", `✅ Nuevo vídeo: ${d.youtube_id}`);
      setTimeout(cargarEstadoLive, 500);
    } else {
      log("liveLog", `❌ ${d.error || "Error desconocido"}`);
    }
  } catch (e) {
    log("liveLog", `❌ Error: ${e.message}`);
  }
}

async function liveProgramar() {
  const ytId = document.getElementById("liveYtIdInput")?.value.trim();
  if (!ytId) return alert("Introduce un YouTube ID");
  log("liveLog", `📌 Programando vídeo: ${ytId}...`);
  try {
    const res = await fetch("/live/programar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ youtube_id: ytId }),
    });
    const d = await res.json();
    if (d.ok) {
      log("liveLog", `✅ Vídeo programado: ${ytId}`);
      setTimeout(cargarEstadoLive, 500);
    } else {
      log("liveLog", `❌ ${d.error || "Error desconocido"}`);
    }
  } catch (e) {
    log("liveLog", `❌ Error: ${e.message}`);
  }
}

// ── Utilidad log ───────────────────────────────────────────────────
function log(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add("visible");
  el.textContent += (el.textContent ? "\n" : "") + `[${new Date().toLocaleTimeString()}] ${msg}`;
  el.scrollTop = el.scrollHeight;
}
