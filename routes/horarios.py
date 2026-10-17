from datetime import date, time

from flask import Blueprint, jsonify, request

from api_utils import ApiError, json_body, positive_int, text_value
from extensions import db
from models import HorarioEmpleado, Usuario


horarios_bp = Blueprint("horarios", __name__, url_prefix="/api/horarios")
EMPLOYEE_ROLES = {"ADMINISTRADOR", "COCINA", "MESERO", "DOMICILIARIO"}


def find_schedule_or_404(schedule_id):
    schedule = db.session.get(HorarioEmpleado, schedule_id)
    if schedule is None:
        raise ApiError("Horario no encontrado.", 404, "SCHEDULE_NOT_FOUND")
    return schedule


def parse_date(value):
    if not isinstance(value, str):
        raise ApiError("La fecha debe usar el formato AAAA-MM-DD.", 400, "VALIDATION_ERROR")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ApiError(
            "La fecha debe usar el formato AAAA-MM-DD.", 400, "VALIDATION_ERROR"
        ) from error


def parse_time(value, field):
    if not isinstance(value, str):
        raise ApiError(f"El campo {field} debe usar el formato HH:MM.", 400, "VALIDATION_ERROR")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ApiError(
            f"El campo {field} debe usar el formato HH:MM.", 400, "VALIDATION_ERROR"
        ) from error
    if parsed.tzinfo is not None:
        raise ApiError(
            f"El campo {field} no debe incluir zona horaria.", 400, "VALIDATION_ERROR"
        )
    return parsed


def validate_employee(user_id):
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise ApiError("Usuario no encontrado.", 404, "USER_NOT_FOUND")
    if not user.activo:
        raise ApiError("El empleado está inactivo.", 409, "EMPLOYEE_INACTIVE")
    if user.tipo_usuario.descripcion not in EMPLOYEE_ROLES:
        raise ApiError(
            "El usuario seleccionado no tiene un rol de empleado.",
            422,
            "USER_IS_NOT_EMPLOYEE",
        )
    return user


def validate_schedule(user_id, schedule_date, start, end, exclude_id=None):
    validate_employee(user_id)
    if end <= start:
        raise ApiError(
            "La hora de finalización debe ser posterior a la hora de inicio.",
            400,
            "INVALID_TIME_RANGE",
        )

    query = db.select(HorarioEmpleado).where(
        HorarioEmpleado.id_usuario == user_id,
        HorarioEmpleado.fecha == schedule_date,
        HorarioEmpleado.hora_inicio < end,
        HorarioEmpleado.hora_fin > start,
    )
    if exclude_id is not None:
        query = query.where(HorarioEmpleado.id_horario != exclude_id)
    if db.session.scalar(query) is not None:
        raise ApiError(
            "El horario se cruza con otro turno del empleado.",
            409,
            "SCHEDULE_OVERLAP",
        )


@horarios_bp.get("")
def list_schedules():
    user_id = request.args.get("id_usuario", type=int)
    date_text = request.args.get("fecha")
    query = db.select(HorarioEmpleado).order_by(
        HorarioEmpleado.fecha, HorarioEmpleado.hora_inicio
    )
    if user_id:
        query = query.where(HorarioEmpleado.id_usuario == user_id)
    if date_text:
        query = query.where(HorarioEmpleado.fecha == parse_date(date_text))

    schedules = db.session.scalars(query).all()
    return jsonify({"datos": [schedule.to_dict() for schedule in schedules]})


@horarios_bp.get("/<int:schedule_id>")
def get_schedule(schedule_id):
    return jsonify({"datos": find_schedule_or_404(schedule_id).to_dict()})


@horarios_bp.post("")
def create_schedule():
    data = json_body(
        {"id_usuario", "fecha", "hora_inicio", "hora_fin", "observacion"},
        {"id_usuario", "fecha", "hora_inicio", "hora_fin"},
    )
    user_id = positive_int(data["id_usuario"], "id_usuario")
    schedule_date = parse_date(data["fecha"])
    start = parse_time(data["hora_inicio"], "hora_inicio")
    end = parse_time(data["hora_fin"], "hora_fin")
    observation = text_value(
        data.get("observacion"), "observacion", 250, required=False
    )
    validate_schedule(user_id, schedule_date, start, end)

    schedule = HorarioEmpleado(
        id_usuario=user_id,
        fecha=schedule_date,
        hora_inicio=start,
        hora_fin=end,
        observacion=observation,
    )
    db.session.add(schedule)
    db.session.commit()
    return jsonify({"datos": schedule.to_dict()}), 201


def update_schedule(schedule_id, partial):
    schedule = find_schedule_or_404(schedule_id)
    fields = {"id_usuario", "fecha", "hora_inicio", "hora_fin", "observacion"}
    required = set() if partial else {"id_usuario", "fecha", "hora_inicio", "hora_fin"}
    data = json_body(fields, required)
    if partial and not data:
        raise ApiError("Debes enviar al menos un campo.", 400, "EMPTY_UPDATE")

    user_id = (
        positive_int(data["id_usuario"], "id_usuario")
        if "id_usuario" in data
        else schedule.id_usuario
    )
    schedule_date = parse_date(data["fecha"]) if "fecha" in data else schedule.fecha
    start = (
        parse_time(data["hora_inicio"], "hora_inicio")
        if "hora_inicio" in data
        else schedule.hora_inicio
    )
    end = (
        parse_time(data["hora_fin"], "hora_fin")
        if "hora_fin" in data
        else schedule.hora_fin
    )
    observation = (
        text_value(data["observacion"], "observacion", 250, required=False)
        if "observacion" in data
        else schedule.observacion
    )
    validate_schedule(user_id, schedule_date, start, end, schedule.id_horario)

    schedule.id_usuario = user_id
    schedule.fecha = schedule_date
    schedule.hora_inicio = start
    schedule.hora_fin = end
    schedule.observacion = observation
    db.session.commit()
    return jsonify({"datos": schedule.to_dict()})


@horarios_bp.put("/<int:schedule_id>")
def replace_schedule(schedule_id):
    return update_schedule(schedule_id, partial=False)


@horarios_bp.patch("/<int:schedule_id>")
def patch_schedule(schedule_id):
    return update_schedule(schedule_id, partial=True)


@horarios_bp.delete("/<int:schedule_id>")
def delete_schedule(schedule_id):
    schedule = find_schedule_or_404(schedule_id)
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({"mensaje": "Horario eliminado correctamente."})
