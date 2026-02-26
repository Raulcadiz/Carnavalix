from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    Float, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from backend.database import Base


class Usuario(UserMixin, Base):
    """Usuario registrado de Carnavalix."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(80))           # nombre visible en el chat
    avatar_color = Column(String(7), default="#d4a843")  # color hex
    avatar_emoji = Column(String(4), default="🎭")
    es_admin = Column(Boolean, default=False)
    activo = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    mensajes = relationship("MensajeChat", back_populates="usuario_obj", foreign_keys="MensajeChat.usuario_id")

    def nombre_visible(self):
        return self.display_name or self.username

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.nombre_visible(),
            "avatar_color": self.avatar_color,
            "avatar_emoji": self.avatar_emoji,
            "es_admin": self.es_admin,
        }


class Grupo(Base):
    """Agrupación del Carnaval de Cádiz."""
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(200), nullable=False, index=True)
    modalidad = Column(String(50), nullable=False)   # chirigota, comparsa, coro, cuarteto, romancero
    autores = Column(String(500))
    descripcion = Column(Text)
    imagen_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="grupo")
    letras = relationship("Letra", back_populates="grupo")

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "modalidad": self.modalidad,
            "autores": self.autores,
            "descripcion": self.descripcion,
            "imagen_url": self.imagen_url,
        }


class Video(Base):
    """Vídeo COAC indexado desde YouTube."""
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("youtube_id", name="uq_youtube_id"),)

    id = Column(Integer, primary_key=True)
    youtube_id = Column(String(20), nullable=False, unique=True, index=True)
    titulo = Column(String(500), nullable=False)
    descripcion = Column(Text)
    thumbnail = Column(String(500))
    duracion = Column(Integer)          # segundos
    vistas = Column(Integer, default=0)
    fecha_publicacion = Column(DateTime)

    # Clasificación COAC
    año = Column(Integer, index=True)
    fase = Column(String(50), index=True)       # preliminar, cuartos, semifinal, final, callejera
    modalidad = Column(String(50), index=True)  # chirigota, comparsa, coro, cuarteto
    tipo = Column(String(20), default="coac")   # coac, callejera, especial

    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=True)
    grupo_nombre = Column(String(200))           # desnormalizado para FTS
    grupo = relationship("Grupo", back_populates="videos")

    tiene_letra = Column(Boolean, default=False)
    odysee_url = Column(String(500))
    destacado = Column(Boolean, default=False)

    # Stats propios
    puntuacion_media = Column(Float, default=0.0)
    total_votos = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    letras = relationship("Letra", back_populates="video")
    votos = relationship("Voto", back_populates="video")

    def to_dict(self, include_letras=False):
        d = {
            "id": self.id,
            "youtube_id": self.youtube_id,
            "titulo": self.titulo,
            "thumbnail": self.thumbnail,
            "duracion": self.duracion,
            "año": self.año,
            "fase": self.fase,
            "modalidad": self.modalidad,
            "tipo": self.tipo,
            "grupo_nombre": self.grupo_nombre,
            "tiene_letra": self.tiene_letra,
            "puntuacion_media": self.puntuacion_media,
            "total_votos": self.total_votos,
            "odysee_url": self.odysee_url,
        }
        if include_letras:
            d["letras"] = [l.to_dict() for l in self.letras]
        return d


class Letra(Base):
    """Letra de una pieza del Carnaval (de Carnaval-Letras o manual)."""
    __tablename__ = "letras"

    id = Column(Integer, primary_key=True)
    titulo = Column(String(300))
    tipo_pieza = Column(String(50))    # presentacion, pasodoble, cuple, estribillo, popurri, romance
    contenido = Column(Text, nullable=False)
    fuente = Column(String(200))       # URL origen
    año = Column(Integer, index=True)
    grupo_nombre = Column(String(200))

    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=True)

    video = relationship("Video", back_populates="letras")
    grupo = relationship("Grupo", back_populates="letras")

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "tipo_pieza": self.tipo_pieza,
            "contenido": self.contenido,
            "año": self.año,
            "grupo_nombre": self.grupo_nombre,
        }


class Voto(Base):
    """Valoración de un vídeo por parte de un usuario (por IP anonimizada)."""
    __tablename__ = "votos"
    __table_args__ = (UniqueConstraint("video_id", "ip_hash", name="uq_voto_ip"),)

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    ip_hash = Column(String(64), nullable=False)
    valor = Column(Integer, nullable=False)     # 1-5

    video = relationship("Video", back_populates="votos")
    created_at = Column(DateTime, default=datetime.utcnow)


class MensajeChat(Base):
    """Historial del chat 24/7."""
    __tablename__ = "mensajes_chat"

    id = Column(Integer, primary_key=True)
    usuario = Column(String(100), default="Anónimo")        # nombre visible (denormalizado)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)  # null = anónimo
    contenido = Column(Text, nullable=False)
    tipo = Column(String(20), default="user")   # user, bot, sistema
    sala = Column(String(50), default="general")
    created_at = Column(DateTime, default=datetime.utcnow)

    usuario_obj = relationship("Usuario", back_populates="mensajes", foreign_keys=[usuario_id])

    def to_dict(self):
        d = {
            "id": self.id,
            "usuario": self.usuario,
            "contenido": self.contenido,
            "tipo": self.tipo,
            "sala": self.sala,
            "hora": self.created_at.strftime("%H:%M"),
        }
        if self.usuario_obj:
            d["avatar_color"] = self.usuario_obj.avatar_color
            d["avatar_emoji"] = self.usuario_obj.avatar_emoji
        return d


class EstadoLive(Base):
    """Estado del canal Live 24/7 (singleton — siempre id=1)."""
    __tablename__ = "estado_live"

    id = Column(Integer, primary_key=True, default=1)
    youtube_id = Column(String(20))
    titulo = Column(String(500))
    duracion = Column(Integer, default=0)       # segundos
    started_at = Column(DateTime, default=datetime.utcnow)
    canal_fuente = Column(String(200), default="ONDACADIZCARNAVAL")

    def segundos_transcurridos(self) -> int:
        if not self.started_at or not self.duracion:
            return 0
        elapsed = int((datetime.utcnow() - self.started_at).total_seconds())
        return min(elapsed, self.duracion - 1)

    def to_dict(self):
        return {
            "youtube_id": self.youtube_id,
            "titulo": self.titulo,
            "duracion": self.duracion,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "segundos_transcurridos": self.segundos_transcurridos(),
            "canal_fuente": self.canal_fuente,
        }


class ConfigSistema(Base):
    """Par clave-valor para configuración dinámica desde admin."""
    __tablename__ = "config_sistema"

    id = Column(Integer, primary_key=True)
    clave = Column(String(100), unique=True, nullable=False)
    valor = Column(Text)
    descripcion = Column(String(300))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
