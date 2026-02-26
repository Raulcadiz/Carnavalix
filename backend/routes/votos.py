import hashlib
from flask import Blueprint, jsonify, request
from sqlalchemy import desc, func
from backend.database import SessionLocal
from backend.models import Voto, Video

bp = Blueprint("votos", __name__)


def _db():
    return SessionLocal()


def _ip_hash(request_obj) -> str:
    ip = request_obj.headers.get("X-Forwarded-For", request_obj.remote_addr or "unknown")
    return hashlib.sha256(ip.encode()).hexdigest()


@bp.route("/", methods=["POST"])
def votar():
    """Registra o actualiza el voto de un usuario para un vídeo."""
    data = request.json or {}
    video_id = data.get("video_id")
    valor = data.get("valor")

    if not video_id or valor not in [1, 2, 3, 4, 5]:
        return jsonify({"error": "video_id y valor (1-5) son requeridos"}), 400

    ip_hash = _ip_hash(request)
    db = _db()
    try:
        # Verificar que el vídeo existe
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return jsonify({"error": "Vídeo no encontrado"}), 404

        # Upsert del voto
        voto = db.query(Voto).filter(
            Voto.video_id == video_id,
            Voto.ip_hash == ip_hash,
        ).first()

        if voto:
            voto.valor = valor
        else:
            voto = Voto(video_id=video_id, ip_hash=ip_hash, valor=valor)
            db.add(voto)

        db.flush()

        # Recalcular media en el vídeo
        stats = db.query(func.avg(Voto.valor), func.count(Voto.id)).filter(
            Voto.video_id == video_id
        ).first()

        video.puntuacion_media = round(float(stats[0] or 0), 2)
        video.total_votos = stats[1]
        db.commit()

        return jsonify({
            "ok": True,
            "puntuacion_media": video.puntuacion_media,
            "total_votos": video.total_votos,
        })
    finally:
        db.close()


@bp.route("/ranking", methods=["GET"])
def ranking():
    """Top vídeos por puntuación media (mínimo N votos)."""
    db = _db()
    try:
        min_votos = request.args.get("min_votos", 3, type=int)
        modalidad = request.args.get("modalidad")
        año = request.args.get("año", type=int)
        limit = min(request.args.get("limit", 20, type=int), 50)

        q = db.query(Video).filter(Video.total_votos >= min_votos)
        if modalidad:
            q = q.filter(Video.modalidad == modalidad)
        if año:
            q = q.filter(Video.año == año)

        videos = q.order_by(desc(Video.puntuacion_media), desc(Video.total_votos)).limit(limit).all()

        return jsonify([{
            **v.to_dict(),
            "posicion": i + 1,
        } for i, v in enumerate(videos)])
    finally:
        db.close()
