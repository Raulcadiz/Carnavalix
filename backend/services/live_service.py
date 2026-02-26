"""
Servicio del canal Live 24/7.
Monitoriza el estado del canal y avanza al siguiente vídeo cuando termina el actual.
"""
import threading
import time
from datetime import datetime
from backend.database import SessionLocal
from backend.models import EstadoLive, Video

_monitor_thread = None
_monitor_running = False


def _seleccionar_siguiente_video(db):
    """
    Selecciona el siguiente vídeo para el canal live.
    Prioriza finales y semifinales de forma aleatoria.
    """
    from sqlalchemy.sql.expression import func

    # Primero intentar finales/semifinales
    video = (
        db.query(Video)
        .filter(Video.fase.in_(["final", "semifinal"]))
        .order_by(func.random())
        .first()
    )
    if video:
        return video

    # Si no hay finales/semifinales, cualquier vídeo del catálogo
    return db.query(Video).order_by(func.random()).first()


def avanzar_al_siguiente():
    """
    Avanza al siguiente vídeo en el canal live.
    Devuelve el youtube_id del nuevo vídeo o None si no hay vídeos.
    """
    db = SessionLocal()
    try:
        video = _seleccionar_siguiente_video(db)
        if not video:
            return None

        estado = db.query(EstadoLive).filter(EstadoLive.id == 1).first()
        if estado:
            estado.youtube_id = video.youtube_id
            estado.titulo = video.titulo
            estado.duracion = video.duracion or 0
            estado.started_at = datetime.utcnow()
            estado.canal_fuente = video.grupo_nombre or "ONDACADIZCARNAVAL"
        else:
            estado = EstadoLive(
                id=1,
                youtube_id=video.youtube_id,
                titulo=video.titulo,
                duracion=video.duracion or 0,
                started_at=datetime.utcnow(),
                canal_fuente=video.grupo_nombre or "ONDACADIZCARNAVAL",
            )
            db.add(estado)

        db.commit()
        print(f"[Live] Nuevo vídeo: {video.titulo[:60]} ({video.youtube_id})")

        # Notificar por SocketIO si está disponible
        try:
            from backend.main import socketio
            socketio.emit("live_cambio", estado.to_dict(), to="live")
        except Exception:
            pass

        return video.youtube_id

    except Exception as e:
        print(f"[Live] Error avanzando: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def programar_video(youtube_id: str) -> bool:
    """Programa un vídeo específico en el canal live."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.youtube_id == youtube_id).first()
        if video:
            duracion = video.duracion or 0
            titulo = video.titulo
        else:
            # Intentar obtener metadata para el vídeo
            try:
                from backend.services.youtube_scraper import metadatos_ytdlp
                meta = metadatos_ytdlp(youtube_id)
                duracion = meta["duracion"] if meta else 0
                titulo = meta["titulo"] if meta else youtube_id
            except Exception:
                duracion = 0
                titulo = youtube_id

        estado = db.query(EstadoLive).filter(EstadoLive.id == 1).first()
        if estado:
            estado.youtube_id = youtube_id
            estado.titulo = titulo
            estado.duracion = duracion
            estado.started_at = datetime.utcnow()
        else:
            db.add(EstadoLive(
                id=1,
                youtube_id=youtube_id,
                titulo=titulo,
                duracion=duracion,
                started_at=datetime.utcnow(),
            ))

        db.commit()

        try:
            from backend.main import socketio
            estado2 = db.query(EstadoLive).filter(EstadoLive.id == 1).first()
            if estado2:
                socketio.emit("live_cambio", estado2.to_dict(), to="live")
        except Exception:
            pass

        return True

    except Exception as e:
        print(f"[Live] Error programando: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def _monitor_loop():
    """
    Bucle de monitorización: detecta cuando termina el vídeo actual
    y avanza al siguiente automáticamente.
    Comprueba cada 30 segundos.
    """
    global _monitor_running
    print("[Live] Monitor iniciado.")
    while _monitor_running:
        try:
            db = SessionLocal()
            try:
                estado = db.query(EstadoLive).filter(EstadoLive.id == 1).first()
                if estado and estado.youtube_id and estado.duracion > 0:
                    elapsed = int((datetime.utcnow() - estado.started_at).total_seconds())
                    # Avanzar si el vídeo ha terminado (con 15s de margen)
                    if elapsed >= estado.duracion + 15:
                        print(f"[Live] Vídeo terminado ({elapsed}s / {estado.duracion}s). Avanzando...")
                        avanzar_al_siguiente()
                else:
                    # Sin registro, sin youtube_id o duración 0 → intentar iniciar
                    avanzar_al_siguiente()
            finally:
                db.close()
        except Exception as e:
            print(f"[Live] Error en monitor: {e}")

        time.sleep(30)


def iniciar_monitor():
    """Inicia el hilo de monitorización del canal live."""
    global _monitor_thread, _monitor_running
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def detener_monitor():
    """Detiene el hilo de monitorización."""
    global _monitor_running
    _monitor_running = False
