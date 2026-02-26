"""
Importador de letras desde la API de Carnaval-Letras.
Fuente: https://g3v3r.pythonanywhere.com/api/letras

Estrategia:
  - Fase 1 (rápida, ~6 min): importa metadata de todas las letras
    paginando el endpoint /api/letras. No descarga el contenido (texto).
  - Contenido bajo demanda: cuando el usuario visualiza una letra, si
    no tiene contenido en la DB local, se fetchea de /api/letra/<id>
    y se cachea para la próxima vez.
"""

import time
import threading
import requests
from backend.database import SessionLocal
from backend.models import Letra

BASE_URL = "https://g3v3r.pythonanywhere.com"
LIST_ENDPOINT = f"{BASE_URL}/api/letras"
DETAIL_ENDPOINT = f"{BASE_URL}/api/letra"

# ── Estado global de la importación (accedido por el endpoint de progreso) ───
_estado = {
    "activo": False,
    "fase": "",
    "importadas": 0,
    "actualizadas": 0,
    "omitidas": 0,
    "total": 0,
    "errores": 0,
    "pagina_actual": 0,
    "total_paginas": 0,
    "mensaje": "",
}
_lock = threading.Lock()


def get_estado() -> dict:
    with _lock:
        return dict(_estado)


def _set(**kwargs):
    with _lock:
        _estado.update(kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 1 — Importar metadata de todas las letras
# ─────────────────────────────────────────────────────────────────────────────

def importar_metadata(
    anio: int = None,
    modalidad: str = None,
    calidad_min: int = 0,
    limite: int = 20000,
    delay: float = 0.05,
):
    """
    Importa metadata (sin contenido) de las letras disponibles en la API.
    Ejecutar en un hilo separado.
    """
    _set(
        activo=True,
        fase="metadata",
        importadas=0,
        actualizadas=0,
        omitidas=0,
        total=0,
        errores=0,
        pagina_actual=0,
        total_paginas=0,
        mensaje="Conectando con Carnaval-Letras API...",
    )

    session = requests.Session()
    session.headers["User-Agent"] = "Carnavalix-Importer/1.0"
    db = SessionLocal()

    try:
        page = 1
        per_page = 50

        while _estado["activo"]:
            params = {"page": page, "per_page": per_page}
            if anio:
                params["anio"] = anio
            if modalidad:
                params["modalidad"] = modalidad

            try:
                resp = session.get(LIST_ENDPOINT, params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                _set(errores=_estado["errores"] + 1, mensaje=f"Error en página {page}: {e}")
                time.sleep(2)
                continue

            letras_api = data.get("letras", [])
            if not letras_api:
                break

            # Actualizar totales en el estado
            if page == 1:
                total_api = min(data.get("total", 0), limite)
                total_pag = data.get("total_pages", 1)
                _set(total=total_api, total_paginas=total_pag)

            _set(
                pagina_actual=page,
                mensaje=f"Importando página {page}/{_estado['total_paginas']}...",
            )

            for item in letras_api:
                if item.get("calidad", 0) < calidad_min:
                    _set(omitidas=_estado["omitidas"] + 1)
                    continue

                fuente_url = f"{DETAIL_ENDPOINT}/{item['id']}"

                # ¿Ya existe esta letra?
                existente = db.query(Letra).filter(Letra.fuente == fuente_url).first()
                if existente:
                    _set(omitidas=_estado["omitidas"] + 1)
                    continue

                letra = Letra(
                    titulo=item.get("titulo") or "",
                    tipo_pieza=item.get("tipo_pieza") or "",
                    contenido="",           # Se descarga bajo demanda
                    fuente=fuente_url,       # URL para obtener el contenido después
                    año=item.get("anio"),
                    grupo_nombre=item.get("agrupacion") or "",
                )
                db.add(letra)
                _set(importadas=_estado["importadas"] + 1)

                if _estado["importadas"] >= limite:
                    db.commit()
                    _set(activo=False, mensaje=f"Límite alcanzado: {limite} letras importadas.")
                    return

            db.commit()

            if page >= data.get("total_pages", 1):
                break

            page += 1
            time.sleep(delay)

        _set(
            activo=False,
            mensaje=(
                f"✅ Importación completada: {_estado['importadas']} nuevas, "
                f"{_estado['omitidas']} omitidas, {_estado['errores']} errores."
            ),
        )

    except Exception as e:
        _set(activo=False, errores=_estado["errores"] + 1, mensaje=f"Error fatal: {e}")
        db.rollback()
    finally:
        db.close()
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# BAJO DEMANDA — Obtener contenido de una letra concreta
# ─────────────────────────────────────────────────────────────────────────────

def obtener_contenido_api(letra_id_local: int) -> str:
    """
    Descarga el contenido de una letra desde la API y lo cachea en la DB.
    Se llama cuando el usuario visualiza una letra cuyo contenido está vacío.
    """
    db = SessionLocal()
    try:
        letra = db.query(Letra).filter(Letra.id == letra_id_local).first()
        if not letra:
            return ""

        # Si ya tiene contenido, devolver directamente
        if letra.contenido and len(letra.contenido) > 10:
            return letra.contenido

        if not letra.fuente or not letra.fuente.startswith("http"):
            return ""

        try:
            resp = requests.get(letra.fuente, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            contenido = data.get("contenido") or data.get("texto") or ""

            if contenido:
                letra.contenido = contenido
                # También actualizar otros campos si están vacíos
                if not letra.titulo and data.get("titulo"):
                    letra.titulo = data["titulo"]
                if not letra.tipo_pieza and data.get("tipo_pieza"):
                    letra.tipo_pieza = data["tipo_pieza"]
                db.commit()

            return contenido
        except Exception as e:
            print(f"[Importer] Error obteniendo contenido de {letra.fuente}: {e}")
            return ""
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# ENRIQUECIMIENTO — Descargar contenido en lote (opcional, proceso largo)
# ─────────────────────────────────────────────────────────────────────────────

def enriquecer_contenido(limite: int = 500, delay: float = 0.2):
    """
    Descarga el contenido de las primeras N letras que aún no lo tienen.
    Ejecutar en hilo separado. Proceso lento pero se puede ir haciendo poco a poco.
    """
    _set(
        activo=True,
        fase="enriquecimiento",
        importadas=0,
        total=0,
        mensaje="Enriqueciendo letras con contenido...",
    )

    db = SessionLocal()
    try:
        sin_contenido = (
            db.query(Letra)
            .filter(
                (Letra.contenido == "") | (Letra.contenido.is_(None)),
                Letra.fuente.isnot(None),
                Letra.fuente.like("http%"),
            )
            .limit(limite)
            .all()
        )
        _set(total=len(sin_contenido))

        for i, letra in enumerate(sin_contenido):
            if not _estado["activo"]:
                break
            try:
                resp = requests.get(letra.fuente, timeout=15)
                data = resp.json()
                contenido = data.get("contenido") or data.get("texto") or ""
                if contenido:
                    letra.contenido = contenido
                    if not letra.titulo and data.get("titulo"):
                        letra.titulo = data["titulo"]
                    db.commit()
                    _set(importadas=_estado["importadas"] + 1)
            except Exception:
                _set(errores=_estado["errores"] + 1)

            _set(mensaje=f"Enriqueciendo {i + 1}/{len(sin_contenido)}...")
            time.sleep(delay)

        _set(
            activo=False,
            mensaje=f"✅ Enriquecimiento completo: {_estado['importadas']} letras con contenido.",
        )
    except Exception as e:
        _set(activo=False, mensaje=f"Error: {e}")
        db.rollback()
    finally:
        db.close()
