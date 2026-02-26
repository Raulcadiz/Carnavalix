/* ══════════════════════════════════════════════════════════════════
   CarnavalPlay — Chat 24/7
   ══════════════════════════════════════════════════════════════════ */

const socket = io({ transports: ["websocket", "polling"] });
let salaActual = "general";

document.addEventListener("DOMContentLoaded", () => {
  cargarHistorial(salaActual);
  initRooms();
  initFormulario();
  initSocket();
});

// ── Socket ─────────────────────────────────────────────────────────
function initSocket() {
  socket.on("connect", () => {
    unirseASala(salaActual);
    document.getElementById("onlineBadge").textContent = "● En línea";
  });

  socket.on("disconnect", () => {
    document.getElementById("onlineBadge").textContent = "● Desconectado";
  });

  socket.on("mensaje", (msg) => {
    renderMensaje(msg);
    scrollAbajo();
  });

  socket.on("sistema", (data) => {
    renderSistema(data.mensaje);
  });
}

function unirseASala(sala) {
  socket.emit("unirse", { sala, nombre: getNombre() });
}

function salirDeSala(sala) {
  socket.emit("salir", { sala, nombre: getNombre() });
}

function getNombre() {
  return (document.getElementById("inputNombre")?.value.trim() || "Anónimo").slice(0, 30);
}

// ── Salas ──────────────────────────────────────────────────────────
function initRooms() {
  document.querySelectorAll(".room-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.sala === salaActual) return;

      salirDeSala(salaActual);
      salaActual = btn.dataset.sala;

      document.querySelectorAll(".room-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("chatSalaNombre").textContent = `# ${salaActual}`;

      document.getElementById("chatMensajes").innerHTML = "";
      cargarHistorial(salaActual);
      unirseASala(salaActual);
    });
  });
}

// ── Historial ──────────────────────────────────────────────────────
async function cargarHistorial(sala) {
  try {
    const msgs = await CP.get(`/api/chat/historial?sala=${sala}&limit=50`);
    msgs.forEach(m => renderMensaje(m, false));
    scrollAbajo();
  } catch (e) {
    console.warn("Error historial:", e);
  }
}

// ── Formulario ─────────────────────────────────────────────────────
function initFormulario() {
  const form = document.getElementById("chatForm");
  const inp = document.getElementById("chatInput");

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = inp.value.trim();
    if (!texto) return;

    socket.emit("mensaje", {
      sala: salaActual,
      usuario: getNombre(),
      contenido: texto,
    });

    inp.value = "";
  });
}

// ── Render mensajes ────────────────────────────────────────────────
function renderMensaje(msg, scroll = true) {
  const contenedor = document.getElementById("chatMensajes");

  let tplId;
  if (msg.tipo === "bot") tplId = "msgBotTemplate";
  else if (msg.tipo === "sistema") tplId = "msgSistemaTemplate";
  else tplId = "msgUserTemplate";

  const tpl = document.getElementById(tplId);
  const node = tpl.content.cloneNode(true);

  const contenidoEl = node.querySelector(".msg-contenido");
  contenidoEl.textContent = msg.contenido;

  const autorEl = node.querySelector(".msg-autor");
  if (autorEl) autorEl.textContent = msg.usuario || msg.tipo;

  const horaEl = node.querySelector(".msg-hora");
  if (horaEl) horaEl.textContent = msg.hora || "";

  contenedor.appendChild(node);
  if (scroll) scrollAbajo();
}

function renderSistema(texto) {
  const tpl = document.getElementById("msgSistemaTemplate");
  const node = tpl.content.cloneNode(true);
  node.querySelector(".msg-contenido").textContent = texto;
  document.getElementById("chatMensajes").appendChild(node);
  scrollAbajo();
}

function scrollAbajo() {
  const el = document.getElementById("chatMensajes");
  el.scrollTop = el.scrollHeight;
}
