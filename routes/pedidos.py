from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from api_utils import ApiError, json_body, positive_int, text_value
from extensions import db
from mesas import EstadoMesa, Mesa
from models import (
    DetallePedido,
    Entrega,
    EstadoEntrega,
    EstadoPedido,
    HistorialEstado,
    Pedido,
    TipoPedido,
    Usuario,
)
from order_rules import (
    CANCELLATION_ROLES,
    DELIVERY_ROLES,
    EDITABLE_ORDER_STATES,
    KITCHEN_ROLES,
    ORDER_TRANSITIONS,
)
from producto import Producto


pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/api/pedidos")
cocina_bp = Blueprint("cocina", __name__, url_prefix="/api/cocina")


def parse_enum(value, enum_class, field):
    if not isinstance(value, str):
        raise ApiError(f"El campo {field} no es válido.", 400, "VALIDATION_ERROR")
    try:
        return enum_class(value.strip().upper())
    except ValueError as error:
        raise ApiError(
            f"El campo {field} no es válido.",
            400,
            "VALIDATION_ERROR",
            {"valores_permitidos": [item.value for item in enum_class]},
        ) from error


def find_order_or_404(order_id):
    order = db.session.get(Pedido, order_id)
    if order is None:
        raise ApiError("Pedido no encontrado.", 404, "ORDER_NOT_FOUND")
    return order


def find_detail_or_404(order_id, detail_id):
    detail = db.session.get(DetallePedido, detail_id)
    if detail is None or detail.id_pedido != order_id:
        raise ApiError("Detalle no encontrado.", 404, "ORDER_DETAIL_NOT_FOUND")
    return detail


def validate_user(user_id, roles=None, field="id_usuario"):
    user_id = positive_int(user_id, field)
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise ApiError("Usuario no encontrado.", 404, "USER_NOT_FOUND")
    if not user.activo:
        raise ApiError("El usuario está inactivo.", 409, "USER_INACTIVE")
    if roles and user.tipo_usuario.descripcion not in roles:
        raise ApiError(
            "El usuario no tiene el rol requerido.",
            422,
            "USER_ROLE_NOT_ALLOWED",
            {"roles_permitidos": sorted(roles)},
        )
    return user


def validate_table(table_id):
    table_id = positive_int(table_id, "id_mesa")
    table = db.session.get(Mesa, table_id)
    if table is None:
        raise ApiError("Mesa no encontrada.", 404, "TABLE_NOT_FOUND")
    return table


def validate_product(product_id):
    product_id = positive_int(product_id, "id_producto")
    product = db.session.get(Producto, product_id)
    if product is None:
        raise ApiError("Producto no encontrado.", 404, "PRODUCT_NOT_FOUND")
    if not product.activo or not product.disponible or not product.categoria.activo:
        raise ApiError(
            "El producto no está disponible para pedidos.",
            409,
            "PRODUCT_UNAVAILABLE",
        )
    return product


