from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from api_utils import ApiError, json_body, positive_int, text_value
from extensions import db
from models import Entrega, EstadoEntrega, Usuario
from shared_dependencies import require_order


entregas_bp = Blueprint("entregas", __name__, url_prefix="/api/entregas")

TRANSITIONS = {
    EstadoEntrega.PENDIENTE_ASIGNACION: {EstadoEntrega.ASIGNADA},
    EstadoEntrega.ASIGNADA: {EstadoEntrega.RECOGIDA, EstadoEntrega.CON_INCIDENCIA},
    EstadoEntrega.RECOGIDA: {EstadoEntrega.EN_CAMINO, EstadoEntrega.CON_INCIDENCIA},
    EstadoEntrega.EN_CAMINO: {EstadoEntrega.ENTREGADA, EstadoEntrega.CON_INCIDENCIA},
    EstadoEntrega.ENTREGADA: set(),
    EstadoEntrega.CON_INCIDENCIA: {EstadoEntrega.ASIGNADA},
}


def find_delivery_or_404(delivery_id):
    delivery = db.session.get(Entrega, delivery_id)
    if delivery is None:
        raise ApiError("Entrega no encontrada.", 404, "DELIVERY_NOT_FOUND")
    return delivery


def parse_delivery_state(value):
    if not isinstance(value, str):
        raise ApiError("El estado de entrega no es válido.", 400, "VALIDATION_ERROR")
    try:
        return EstadoEntrega(value.strip().upper())
    except ValueError as error:
        raise ApiError(
            "El estado de entrega no es válido.",
            400,
            "VALIDATION_ERROR",
            {"valores_permitidos": [state.value for state in EstadoEntrega]},
        ) from error


def validate_courier(user_id):
    user_id = positive_int(user_id, "id_domiciliario")
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise ApiError("Domiciliario no encontrado.", 404, "COURIER_NOT_FOUND")
    if not user.activo:
        raise ApiError("El domiciliario está inactivo.", 409, "COURIER_INACTIVE")
    if user.tipo_usuario.descripcion != "DOMICILIARIO":
        raise ApiError(
            "El usuario seleccionado no tiene rol DOMICILIARIO.",
            422,
            "USER_IS_NOT_COURIER",
        )
    return user


def validate_delivery_order(order_id):
    order = require_order(order_id, {"tipo"})
    if order["tipo"].upper() != "DOMICILIO":
        raise ApiError(
            "Solo los pedidos de tipo DOMICILIO pueden tener entrega.",
            422,
            "ORDER_IS_NOT_DELIVERY",
        )
    return order


@entregas_bp.get("")
def list_deliveries():
    state = request.args.get("estado")
    courier_id = request.args.get("id_domiciliario", type=int)
    order_id = request.args.get("id_pedido", type=int)
    query = db.select(Entrega).order_by(Entrega.id_entrega)
    if state:
        query = query.where(Entrega.estado == parse_delivery_state(state))
    if courier_id:
        query = query.where(Entrega.id_domiciliario == courier_id)
    if order_id:
        query = query.where(Entrega.id_pedido == order_id)
    deliveries = db.session.scalars(query).all()
    return jsonify({"datos": [delivery.to_dict() for delivery in deliveries]})


@entregas_bp.get("/<int:delivery_id>")
def get_delivery(delivery_id):
    return jsonify({"datos": find_delivery_or_404(delivery_id).to_dict()})


@entregas_bp.post("")
def create_delivery():
    data = json_body(
        {
            "id_pedido",
            "id_domiciliario",
            "direccion_entrega",
            "telefono_contacto",
            "observacion",
        },
        {"id_pedido", "direccion_entrega", "telefono_contacto"},
    )
    order_id = positive_int(data["id_pedido"], "id_pedido")
    validate_delivery_order(order_id)
    courier_id = data.get("id_domiciliario")
    if courier_id is not None:
        validate_courier(courier_id)
    address = text_value(data["direccion_entrega"], "direccion_entrega", 250)
    phone = text_value(data["telefono_contacto"], "telefono_contacto", 20)
    observation = text_value(
        data.get("observacion"), "observacion", 500, required=False
    )

    existing = db.session.scalar(db.select(Entrega).where(Entrega.id_pedido == order_id))
    if existing:
        raise ApiError("El pedido ya tiene una entrega registrada.", 409, "ORDER_DELIVERY_EXISTS")

    delivery = Entrega(
        id_pedido=order_id,
        id_domiciliario=courier_id,
        direccion_entrega=address,
        telefono_contacto=phone,
        observacion=observation,
        estado=(
            EstadoEntrega.ASIGNADA
            if courier_id is not None
            else EstadoEntrega.PENDIENTE_ASIGNACION
        ),
        fecha_asignacion=datetime.now() if courier_id is not None else None,
    )
    db.session.add(delivery)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "El pedido ya tiene una entrega registrada.",
            409,
            "ORDER_DELIVERY_EXISTS",
        ) from error
    return jsonify({"datos": delivery.to_dict()}), 201


