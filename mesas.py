import enum

from sqlalchemy.exc import SQLAlchemyError

from extensions import db


class EstadoMesa(str, enum.Enum):
    LIBRE = "LIBRE"
    OCUPADA = "OCUPADA"
    FUERA_DE_SERVICIO = "FUERA_DE_SERVICIO"


ESTADOS_VALIDOS = tuple(estado.value for estado in EstadoMesa)


class Mesa(db.Model):
    __tablename__ = "mesa"

    id_mesa = db.Column(db.Integer, primary_key=True)
    numero_mesa = db.Column(db.Integer, nullable=False, unique=True)
    estado = db.Column(
        db.Enum(EstadoMesa, name="estado_mesa"),
        nullable=False,
        default=EstadoMesa.LIBRE,
        server_default=EstadoMesa.LIBRE.value,
    )


def normalizar_estado(estado):
    if not isinstance(estado, str):
        return None
    try:
        return EstadoMesa(estado.strip().upper())
    except ValueError:
        return None


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
    except SQLAlchemyError:
        db.session.rollback()
        return None, "No fue posible guardar la mesa."
    return mesa, None


def listar_mesas(estado=None):
    estado_normalizado = None
    if estado is not None:
        estado_normalizado = normalizar_estado(estado)
        if estado_normalizado is None:
            return None, f"El estado debe ser uno de: {', '.join(ESTADOS_VALIDOS)}."

    consulta = db.select(Mesa).order_by(Mesa.numero_mesa)
    if estado_normalizado is not None:
        consulta = consulta.where(Mesa.estado == estado_normalizado)
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
    except SQLAlchemyError:
        db.session.rollback()
        return None, "No fue posible actualizar la mesa."
    return mesa, None


def cambiar_estado(id_mesa, nuevo_estado):
    mesa, error = consultar_mesa(id_mesa)
    if error:
        return None, error

    estado_normalizado = normalizar_estado(nuevo_estado)
    if estado_normalizado is None:
        return None, f"El estado debe ser uno de: {', '.join(ESTADOS_VALIDOS)}."
    if mesa.estado == estado_normalizado:
        return None, f"La mesa {mesa.numero_mesa} ya está {estado_normalizado.value}."

    mesa.estado = estado_normalizado
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, "No fue posible cambiar el estado."
    return mesa, None


def ocupar_mesa(id_mesa):
    return cambiar_estado(id_mesa, EstadoMesa.OCUPADA.value)


def liberar_mesa(id_mesa):
    return cambiar_estado(id_mesa, EstadoMesa.LIBRE.value)
