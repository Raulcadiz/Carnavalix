"""
Servicio de backup a Odysee (LBRY).
Sube metadatos y links de vídeos como publicaciones en Odysee.

Nota: Odysee no permite re-subir vídeos de YouTube directamente.
Este servicio crea publicaciones con el enlace a YouTube como respaldo/catálogo.
Para subir el archivo de vídeo real necesitarías descargarlo primero (yt-dlp).
"""
import requests
from backend.config import config
from backend.database import SessionLocal
from backend.models import Video


ODYSEE_API = "https://api.na-backend.odysee.com/api/v1/proxy"


class OdyseeClient:
    def __init__(self):
        self._auth_token: str = ""

    def _call(self, method: str, params: dict) -> dict:
        resp = requests.post(
            ODYSEE_API,
            json={"method": method, "params": params},
            headers={"X-Lbry-Auth-Token": self._auth_token},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def autenticar(self) -> bool:
        """Autentica con email/password y obtiene token."""
        try:
            resp = requests.post(
                "https://api.odysee.com/user/signin",
                data={
                    "email": config.ODYSEE_EMAIL,
                    "password": config.ODYSEE_PASSWORD,
                },
                timeout=15,
            )
            body = resp.json()
            # La API puede devolver {"data": null, "error": "..."} en caso de fallo
            data_section = body.get("data") or {}
            self._auth_token = data_section.get("auth_token", "")
            if not self._auth_token:
                error_msg = body.get("error", "Credenciales incorrectas o cuenta no verificada")
                print(f"[Odysee] Autenticación fallida: {error_msg}")
            return bool(self._auth_token)
        except Exception as e:
            print(f"[Odysee] Error autenticación: {e}")
            return False

    def publicar_video(self, video: Video) -> str | None:
        """
        Publica un vídeo en Odysee como publicación de texto con link de YouTube.
        Devuelve la URL de Odysee o None si falla.
        """
        if not self._auth_token:
            if not self.autenticar():
                return None

        nombre_url = (
            f"coac-{video.año or 'sin-año'}-"
            f"{(video.modalidad or 'video').replace(' ', '-')}-"
            f"{video.youtube_id}"
        ).lower()

        descripcion = f"""
# {video.titulo}

**Año:** {video.año or 'Desconocido'}
**Modalidad:** {video.modalidad or '-'}
**Fase:** {video.fase or '-'}
**Grupo:** {video.grupo_nombre or '-'}

▶️ Ver en YouTube: https://www.youtube.com/watch?v={video.youtube_id}

---
*Archivado por CarnavalPlay — Preservando el patrimonio del Carnaval de Cádiz*
        """.strip()

        try:
            result = self._call("publish", {
                "name": nombre_url,
                "title": video.titulo,
                "description": descripcion,
                "channel_name": config.ODYSEE_CHANNEL,
                "tags": ["carnaval", "cadiz", "coac", video.modalidad or "", str(video.año or "")],
                "languages": ["es"],
                "bid": "0.001",
            })

            claim = result.get("result", {}).get("outputs", [{}])[0]
            permanent_url = claim.get("permanent_url", "")
            if permanent_url:
                odysee_url = permanent_url.replace("lbry://", "https://odysee.com/")
                return odysee_url
        except Exception as e:
            print(f"[Odysee] Error publicando {video.youtube_id}: {e}")

        return None


def sincronizar_pendientes(limite: int = 20):
    """Sube a Odysee los vídeos que aún no tienen backup."""
    client = OdyseeClient()
    if not client.autenticar():
        print("[Odysee] No se pudo autenticar.")
        return

    db = SessionLocal()
    try:
        pendientes = (
            db.query(Video)
            .filter(Video.odysee_url.is_(None))
            .limit(limite)
            .all()
        )
        subidos = 0
        for video in pendientes:
            url = client.publicar_video(video)
            if url:
                video.odysee_url = url
                db.commit()
                subidos += 1
                print(f"[Odysee] Subido: {video.titulo} → {url}")

        print(f"[Odysee] Sincronización completa: {subidos}/{len(pendientes)}")
    finally:
        db.close()