def update_delivery(delivery_id, partial):
    delivery = find_delivery_or_404(delivery_id)
    if delivery.estado == EstadoEntrega.ENTREGADA:
        raise ApiError(
            "Una entrega finalizada no puede modificarse.", 409, "DELIVERY_ALREADY_FINAL"
        )
    fields = {"id_domiciliario", "direccion_entrega", "telefono_contacto", "observacion"}
    required = set() if partial else {"direccion_entrega", "telefono_contacto"}
    data = json_body(fields, required)
    if partial and not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")

    if "direccion_entrega" in data:
        delivery.direccion_entrega = text_value(
            data["direccion_entrega"], "direccion_entrega", 250
        )
    if "telefono_contacto" in data:
        delivery.telefono_contacto = text_value(
            data["telefono_contacto"], "telefono_contacto", 20
        )
    if "observacion" in data:
        delivery.observacion = text_value(
            data["observacion"], "observacion", 500, required=False
        )
    if "id_domiciliario" in data:
        validate_courier(data["id_domiciliario"])
        delivery.id_domiciliario = data["id_domiciliario"]
        if delivery.estado in {
            EstadoEntrega.PENDIENTE_ASIGNACION,
            EstadoEntrega.CON_INCIDENCIA,
        }:
            delivery.estado = EstadoEntrega.ASIGNADA
            delivery.fecha_asignacion = datetime.now()

    db.session.commit()
    return jsonify({"datos": delivery.to_dict()})


@entregas_bp.put("/<int:delivery_id>")
def replace_delivery(delivery_id):
    return update_delivery(delivery_id, partial=False)


@entregas_bp.patch("/<int:delivery_id>")
def patch_delivery(delivery_id):
    return update_delivery(delivery_id, partial=True)


@entregas_bp.patch("/<int:delivery_id>/estado")
def change_delivery_status(delivery_id):
    delivery = find_delivery_or_404(delivery_id)
    data = json_body({"estado", "observacion", "id_domiciliario"}, {"estado"})
    new_state = parse_delivery_state(data["estado"])
    if new_state not in TRANSITIONS[delivery.estado]:
        raise ApiError(
            f"No se permite pasar de {delivery.estado.value} a {new_state.value}.",
            409,
            "INVALID_DELIVERY_TRANSITION",
        )

    if "id_domiciliario" in data:
        validate_courier(data["id_domiciliario"])
        delivery.id_domiciliario = data["id_domiciliario"]
    if new_state == EstadoEntrega.ASIGNADA and delivery.id_domiciliario is None:
        raise ApiError(
            "Para asignar la entrega debes indicar id_domiciliario.",
            400,
            "COURIER_REQUIRED",
        )
    if "observacion" in data:
        delivery.observacion = text_value(
            data["observacion"], "observacion", 500, required=False
        )
    if new_state == EstadoEntrega.CON_INCIDENCIA and not delivery.observacion:
        raise ApiError(
            "Una incidencia requiere una observación.",
            400,
            "INCIDENT_OBSERVATION_REQUIRED",
        )

    delivery.estado = new_state
    now = datetime.now()
    if new_state == EstadoEntrega.ASIGNADA:
        delivery.fecha_asignacion = now
    elif new_state == EstadoEntrega.RECOGIDA:
        delivery.fecha_recogida = now
    elif new_state == EstadoEntrega.ENTREGADA:
        delivery.fecha_entrega = now
    db.session.commit()
    return jsonify({"datos": delivery.to_dict()})


@entregas_bp.delete("/<int:delivery_id>")
def delete_delivery(delivery_id):
    delivery = find_delivery_or_404(delivery_id)
    if delivery.estado != EstadoEntrega.PENDIENTE_ASIGNACION:
        raise ApiError(
            "Solo una entrega pendiente de asignación puede eliminarse.",
            409,
            "DELIVERY_CANNOT_BE_DELETED",
        )
    db.session.delete(delivery)
    db.session.commit()
    return jsonify({"mensaje": "Entrega pendiente eliminada correctamente."})
