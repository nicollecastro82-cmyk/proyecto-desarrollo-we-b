from flask import Blueprint, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from api_utils import ApiError, bool_value, json_body, query_bool, text_value
from extensions import db
from models import Categoria


categorias_bp = Blueprint("categorias", __name__, url_prefix="/api/categorias")


def find_category_or_404(category_id):
    category = db.session.get(Categoria, category_id)
    if category is None:
        raise ApiError("Categoría no encontrada.", 404, "CATEGORY_NOT_FOUND")
    return category


def ensure_unique_name(name, exclude_id=None):
    query = db.select(Categoria).where(func.lower(Categoria.nombre) == name.lower())
    if exclude_id is not None:
        query = query.where(Categoria.id_categoria != exclude_id)
    if db.session.scalar(query) is not None:
        raise ApiError(
            "Ya existe una categoría con ese nombre.",
            409,
            "CATEGORY_NAME_EXISTS",
        )


@categorias_bp.get("")
def list_categories():
    include_inactive = query_bool("incluir_inactivas", False)
    search = request.args.get("q", "").strip()
    query = db.select(Categoria).order_by(Categoria.id_categoria)

    if not include_inactive:
        query = query.where(Categoria.activo.is_(True))
    if search:
        query = query.where(Categoria.nombre.ilike(f"%{search}%"))

    categories = db.session.scalars(query).all()
    return jsonify({"datos": [category.to_dict() for category in categories]})


@categorias_bp.get("/<int:category_id>")
def get_category(category_id):
    return jsonify({"datos": find_category_or_404(category_id).to_dict()})


@categorias_bp.post("")
def create_category():
    data = json_body({"nombre", "activo"}, {"nombre"})
    name = text_value(data.get("nombre"), "nombre", 80)
    active = bool_value(data.get("activo", True), "activo")
    ensure_unique_name(name)

    category = Categoria(nombre=name, activo=active)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "Ya existe una categoría con ese nombre.",
            409,
            "CATEGORY_NAME_EXISTS",
        ) from error

    return jsonify({"datos": category.to_dict()}), 201


def update_category(category_id, partial):
    category = find_category_or_404(category_id)
    required = set() if partial else {"nombre", "activo"}
    data = json_body({"nombre", "activo"}, required)
    if partial and not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")

    if "nombre" in data:
        name = text_value(data["nombre"], "nombre", 80)
        ensure_unique_name(name, category.id_categoria)
        category.nombre = name
    if "activo" in data:
        category.activo = bool_value(data["activo"], "activo")

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "Ya existe una categoría con ese nombre.",
            409,
            "CATEGORY_NAME_EXISTS",
        ) from error
    return jsonify({"datos": category.to_dict()})


@categorias_bp.put("/<int:category_id>")
def replace_category(category_id):
    return update_category(category_id, partial=False)


@categorias_bp.patch("/<int:category_id>")
def patch_category(category_id):
    return update_category(category_id, partial=True)


@categorias_bp.patch("/<int:category_id>/estado")
def change_category_status(category_id):
    category = find_category_or_404(category_id)
    data = json_body({"activo"}, {"activo"})
    category.activo = bool_value(data["activo"], "activo")
    db.session.commit()
    return jsonify({"datos": category.to_dict()})


@categorias_bp.delete("/<int:category_id>")
def deactivate_category(category_id):
    category = find_category_or_404(category_id)
    category.activo = False
    db.session.commit()
    return jsonify(
        {
            "mensaje": "Categoría desactivada correctamente.",
            "datos": category.to_dict(),
        }
    )
