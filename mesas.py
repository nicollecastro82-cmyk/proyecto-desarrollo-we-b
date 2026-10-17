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


def listar_mesas(estado=None):
    if estado is not None and estado not in ESTADOS_VALIDOS:
        return None, f"El estado debe ser uno de: {', '.join(ESTADOS_VALIDOS)}."

    consulta = db.select(Mesa).order_by(Mesa.numero_mesa)
    if estado is not None:
        consulta = consulta.where(Mesa.estado == estado)
    return db.session.scalars(consulta).all(), None


def consultar_mesa(id_mesa):
    mesa = db.session.get(Mesa, id_mesa)
    if mesa is None:
        return None, f"No existe una mesa con id {id_mesa}."
    return mesa, None


def actualizar_mesa(id_mesa, nuevo_numero):
    mesa, error = consultar_mesa(id_mesa)
    if error:
        return None, error

    error = validar_numero(nuevo_numero)
    if error:
        return None, error
    if numero_duplicado(nuevo_numero, excluir_id=id_mesa):
        return None, f"Ya existe la mesa {nuevo_numero}."

    mesa.numero_mesa = nuevo_numero
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return None, f"No fue posible actualizar la mesa. Detalle: {e}"
    return mesa, None


def cambiar_estado(id_mesa, nuevo_estado):
    mesa, error = consultar_mesa(id_mesa)
    if error:
        return None, error
    if mesa.estado == nuevo_estado:
        return None, f"La mesa {mesa.numero_mesa} ya está {nuevo_estado}."

    mesa.estado = nuevo_estado
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return None, f"No fue posible cambiar el estado. Detalle: {e}"
    return mesa, None


def ocupar_mesa(id_mesa):
    return cambiar_estado(id_mesa, "ocupada")


def liberar_mesa(id_mesa):
    return cambiar_estado(id_mesa, "libre")