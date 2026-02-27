"""
Servicio de scraping de YouTube para contenido COAC.

Estrategia de dos niveles:
  1. YouTube Data API v3 (10.000 unidades/dia gratuitas)
  2. yt-dlp como fallback cuando la cuota se agota o no hay API key
"""
import re
import sys
import subprocess
import json
from datetime import datetime
from typing import Optional

# Invocar yt-dlp a través del intérprete activo para evitar problemas de PATH en Windows
_YTDLP = [sys.executable, "-m", "yt_dlp"]
_YTDLP_PLAYER = [
    "--extractor-args", "youtube:player_client=android,web",
    # User-Agent de Android para evitar deteccion anti-bot en el servidor
    "--user-agent",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
]

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _API_DISPONIBLE = True
except ImportError:
    _API_DISPONIBLE = False

from backend.config import config
from backend.database import SessionLocal
from backend.models import Video, Grupo

# ---------------------------------------------------------------------------
# Constantes / expresiones regulares
# ---------------------------------------------------------------------------

_RE_YEAR = re.compile(r"\b(20\d{2}|199\d)\b")
_RE_CHANNEL_URL = re.compile(
    r"youtube\.com/(?:@([^/\s?]+)|channel/(UC[^/\s?]+)|c/([^/\s?]+)|user/([^/\s?]+))"
)

_MODALIDAD_KW = {
    "chirigota": "chirigota",
    "comparsa": "comparsa",
    "coro": "coro",
    "cuarteto": "cuarteto",
    "romancero": "romancero",
}

