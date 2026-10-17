import re

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from api_utils import (
    ApiError,
    bool_value,
    json_body,
    positive_int,
    query_bool,
    text_value,
)
from extensions import db
from models import TipoUsuario, Usuario


usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SYSTEM_ROLES = {"ADMINISTRADOR", "COCINA", "MESERO", "CLIENTE", "DOMICILIARIO"}


def find_role_or_404(role_id):
    role = db.session.get(TipoUsuario, role_id)
    if role is None:
        raise ApiError("Tipo de usuario no encontrado.", 404, "ROLE_NOT_FOUND")
    return role


def find_user_or_404(user_id):
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise ApiError("Usuario no encontrado.", 404, "USER_NOT_FOUND")
    return user


def normalized_email(value):
    email = text_value(value, "correo", 120, required=False)
    if email is None:
        return None
    email = email.lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ApiError("El correo no tiene un formato válido.", 400, "VALIDATION_ERROR")
    return email


def password_hash(value):
    if not isinstance(value, str) or len(value) < 8:
        raise ApiError(
            "La contraseña debe tener al menos 8 caracteres.",
            400,
            "VALIDATION_ERROR",
        )
    if len(value) > 128:
        raise ApiError(
            "La contraseña no puede superar 128 caracteres.",
            400,
            "VALIDATION_ERROR",
        )
    return generate_password_hash(value)


def ensure_unique_user(login, email, exclude_id=None):
    login_query = db.select(Usuario).where(func.lower(Usuario.usuario_login) == login.lower())
    if exclude_id is not None:
        login_query = login_query.where(Usuario.id_usuario != exclude_id)
    if db.session.scalar(login_query) is not None:
        raise ApiError("El usuario de acceso ya existe.", 409, "LOGIN_EXISTS")

    if email:
        email_query = db.select(Usuario).where(func.lower(Usuario.correo) == email.lower())
        if exclude_id is not None:
            email_query = email_query.where(Usuario.id_usuario != exclude_id)
        if db.session.scalar(email_query) is not None:
            raise ApiError("El correo ya está registrado.", 409, "EMAIL_EXISTS")


@usuarios_bp.get("/tipos-usuario")
def list_roles():
    roles = db.session.scalars(
        db.select(TipoUsuario).order_by(TipoUsuario.id_tipo_usuario)
    ).all()
    return jsonify({"datos": [role.to_dict() for role in roles]})


@usuarios_bp.get("/tipos-usuario/<int:role_id>")
def get_role(role_id):
    return jsonify({"datos": find_role_or_404(role_id).to_dict()})


@usuarios_bp.post("/tipos-usuario")
def create_role():
    data = json_body({"descripcion"}, {"descripcion"})
    description = text_value(data["descripcion"], "descripcion", 50).upper()
    existing = db.session.scalar(
        db.select(TipoUsuario).where(func.lower(TipoUsuario.descripcion) == description.lower())
    )
    if existing:
        raise ApiError("El tipo de usuario ya existe.", 409, "ROLE_EXISTS")

    role = TipoUsuario(descripcion=description)
    db.session.add(role)
    db.session.commit()
    return jsonify({"datos": role.to_dict()}), 201


def update_role(role_id):
    role = find_role_or_404(role_id)
    if role.descripcion in SYSTEM_ROLES:
        raise ApiError(
            "Los roles base del sistema no pueden renombrarse.",
            409,
            "SYSTEM_ROLE_IMMUTABLE",
        )
    data = json_body({"descripcion"}, {"descripcion"})
    description = text_value(data["descripcion"], "descripcion", 50).upper()
    duplicate = db.session.scalar(
        db.select(TipoUsuario).where(
            func.lower(TipoUsuario.descripcion) == description.lower(),
            TipoUsuario.id_tipo_usuario != role.id_tipo_usuario,
        )
    )
    if duplicate:
        raise ApiError("El tipo de usuario ya existe.", 409, "ROLE_EXISTS")

    role.descripcion = description
    db.session.commit()
    return jsonify({"datos": role.to_dict()})


@usuarios_bp.put("/tipos-usuario/<int:role_id>")
@usuarios_bp.patch("/tipos-usuario/<int:role_id>")
def change_role(role_id):
    return update_role(role_id)


@usuarios_bp.delete("/tipos-usuario/<int:role_id>")
def delete_role(role_id):
    role = find_role_or_404(role_id)
    if role.descripcion in SYSTEM_ROLES:
        raise ApiError(
            "Los roles base del sistema no pueden eliminarse.",
            409,
            "SYSTEM_ROLE_IMMUTABLE",
        )
    assigned = db.session.scalar(
        db.select(func.count(Usuario.id_usuario)).where(Usuario.id_tipo_usuario == role.id_tipo_usuario)
    )
    if assigned:
        raise ApiError(
            "No se puede eliminar un tipo de usuario que tiene usuarios asignados.",
            409,
            "ROLE_IN_USE",
        )
    db.session.delete(role)
    db.session.commit()
    return jsonify({"mensaje": "Tipo de usuario eliminado correctamente."})


