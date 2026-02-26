import os
from dotenv import load_dotenv

# Ruta absoluta al .env (funciona sin importar desde dónde se ejecute el proceso)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")
load_dotenv(dotenv_path=_ENV_PATH, override=True)

class Config:
    # App
    SECRET_KEY = os.getenv("SECRET_KEY", "carnaval-cadiz-secret-2025")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # Base de datos
    BASE_DIR = _BASE_DIR
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_BASE_DIR, 'data', 'carnavalplay.db')}"
    )

    # YouTube Data API v3 — valor en .env
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    YOUTUBE_QUOTA_LIMIT = 10000  # unidades gratuitas/día

    # Odysee / LBRY — valores en .env
    ODYSEE_EMAIL = os.getenv("ODYSEE_EMAIL", "")
    ODYSEE_PASSWORD = os.getenv("ODYSEE_PASSWORD", "")
    ODYSEE_CHANNEL = os.getenv("ODYSEE_CHANNEL", "@Carnavalix")

    # Groq AI (chatbot) — valor en .env
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = "llama3-70b-8192"

    # Scheduler
    SCRAPER_INTERVAL_HOURS = int(os.getenv("SCRAPER_INTERVAL_HOURS", 24))

    # Canales de YouTube con contenido COAC (puedes ampliar)
    YOUTUBE_COAC_CHANNELS = [
        "UCXy0GByO1VqK0xrRUFPZxsA",  # Canal Sur Andalucía
        # Añadir más canales aquí
    ]

    # Términos de búsqueda para scraping COAC
    YOUTUBE_SEARCH_QUERIES = [
        "COAC {year} final carnaval cadiz",
        "COAC {year} semifinal chirigota",
        "COAC {year} comparsa final",
        "COAC {year} coro final",
        "carnaval cadiz {year} callejera",
        "chirigota {year} carnaval cadiz",
    ]

    YEARS_RANGE = list(range(2010, 2026))  # Años a scrapear

config = Config()