def validate_positive_quantity(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ApiError(
            "La cantidad debe ser un entero positivo.", 400, "VALIDATION_ERROR"
        )
    return value


def ensure_order_editable(order):
    if order.estado.value not in EDITABLE_ORDER_STATES:
        raise ApiError(
            "El pedido ya no admite modificaciones en su detalle.",
            409,
            "ORDER_NOT_EDITABLE",
        )


def add_history(order, state, user_id=None, observation=None):
    history = HistorialEstado(
        pedido=order,
        id_usuario_cambio=user_id,
        estado=state,
        observacion=observation,
    )
    db.session.add(history)
    return history


def recalculate_total(order):
    db.session.flush()
    total = db.session.scalar(
        db.select(
            func.coalesce(
                func.sum(DetallePedido.cantidad * DetallePedido.precio_unitario), 0
            )
        ).where(DetallePedido.id_pedido == order.id_pedido)
    )
    order.valor_total = Decimal(total).quantize(Decimal("0.01"))
    order.fecha_ultima_actualizacion = datetime.now()


def order_to_dict(order, include_details=False):
    data = order.to_dict()
    if include_details:
        data["detalles"] = [detail.to_dict() for detail in order.detalles]
        data["pago"] = order.pago.to_dict() if order.pago else None
        data["entrega"] = order.entrega.to_dict() if order.entrega else None
    return data


def validate_order_associations(order_type, table_id, waiter_id, client_id):
    table = None
    waiter = None
    client = None

    if order_type == TipoPedido.SALON:
        if table_id is None or waiter_id is None:
            raise ApiError(
                "Un pedido en salón requiere id_mesa e id_mesero.",
                400,
                "SALON_ORDER_DATA_REQUIRED",
            )
        table = validate_table(table_id)
        waiter = validate_user(waiter_id, {"MESERO"}, "id_mesero")
    elif table_id is not None:
        raise ApiError(
            "Solo los pedidos de SALON pueden asociarse a una mesa.",
            422,
            "TABLE_NOT_ALLOWED_FOR_ORDER_TYPE",
        )

    if waiter_id is not None and waiter is None:
        waiter = validate_user(waiter_id, {"MESERO"}, "id_mesero")
    if client_id is not None:
        client = validate_user(client_id, {"CLIENTE"}, "id_cliente")
    if order_type == TipoPedido.DOMICILIO and client is None:
        raise ApiError(
            "Un pedido a domicilio requiere id_cliente.",
            400,
            "DELIVERY_ORDER_CLIENT_REQUIRED",
        )
    return table, waiter, client


@pedidos_bp.get("")
def list_orders():
    state_text = request.args.get("estado")
    type_text = request.args.get("tipo")
    table_id = request.args.get("id_mesa", type=int)
    query = db.select(Pedido).order_by(Pedido.fecha_creacion, Pedido.id_pedido)
    if state_text:
        query = query.where(
            Pedido.estado == parse_enum(state_text, EstadoPedido, "estado")
        )
    if type_text:
        query = query.where(Pedido.tipo == parse_enum(type_text, TipoPedido, "tipo"))
    if table_id:
        query = query.where(Pedido.id_mesa == table_id)
    orders = db.session.scalars(query).unique().all()
    return jsonify({"datos": [order_to_dict(order) for order in orders]})


@pedidos_bp.get("/<int:order_id>")
def get_order(order_id):
    return jsonify({"datos": order_to_dict(find_order_or_404(order_id), True)})


@pedidos_bp.post("")
def create_order():
    data = json_body(
        {
            "tipo",
            "id_mesa",
            "id_mesero",
            "id_cliente",
            "observaciones",
            "direccion_entrega",
            "telefono_contacto",
        },
        {"tipo"},
    )
    order_type = parse_enum(data["tipo"], TipoPedido, "tipo")
    table_id = (
        positive_int(data["id_mesa"], "id_mesa") if "id_mesa" in data else None
    )
    waiter_id = (
        positive_int(data["id_mesero"], "id_mesero")
        if "id_mesero" in data
        else None
    )
    client_id = (
        positive_int(data["id_cliente"], "id_cliente")
        if "id_cliente" in data
        else None
    )
    table, _, _ = validate_order_associations(
        order_type, table_id, waiter_id, client_id
    )
    if table is not None and table.estado != EstadoMesa.LIBRE:
        raise ApiError("La mesa no está libre.", 409, "TABLE_NOT_AVAILABLE")

    observation = text_value(
        data.get("observaciones"), "observaciones", 500, required=False
    )
    address = None
    phone = None
    if order_type == TipoPedido.DOMICILIO:
        address = text_value(data.get("direccion_entrega"), "direccion_entrega", 250)
        phone = text_value(data.get("telefono_contacto"), "telefono_contacto", 20)
    elif "direccion_entrega" in data or "telefono_contacto" in data:
        raise ApiError(
            "Los datos de entrega solo aplican a pedidos DOMICILIO.",
            422,
            "DELIVERY_DATA_NOT_ALLOWED",
        )

    order = Pedido(
        id_mesa=table_id,
        id_mesero=waiter_id,
        id_cliente=client_id,
        tipo=order_type,
        estado=EstadoPedido.PENDIENTE,
        valor_total=Decimal("0.00"),
        observaciones=observation,
    )
    db.session.add(order)
    db.session.flush()
    responsible_id = waiter_id if order_type == TipoPedido.SALON else client_id
    add_history(order, EstadoPedido.PENDIENTE, responsible_id, "Pedido registrado.")

    if table is not None:
        table.estado = EstadoMesa.OCUPADA
    if order_type == TipoPedido.DOMICILIO:
        db.session.add(
            Entrega(
                pedido=order,
                direccion_entrega=address,
                telefono_contacto=phone,
                estado=EstadoEntrega.PENDIENTE_ASIGNACION,
            )
        )
    db.session.commit()
    return jsonify({"datos": order_to_dict(order, True)}), 201


def update_order_data(order_id):
    order = find_order_or_404(order_id)
    ensure_order_editable(order)
    data = json_body({"id_mesa", "id_mesero", "id_cliente", "observaciones"})
    if not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")

    table_id = order.id_mesa
    waiter_id = order.id_mesero
    client_id = order.id_cliente
    if "id_mesa" in data:
        table_id = positive_int(data["id_mesa"], "id_mesa")
    if "id_mesero" in data:
        waiter_id = positive_int(data["id_mesero"], "id_mesero")
    if "id_cliente" in data:
        client_id = positive_int(data["id_cliente"], "id_cliente")

    new_table, _, _ = validate_order_associations(
        order.tipo, table_id, waiter_id, client_id
    )
    if new_table is not None and new_table.id_mesa != order.id_mesa:
        if new_table.estado != EstadoMesa.LIBRE:
            raise ApiError("La mesa no está libre.", 409, "TABLE_NOT_AVAILABLE")
        if order.mesa is not None:
            order.mesa.estado = EstadoMesa.LIBRE
        new_table.estado = EstadoMesa.OCUPADA

    order.id_mesa = table_id
    order.id_mesero = waiter_id
    order.id_cliente = client_id
    if "observaciones" in data:
        order.observaciones = text_value(
            data["observaciones"], "observaciones", 500, required=False
        )
    order.fecha_ultima_actualizacion = datetime.now()
    db.session.commit()
    return jsonify({"datos": order_to_dict(order, True)})


@pedidos_bp.put("/<int:order_id>")
@pedidos_bp.patch("/<int:order_id>")
def update_order(order_id):
    return update_order_data(order_id)


@pedidos_bp.get("/<int:order_id>/detalles")
def list_order_details(order_id):
    order = find_order_or_404(order_id)
    return jsonify({"datos": [detail.to_dict() for detail in order.detalles]})


@pedidos_bp.post("/<int:order_id>/detalles")
def create_order_detail(order_id):
    order = find_order_or_404(order_id)
    ensure_order_editable(order)
    data = json_body(
        {"id_producto", "cantidad", "comentarios"}, {"id_producto", "cantidad"}
    )
    product = validate_product(data["id_producto"])
    quantity = validate_positive_quantity(data["cantidad"])
    comments = text_value(
        data.get("comentarios"), "comentarios", 500, required=False
    )
    duplicate = db.session.scalar(
        db.select(DetallePedido).where(
            DetallePedido.id_pedido == order.id_pedido,
            DetallePedido.id_producto == product.id_producto,
        )
    )
    if duplicate is not None:
        raise ApiError(
            "El producto ya está agregado al pedido.", 409, "ORDER_PRODUCT_EXISTS"
        )

    detail = DetallePedido(
        pedido=order,
        producto=product,
        cantidad=quantity,
        precio_unitario=product.precio,
        comentarios=comments,
    )
    db.session.add(detail)
    try:
        recalculate_total(order)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "El producto ya está agregado al pedido.", 409, "ORDER_PRODUCT_EXISTS"
        ) from error
    return jsonify({"datos": detail.to_dict(), "valor_total": str(order.valor_total)}), 201


