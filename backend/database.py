from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import config


engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite
    echo=config.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency para obtener sesión de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea todas las tablas si no existen."""
    from backend import models  # noqa: F401 — importar para registrar modelos
    Base.metadata.create_all(bind=engine)
    _enable_fts(engine)
    print("[DB] Base de datos inicializada correctamente.")


def _enable_fts(eng):
    """Crea índice FTS5 para búsqueda de texto completo en vídeos y letras."""
    with eng.connect() as conn:
        # FTS para vídeos
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts
            USING fts5(titulo, descripcion, grupo_nombre, content='videos', content_rowid='id')
        """))
        # FTS para letras
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS letras_fts
            USING fts5(titulo, contenido, grupo_nombre, content='letras', content_rowid='id')
        """))
        conn.commit()
