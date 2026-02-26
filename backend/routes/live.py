"""
Rutas del canal Live 24/7.

GET  /live/          — Página del canal live
GET  /live/estado    — Estado actual (youtube_id, segundos_transcurridos, título)
POST /live/siguiente — Admin: avanza al siguiente vídeo aleatoriamente
POST /live/programar — Admin: programa un vídeo específico por youtube_id
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import current_user
from backend.database import SessionLocal
from backend.models import EstadoLive

bp = Blueprint("live", __name__)


@bp.route("/")
def live_page():
    return render_template("live.html")


@bp.route("/estado", methods=["GET"])
def estado_live():
    """
    Devuelve el estado actual del canal live.
    Si no hay estado o vídeo activo, intenta auto-iniciar con los vídeos del catálogo.
    """
    db = SessionLocal()
    try:
        estado = db.query(EstadoLive).filter(EstadoLive.id == 1).first()
        if not estado or not estado.youtube_id:
            # Intentar arrancar automáticamente
            db.close()
            from backend.services.live_service import avanzar_al_siguiente
            nuevo_id = avanzar_al_siguiente()
            if not nuevo_id:
                return jsonify({"error": "Sin contenido. Añade vídeos desde el Admin."}), 404
            # Releer estado
            db = SessionLocal()
            estado = db.query(EstadoLive).filter(EstadoLive.id == 1).first()
            if not estado:
                return jsonify({"error": "Error iniciando el canal"}), 500
        return jsonify(estado.to_dict())
    finally:
        db.close()


@bp.route("/siguiente", methods=["POST"])
def siguiente_video():
    """
    Avanza al siguiente vídeo manualmente.
    Requiere estar autenticado. Si no hay usuarios aún (setup inicial), permite acceso libre.
    """
    from backend.database import SessionLocal as _SL
    from backend.models import Usuario as _U

    # Verificar si hay usuarios en el sistema
    _db = _SL()
    try:
        hay_usuarios = _db.query(_U).first() is not None
    finally:
        _db.close()

    # Si hay usuarios, requiere ser admin
    if hay_usuarios and (not current_user.is_authenticated or not current_user.es_admin):
        return jsonify({"error": "Se requiere cuenta de administrador"}), 403

    from backend.services.live_service import avanzar_al_siguiente
    nuevo_id = avanzar_al_siguiente()
    if nuevo_id:
        return jsonify({"ok": True, "youtube_id": nuevo_id})
    return jsonify({"error": "No hay vídeos disponibles en el catálogo"}), 404


@bp.route("/programar", methods=["POST"])
def programar_video():
    """
    Programa un vídeo específico en el canal live.
    Requiere estar autenticado como admin.
    Si no hay usuarios aún (setup inicial), permite acceso libre.
    """
    import re
    from backend.database import SessionLocal as _SL
    from backend.models import Usuario as _U

    _db = _SL()
    try:
        hay_usuarios = _db.query(_U).first() is not None
    finally:
        _db.close()

    if hay_usuarios and (not current_user.is_authenticated or not current_user.es_admin):
        return jsonify({"error": "Se requiere cuenta de administrador"}), 403

    data = request.json or {}
    valor = (data.get("youtube_id") or "").strip()
    if not valor:
        return jsonify({"error": "Falta youtube_id"}), 400

    # Extraer ID si se pasa una URL completa
    match = re.search(r'(?:v=|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})', valor)
    youtube_id = match.group(1) if match else valor

    from backend.services.live_service import programar_video as _programar
    if _programar(youtube_id):
        return jsonify({"ok": True, "youtube_id": youtube_id})
    return jsonify({"error": "No se pudo programar el vídeo"}), 400
