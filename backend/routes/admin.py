import re
from flask import Blueprint, jsonify, request, render_template
from backend.database import SessionLocal
from backend.models import Video, Letra, Grupo, ConfigSistema

bp = Blueprint("admin", __name__)

_YT_ID_RE = re.compile(r'(?:v=|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})')


def _extraer_yt_id(valor: str) -> str:
    """Extrae el ID de YouTube de una URL completa, o devuelve el valor tal cual."""
    valor = valor.strip()
    match = _YT_ID_RE.search(valor)
    return match.group(1) if match else valor


@bp.route("/")
def panel():
    return render_template("admin.html")


@bp.route("/estadisticas", methods=["GET"])
def estadisticas():
    db = SessionLocal()
    try:
        return jsonify({
            "videos": db.query(Video).count(),
            "letras": db.query(Letra).count(),
            "grupos": db.query(Grupo).count(),
            "videos_con_letra": db.query(Video).filter(Video.tiene_letra == True).count(),  # noqa: E712
        })
    finally:
        db.close()


@bp.route("/scraper/youtube", methods=["POST"])
def lanzar_scraper_youtube():
    """
    Lanza el scraper de YouTube en segundo plano.

    Modos:
      - Sin channel_url: busca por términos COAC (API o yt-dlp).
      - Con channel_url: scracea el canal completo con yt-dlp.

    Parámetros JSON opcionales:
      años        Lista de años [2024, 2025]
      modalidades Lista de modalidades ["chirigota", "comparsa"]
      channel_url URL del canal, ej https://youtube.com/@ONDACADIZCARNAVAL
      forzar_ytdlp true/false — omite la API y usa yt-dlp directamente
      max_videos  Máximo de vídeos al scrapear canal (defecto 200)
    """
    import threading
    from backend.config import config as cfg

    data = request.json or {}
    channel_url = (data.get("channel_url") or "").strip()
    forzar_ytdlp = bool(data.get("forzar_ytdlp", False))
    años = data.get("años", [])
    modalidades = data.get("modalidades", [])
    max_videos = int(data.get("max_videos", 200))

    # Modo canal: scracea canal completo con yt-dlp (no requiere API key)
    if channel_url:
        try:
            from backend.services.youtube_scraper import scrapear_canal_coac
        except ImportError as e:
            return jsonify({"ok": False, "error": str(e)}), 500

        def _run_canal():
            try:
                scrapear_canal_coac(channel_url, max_videos=max_videos)
            except Exception as e:
                print(f"[Scraper canal] Error en hilo: {e}")

        threading.Thread(target=_run_canal, daemon=True).start()
        return jsonify({"ok": True, "mensaje": f"Scraper de canal iniciado: {channel_url}"})

    # Modo búsqueda por términos: requiere API key (salvo forzar_ytdlp)
    if not forzar_ytdlp and not cfg.YOUTUBE_API_KEY:
        return jsonify({
            "ok": False,
            "error": "YOUTUBE_API_KEY no configurada. Activa 'Forzar yt-dlp' para continuar sin cuota API."
        }), 400

    try:
        from backend.services.youtube_scraper import scrapear_coac
    except ImportError as e:
        return jsonify({"ok": False, "error": f"Librería no instalada: {e}"}), 500

    def _run():
        try:
            scrapear_coac(
                annos=años or None,
                modalidades=modalidades or None,
                forzar_ytdlp=forzar_ytdlp,
            )
        except Exception as e:
            print(f"[Scraper] Error en hilo: {e}")

    threading.Thread(target=_run, daemon=True).start()
    modo = "yt-dlp (sin cuota)" if forzar_ytdlp else "YouTube Data API v3"
    return jsonify({"ok": True, "mensaje": f"Scraper iniciado ({modo}). Revisa la consola para ver el progreso."})


