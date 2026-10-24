"""Nombres canónicos de las 15 funcionalidades visibles del proyecto."""


FUNCTIONALITY_NAMES = (
    "Gestionar categorías",
    "Gestionar productos y menú",
    "Gestionar mesas",
    "Gestionar usuarios",
    "Gestionar roles",
    "Iniciar sesión",
    "Gestionar horarios",
    "Registrar pedidos en salón",
    "Registrar pedidos a domicilio",
    "Gestionar detalle del pedido",
    "Consultar y filtrar pedidos en Cocina",
    "Actualizar estado de preparación",
    "Gestionar pagos",
    "Gestionar domicilios y entregas",
    "Consultar estado e historial de pedidos",
)


def functionality_label(number):
    """Devuelve el rótulo numerado que comparten Driver, ORM y Postman."""
    return f"{number:02d}. {FUNCTIONALITY_NAMES[number - 1]}"
