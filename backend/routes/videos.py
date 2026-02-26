from flask import Blueprint, jsonify, request
from sqlalchemy import or_, desc
from backend.database import SessionLocal
from backend.models import Video, Grupo

bp = Blueprint("videos", __name__)


def _db():
    return SessionLocal()


@bp.route("/", methods=["GET"])
def listar_videos():
    """
    Lista vídeos con filtros opcionales.
    Query params: año, fase, modalidad, tipo, grupo_id, q (búsqueda), page, per_page
    """
    db = _db()
    try:
        q = db.query(Video)

        año = request.args.get("año", type=int)
        fase = request.args.get("fase")
        modalidad = request.args.get("modalidad")
        tipo = request.args.get("tipo")
        grupo_id = request.args.get("grupo_id", type=int)
        busqueda = request.args.get("q", "").strip()
        destacados = request.args.get("destacados", "false").lower() == "true"
        tiene_letra = request.args.get("tiene_letra", "false").lower() == "true"

        if año:
            q = q.filter(Video.año == año)
        if fase:
            q = q.filter(Video.fase == fase)
        if modalidad:
            q = q.filter(Video.modalidad == modalidad)
        if tipo:
            q = q.filter(Video.tipo == tipo)
        if grupo_id:
            q = q.filter(Video.grupo_id == grupo_id)
        if destacados:
            q = q.filter(Video.destacado == True)  # noqa: E712
        if tiene_letra:
            q = q.filter(Video.tiene_letra == True)  # noqa: E712
        if busqueda:
            patron = f"%{busqueda}%"
            q = q.filter(
                or_(
                    Video.titulo.ilike(patron),
                    Video.grupo_nombre.ilike(patron),
                    Video.descripcion.ilike(patron),
                )
            )

        # Paginación
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 24, type=int), 100)
        total = q.count()
        videos = q.order_by(desc(Video.año), desc(Video.vistas)).offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "videos": [v.to_dict() for v in videos],
        })
    finally:
        db.close()


@bp.route("/<int:video_id>", methods=["GET"])
def detalle_video(video_id):
    """Detalle de un vídeo con sus letras."""
    db = _db()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return jsonify({"error": "Vídeo no encontrado"}), 404
        return jsonify(video.to_dict(include_letras=True))
    finally:
        db.close()


@bp.route("/años", methods=["GET"])
def años_disponibles():
    """Lista de años con contenido."""
    db = _db()
    try:
        años = db.query(Video.año).distinct().filter(Video.año.isnot(None)).order_by(desc(Video.año)).all()
        return jsonify([a[0] for a in años])
    finally:
        db.close()


@bp.route("/estadisticas", methods=["GET"])
def estadisticas():
    """Resumen de contenido disponible."""
    db = _db()
    try:
        total = db.query(Video).count()
        por_modalidad = {}
        for modalidad in ["chirigota", "comparsa", "coro", "cuarteto", "romancero"]:
            por_modalidad[modalidad] = db.query(Video).filter(Video.modalidad == modalidad).count()
        callejeras = db.query(Video).filter(Video.tipo == "callejera").count()
        con_letra = db.query(Video).filter(Video.tiene_letra == True).count()  # noqa: E712

        return jsonify({
            "total_videos": total,
            "por_modalidad": por_modalidad,
            "callejeras": callejeras,
            "con_letra": con_letra,
            "total_grupos": db.query(Grupo).count(),
        })
    finally:
        db.close()


@bp.route("/aleatorio", methods=["GET"])
def video_aleatorio():
    """Devuelve un vídeo aleatorio (para modo shuffle)."""
    db = _db()
    try:
        from sqlalchemy.sql.expression import func
        modalidad = request.args.get("modalidad")
        q = db.query(Video)
        if modalidad:
            q = q.filter(Video.modalidad == modalidad)
        video = q.order_by(func.random()).first()
        if not video:
            return jsonify({"error": "Sin vídeos"}), 404
        return jsonify(video.to_dict())
    finally:
        db.close()