@bp.route("/video", methods=["POST"])
def añadir_video_manual():
    """
    Añade un vídeo manualmente.
    Acepta tanto el ID de YouTube (8FKb8TbO8mI) como la URL completa
    (https://www.youtube.com/watch?v=8FKb8TbO8mI).
    """
    data = request.json or {}
    valor_raw = (data.get("youtube_id") or "").strip()
    if not valor_raw:
        return jsonify({"error": "Falta youtube_id o URL"}), 400

    # Extraer ID si se pasó URL completa
    youtube_id = _extraer_yt_id(valor_raw)
    if len(youtube_id) != 11:
        return jsonify({"error": f"No se pudo extraer un YouTube ID válido de: {valor_raw}"}), 400

    # Intentar con API primero; fallback a yt-dlp
    from backend.services.youtube_scraper import obtener_metadata_video, metadatos_ytdlp
    meta = obtener_metadata_video(youtube_id) or metadatos_ytdlp(youtube_id)
    if not meta:
        return jsonify({"error": f"No se pudo obtener metadata del vídeo {youtube_id}. Comprueba que el ID es correcto."}), 400

    db = SessionLocal()
    try:
        from backend.models import Video as V
        existente = db.query(V).filter(V.youtube_id == youtube_id).first()
        if existente:
            return jsonify({"error": "El vídeo ya existe", "id": existente.id}), 409

        video = V(
            youtube_id=youtube_id,
            titulo=meta.get("titulo", ""),
            descripcion=meta.get("descripcion", ""),
            thumbnail=meta.get("thumbnail", ""),
            duracion=meta.get("duracion", 0),
            vistas=meta.get("vistas", 0),
            fecha_publicacion=meta.get("fecha_publicacion"),
            año=data.get("año"),
            fase=data.get("fase"),
            modalidad=data.get("modalidad"),
            tipo=data.get("tipo", "coac"),
            grupo_nombre=data.get("grupo_nombre", ""),
            destacado=data.get("destacado", False),
        )
        db.add(video)
        db.commit()
        return jsonify({"ok": True, "id": video.id})
    finally:
        db.close()


@bp.route("/video/<int:video_id>", methods=["PATCH"])
def editar_video(video_id):
    """Edita metadatos de un vídeo (año, fase, modalidad, grupo_nombre, destacado)."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return jsonify({"error": "No encontrado"}), 404

        data = request.json or {}
        for campo in ["año", "fase", "modalidad", "tipo", "grupo_nombre", "destacado", "odysee_url"]:
            if campo in data:
                setattr(video, campo, data[campo])

        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@bp.route("/video/<int:video_id>", methods=["DELETE"])
def eliminar_video(video_id):
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return jsonify({"error": "No encontrado"}), 404
        db.delete(video)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@bp.route("/odysee/sync", methods=["POST"])
def sincronizar_odysee():
    """Lanza la sincronización con Odysee en segundo plano."""
    import threading
    from backend.config import config as cfg

    if not cfg.ODYSEE_EMAIL or not cfg.ODYSEE_PASSWORD:
        return jsonify({"ok": False, "error": "ODYSEE_EMAIL y ODYSEE_PASSWORD no configurados en .env"}), 400

    data = request.json or {}
    limite = int(data.get("limite", 10))

    try:
        from backend.services.odysee_uploader import sincronizar_pendientes
    except ImportError as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    threading.Thread(target=sincronizar_pendientes, args=(limite,), daemon=True).start()
    return jsonify({"ok": True, "mensaje": f"Sincronizando {limite} vídeos con Odysee en segundo plano."})


@bp.route("/config", methods=["GET"])
def get_config():
    db = SessionLocal()
    try:
        items = db.query(ConfigSistema).all()
        return jsonify({i.clave: i.valor for i in items})
    finally:
        db.close()


@bp.route("/config", methods=["POST"])
def set_config():
    db = SessionLocal()
    try:
        data = request.json or {}
        for clave, valor in data.items():
            item = db.query(ConfigSistema).filter(ConfigSistema.clave == clave).first()
            if item:
                item.valor = str(valor)
            else:
                db.add(ConfigSistema(clave=clave, valor=str(valor)))
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