@usuarios_bp.get("/usuarios")
def list_users():
    include_inactive = query_bool("incluir_inactivos", False)
    search = request.args.get("q", "").strip()
    role_id = request.args.get("id_tipo_usuario", type=int)
    query = db.select(Usuario).order_by(Usuario.id_usuario)

    if not include_inactive:
        query = query.where(Usuario.activo.is_(True))
    if role_id:
        query = query.where(Usuario.id_tipo_usuario == role_id)
    if search:
        query = query.where(
            or_(
                Usuario.nombre.ilike(f"%{search}%"),
                Usuario.usuario_login.ilike(f"%{search}%"),
                Usuario.correo.ilike(f"%{search}%"),
            )
        )

    users = db.session.scalars(query).unique().all()
    return jsonify({"datos": [user.to_dict() for user in users]})


@usuarios_bp.get("/usuarios/<int:user_id>")
def get_user(user_id):
    return jsonify({"datos": find_user_or_404(user_id).to_dict()})


@usuarios_bp.post("/usuarios")
def create_user():
    data = json_body(
        {
            "id_tipo_usuario",
            "nombre",
            "usuario_login",
            "contrasena",
            "correo",
            "telefono",
            "activo",
        },
        {"id_tipo_usuario", "nombre", "usuario_login", "contrasena"},
    )
    role_id = positive_int(data["id_tipo_usuario"], "id_tipo_usuario")
    find_role_or_404(role_id)
    name = text_value(data["nombre"], "nombre", 120)
    login = text_value(data["usuario_login"], "usuario_login", 80).lower()
    email = normalized_email(data.get("correo"))
    phone = text_value(data.get("telefono"), "telefono", 20, required=False)
    active = bool_value(data.get("activo", True), "activo")
    ensure_unique_user(login, email)

    user = Usuario(
        id_tipo_usuario=role_id,
        nombre=name,
        usuario_login=login,
        contrasena_hash=password_hash(data["contrasena"]),
        correo=email,
        telefono=phone,
        activo=active,
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "El usuario o correo ya está registrado.", 409, "USER_EXISTS"
        ) from error
    return jsonify({"datos": user.to_dict()}), 201


def update_user(user_id, partial):
    user = find_user_or_404(user_id)
    allowed = {
        "id_tipo_usuario",
        "nombre",
        "usuario_login",
        "contrasena",
        "correo",
        "telefono",
        "activo",
    }
    required = set() if partial else {
        "id_tipo_usuario",
        "nombre",
        "usuario_login",
        "activo",
    }
    data = json_body(allowed, required)
    if partial and not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")

    role_id = user.id_tipo_usuario
    name = user.nombre
    login = user.usuario_login
    email = user.correo
    phone = user.telefono
    active = user.activo

    if "id_tipo_usuario" in data:
        role_id = positive_int(data["id_tipo_usuario"], "id_tipo_usuario")
        find_role_or_404(role_id)
    if "nombre" in data:
        name = text_value(data["nombre"], "nombre", 120)
    if "usuario_login" in data:
        login = text_value(data["usuario_login"], "usuario_login", 80).lower()
    if "correo" in data:
        email = normalized_email(data["correo"])
    if "telefono" in data:
        phone = text_value(data["telefono"], "telefono", 20, required=False)
    if "activo" in data:
        active = bool_value(data["activo"], "activo")

    ensure_unique_user(login, email, user.id_usuario)
    user.id_tipo_usuario = role_id
    user.nombre = name
    user.usuario_login = login
    user.correo = email
    user.telefono = phone
    user.activo = active
    if "contrasena" in data:
        user.contrasena_hash = password_hash(data["contrasena"])

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "El usuario o correo ya está registrado.", 409, "USER_EXISTS"
        ) from error
    return jsonify({"datos": user.to_dict()})


@usuarios_bp.put("/usuarios/<int:user_id>")
def replace_user(user_id):
    return update_user(user_id, partial=False)


@usuarios_bp.patch("/usuarios/<int:user_id>")
def patch_user(user_id):
    return update_user(user_id, partial=True)


@usuarios_bp.patch("/usuarios/<int:user_id>/estado")
def change_user_status(user_id):
    user = find_user_or_404(user_id)
    data = json_body({"activo"}, {"activo"})
    user.activo = bool_value(data["activo"], "activo")
    db.session.commit()
    return jsonify({"datos": user.to_dict()})


@usuarios_bp.delete("/usuarios/<int:user_id>")
def deactivate_user(user_id):
    user = find_user_or_404(user_id)
    user.activo = False
    db.session.commit()
    return jsonify(
        {"mensaje": "Usuario desactivado correctamente.", "datos": user.to_dict()}
    )


@usuarios_bp.post("/auth/login")
def login():
    data = json_body({"usuario_login", "contrasena"}, {"usuario_login", "contrasena"})
    login_value = text_value(data["usuario_login"], "usuario_login", 80).lower()
    user = db.session.scalar(
        db.select(Usuario).where(func.lower(Usuario.usuario_login) == login_value)
    )
    if user is None or not check_password_hash(user.contrasena_hash, data["contrasena"]):
        raise ApiError("Credenciales inválidas.", 401, "INVALID_CREDENTIALS")
    if not user.activo:
        raise ApiError("El usuario está inactivo.", 403, "USER_INACTIVE")
    return jsonify({"mensaje": "Credenciales válidas.", "datos": user.to_dict()})
