from sqlalchemy import func

from app import app, create_app
from extensions import db
from models import Categoria


def validar_nombre(nombre):
    if not nombre:
        return "El nombre de la categoría es obligatorio."
    if len(nombre) > 80:
        return "El nombre no puede superar los 80 caracteres."
    return None


def nombre_duplicado(nombre, excluir_id=None):
    consulta = db.select(Categoria).where(func.lower(Categoria.nombre) == nombre.lower())
    if excluir_id is not None:
        consulta = consulta.where(Categoria.id_categoria != excluir_id)
    return db.session.scalar(consulta) is not None
