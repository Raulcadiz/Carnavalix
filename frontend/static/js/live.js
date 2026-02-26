/* ══════════════════════════════════════════════════════════════════
   Carnavalix — Canal Live 24/7
   Usa iframe estático (igual que player.html) para máxima compatibilidad.
   Sincroniza con el servidor cada 30 s actualizando el src del iframe.
   ══════════════════════════════════════════════════════════════════ */

let _estadoActual = null;
let _syncInterval = null;
const SYNC_INTERVAL_MS = 30000; // sincronizar cada 30 segundos

document.addEventListener("DOMContentLoaded", iniciarLive);

// ── Arranque ─────────────────────────────────────────────────────────────────
async function iniciarLive() {
  const estado = await obtenerEstado();
  if (!estado) return;

  _estadoActual = estado;
  cargarPlayer(estado.youtube_id, estado.segundos_transcurridos);
  actualizarInfoPanel(estado);

  // Polling de sincronización
  _syncInterval = setInterval(sincronizarEstado, SYNC_INTERVAL_MS);

  // Chat lateral
  iniciarChat("live");
}

// ── Player ────────────────────────────────────────────────────────────────────
function cargarPlayer(ytId, seekTo) {
  const iframe = document.getElementById("livePlayer");
  const loading = document.getElementById("liveLoading");
  if (!iframe) return;

  const start = Math.max(0, Math.floor(seekTo || 0));
  // controls=0 oculta la barra de progreso → comportamiento de canal TV
  iframe.src = `https://www.youtube.com/embed/${ytId}?autoplay=1&start=${start}&controls=0&rel=0&modestbranding=1&iv_load_policy=3&disablekb=1`;

  // Ocultar spinner cuando cargue el iframe
  iframe.onload = () => {
    if (loading) loading.style.display = "none";
  };
  if (loading) loading.style.display = "flex";
}

// ── Sincronización con el servidor ───────────────────────────────────────────
async function sincronizarEstado() {
  const estado = await obtenerEstado();
  if (!estado) return;

  // Si el vídeo cambió, recargar el player con el nuevo vídeo y seek
  if (!_estadoActual || estado.youtube_id !== _estadoActual.youtube_id) {
    _estadoActual = estado;
    actualizarInfoPanel(estado);
    cargarPlayer(estado.youtube_id, estado.segundos_transcurridos);
    return;
  }

  // Mismo vídeo — actualizar estado interno (no podemos seekTo con iframe estático,
  // pero el start= del src ya puso al usuario en la posición correcta al cargar)
  _estadoActual = estado;
}

// ── API estado ────────────────────────────────────────────────────────────────
async function obtenerEstado() {
  try {
    const res = await fetch("/live/estado");
    if (!res.ok) {
      mostrarError("El canal no tiene vídeo activo. Vuelve más tarde.");
      return null;
    }
    return await res.json();
  } catch {
    mostrarError("No se pudo conectar con el servidor del canal.");
    return null;
  }
}

// ── Panel de info ─────────────────────────────────────────────────────────────
function actualizarInfoPanel(estado) {
  const titulo = document.getElementById("liveTituloActual");
  const canal  = document.getElementById("liveCanal");

  if (titulo) titulo.textContent = estado.titulo || estado.youtube_id;
  if (canal)  canal.textContent  = estado.canal_fuente || "ONDACADIZCARNAVAL";

  // Mostrar botón "Siguiente" sólo si el usuario es admin
  fetch("/api/auth/yo").then(r => r.json()).then(d => {
    const btn = document.getElementById("btnLiveSiguientePub");
    if (btn) btn.style.display = (d.autenticado && d.usuario?.es_admin) ? "inline-flex" : "none";
  }).catch(() => {});
}