def update_order_detail(order_id, detail_id, partial):
    order = find_order_or_404(order_id)
    ensure_order_editable(order)
    detail = find_detail_or_404(order_id, detail_id)
    required = set() if partial else {"cantidad"}
    data = json_body({"cantidad", "comentarios"}, required)
    if partial and not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")
    if "cantidad" in data:
        detail.cantidad = validate_positive_quantity(data["cantidad"])
    if "comentarios" in data:
        detail.comentarios = text_value(
            data["comentarios"], "comentarios", 500, required=False
        )
    recalculate_total(order)
    db.session.commit()
    return jsonify({"datos": detail.to_dict(), "valor_total": str(order.valor_total)})


@pedidos_bp.put("/<int:order_id>/detalles/<int:detail_id>")
def replace_order_detail(order_id, detail_id):
    return update_order_detail(order_id, detail_id, partial=False)


@pedidos_bp.patch("/<int:order_id>/detalles/<int:detail_id>")
def patch_order_detail(order_id, detail_id):
    return update_order_detail(order_id, detail_id, partial=True)


@pedidos_bp.delete("/<int:order_id>/detalles/<int:detail_id>")
def delete_order_detail(order_id, detail_id):
    order = find_order_or_404(order_id)
    ensure_order_editable(order)
    detail = find_detail_or_404(order_id, detail_id)
    db.session.delete(detail)
    recalculate_total(order)
    db.session.commit()
    return jsonify(
        {
            "mensaje": "Producto retirado del pedido.",
            "valor_total": str(order.valor_total),
        }
    )


