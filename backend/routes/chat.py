import random
import threading
import time
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from backend.main import socketio
from backend.database import SessionLocal
from backend.models import MensajeChat, Letra, Video

# Alias para acceder al SID del socket en handlers (Flask pone el SID en request.sid)
_get_sid = lambda: getattr(request, "sid", None)

bp = Blueprint("chat", __name__)

# Intervalo en segundos entre mensajes del bot (5 minutos)
BOT_INTERVAL = 300
_bot_thread = None
_bot_running = False


# ─── REST: historial ──────────────────────────────────────────────────────────

@bp.route("/historial", methods=["GET"])
def historial():
    db = SessionLocal()
    try:
        sala = request.args.get("sala", "general")
        limit = min(request.args.get("limit", 50, type=int), 200)
        mensajes = (
            db.query(MensajeChat)
            .filter(MensajeChat.sala == sala)
            .order_by(MensajeChat.created_at.desc())
            .limit(limit)
            .all()
        )
        return jsonify([m.to_dict() for m in reversed(mensajes)])
    finally:
        db.close()


# ─── SocketIO: eventos ────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    emit("sistema", {"mensaje": "Conectado al chat del Carnaval 🎭"})
    _iniciar_bot()


@socketio.on("unirse")
def on_unirse(data):
    sala = data.get("sala", "general")
    nombre = data.get("nombre", "Anónimo")[:50]
    join_room(sala)
    emit("sistema", {"mensaje": f"{nombre} se ha unido a #{sala}"}, to=sala)


@socketio.on("salir")
def on_salir(data):
    sala = data.get("sala", "general")
    nombre = data.get("nombre", "Anónimo")[:50]
    leave_room(sala)
    emit("sistema", {"mensaje": f"{nombre} ha salido de #{sala}"}, to=sala)


@socketio.on("mensaje")
def on_mensaje(data):
    sala = data.get("sala", "general")
    contenido = (data.get("contenido") or "").strip()[:500]

    if not contenido:
        return

    # Si el usuario está autenticado, usar su nombre y avatar
    if current_user.is_authenticated:
        nombre = current_user.nombre_visible()
        usuario_id = current_user.id
    else:
        nombre = (data.get("usuario") or "Anónimo").strip()[:50]
        usuario_id = None

    # Guardar en DB
    payload = None
    db = SessionLocal()
    try:
        msg = MensajeChat(
            usuario=nombre,
            usuario_id=usuario_id,
            contenido=contenido,
            tipo="user",
            sala=sala,
        )
        db.add(msg)
        db.commit()
        payload = msg.to_dict()
    except Exception as e:
        print(f"[Chat] Error guardando mensaje en DB: {e}")
        db.rollback()
        # Emitir igualmente aunque no se haya persistido
        from datetime import datetime as _dt
        payload = {
            "usuario": nombre,
            "contenido": contenido,
            "tipo": "user",
            "sala": sala,
            "hora": _dt.utcnow().strftime("%H:%M"),
        }
    finally:
        db.close()

    if payload:
        # 1) Enviar directamente al emisor (garantiza que siempre vea su propio mensaje)
        emit("mensaje", payload)
        # 2) Broadcast al resto de la sala (excluyendo al emisor para evitar duplicados)
        sid = _get_sid()
        if sid:
            socketio.emit("mensaje", payload, to=sala, skip_sid=sid)
        else:
            socketio.emit("mensaje", payload, to=sala)


# ─── Bot de carnaval aleatorio ────────────────────────────────────────────────

def _mensaje_bot_aleatorio() -> dict:
    """Genera un mensaje del bot con contenido carnavalesco aleatorio."""
    db = SessionLocal()
    try:
        tipo = random.choice(["letra", "video", "dato"])

        if tipo == "letra":
            letra = db.query(Letra).order_by(
                __import__("sqlalchemy.sql.expression", fromlist=["func"]).func.random()
            ).first()
            if letra:
                fragmento = (letra.contenido or "")[:280]
                return {
                    "usuario": "Bot Carnaval 🎭",
                    "contenido": f"🎶 *{letra.grupo_nombre or 'Grupo desconocido'}* ({letra.año or '?'})\n\n_{fragmento}_",
                    "tipo": "bot",
                    "sala": "general",
                    "hora": datetime.utcnow().strftime("%H:%M"),
                }

        if tipo == "video":
            video = db.query(Video).order_by(
                __import__("sqlalchemy.sql.expression", fromlist=["func"]).func.random()
            ).first()
            if video:
                return {
                    "usuario": "Bot Carnaval 🎭",
                    "contenido": f"📺 *{video.titulo}*\n🗓 {video.año} | {video.modalidad or ''} | {video.fase or ''}\nhttps://www.youtube.com/watch?v={video.youtube_id}",
                    "tipo": "bot",
                    "sala": "general",
                    "hora": datetime.utcnow().strftime("%H:%M"),
                }

        # Dato curioso estático
        datos = [
            "¿Sabías que el COAC se celebra en el Gran Teatro Falla desde 1905? 🏛️",
            "Las chirigotas son el tipo más popular del Carnaval de Cádiz por su humor ácido y crítica social 😂",
            "Una comparsa puede tener entre 10 y 20 componentes, mientras un cuarteto solo tiene 4 🎭",
            "El Carnaval de Cádiz es el único del mundo donde la competición oficial se llama COAC 🏆",
            "Las letras del carnaval gaditano llevan más de 140 años recogiendo la historia de España 📜",
        ]
        return {
            "usuario": "Bot Carnaval 🎭",
            "contenido": random.choice(datos),
            "tipo": "bot",
            "sala": "general",
            "hora": datetime.utcnow().strftime("%H:%M"),
        }
    finally:
        db.close()


def _loop_bot():
    global _bot_running
    while _bot_running:
        time.sleep(BOT_INTERVAL)
        if not _bot_running:
            break
        try:
            payload = _mensaje_bot_aleatorio()
            # Guardar en DB
            db = SessionLocal()
            try:
                msg = MensajeChat(
                    usuario=payload["usuario"],
                    contenido=payload["contenido"],
                    tipo="bot",
                    sala=payload.get("sala", "general"),
                )
                db.add(msg)
                db.commit()
            finally:
                db.close()
            socketio.emit("mensaje", payload, to="general")
        except Exception as e:
            print(f"[Bot] Error: {e}")


def _iniciar_bot():
    global _bot_thread, _bot_running
    if _bot_thread is None or not _bot_thread.is_alive():
        _bot_running = True
        _bot_thread = threading.Thread(target=_loop_bot, daemon=True)
        _bot_thread.start()
        print("[Bot] Bot del carnaval iniciado.")
