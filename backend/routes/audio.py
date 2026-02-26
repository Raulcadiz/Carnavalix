"""
backend/routes/audio.py
Escanea data/audio/{modalidad}/{grupo}/*.mp3 y sirve los archivos.
"""
import re
from pathlib import Path
from urllib.parse import quote

from flask import Blueprint, jsonify, send_from_directory, current_app, abort

bp = Blueprint("audio", __name__)

_AUDIO_SUBDIR = Path("data") / "audio"
# Elimina prefijo "01 - 01.- " o "01 - 01 - " del nombre de archivo
_PREFIX_RE = re.compile(r"^\d+\s*[-–]\s*\d+[.\-]*\s*")

ICONOS_MODALIDAD = {
    "chirigotas": "🎭",
    "comparsas":  "🎺",
    "coros":      "🎵",
    "cuartetos":  "🎤",
    "romanceros":  "📜",
}


def _audio_dir() -> Path:
    """Ruta absoluta a data/audio/ relativa al paquete backend."""
    return Path(current_app.root_path).parent / _AUDIO_SUBDIR


def _limpiar_titulo(nombre: str) -> str:
    """'01 - 02.- Presentación.mp3' → 'Presentación'"""
    stem = Path(nombre).stem
    return _PREFIX_RE.sub("", stem).strip()


# ── API: listado ──────────────────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
def listar_audio():
    """
    Devuelve estructura completa de data/audio/ como JSON:
    [
      {
        "modalidad": "chirigotas",
        "icono": "🎭",
        "grupos": [
          {
            "nombre": "Los Yesterday - Juan Carlos Aragón",
            "slug_url": "chirigotas/Los%20Yesterday...",
            "tracks": [
              { "titulo": "Presentación", "url": "/api/audio/file/..." }
            ]
          }
        ]
      }
    ]
    """
    base = _audio_dir()
    if not base.exists():
        return jsonify([])

    resultado = []

    for mod_dir in sorted(base.iterdir()):
        if not mod_dir.is_dir():
            continue

        modalidad = mod_dir.name
        icono = ICONOS_MODALIDAD.get(modalidad, "🎵")
        grupos = []

        for grupo_dir in sorted(mod_dir.iterdir()):
            if not grupo_dir.is_dir():
                continue

            tracks = []
            for f in sorted(grupo_dir.iterdir()):
                if f.suffix.lower() != ".mp3":
                    continue
                # URL con codificación para caracteres especiales
                url = "/api/audio/file/{}/{}/{}".format(
                    quote(modalidad, safe=""),
                    quote(grupo_dir.name, safe=""),
                    quote(f.name, safe=""),
                )
                tracks.append({
                    "titulo": _limpiar_titulo(f.name),
                    "url":    url,
                })

            if tracks:
                grupos.append({
                    "nombre":  grupo_dir.name,
                    "tracks":  tracks,
                })

        if grupos:
            resultado.append({
                "modalidad": modalidad,
                "icono":     icono,
                "grupos":    grupos,
            })

    return jsonify(resultado)


# ── Servicio de archivos MP3 ──────────────────────────────────────────────────

@bp.route("/file/<modalidad>/<grupo>/<archivo>", methods=["GET"])
def servir_audio(modalidad, grupo, archivo):
    """
    Sirve el MP3 con send_from_directory.
    Flask decodifica automáticamente la URL antes de pasarla al handler.
    send_from_directory protege contra path traversal.
    """
    grupo_dir = _audio_dir() / modalidad / grupo
    if not grupo_dir.is_dir():
        abort(404)
    return send_from_directory(
        str(grupo_dir),
        archivo,
        mimetype="audio/mpeg",
        conditional=True,   # soporta Range requests (seek en el player)
    )