def validate_transition_actor(order, new_state, user):
    role = user.tipo_usuario.descripcion
    if new_state in {EstadoPedido.EN_PREPARACION, EstadoPedido.LISTO}:
        allowed = KITCHEN_ROLES
    elif new_state == EstadoPedido.ENTREGADO:
        allowed = DELIVERY_ROLES if order.tipo == TipoPedido.DOMICILIO else {"MESERO", "ADMINISTRADOR"}
    elif new_state == EstadoPedido.CANCELADO:
        allowed = CANCELLATION_ROLES
    else:
        allowed = {"ADMINISTRADOR"}
    if role not in allowed:
        raise ApiError(
            "El rol del usuario no permite realizar este cambio de estado.",
            403,
            "ORDER_TRANSITION_FORBIDDEN",
            {"roles_permitidos": sorted(allowed)},
        )
    if role == "CLIENTE" and (
        order.id_cliente != user.id_usuario or order.estado != EstadoPedido.PENDIENTE
    ):
        raise ApiError(
            "El cliente solo puede cancelar su propio pedido mientras esté pendiente.",
            403,
            "CLIENT_CANCELLATION_FORBIDDEN",
        )
    if role == "MESERO" and order.id_mesero not in {None, user.id_usuario}:
        raise ApiError(
            "El mesero no está asignado a este pedido.",
            403,
            "WAITER_NOT_ASSIGNED",
        )


def apply_state_change(order, new_state, user, observation=None):
    allowed = ORDER_TRANSITIONS[order.estado.value]
    if new_state.value not in allowed:
        raise ApiError(
            f"No se permite pasar de {order.estado.value} a {new_state.value}.",
            409,
            "INVALID_ORDER_TRANSITION",
        )
    validate_transition_actor(order, new_state, user)
    if new_state in {EstadoPedido.EN_PREPARACION, EstadoPedido.LISTO} and not order.detalles:
        raise ApiError(
            "No se puede preparar un pedido sin productos.", 409, "ORDER_EMPTY"
        )
    if new_state == EstadoPedido.CANCELADO and not observation:
        raise ApiError(
            "La cancelación requiere una observación.",
            400,
            "CANCELLATION_REASON_REQUIRED",
        )
    if order.tipo == TipoPedido.DOMICILIO and new_state == EstadoPedido.ENTREGADO:
        if order.entrega is None or order.entrega.estado != EstadoEntrega.ENTREGADA:
            raise ApiError(
                "El domicilio debe marcarse como entregado antes de cerrar el pedido.",
                409,
                "DELIVERY_NOT_FINISHED",
            )

    order.estado = new_state
    order.fecha_ultima_actualizacion = datetime.now()
    add_history(order, new_state, user.id_usuario, observation)
    if new_state in {EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO} and order.mesa:
        order.mesa.estado = EstadoMesa.LIBRE


