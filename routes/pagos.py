from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from api_utils import ApiError, json_body, positive_int, text_value
from extensions import db
from models import EstadoPago, MetodoPago, Pago, Usuario
from shared_dependencies import require_order


pagos_bp = Blueprint("pagos", __name__, url_prefix="/api/pagos")


def find_payment_or_404(payment_id):
    payment = db.session.get(Pago, payment_id)
    if payment is None:
        raise ApiError("Pago no encontrado.", 404, "PAYMENT_NOT_FOUND")
    return payment


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


def parse_amount(value):
    if isinstance(value, bool):
        raise ApiError("El valor del pago debe ser positivo.", 400, "VALIDATION_ERROR")
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as error:
        raise ApiError(
            "El valor del pago debe ser numérico.", 400, "VALIDATION_ERROR"
        ) from error
    if amount <= 0 or amount > Decimal("9999999999.99"):
        raise ApiError("El valor del pago debe ser positivo.", 400, "VALIDATION_ERROR")
    return amount


def validate_confirmer(user_id):
    user_id = positive_int(user_id, "id_usuario_confirma")
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise ApiError("Usuario confirmador no encontrado.", 404, "USER_NOT_FOUND")
    if not user.activo:
        raise ApiError("El usuario confirmador está inactivo.", 409, "USER_INACTIVE")
    if user.tipo_usuario.descripcion == "CLIENTE":
        raise ApiError(
            "Un cliente no puede confirmar pagos.", 422, "USER_CANNOT_CONFIRM_PAYMENT"
        )
    return user


def validate_payment_reference(method, state, reference):
    if method == MetodoPago.PSE and state == EstadoPago.APROBADO and not reference:
        raise ApiError(
            "Un pago PSE aprobado requiere referencia de transacción.",
            400,
            "PAYMENT_REFERENCE_REQUIRED",
        )


@pagos_bp.get("")
def list_payments():
    state = request.args.get("estado")
    order_id = request.args.get("id_pedido", type=int)
    query = db.select(Pago).order_by(Pago.id_pago)
    if state:
        query = query.where(Pago.estado == parse_enum(state, EstadoPago, "estado"))
    if order_id:
        query = query.where(Pago.id_pedido == order_id)
    payments = db.session.scalars(query).all()
    return jsonify({"datos": [payment.to_dict() for payment in payments]})


@pagos_bp.get("/<int:payment_id>")
def get_payment(payment_id):
    return jsonify({"datos": find_payment_or_404(payment_id).to_dict()})


@pagos_bp.post("")
def create_payment():
    data = json_body(
        {"id_pedido", "metodo", "valor", "referencia_transaccion"},
        {"id_pedido", "metodo", "valor"},
    )
    order_id = positive_int(data["id_pedido"], "id_pedido")
    require_order(order_id)
    method = parse_enum(data["metodo"], MetodoPago, "metodo")
    amount = parse_amount(data["valor"])
    reference = text_value(
        data.get("referencia_transaccion"),
        "referencia_transaccion",
        150,
        required=False,
    )

    existing = db.session.scalar(db.select(Pago).where(Pago.id_pedido == order_id))
    if existing:
        raise ApiError("El pedido ya tiene un pago registrado.", 409, "ORDER_PAYMENT_EXISTS")

    payment = Pago(
        id_pedido=order_id,
        metodo=method,
        estado=EstadoPago.PENDIENTE,
        valor=amount,
        referencia_transaccion=reference,
    )
    db.session.add(payment)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "El pedido o la referencia ya tienen un pago registrado.",
            409,
            "PAYMENT_EXISTS",
        ) from error
    return jsonify({"datos": payment.to_dict()}), 201


def update_payment(payment_id, partial):
    payment = find_payment_or_404(payment_id)
    if payment.estado != EstadoPago.PENDIENTE:
        raise ApiError(
            "Un pago finalizado no puede modificarse.", 409, "PAYMENT_ALREADY_FINAL"
        )
    allowed = {"metodo", "valor", "referencia_transaccion"}
    required = set() if partial else {"metodo", "valor"}
    data = json_body(allowed, required)
    if partial and not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")

    if "metodo" in data:
        payment.metodo = parse_enum(data["metodo"], MetodoPago, "metodo")
    if "valor" in data:
        payment.valor = parse_amount(data["valor"])
    if "referencia_transaccion" in data:
        payment.referencia_transaccion = text_value(
            data["referencia_transaccion"],
            "referencia_transaccion",
            150,
            required=False,
        )
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "La referencia de transacción ya está registrada.",
            409,
            "PAYMENT_REFERENCE_EXISTS",
        ) from error
    return jsonify({"datos": payment.to_dict()})


@pagos_bp.put("/<int:payment_id>")
def replace_payment(payment_id):
    return update_payment(payment_id, partial=False)


@pagos_bp.patch("/<int:payment_id>")
def patch_payment(payment_id):
    return update_payment(payment_id, partial=True)


@pagos_bp.patch("/<int:payment_id>/estado")
def change_payment_status(payment_id):
    payment = find_payment_or_404(payment_id)
    if payment.estado != EstadoPago.PENDIENTE:
        raise ApiError(
            "Un pago finalizado no puede cambiar nuevamente de estado.",
            409,
            "PAYMENT_ALREADY_FINAL",
        )
    data = json_body(
        {"estado", "id_usuario_confirma", "referencia_transaccion"}, {"estado"}
    )
    new_state = parse_enum(data["estado"], EstadoPago, "estado")
    if new_state == EstadoPago.PENDIENTE:
        raise ApiError(
            "El pago ya se encuentra pendiente.", 400, "INVALID_PAYMENT_TRANSITION"
        )

    confirmer_id = data.get("id_usuario_confirma")
    if new_state == EstadoPago.APROBADO and confirmer_id is None:
        raise ApiError(
            "Para aprobar el pago debes indicar id_usuario_confirma.",
            400,
            "PAYMENT_CONFIRMER_REQUIRED",
        )
    if confirmer_id is not None:
        validate_confirmer(confirmer_id)
        payment.id_usuario_confirma = confirmer_id
    if "referencia_transaccion" in data:
        payment.referencia_transaccion = text_value(
            data["referencia_transaccion"],
            "referencia_transaccion",
            150,
            required=False,
        )

    validate_payment_reference(payment.metodo, new_state, payment.referencia_transaccion)
    payment.estado = new_state
    payment.fecha_pago = datetime.now() if new_state == EstadoPago.APROBADO else None
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "La referencia de transacción ya está registrada.",
            409,
            "PAYMENT_REFERENCE_EXISTS",
        ) from error
    return jsonify({"datos": payment.to_dict()})


@pagos_bp.delete("/<int:payment_id>")
def delete_payment(payment_id):
    payment = find_payment_or_404(payment_id)
    if payment.estado != EstadoPago.PENDIENTE:
        raise ApiError(
            "Los pagos aprobados o rechazados se conservan para auditoría.",
            409,
            "PAYMENT_CANNOT_BE_DELETED",
        )
    db.session.delete(payment)
    db.session.commit()
    return jsonify({"mensaje": "Pago pendiente eliminado correctamente."})
