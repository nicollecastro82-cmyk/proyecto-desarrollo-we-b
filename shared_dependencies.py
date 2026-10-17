from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from api_utils import ApiError
from extensions import db


def enum_text(value):
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def require_order(order_id, required_columns=()):
    inspector = inspect(db.engine)
    if not inspector.has_table("pedido"):
        raise ApiError(
            "La funcionalidad requiere la tabla compartida pedido, que aún no está integrada.",
            503,
            "ORDER_DEPENDENCY_UNAVAILABLE",
        )

    available = {column["name"] for column in inspector.get_columns("pedido")}
    needed = {"id_pedido", *required_columns}
    missing = sorted(needed - available)
    if missing:
        raise ApiError(
            "La tabla pedido no tiene todavía el contrato esperado.",
            503,
            "ORDER_DEPENDENCY_INCOMPATIBLE",
            {"columnas_faltantes": missing},
        )

    selected = ["id_pedido", *sorted(set(required_columns))]
    try:
        row = db.session.execute(
            text(
                f"SELECT {', '.join(selected)} FROM pedido "
                "WHERE id_pedido = :id_pedido"
            ),
            {"id_pedido": order_id},
        ).mappings().first()
    except SQLAlchemyError as error:
        raise ApiError(
            "No fue posible consultar el modelo compartido Pedido.",
            503,
            "ORDER_DEPENDENCY_INCOMPATIBLE",
        ) from error

    if row is None:
        raise ApiError("Pedido no encontrado.", 404, "ORDER_NOT_FOUND")
    return {key: enum_text(value) for key, value in row.items()}
