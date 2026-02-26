from flask import Blueprint, jsonify, request
from sqlalchemy import desc
from backend.database import SessionLocal
from backend.models import Letra

bp = Blueprint("letras", __name__)


def _db():
    return SessionLocal()


@bp.route("/", methods=["GET"])
def listar_letras():
    """Lista letras con filtros."""
    db = _db()
    try:
        q = db.query(Letra)

        año = request.args.get("año", type=int)
        tipo_pieza = request.args.get("tipo_pieza")
        grupo = request.args.get("grupo", "").strip()
        busqueda = request.args.get("q", "").strip()

        if año:
            q = q.filter(Letra.año == año)
        if tipo_pieza:
            q = q.filter(Letra.tipo_pieza == tipo_pieza)
        if grupo:
            q = q.filter(Letra.grupo_nombre.ilike(f"%{grupo}%"))
        if busqueda:
            q = q.filter(
                Letra.contenido.ilike(f"%{busqueda}%") |
                Letra.titulo.ilike(f"%{busqueda}%") |
                Letra.grupo_nombre.ilike(f"%{busqueda}%")
            )

        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 100)
        total = q.count()
        letras = q.order_by(desc(Letra.año)).offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "total": total,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
            "letras": [l.to_dict() for l in letras],
        })
    finally:
        db.close()


@bp.route("/<int:letra_id>", methods=["GET"])
def detalle_letra(letra_id):
    """Devuelve una letra. Si no tiene contenido, lo descarga de la API y lo cachea."""
    db = _db()
    try:
        letra = db.query(Letra).filter(Letra.id == letra_id).first()
        if not letra:
            return jsonify({"error": "Letra no encontrada"}), 404

        # Contenido bajo demanda: si está vacío y tenemos URL de origen, lo descargamos
        if not letra.contenido or len(letra.contenido) < 10:
            from backend.services.letras_importer import obtener_contenido_api
            obtener_contenido_api(letra_id)
            # Re-leer tras la actualización
            db.refresh(letra)

        return jsonify(letra.to_dict())
    finally:
        db.close()


@bp.route("/por-video/<int:video_id>", methods=["GET"])
def letras_de_video(video_id):
    """Devuelve todas las letras asociadas a un vídeo (para mostrar mientras se reproduce)."""
    db = _db()
    try:
        letras = db.query(Letra).filter(Letra.video_id == video_id).all()
        return jsonify([l.to_dict() for l in letras])
    finally:
        db.close()


@bp.route("/por-grupo", methods=["GET"])
def letras_por_grupo():
    """Busca letras de un grupo por nombre (para vincular a vídeos)."""
    grupo = request.args.get("grupo", "").strip()
    año = request.args.get("año", type=int)
    if not grupo:
        return jsonify({"error": "Parámetro 'grupo' requerido"}), 400

    db = _db()
    try:
        q = db.query(Letra).filter(Letra.grupo_nombre.ilike(f"%{grupo}%"))
        if año:
            q = q.filter(Letra.año == año)
        letras = q.limit(50).all()
        return jsonify([l.to_dict() for l in letras])
    finally:
        db.close()


@bp.route("/aleatoria", methods=["GET"])
def letra_aleatoria():
    """Letra aleatoria para el bot del chat. Prefiere las que tienen contenido."""
    db = _db()
    try:
        from sqlalchemy.sql.expression import func
        # Primero intentar con contenido
        letra = (
            db.query(Letra)
            .filter(Letra.contenido != "", Letra.contenido.isnot(None))
            .order_by(func.random())
            .first()
        )
        # Si no hay ninguna con contenido, cualquiera sirve
        if not letra:
            letra = db.query(Letra).order_by(func.random()).first()
        if not letra:
            return jsonify({"error": "Sin letras"}), 404
        return jsonify(letra.to_dict())
    finally:
        db.close()


@bp.route("/importar", methods=["POST"])
def importar_letras_api():
    """
    Lanza la importación desde la API de Carnaval-Letras en segundo plano.
    Parámetros opcionales: anio, modalidad, calidad_min, limite.
    """
    import threading
    from backend.services.letras_importer import importar_metadata, get_estado

    # No lanzar si ya hay una importación activa
    estado = get_estado()
    if estado["activo"]:
        return jsonify({"error": "Ya hay una importación en curso"}), 409

    data = request.json or {}
    kwargs = {
        "anio": data.get("anio") or None,
        "modalidad": data.get("modalidad") or None,
        "calidad_min": int(data.get("calidad_min", 0)),
        "limite": int(data.get("limite", 20000)),
    }

    threading.Thread(target=importar_metadata, kwargs=kwargs, daemon=True).start()
    return jsonify({"ok": True, "mensaje": "Importación iniciada. Usa /api/letras/progreso para seguir el estado."})


@bp.route("/progreso", methods=["GET"])
def progreso_importacion():
    """Estado actual de la importación en curso."""
    from backend.services.letras_importer import get_estado
    return jsonify(get_estado())


@bp.route("/enriquecer", methods=["POST"])
def enriquecer_contenido():
    """
    Descarga el contenido (texto) de letras que solo tienen metadata.
    Proceso lento — configura el límite según el tiempo disponible.
    """
    import threading
    from backend.services.letras_importer import enriquecer_contenido as _enriquecer, get_estado

    estado = get_estado()
    if estado["activo"]:
        return jsonify({"error": "Ya hay un proceso activo"}), 409

    data = request.json or {}
    limite = int(data.get("limite", 200))

    threading.Thread(target=_enriquecer, kwargs={"limite": limite}, daemon=True).start()
    return jsonify({"ok": True, "mensaje": f"Enriqueciendo hasta {limite} letras con contenido."})
