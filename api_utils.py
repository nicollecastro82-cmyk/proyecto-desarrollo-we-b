from flask import request


class ApiError(Exception):
    def __init__(self, message, status_code=400, code="BAD_REQUEST", details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


def json_body(allowed_fields, required_fields=()):
    if not request.is_json:
        raise ApiError(
            "La solicitud debe usar Content-Type application/json.",
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Debes enviar un objeto JSON válido.", 400, "INVALID_JSON")

    unknown = sorted(set(data) - set(allowed_fields))
    if unknown:
        raise ApiError(
            "La solicitud contiene campos no permitidos.",
            400,
            "UNKNOWN_FIELDS",
            {"campos": unknown},
        )

    missing = sorted(field for field in required_fields if field not in data)
    if missing:
        raise ApiError(
            "Faltan campos obligatorios.",
            400,
            "MISSING_FIELDS",
            {"campos": missing},
        )

    return data


def text_value(value, field, max_length, required=True):
    if value is None:
        if required:
            raise ApiError(f"El campo {field} es obligatorio.", 400, "VALIDATION_ERROR")
        return None
    if not isinstance(value, str):
        raise ApiError(f"El campo {field} debe ser texto.", 400, "VALIDATION_ERROR")

    normalized = value.strip()
    if required and not normalized:
        raise ApiError(f"El campo {field} es obligatorio.", 400, "VALIDATION_ERROR")
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ApiError(
            f"El campo {field} no puede superar {max_length} caracteres.",
            400,
            "VALIDATION_ERROR",
        )
    return normalized


def bool_value(value, field):
    if not isinstance(value, bool):
        raise ApiError(
            f"El campo {field} debe ser verdadero o falso.",
            400,
            "VALIDATION_ERROR",
        )
    return value


def positive_int(value, field, required=True):
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ApiError(
            f"El campo {field} debe ser un entero positivo.",
            400,
            "VALIDATION_ERROR",
        )
    return value


def query_bool(name, default=False):
    value = request.args.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "si", "sí"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ApiError(
        f"El parámetro {name} debe ser true o false.",
        400,
        "VALIDATION_ERROR",
    )
