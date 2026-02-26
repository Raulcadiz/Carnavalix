import re
from flask import Blueprint, jsonify, request, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
from backend.database import SessionLocal
from backend.models import Usuario

bp = Blueprint("auth", __name__)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{3,30}$")


# ─── Páginas ──────────────────────────────────────────────────────────────────

@bp.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth/login.html")


@bp.route("/registro")
def registro_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth/registro.html")


@bp.route("/perfil")
@login_required
def perfil_page():
    return render_template("auth/perfil.html", usuario=current_user)


# ─── API ──────────────────────────────────────────────────────────────────────

@bp.route("/api/auth/registro", methods=["POST"])
def api_registro():
    data = request.json or {}
    username = (data.get("username") or "").strip().lower()
    password = (data.get("password") or "").strip()
    display_name = (data.get("display_name") or username).strip()[:80]
    avatar_emoji = (data.get("avatar_emoji") or "🎭")[:4]
    avatar_color = (data.get("avatar_color") or "#d4a843")[:7]

    # Validaciones
    if not _USERNAME_RE.match(username):
        return jsonify({"error": "Usuario: 3-30 caracteres, solo letras, números, _ - ."}), 400
    if len(password) < 6:
        return jsonify({"error": "Contraseña mínima 6 caracteres"}), 400

    db = SessionLocal()
    try:
        if db.query(Usuario).filter(Usuario.username == username).first():
            return jsonify({"error": "Ese nombre de usuario ya está en uso"}), 409

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        usuario = Usuario(
            username=username,
            password_hash=pw_hash,
            display_name=display_name,
            avatar_emoji=avatar_emoji,
            avatar_color=avatar_color,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        login_user(usuario, remember=True)
        return jsonify({"ok": True, "usuario": usuario.to_dict()})
    finally:
        db.close()


@bp.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = (data.get("username") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Usuario y contraseña requeridos"}), 400

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(
            Usuario.username == username,
            Usuario.activo == True  # noqa: E712
        ).first()

        if not usuario or not bcrypt.checkpw(password.encode(), usuario.password_hash.encode()):
            return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

        from datetime import datetime
        usuario.last_seen = datetime.utcnow()
        db.commit()

        login_user(usuario, remember=data.get("recordar", True))
        return jsonify({"ok": True, "usuario": usuario.to_dict()})
    finally:
        db.close()


@bp.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})


@bp.route("/api/auth/yo", methods=["GET"])
def api_yo():
    """Devuelve el usuario actual si está autenticado."""
    if current_user.is_authenticated:
        return jsonify({"autenticado": True, "usuario": current_user.to_dict()})
    return jsonify({"autenticado": False})


@bp.route("/api/auth/perfil", methods=["PATCH"])
@login_required
def api_actualizar_perfil():
    """Actualiza display_name, avatar_emoji, avatar_color."""
    data = request.json or {}
    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()
        if not usuario:
            return jsonify({"error": "No encontrado"}), 404

        if "display_name" in data:
            usuario.display_name = (data["display_name"] or "").strip()[:80]
        if "avatar_emoji" in data:
            usuario.avatar_emoji = (data["avatar_emoji"] or "🎭")[:4]
        if "avatar_color" in data:
            color = data["avatar_color"]
            if re.match(r"^#[0-9a-fA-F]{6}$", color):
                usuario.avatar_color = color

        db.commit()
        return jsonify({"ok": True, "usuario": usuario.to_dict()})
    finally:
        db.close()