function mostrarError(msg) {
  const loading = document.getElementById("liveLoading");
  if (loading) {
    loading.style.display = "flex";
    loading.innerHTML = `<p style="color:var(--text-muted,#888);text-align:center;padding:20px">${msg}</p>`;
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────
function iniciarChat(sala) {
  if (typeof CP === "undefined" || !CP.socket) {
    // socket.io no inicializado aún, reintentamos
    setTimeout(() => iniciarChat(sala), 500);
    return;
  }

  // Historial
  fetch(`/api/chat/historial?sala=${sala}&limit=50`)
    .then(r => r.json())
    .then(msgs => {
      const cont = document.getElementById("chatMensajes");
      if (cont) { cont.innerHTML = ""; msgs.forEach(m => añadirMensaje(m)); }
    })
    .catch(() => {});

  // Unirse a la sala
  CP.socket.emit("unirse", { sala, nombre: obtenerNombreChat() });

  // Escuchar mensajes nuevos
  CP.socket.on("mensaje", (msg) => {
    if (msg.sala === sala || !msg.sala) añadirMensaje(msg);
  });
  CP.socket.on("sistema", (d) => añadirSistema(d.mensaje));

  // El servidor cambió el vídeo → sincronizar
  CP.socket.on("live_cambio", () => {
    sincronizarEstado();
  });

  // Enviar mensajes
  const input = document.getElementById("chatInput");
  const btn   = document.getElementById("btnChatSend");
  const enviar = () => {
    const txt = input?.value.trim();
    if (!txt) return;
    CP.socket.emit("mensaje", { sala, contenido: txt, usuario: obtenerNombreChat() });
    if (input) input.value = "";
  };
  btn?.addEventListener("click", enviar);
  input?.addEventListener("keydown", (e) => { if (e.key === "Enter") enviar(); });

  // Mostrar info de usuario autenticado
  fetch("/api/auth/yo").then(r => r.json()).then(d => {
    const anonInfo = document.getElementById("chatAnonimoInfo");
    const usuInfo  = document.getElementById("chatUsuarioInfo");
    if (d.autenticado && d.usuario) {
      if (anonInfo) anonInfo.style.display = "none";
      if (usuInfo) {
        usuInfo.style.display = "flex";
        const el = document.getElementById("chatAvatarEmoji");
        const nm = document.getElementById("chatNombreVisible");
        if (el) el.textContent = d.usuario.avatar_emoji || "🎭";
        if (nm) nm.textContent = d.usuario.display_name;
      }
    }
  }).catch(() => {});
}

function obtenerNombreChat() {
  const input = document.getElementById("chatNombreAnonimo");
  return input?.value.trim() || "Anónimo";
}

function añadirMensaje(msg) {
  const cont = document.getElementById("chatMensajes");
  if (!cont) return;
  const div = document.createElement("div");
  div.className = `chat-msg tipo-${msg.tipo || "user"}`;
  const emoji = msg.avatar_emoji || "🎭";
  const color = msg.avatar_color || "#d4a843";
  const hora  = msg.hora || "";
  div.innerHTML = `
    <span class="msg-avatar" style="background:${color}">${emoji}</span>
    <div class="msg-body">
      <span class="msg-user">${escHtml(msg.usuario)}</span>
      <span class="msg-hora">${hora}</span>
      <p class="msg-texto">${escHtml(msg.contenido)}</p>
    </div>`;
  cont.appendChild(div);
  cont.scrollTop = cont.scrollHeight;
}

function añadirSistema(msg) {
  const cont = document.getElementById("chatMensajes");
  if (!cont) return;
  const div = document.createElement("div");
  div.className = "chat-msg tipo-sistema";
  div.textContent = msg;
  cont.appendChild(div);
  cont.scrollTop = cont.scrollHeight;
}

function escHtml(s) {
  return (s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Botón admin: siguiente vídeo ──────────────────────────────────────────────
document.getElementById("btnLiveSiguientePub")?.addEventListener("click", async () => {
  await fetch("/live/siguiente", { method: "POST" });
  setTimeout(sincronizarEstado, 1000);
});
