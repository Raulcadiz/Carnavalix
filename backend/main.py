from flask import Flask
from flask_socketio import SocketIO
from flask_login import LoginManager
from backend.config import config
from backend.database import init_db

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
login_manager = LoginManager()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
    )
    app.secret_key = config.SECRET_KEY

    # Inicializar base de datos
    init_db()

    # Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "Debes iniciar sesión para acceder."

    @login_manager.user_loader
    def load_user(user_id):
        from backend.database import SessionLocal
        from backend.models import Usuario
        db = SessionLocal()
        try:
            return db.query(Usuario).get(int(user_id))
        finally:
            db.close()

    # Registrar blueprints
    from backend.routes.videos import bp as videos_bp
    from backend.routes.letras import bp as letras_bp
    from backend.routes.votos import bp as votos_bp
    from backend.routes.chat import bp as chat_bp
    from backend.routes.admin import bp as admin_bp
    from backend.routes.auth import bp as auth_bp
    from backend.routes.live import bp as live_bp
    from backend.routes.audio import bp as audio_bp

    app.register_blueprint(videos_bp, url_prefix="/api/videos")
    app.register_blueprint(letras_bp, url_prefix="/api/letras")
    app.register_blueprint(votos_bp, url_prefix="/api/votos")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(audio_bp, url_prefix="/api/audio")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="")   # /login, /registro, /api/auth/*
    app.register_blueprint(live_bp, url_prefix="/live")

    # Rutas principales
    from flask import render_template

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/player/<youtube_id>")
    def player(youtube_id):
        return render_template("player.html", youtube_id=youtube_id)

    @app.route("/chat")
    def chat():
        return render_template("chat.html")

    @app.route("/audios")
    def audios():
        return render_template("audios.html")

    # SocketIO
    socketio.init_app(app)
    from backend.routes import chat as chat_events  # noqa: F401

    # Monitor del canal Live 24/7
    from backend.services.live_service import iniciar_monitor
    iniciar_monitor()

    # Scheduler de tareas (scraping automático)
    if not config.DEBUG:
        from backend.services.scheduler import start_scheduler
        start_scheduler()

    return app


if __name__ == "__main__":
    app = create_app()
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False,
    )