_FASE_KW = {
    "final": "final",
    "semifinal": "semifinal",
    "cuartos": "cuartos",
    "preliminar": "preliminar",
    "callejera": "callejera",
    "calle": "callejera",
}

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _build_client():
    """Construye el cliente de YouTube Data API v3."""
    if not _API_DISPONIBLE:
        raise ImportError("google-api-python-client no instalado")
    if not config.YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY no configurada en .env")
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def _parse_duration(iso_duration: str) -> int:
    """Convierte duracion ISO 8601 (PT1H2M3S) a segundos."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0
    h, m, s = (int(g or 0) for g in match.groups())
    return h * 3600 + m * 60 + s


def _inferir_metadatos(titulo: str, descripcion: str = "") -> dict:
    """Infiere anno, modalidad y fase a partir del titulo/descripcion."""
    texto = (titulo + " " + descripcion).lower()

    annos = _RE_YEAR.findall(texto)
    anno = int(annos[0]) if annos else None

    modalidad = None
    for kw, val in _MODALIDAD_KW.items():
        if kw in texto:
            modalidad = val
            break

    fase = None
    tipo = "coac"
    for kw, val in _FASE_KW.items():
        if kw in texto:
            fase = val
            if val == "callejera":
                tipo = "callejera"
            break

    return {"anno": anno, "modalidad": modalidad, "fase": fase, "tipo": tipo}


def _ytdlp_disponible() -> bool:
    """Comprueba si yt-dlp esta disponible en el entorno Python actual."""
    try:
        result = subprocess.run(
            _YTDLP + ["--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Funciones publicas de extraccion de metadatos
# ---------------------------------------------------------------------------

def extraer_channel_id_de_url(url: str) -> Optional[str]:
    """
    Extrae el identificador de canal de una URL de YouTube.

    Soporta formatos:
      - youtube.com/@NombreCanal
      - youtube.com/channel/UCxxxxxxxx
      - youtube.com/c/NombreCanal
      - youtube.com/user/NombreCanal

    Devuelve el identificador crudo (ej. "@NombreCanal" o "UCxxxxxxxx").
    """
    match = _RE_CHANNEL_URL.search(url)
    if not match:
        return None
    handle, channel_id, custom, user = match.groups()
    if channel_id:
        return channel_id           # UCxxxxxxxx  (ID directo)
    if handle:
        return f"@{handle}"         # @NombreCanal
    if custom:
        return custom               # c/NombreCanal -> devuelve NombreCanal
    if user:
        return user                 # user/NombreCanal -> devuelve NombreCanal
    return None


def obtener_metadata_video(youtube_id: str) -> Optional[dict]:
    """Obtiene metadatos de un unico video via YouTube Data API v3."""
    try:
        yt = _build_client()
        resp = yt.videos().list(
            part="snippet,contentDetails,statistics",
            id=youtube_id,
        ).execute()

        items = resp.get("items", [])
        if not items:
            return None

        item = items[0]
        snippet = item["snippet"]
        details = item.get("contentDetails", {})
        stats = item.get("statistics", {})

        fecha_str = snippet.get("publishedAt", "")
        fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")) if fecha_str else None

        return {
            "titulo": snippet.get("title", ""),
            "descripcion": snippet.get("description", "")[:1000],
            "thumbnail": (
                snippet.get("thumbnails", {}).get("maxres")
                or snippet.get("thumbnails", {}).get("high")
                or {}
            ).get("url", ""),
            "duracion": _parse_duration(details.get("duration", "")),
            "vistas": int(stats.get("viewCount", 0)),
            "fecha_publicacion": fecha,
            "canal": snippet.get("channelTitle", ""),
            "canal_id": snippet.get("channelId", ""),
        }
    except Exception as e:
        print(f"[YouTube API] Error obteniendo metadata de {youtube_id}: {e}")
        return None


def metadatos_ytdlp(youtube_id: str) -> Optional[dict]:
    """
    Obtiene metadatos de un video usando yt-dlp, sin consumir cuota de API.
    Util cuando la cuota esta agotada o no hay API key.
    """
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    try:
        result = subprocess.run(
            _YTDLP + _YTDLP_PLAYER + [
                "--dump-json",
                "--no-playlist",
                "--skip-download",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"[yt-dlp] Error para {youtube_id}: {result.stderr[:200]}")
            return None

        data = json.loads(result.stdout)

        # Normalizar thumbnail: preferir la de mayor resolucion
        thumbnails = data.get("thumbnails", [])
        thumbnail_url = ""
        if thumbnails:
            best = max(thumbnails, key=lambda t: t.get("preference", 0))
            thumbnail_url = best.get("url", "")
        if not thumbnail_url:
            thumbnail_url = data.get("thumbnail", "")

        # Fecha de publicacion
        upload_date = data.get("upload_date", "")   # YYYYMMDD
        fecha = None
        if upload_date and len(upload_date) == 8:
            try:
                fecha = datetime.strptime(upload_date, "%Y%m%d")
            except ValueError:
                pass

        return {
            "titulo": data.get("title", ""),
            "descripcion": (data.get("description") or "")[:1000],
            "thumbnail": thumbnail_url,
            "duracion": int(data.get("duration") or 0),
            "vistas": int(data.get("view_count") or 0),
            "fecha_publicacion": fecha,
            "canal": data.get("channel", data.get("uploader", "")),
            "canal_id": data.get("channel_id", ""),
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[yt-dlp] Excepcion para {youtube_id}: {e}")
        return None


def _obtener_mejor_metadata(youtube_id: str, forzar_ytdlp: bool = False) -> Optional[dict]:
    """
    Intenta obtener metadata via API; si falla o forzar_ytdlp=True usa yt-dlp.
    """
    if not forzar_ytdlp:
        data = obtener_metadata_video(youtube_id)
        if data:
            return data
    # Fallback a yt-dlp
    return metadatos_ytdlp(youtube_id)


# ---------------------------------------------------------------------------
# Busqueda de videos
# ---------------------------------------------------------------------------

def _buscar_videos_api(query: str, max_results: int = 50) -> list:
    """Busca videos via YouTube Data API v3."""
    try:
        yt = _build_client()
        resp = yt.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=min(max_results, 50),
        ).execute()

        resultados = []
        for item in resp.get("items", []):
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id:
                continue
            snippet = item.get("snippet", {})
            resultados.append({
                "youtube_id": vid_id,
                "titulo": snippet.get("title", ""),
                "descripcion": snippet.get("description", "")[:500],
                "thumbnail": (snippet.get("thumbnails", {}).get("high") or {}).get("url", ""),
                "canal": snippet.get("channelTitle", ""),
                "canal_id": snippet.get("channelId", ""),
            })
        return resultados
    except Exception as e:
        print(f"[YouTube API] Error en busqueda {query!r}: {e}")
        return []


def _buscar_videos_ytdlp(query: str, max_results: int = 20) -> list:
    """Busca videos en YouTube usando yt-dlp (ytsearch)."""
    try:
        result = subprocess.run(
            _YTDLP + _YTDLP_PLAYER + [
                f"ytsearch{max_results}:{query}",
                "--dump-json",
                "--no-playlist",
                "--skip-download",
                "--flat-playlist",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"[yt-dlp] Error busqueda {query!r}: {result.stderr[:200]}")
            return []

        resultados = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            vid_id = data.get("id", "") or data.get("youtube_id", "")
            if not vid_id:
                continue

            thumbnails = data.get("thumbnails", [])
            thumbnail_url = ""
            if thumbnails:
                best = max(thumbnails, key=lambda t: t.get("preference", 0))
                thumbnail_url = best.get("url", "")
            if not thumbnail_url:
                thumbnail_url = data.get("thumbnail", "")

            resultados.append({
                "youtube_id": vid_id,
                "titulo": data.get("title", ""),
                "descripcion": (data.get("description") or "")[:500],
                "thumbnail": thumbnail_url,
                "canal": data.get("channel", data.get("uploader", "")),
                "canal_id": data.get("channel_id", ""),
            })
        return resultados
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[yt-dlp] Excepcion en busqueda {query!r}: {e}")
        return []


def buscar_videos(
    query: str,
    max_results: int = 50,
    forzar_ytdlp: bool = False,
) -> list:
    """
    Busca videos en YouTube.

    Intenta primero con la YouTube Data API v3; si no hay clave configurada,
    la cuota esta agotada o forzar_ytdlp=True, usa yt-dlp como fallback.

    Args:
        query: Termino de busqueda.
        max_results: Numero maximo de resultados (hasta 50 via API).
        forzar_ytdlp: Si True, omite la API y va directamente a yt-dlp.

    Returns:
        Lista de dicts con youtube_id, titulo, descripcion, thumbnail, canal.
    """
    if not forzar_ytdlp and config.YOUTUBE_API_KEY:
        resultados = _buscar_videos_api(query, max_results)
        if resultados:
            return resultados
        print("[Scraper] API sin resultados o cuota agotada, usando yt-dlp...")

    # Fallback
    return _buscar_videos_ytdlp(query, min(max_results, 50))


# ---------------------------------------------------------------------------
# Scraping de canal completo
# ---------------------------------------------------------------------------

def scrapear_canal_coac(channel_url: str, max_videos: int = 200) -> dict:
    """
    Scracea todos los videos de un canal de YouTube.

    Soporta URLs tipo:
      - https://www.youtube.com/@COAC_Cadiz
      - https://www.youtube.com/channel/UCxxxxxxxx
      - https://www.youtube.com/c/NombreCanal

    Guarda los videos en DB y devuelve un resumen con nuevos/existentes/errores.
    """
    print(f"[Canal] Scrapeando canal: {channel_url}")
    db = SessionLocal()
    nuevos = 0
    existentes = 0
    errores = 0

    try:
        result = subprocess.run(
            _YTDLP + _YTDLP_PLAYER + [
                channel_url,
                "--dump-json",
                "--flat-playlist",
                "--skip-download",
                "--yes-playlist",
                "--playlist-end", str(max_videos),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"[Canal] yt-dlp error: {result.stderr[:300]}")
            return {"nuevos": 0, "existentes": 0, "errores": 1, "canal": channel_url}

        ids_canal = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                vid_id = data.get("id") or data.get("youtube_id")
                if vid_id:
                    ids_canal.append(vid_id)
            except json.JSONDecodeError:
                continue

        print(f"[Canal] Encontrados {len(ids_canal)} videos en el canal")

        for vid_id in ids_canal:
            existente = db.query(Video).filter(Video.youtube_id == vid_id).first()
            if existente:
                existentes += 1
                continue

            meta_raw = metadatos_ytdlp(vid_id)
            if not meta_raw:
                errores += 1
                continue

            meta = _inferir_metadatos(meta_raw["titulo"], meta_raw["descripcion"])

            video = Video(
                youtube_id=vid_id,
                titulo=meta_raw["titulo"],
                descripcion=meta_raw["descripcion"],
                thumbnail=meta_raw["thumbnail"],
                duracion=meta_raw["duracion"],
                vistas=meta_raw["vistas"],
                fecha_publicacion=meta_raw["fecha_publicacion"],
                año=meta["anno"],
                fase=meta["fase"],
                modalidad=meta["modalidad"],
                tipo=meta["tipo"],
                grupo_nombre=meta_raw["canal"],
            )
            db.add(video)
            nuevos += 1

            if nuevos % 20 == 0:
                db.commit()
                print(f"[Canal] Guardados {nuevos} nuevos videos...")

        db.commit()
        resumen = {
            "nuevos": nuevos,
            "existentes": existentes,
            "errores": errores,
            "canal": channel_url,
        }
        print(f"[Canal] Finalizado: {resumen}")
        return resumen

    except Exception as e:
        print(f"[Canal] Error inesperado: {e}")
        db.rollback()
        return {
            "nuevos": nuevos,
            "existentes": existentes,
            "errores": errores + 1,
            "canal": channel_url,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Proceso principal de scraping COAC
# ---------------------------------------------------------------------------

def scrapear_coac(
    annos: list = None,
    modalidades: list = None,
    forzar_ytdlp: bool = False,
) -> dict:
    """
    Proceso principal: busca videos COAC en YouTube y los guarda en DB.

    Estrategia:
      - Usa YouTube Data API v3 si hay clave configurada y forzar_ytdlp=False.
      - Cae a yt-dlp si la cuota se agota o forzar_ytdlp=True.
      - Para cada video encontrado, obtiene metadata completa y la guarda.

    Args:
        annos: Lista de annos a buscar (defecto: config.YEARS_RANGE).
        modalidades: Filtrar por modalidades especificas (None = todas).
        forzar_ytdlp: Si True, usa yt-dlp en lugar de la API.

    Returns:
        Dict con estadisticas: nuevos, existentes, errores, queries_usadas.
    """
    annos = annos or getattr(
        config, "YEARS_RANGE", list(range(2010, datetime.now().year + 1))
    )
    queries_usadas = 0
    nuevos = 0
    existentes = 0
    errores = 0
    db = SessionLocal()

    templates = getattr(
        config,
        "YOUTUBE_SEARCH_QUERIES",
        [
            "carnaval cadiz {year} coac",
            "carnaval cadiz {year} chirigota",
            "carnaval cadiz {year} comparsa",
            "carnaval cadiz {year} coro",
            "carnaval cadiz {year} cuarteto",
        ],
    )

    try:
        for anno in annos:
            for template in templates:
                query = template.format(year=anno)
                print(f"[Scraper] Buscando: {query}")

                resultados = buscar_videos(query, max_results=25, forzar_ytdlp=forzar_ytdlp)
                queries_usadas += 1

                for r in resultados:
                    existente_db = db.query(Video).filter(
                        Video.youtube_id == r["youtube_id"]
                    ).first()
                    if existente_db:
                        existentes += 1
                        continue

                    meta = _inferir_metadatos(r["titulo"], r["descripcion"])

                    if modalidades and meta["modalidad"] not in modalidades:
                        continue

                    detalles = _obtener_mejor_metadata(r["youtube_id"], forzar_ytdlp)
                    queries_usadas += 1

                    if not detalles:
                        errores += 1
                        continue

                    video = Video(
                        youtube_id=r["youtube_id"],
                        titulo=r["titulo"],
                        descripcion=r["descripcion"],
                        thumbnail=detalles.get("thumbnail") or r["thumbnail"],
                        duracion=detalles.get("duracion", 0),
                        vistas=detalles.get("vistas", 0),
                        fecha_publicacion=detalles.get("fecha_publicacion"),
                        año=meta["anno"] or anno,
                        fase=meta["fase"],
                        modalidad=meta["modalidad"],
                        tipo=meta["tipo"],
                        grupo_nombre=r.get("canal", ""),
                    )
                    db.add(video)
                    nuevos += 1

                db.commit()

                # Control de cuota de API (~100 unidades por search)
                if not forzar_ytdlp and queries_usadas >= 80:
                    print(
                        f"[Scraper] Cuota casi agotada ({queries_usadas} queries). "
                        "Cambiando a yt-dlp..."
                    )
                    forzar_ytdlp = True

        resumen = {
            "nuevos": nuevos,
            "existentes": existentes,
            "errores": errores,
            "queries_usadas": queries_usadas,
        }
        print(f"[Scraper] Finalizado: {resumen}")
        return resumen

    except Exception as e:
        print(f"[Scraper] Error inesperado: {e}")
        db.rollback()
        return {
            "nuevos": nuevos,
            "existentes": existentes,
            "errores": errores + 1,
            "queries_usadas": queries_usadas,
        }
    finally:
        db.close()
