from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from categorias import app, db

ESTADOS_VALIDOS = ("libre", "ocupada")


class Mesa(db.Model):
    __tablename__ = "mesa"

    id_mesa = db.Column(db.Integer, primary_key=True)
    numero_mesa = db.Column(db.Integer, nullable=False, unique=True)
    estado = db.Column(db.String(20), nullable=False, default="libre", server_default="libre")


def validar_numero(numero):
    if numero is None:
        return "El número de la mesa es obligatorio."
    if numero <= 0:
        return "El número de la mesa debe ser mayor que cero."
    return None


def numero_duplicado(numero, excluir_id=None):
    consulta = db.select(Mesa).where(Mesa.numero_mesa == numero)
    if excluir_id is not None:
        consulta = consulta.where(Mesa.id_mesa != excluir_id)
    return db.session.scalar(consulta) is not None


def crear_mesa(numero):
    error = validar_numero(numero)
    if error:
        return None, error
    if numero_duplicado(numero):
        return None, f"Ya existe la mesa {numero}."

    mesa = Mesa(numero_mesa=numero)
    db.session.add(mesa)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return None, f"No fue posible guardar la mesa. Detalle: {e}"
    return mesa, None