@pedidos_bp.patch("/<int:order_id>/estado")
def change_order_status(order_id):
    order = find_order_or_404(order_id)
    data = json_body(
        {"estado", "id_usuario_cambio", "observacion"},
        {"estado", "id_usuario_cambio"},
    )
    new_state = parse_enum(data["estado"], EstadoPedido, "estado")
    user = validate_user(data["id_usuario_cambio"], field="id_usuario_cambio")
    observation = text_value(
        data.get("observacion"), "observacion", 500, required=False
    )
    apply_state_change(order, new_state, user, observation)
    db.session.commit()
    return jsonify({"datos": order_to_dict(order, True)})


@pedidos_bp.delete("/<int:order_id>")
def cancel_order(order_id):
    order = find_order_or_404(order_id)
    data = json_body(
        {"id_usuario_cambio", "observacion"},
        {"id_usuario_cambio", "observacion"},
    )
    user = validate_user(data["id_usuario_cambio"], field="id_usuario_cambio")
    observation = text_value(data["observacion"], "observacion", 500)
    apply_state_change(order, EstadoPedido.CANCELADO, user, observation)
    db.session.commit()
    return jsonify({"mensaje": "Pedido cancelado.", "datos": order_to_dict(order)})


@pedidos_bp.patch("/<int:order_id>/domiciliario")
def assign_courier(order_id):
    order = find_order_or_404(order_id)
    if order.tipo != TipoPedido.DOMICILIO:
        raise ApiError(
            "Solo los pedidos DOMICILIO pueden asignarse.",
            422,
            "ORDER_IS_NOT_DELIVERY",
        )
    if order.estado != EstadoPedido.LISTO:
        raise ApiError(
            "El pedido debe estar LISTO antes de asignar un domiciliario.",
            409,
            "ORDER_NOT_READY",
        )
    data = json_body({"id_domiciliario"}, {"id_domiciliario"})
    courier = validate_user(
        data["id_domiciliario"], {"DOMICILIARIO"}, "id_domiciliario"
    )
    if order.entrega is None:
        raise ApiError(
            "El pedido no tiene datos de entrega.", 409, "DELIVERY_DATA_MISSING"
        )
    order.entrega.id_domiciliario = courier.id_usuario
    order.entrega.estado = EstadoEntrega.ASIGNADA
    order.entrega.fecha_asignacion = datetime.now()
    db.session.commit()
    return jsonify({"datos": order.entrega.to_dict()})


@pedidos_bp.get("/<int:order_id>/historial")
def get_order_history(order_id):
    order = find_order_or_404(order_id)
    return jsonify({"datos": [item.to_dict() for item in order.historial]})


@cocina_bp.get("/pedidos")
def list_kitchen_orders():
    state_text = request.args.get("estado")
    query = db.select(Pedido).order_by(Pedido.fecha_creacion, Pedido.id_pedido)
    if state_text:
        state = parse_enum(state_text, EstadoPedido, "estado")
        query = query.where(Pedido.estado == state)
    else:
        query = query.where(
            Pedido.estado.in_(
                [
                    EstadoPedido.PENDIENTE,
                    EstadoPedido.EN_PREPARACION,
                    EstadoPedido.LISTO,
                ]
            )
        )
    orders = db.session.scalars(query).unique().all()
    return jsonify({"datos": [order_to_dict(order, True) for order in orders]})
