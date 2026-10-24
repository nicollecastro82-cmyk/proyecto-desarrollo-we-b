"""Carga idempotente de datos ficticios para la sustentación de PoliRestaurante.

Solo inserta registros identificados como demostración. No contiene UPDATE,
DELETE, TRUNCATE ni operaciones de esquema. Si una validación falla, toda la
transacción se revierte.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from getpass import getpass
from pathlib import Path

from sqlalchemy import func, inspect, text
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from extensions import db  # noqa: E402
from mesas import EstadoMesa, Mesa  # noqa: E402
from models import (  # noqa: E402
    Categoria,
    DetallePedido,
    Entrega,
    EstadoEntrega,
    EstadoPago,
    EstadoPedido,
    HistorialEstado,
    HorarioEmpleado,
    MetodoPago,
    Pago,
    Pedido,
    TipoPedido,
    TipoUsuario,
    Usuario,
)
from producto import Producto  # noqa: E402


PASSWORD_ENV = "POLIRESTAURANTE_DEMO_PASSWORD"
DEMO_MARKER = "[DEMO]"
OFFICIAL_TABLES = (
    "categoria",
    "producto",
    "mesa",
    "tipo_usuario",
    "usuario",
    "horario_empleado",
    "pedido",
    "detalle_pedido",
    "pago",
    "entrega",
    "historial_estado",
)
MODELS_BY_TABLE = {
    "categoria": Categoria,
    "producto": Producto,
    "mesa": Mesa,
    "tipo_usuario": TipoUsuario,
    "usuario": Usuario,
    "horario_empleado": HorarioEmpleado,
    "pedido": Pedido,
    "detalle_pedido": DetallePedido,
    "pago": Pago,
    "entrega": Entrega,
    "historial_estado": HistorialEstado,
}
EXPECTED_ENUMS = {
    "estado_entrega": [
        "PENDIENTE_ASIGNACION",
        "ASIGNADA",
        "RECOGIDA",
        "EN_CAMINO",
        "ENTREGADA",
        "CON_INCIDENCIA",
    ],
    "estado_mesa": ["LIBRE", "OCUPADA", "FUERA_DE_SERVICIO"],
    "estado_pago": ["PENDIENTE", "APROBADO", "RECHAZADO"],
    "estado_pedido": [
        "PENDIENTE",
        "EN_PREPARACION",
        "LISTO",
        "ENTREGADO",
        "CANCELADO",
    ],
    "metodo_pago": ["EFECTIVO", "PSE"],
    "tipo_pedido": ["SALON", "PARA_LLEVAR", "DOMICILIO"],
}

CATEGORY_DATA = (
    ("Entradas [DEMO]",),
    ("Platos fuertes [DEMO]",),
    ("Bebidas [DEMO]",),
    ("Postres [DEMO]",),
)
PRODUCT_DATA = (
    ("Empanadas colombianas [DEMO]", "Entradas [DEMO]", "Empanadas de carne con ají de la casa.", "7000.00"),
    ("Papas criollas [DEMO]", "Entradas [DEMO]", "Papas criollas doradas con salsa de cilantro.", "9000.00"),
    ("Patacones [DEMO]", "Entradas [DEMO]", "Patacones crocantes acompañados de hogao.", "10000.00"),
    ("Ajiaco santafereño [DEMO]", "Platos fuertes [DEMO]", "Ajiaco con pollo, mazorca, alcaparras y crema.", "28000.00"),
    ("Bandeja paisa [DEMO]", "Platos fuertes [DEMO]", "Fríjoles, arroz, carne, chicharrón, huevo y aguacate.", "35000.00"),
    ("Hamburguesa artesanal [DEMO]", "Platos fuertes [DEMO]", "Carne artesanal, queso, vegetales y pan brioche.", "26000.00"),
    ("Limonada natural [DEMO]", "Bebidas [DEMO]", "Limonada natural preparada al momento.", "8000.00"),
    ("Jugo de mora [DEMO]", "Bebidas [DEMO]", "Jugo de mora en agua, sin conservantes.", "9000.00"),
    ("Gaseosa [DEMO]", "Bebidas [DEMO]", "Bebida gaseosa personal fría.", "6000.00"),
    ("Torta de tres leches [DEMO]", "Postres [DEMO]", "Porción de torta húmeda de tres leches.", "12000.00"),
    ("Flan de caramelo [DEMO]", "Postres [DEMO]", "Flan suave con caramelo artesanal.", "10000.00"),
    ("Brownie [DEMO]", "Postres [DEMO]", "Brownie de chocolate con nueces.", "11000.00"),
)
USER_DATA = (
    ("demo_admin", "ADMINISTRADOR", "Valentina Torres", "demo.admin@example.test", "3000000101"),
    ("demo_cocina", "COCINA", "Carlos Mendoza", "demo.cocina@example.test", "3000000102"),
    ("demo_mesero_1", "MESERO", "Mateo Rojas", "demo.mesero1@example.test", "3000000103"),
    ("demo_mesero_2", "MESERO", "Sara Díaz", "demo.mesero2@example.test", "3000000104"),
    ("demo_cliente_1", "CLIENTE", "Camila Pérez", "demo.cliente1@example.test", "3000000105"),
    ("demo_cliente_2", "CLIENTE", "Andrés Gómez", "demo.cliente2@example.test", "3000000106"),
    ("demo_domiciliario", "DOMICILIARIO", "Julián Castro", "demo.domiciliario@example.test", "3000000107"),
)
MESA_DATA = (
    (9101, EstadoMesa.OCUPADA),
    (9102, EstadoMesa.OCUPADA),
    (9103, EstadoMesa.LIBRE),
    (9104, EstadoMesa.LIBRE),
)


class LoadStats:
    def __init__(self):
        self.created = defaultdict(int)
        self.existing = defaultdict(int)

    def mark(self, table: str, created: bool) -> None:
        target = self.created if created else self.existing
        target[table] += 1

    def payload(self) -> dict:
        return {
            table: {
                "creados": self.created[table],
                "ya_existian": self.existing[table],
            }
            for table in OFFICIAL_TABLES
        }


def row_counts() -> dict[str, int]:
    return {
        table: db.session.scalar(db.select(func.count()).select_from(model))
        for table, model in MODELS_BY_TABLE.items()
    }


def preflight() -> tuple[dict, dict[str, int]]:
    if db.engine.dialect.name != "postgresql":
        raise RuntimeError("La carga de demostración solo se permite sobre PostgreSQL.")

    connection = db.session.execute(
        text(
            "SELECT current_database() AS base, current_schema() AS esquema, "
            "current_setting('port') AS puerto"
        )
    ).mappings().one()
    if connection["base"] != "polirestaurante" or connection["esquema"] != "public":
        raise RuntimeError(
            "Conexión rechazada: se esperaba polirestaurante/public y se obtuvo "
            f"{connection['base']}/{connection['esquema']}."
        )

    inspector = inspect(db.engine)
    available = set(inspector.get_table_names(schema="public"))
    missing = set(OFFICIAL_TABLES) - available
    if missing:
        raise RuntimeError(f"Faltan tablas oficiales: {sorted(missing)}")

    enum_rows = db.session.execute(
        text(
            "SELECT t.typname AS enum, e.enumlabel AS valor "
            "FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = 'public' ORDER BY t.typname, e.enumsortorder"
        )
    ).mappings()
    enums = defaultdict(list)
    for row in enum_rows:
        enums[row["enum"]].append(row["valor"])
    for enum_name, expected in EXPECTED_ENUMS.items():
        if enums.get(enum_name) != expected:
            raise RuntimeError(
                f"El enum {enum_name} no coincide con el modelo: {enums.get(enum_name)}"
            )

    required_fks = {
        "producto": {("id_categoria", "categoria")},
        "usuario": {("id_tipo_usuario", "tipo_usuario")},
        "horario_empleado": {("id_usuario", "usuario")},
        "detalle_pedido": {("id_pedido", "pedido"), ("id_producto", "producto")},
        "pago": {("id_pedido", "pedido")},
        "entrega": {("id_pedido", "pedido"), ("id_domiciliario", "usuario")},
        "historial_estado": {("id_pedido", "pedido"), ("id_usuario_cambio", "usuario")},
    }
    for table, expected in required_fks.items():
        actual = {
            (fk["constrained_columns"][0], fk["referred_table"])
            for fk in inspector.get_foreign_keys(table, schema="public")
        }
        if not expected.issubset(actual):
            raise RuntimeError(f"Faltan relaciones en {table}: {sorted(expected - actual)}")

    trigger_exists = db.session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgname = 'trg_detalle_recalcular_total' AND NOT tgisinternal)"
        )
    )
    if not trigger_exists:
        raise RuntimeError("No existe el trigger de recálculo de totales.")

    counts = row_counts()
    db.session.rollback()
    return dict(connection), counts


def demo_password() -> str:
    value = os.getenv(PASSWORD_ENV)
    if value is None and sys.stdin.isatty():
        value = getpass(f"Contraseña para las cuentas demo ({PASSWORD_ENV}): ")
    if not value:
        raise RuntimeError(
            f"Define {PASSWORD_ENV} con una contraseña temporal de al menos 8 caracteres."
        )
    if len(value) < 8 or len(value) > 128:
        raise RuntimeError("La contraseña demo debe tener entre 8 y 128 caracteres.")
    return value


def require_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise RuntimeError(
            f"El registro demo existente '{label}' no coincide: "
            f"se esperaba {expected!r} y se encontró {actual!r}. No fue modificado."
        )


def ensure_roles(stats: LoadStats) -> dict[str, TipoUsuario]:
    result = {}
    for description in ("ADMINISTRADOR", "COCINA", "MESERO", "CLIENTE", "DOMICILIARIO"):
        role = db.session.scalar(
            db.select(TipoUsuario).where(
                func.lower(TipoUsuario.descripcion) == description.lower()
            )
        )
        created = role is None
        if created:
            role = TipoUsuario(descripcion=description)
            db.session.add(role)
            db.session.flush()
        else:
            require_equal(description, role.descripcion, description)
        stats.mark("tipo_usuario", created)
        result[description] = role
    return result


def ensure_categories(stats: LoadStats) -> dict[str, Categoria]:
    result = {}
    for (name,) in CATEGORY_DATA:
        category = db.session.scalar(
            db.select(Categoria).where(func.lower(Categoria.nombre) == name.lower())
        )
        created = category is None
        if created:
            category = Categoria(nombre=name, activo=True)
            db.session.add(category)
            db.session.flush()
        else:
            require_equal(name, category.nombre, name)
            require_equal(name, category.activo, True)
        stats.mark("categoria", created)
        result[name] = category
    return result


def ensure_products(stats: LoadStats, categories: dict[str, Categoria]) -> dict[str, Producto]:
    result = {}
    for name, category_name, description, price_text in PRODUCT_DATA:
        product = db.session.scalar(
            db.select(Producto).where(func.lower(Producto.nombre) == name.lower())
        )
        price = Decimal(price_text)
        created = product is None
        if created:
            product = Producto(
                nombre=name,
                descripcion=f"{DEMO_MARKER} {description}",
                precio=price,
                activo=True,
                disponible=True,
                id_categoria=categories[category_name].id_categoria,
            )
            db.session.add(product)
            db.session.flush()
        else:
            require_equal(name, product.nombre, name)
            require_equal(name, product.id_categoria, categories[category_name].id_categoria)
            require_equal(name, Decimal(product.precio), price)
            require_equal(name, product.activo, True)
            require_equal(name, product.disponible, True)
        stats.mark("producto", created)
        result[name] = product
    return result


def ensure_users(
    stats: LoadStats, roles: dict[str, TipoUsuario], password: str
) -> dict[str, Usuario]:
    result = {}
    for login, role_name, name, email, phone in USER_DATA:
        user = db.session.scalar(
            db.select(Usuario).where(func.lower(Usuario.usuario_login) == login.lower())
        )
        created = user is None
        if created:
            user = Usuario(
                id_tipo_usuario=roles[role_name].id_tipo_usuario,
                nombre=name,
                usuario_login=login,
                contrasena_hash=generate_password_hash(password),
                correo=email,
                telefono=phone,
                activo=True,
            )
            db.session.add(user)
            db.session.flush()
        else:
            require_equal(login, user.usuario_login, login)
            require_equal(login, user.id_tipo_usuario, roles[role_name].id_tipo_usuario)
            require_equal(login, user.activo, True)
        stats.mark("usuario", created)
        result[login] = user
    return result


def ensure_schedules(stats: LoadStats, users: dict[str, Usuario]) -> None:
    definitions = (
        ("demo_admin", time(8), time(16), "Turno administrativo"),
        ("demo_cocina", time(9), time(17), "Turno de cocina"),
        ("demo_mesero_1", time(10), time(18), "Turno de atención en salón"),
        ("demo_domiciliario", time(11), time(19), "Turno de domicilios"),
    )
    schedule_date = date(2026, 10, 26)
    for login, start, end, description in definitions:
        observation = f"{DEMO_MARKER} {description}"
        schedule = db.session.scalar(
            db.select(HorarioEmpleado).where(
                HorarioEmpleado.id_usuario == users[login].id_usuario,
                HorarioEmpleado.fecha == schedule_date,
                HorarioEmpleado.hora_inicio == start,
                HorarioEmpleado.hora_fin == end,
                HorarioEmpleado.observacion == observation,
            )
        )
        created = schedule is None
        if created:
            db.session.add(
                HorarioEmpleado(
                    id_usuario=users[login].id_usuario,
                    fecha=schedule_date,
                    hora_inicio=start,
                    hora_fin=end,
                    observacion=observation,
                )
            )
            db.session.flush()
        stats.mark("horario_empleado", created)


def ensure_tables(stats: LoadStats) -> dict[int, Mesa]:
    result = {}
    for number, state in MESA_DATA:
        table = db.session.scalar(db.select(Mesa).where(Mesa.numero_mesa == number))
        created = table is None
        if created:
            table = Mesa(numero_mesa=number, estado=state)
            db.session.add(table)
            db.session.flush()
        else:
            require_equal(f"mesa {number}", table.estado, state)
        stats.mark("mesa", created)
        result[number] = table
    return result


def ensure_order(
    stats: LoadStats,
    marker: str,
    order_type: TipoPedido,
    state: EstadoPedido,
    created_at: datetime,
    *,
    table: Mesa | None = None,
    waiter: Usuario | None = None,
    client: Usuario | None = None,
) -> Pedido:
    order = db.session.scalar(
        db.select(Pedido).where(Pedido.observaciones == marker)
    )
    created = order is None
    if created:
        order = Pedido(
            id_mesa=table.id_mesa if table else None,
            id_mesero=waiter.id_usuario if waiter else None,
            id_cliente=client.id_usuario if client else None,
            tipo=order_type,
            estado=state,
            valor_total=Decimal("0.00"),
            observaciones=marker,
            fecha_creacion=created_at,
            fecha_ultima_actualizacion=created_at,
        )
        db.session.add(order)
        db.session.flush()
    else:
        require_equal(marker, order.tipo, order_type)
        require_equal(marker, order.estado, state)
        require_equal(marker, order.id_mesa, table.id_mesa if table else None)
        require_equal(marker, order.id_mesero, waiter.id_usuario if waiter else None)
        require_equal(marker, order.id_cliente, client.id_usuario if client else None)
    stats.mark("pedido", created)
    return order


def ensure_detail(
    stats: LoadStats,
    order: Pedido,
    product: Producto,
    quantity: int,
    comment: str,
) -> None:
    detail = db.session.scalar(
        db.select(DetallePedido).where(
            DetallePedido.id_pedido == order.id_pedido,
            DetallePedido.id_producto == product.id_producto,
        )
    )
    created = detail is None
    if created:
        db.session.add(
            DetallePedido(
                id_pedido=order.id_pedido,
                id_producto=product.id_producto,
                cantidad=quantity,
                precio_unitario=product.precio,
                comentarios=f"{DEMO_MARKER} {comment}",
            )
        )
        db.session.flush()
    else:
        require_equal(product.nombre, detail.cantidad, quantity)
        require_equal(product.nombre, Decimal(detail.precio_unitario), Decimal(product.precio))
    stats.mark("detalle_pedido", created)


def ensure_history(
    stats: LoadStats,
    order: Pedido,
    state: EstadoPedido,
    responsible: Usuario,
    changed_at: datetime,
    observation: str,
) -> None:
    full_observation = f"{DEMO_MARKER} {observation}"
    history = db.session.scalar(
        db.select(HistorialEstado).where(
            HistorialEstado.id_pedido == order.id_pedido,
            HistorialEstado.estado == state,
            HistorialEstado.observacion == full_observation,
        )
    )
    created = history is None
    if created:
        db.session.add(
            HistorialEstado(
                id_pedido=order.id_pedido,
                id_usuario_cambio=responsible.id_usuario,
                estado=state,
                fecha=changed_at,
                observacion=full_observation,
            )
        )
        db.session.flush()
    else:
        require_equal(full_observation, history.id_usuario_cambio, responsible.id_usuario)
        require_equal(full_observation, history.fecha, changed_at)
    stats.mark("historial_estado", created)


def ensure_delivery(
    stats: LoadStats,
    order: Pedido,
    state: EstadoEntrega,
    address: str,
    phone: str,
    courier: Usuario | None = None,
    assigned_at: datetime | None = None,
    picked_at: datetime | None = None,
    delivered_at: datetime | None = None,
) -> Entrega:
    delivery = db.session.scalar(
        db.select(Entrega).where(Entrega.id_pedido == order.id_pedido)
    )
    created = delivery is None
    if created:
        delivery = Entrega(
            id_pedido=order.id_pedido,
            id_domiciliario=courier.id_usuario if courier else None,
            direccion_entrega=address,
            telefono_contacto=phone,
            estado=state,
            fecha_asignacion=assigned_at,
            fecha_recogida=picked_at,
            fecha_entrega=delivered_at,
            observacion=f"{DEMO_MARKER} Dirección y teléfono ficticios.",
        )
        db.session.add(delivery)
        db.session.flush()
    else:
        require_equal(address, delivery.estado, state)
        require_equal(address, delivery.id_domiciliario, courier.id_usuario if courier else None)
        require_equal(address, delivery.direccion_entrega, address)
        require_equal(address, delivery.telefono_contacto, phone)
    stats.mark("entrega", created)
    return delivery


def ensure_payment(
    stats: LoadStats,
    order: Pedido,
    method: MetodoPago,
    state: EstadoPago,
    reference: str,
    confirmer: Usuario | None,
    created_at: datetime,
    paid_at: datetime | None,
) -> Pago:
    payment = db.session.scalar(db.select(Pago).where(Pago.id_pedido == order.id_pedido))
    created = payment is None
    if created:
        payment = Pago(
            id_pedido=order.id_pedido,
            id_usuario_confirma=confirmer.id_usuario if confirmer else None,
            metodo=method,
            estado=state,
            valor=order.valor_total,
            referencia_transaccion=reference,
            fecha_creacion=created_at,
            fecha_pago=paid_at,
        )
        db.session.add(payment)
        db.session.flush()
    else:
        require_equal(reference, payment.metodo, method)
        require_equal(reference, payment.estado, state)
        require_equal(reference, Decimal(payment.valor), Decimal(order.valor_total))
        require_equal(reference, payment.referencia_transaccion, reference)
    stats.mark("pago", created)
    return payment


def create_demo_data(password: str) -> tuple[LoadStats, dict[str, Pedido]]:
    stats = LoadStats()
    roles = ensure_roles(stats)
    categories = ensure_categories(stats)
    products = ensure_products(stats, categories)
    users = ensure_users(stats, roles, password)
    ensure_schedules(stats, users)
    tables = ensure_tables(stats)

    orders = {
        "salon_pending": ensure_order(
            stats,
            "[DEMO:PEDIDO_SALON_PENDIENTE] Almuerzo mesa 9101",
            TipoPedido.SALON,
            EstadoPedido.PENDIENTE,
            datetime(2026, 10, 23, 12, 0),
            table=tables[9101],
            waiter=users["demo_mesero_1"],
            client=users["demo_cliente_1"],
        ),
        "salon_preparing": ensure_order(
            stats,
            "[DEMO:PEDIDO_SALON_EN_PREPARACION] Almuerzo mesa 9102",
            TipoPedido.SALON,
            EstadoPedido.EN_PREPARACION,
            datetime(2026, 10, 23, 12, 10),
            table=tables[9102],
            waiter=users["demo_mesero_2"],
            client=users["demo_cliente_2"],
        ),
        "salon_delivered": ensure_order(
            stats,
            "[DEMO:PEDIDO_SALON_ENTREGADO] Servicio finalizado mesa 9103",
            TipoPedido.SALON,
            EstadoPedido.ENTREGADO,
            datetime(2026, 10, 23, 11, 0),
            table=tables[9103],
            waiter=users["demo_mesero_1"],
            client=users["demo_cliente_1"],
        ),
        "delivery_pending": ensure_order(
            stats,
            "[DEMO:PEDIDO_DOMICILIO_PENDIENTE] Zona norte",
            TipoPedido.DOMICILIO,
            EstadoPedido.PENDIENTE,
            datetime(2026, 10, 23, 12, 20),
            client=users["demo_cliente_1"],
        ),
        "delivery_ready": ensure_order(
            stats,
            "[DEMO:PEDIDO_DOMICILIO_LISTO] Zona centro",
            TipoPedido.DOMICILIO,
            EstadoPedido.LISTO,
            datetime(2026, 10, 23, 10, 0),
            client=users["demo_cliente_2"],
        ),
        "delivery_delivered": ensure_order(
            stats,
            "[DEMO:PEDIDO_DOMICILIO_ENTREGADO] Zona occidente",
            TipoPedido.DOMICILIO,
            EstadoPedido.ENTREGADO,
            datetime(2026, 10, 23, 9, 0),
            client=users["demo_cliente_1"],
        ),
        "takeaway_cancelled": ensure_order(
            stats,
            "[DEMO:PEDIDO_PARA_LLEVAR_CANCELADO] Cancelación de demostración",
            TipoPedido.PARA_LLEVAR,
            EstadoPedido.CANCELADO,
            datetime(2026, 10, 23, 12, 30),
            waiter=users["demo_mesero_2"],
            client=users["demo_cliente_2"],
        ),
    }

    detail_definitions = (
        ("salon_pending", "Hamburguesa artesanal [DEMO]", 2, "Término medio"),
        ("salon_pending", "Limonada natural [DEMO]", 2, "Poco azúcar"),
        ("salon_preparing", "Ajiaco santafereño [DEMO]", 1, "Con alcaparras aparte"),
        ("salon_preparing", "Torta de tres leches [DEMO]", 1, "Servir después del plato fuerte"),
        ("salon_delivered", "Bandeja paisa [DEMO]", 1, "Porción completa"),
        ("salon_delivered", "Gaseosa [DEMO]", 1, "Bebida fría"),
        ("delivery_pending", "Empanadas colombianas [DEMO]", 2, "Incluir ají"),
        ("delivery_pending", "Jugo de mora [DEMO]", 1, "Sin azúcar"),
        ("delivery_ready", "Patacones [DEMO]", 1, "Hogao separado"),
        ("delivery_ready", "Hamburguesa artesanal [DEMO]", 1, "Sin cebolla"),
        ("delivery_delivered", "Ajiaco santafereño [DEMO]", 1, "Empaque sellado"),
        ("delivery_delivered", "Brownie [DEMO]", 2, "Dos porciones"),
        ("takeaway_cancelled", "Papas criollas [DEMO]", 1, "Pedido cancelado antes de preparar"),
    )
    for order_key, product_name, quantity, comment in detail_definitions:
        ensure_detail(stats, orders[order_key], products[product_name], quantity, comment)

    db.session.flush()
    for order in orders.values():
        db.session.refresh(order)

    histories = {
        "salon_pending": (
            (EstadoPedido.PENDIENTE, "demo_mesero_1", datetime(2026, 10, 23, 12, 0), "Pedido registrado por el mesero."),
        ),
        "salon_preparing": (
            (EstadoPedido.PENDIENTE, "demo_mesero_2", datetime(2026, 10, 23, 12, 10), "Pedido registrado por el mesero."),
            (EstadoPedido.EN_PREPARACION, "demo_cocina", datetime(2026, 10, 23, 12, 15), "Cocina inició la preparación."),
        ),
        "salon_delivered": (
            (EstadoPedido.PENDIENTE, "demo_mesero_1", datetime(2026, 10, 23, 11, 0), "Pedido registrado por el mesero."),
            (EstadoPedido.EN_PREPARACION, "demo_cocina", datetime(2026, 10, 23, 11, 5), "Cocina inició la preparación."),
            (EstadoPedido.LISTO, "demo_cocina", datetime(2026, 10, 23, 11, 30), "Pedido listo para servir."),
            (EstadoPedido.ENTREGADO, "demo_mesero_1", datetime(2026, 10, 23, 11, 40), "Pedido entregado en la mesa."),
        ),
        "delivery_pending": (
            (EstadoPedido.PENDIENTE, "demo_cliente_1", datetime(2026, 10, 23, 12, 20), "Pedido a domicilio registrado."),
        ),
        "delivery_ready": (
            (EstadoPedido.PENDIENTE, "demo_cliente_2", datetime(2026, 10, 23, 10, 0), "Pedido a domicilio registrado."),
            (EstadoPedido.EN_PREPARACION, "demo_cocina", datetime(2026, 10, 23, 10, 5), "Cocina inició la preparación."),
            (EstadoPedido.LISTO, "demo_cocina", datetime(2026, 10, 23, 10, 25), "Pedido listo para recoger."),
        ),
        "delivery_delivered": (
            (EstadoPedido.PENDIENTE, "demo_cliente_1", datetime(2026, 10, 23, 9, 0), "Pedido a domicilio registrado."),
            (EstadoPedido.EN_PREPARACION, "demo_cocina", datetime(2026, 10, 23, 9, 5), "Cocina inició la preparación."),
            (EstadoPedido.LISTO, "demo_cocina", datetime(2026, 10, 23, 9, 25), "Pedido listo para recoger."),
            (EstadoPedido.ENTREGADO, "demo_domiciliario", datetime(2026, 10, 23, 9, 50), "Domicilio entregado al cliente."),
        ),
        "takeaway_cancelled": (
            (EstadoPedido.PENDIENTE, "demo_mesero_2", datetime(2026, 10, 23, 12, 30), "Pedido para llevar registrado."),
            (EstadoPedido.CANCELADO, "demo_mesero_2", datetime(2026, 10, 23, 12, 35), "Pedido cancelado antes de iniciar preparación."),
        ),
    }
    for order_key, changes in histories.items():
        for state, login, changed_at, observation in changes:
            ensure_history(stats, orders[order_key], state, users[login], changed_at, observation)

    ensure_delivery(
        stats,
        orders["delivery_pending"],
        EstadoEntrega.PENDIENTE_ASIGNACION,
        "Calle 100 # 20-30, Bogotá (dirección ficticia)",
        "3000000201",
    )
    ensure_delivery(
        stats,
        orders["delivery_ready"],
        EstadoEntrega.ASIGNADA,
        "Carrera 15 # 45-20, Bogotá (dirección ficticia)",
        "3000000202",
        users["demo_domiciliario"],
        datetime(2026, 10, 23, 10, 27),
    )
    ensure_delivery(
        stats,
        orders["delivery_delivered"],
        EstadoEntrega.ENTREGADA,
        "Calle 80 # 70-10, Bogotá (dirección ficticia)",
        "3000000203",
        users["demo_domiciliario"],
        datetime(2026, 10, 23, 9, 27),
        datetime(2026, 10, 23, 9, 32),
        datetime(2026, 10, 23, 9, 50),
    )

    ensure_payment(
        stats,
        orders["salon_delivered"],
        MetodoPago.EFECTIVO,
        EstadoPago.APROBADO,
        "DEMO-EFECTIVO-SALON-001",
        users["demo_mesero_1"],
        datetime(2026, 10, 23, 11, 35),
        datetime(2026, 10, 23, 11, 39),
    )
    ensure_payment(
        stats,
        orders["delivery_ready"],
        MetodoPago.PSE,
        EstadoPago.PENDIENTE,
        "DEMO-PSE-PENDIENTE-001",
        None,
        datetime(2026, 10, 23, 10, 26),
        None,
    )
    ensure_payment(
        stats,
        orders["delivery_delivered"],
        MetodoPago.PSE,
        EstadoPago.APROBADO,
        "DEMO-PSE-APROBADO-001",
        users["demo_admin"],
        datetime(2026, 10, 23, 9, 26),
        datetime(2026, 10, 23, 9, 28),
    )

    return stats, orders


def verify_demo_data() -> dict:
    orders = db.session.scalars(
        db.select(Pedido)
        .where(Pedido.observaciones.like("[DEMO:%"))
        .order_by(Pedido.id_pedido)
    ).unique().all()
    if len(orders) != 7:
        raise RuntimeError(f"Se esperaban 7 pedidos demo y se encontraron {len(orders)}.")

    for order in orders:
        calculated = db.session.scalar(
            db.select(
                func.coalesce(
                    func.sum(DetallePedido.cantidad * DetallePedido.precio_unitario),
                    0,
                )
            ).where(DetallePedido.id_pedido == order.id_pedido)
        )
        require_equal(order.observaciones, Decimal(order.valor_total), Decimal(calculated))
        payment = db.session.scalar(
            db.select(Pago).where(Pago.id_pedido == order.id_pedido)
        )
        if payment is not None:
            require_equal(
                f"pago del pedido {order.id_pedido}",
                Decimal(payment.valor),
                Decimal(order.valor_total),
            )
        delivery = db.session.scalar(
            db.select(Entrega).where(Entrega.id_pedido == order.id_pedido)
        )
        if delivery is not None:
            require_equal(
                f"entrega del pedido {order.id_pedido}", order.tipo, TipoPedido.DOMICILIO
            )
            if delivery.id_domiciliario is not None:
                courier = db.session.get(Usuario, delivery.id_domiciliario)
                require_equal(
                    f"domiciliario del pedido {order.id_pedido}",
                    courier.tipo_usuario.descripcion,
                    "DOMICILIARIO",
                )
        history = db.session.scalars(
            db.select(HistorialEstado)
            .where(HistorialEstado.id_pedido == order.id_pedido)
            .order_by(HistorialEstado.fecha, HistorialEstado.id_historial)
        ).all()
        if not history:
            raise RuntimeError(f"El pedido {order.id_pedido} no tiene historial.")
        require_equal(
            f"historial del pedido {order.id_pedido}", history[-1].estado, order.estado
        )

    for number in (9101, 9102):
        table = db.session.scalar(db.select(Mesa).where(Mesa.numero_mesa == number))
        require_equal(f"mesa {number}", table.estado, EstadoMesa.OCUPADA)
        active_orders = db.session.scalar(
            db.select(func.count(Pedido.id_pedido)).where(
                Pedido.id_mesa == table.id_mesa,
                Pedido.estado.in_([EstadoPedido.PENDIENTE, EstadoPedido.EN_PREPARACION, EstadoPedido.LISTO]),
            )
        )
        if active_orders != 1:
            raise RuntimeError(f"La mesa {number} debe tener exactamente un pedido activo.")

    return {
        "pedidos_demo": len(orders),
        "totales_correctos": True,
        "historiales_coherentes": True,
        "entregas_domicilio": True,
        "mesas_ocupadas_coherentes": True,
    }


def print_report(connection: dict, initial: dict, stats: LoadStats | None, final: dict, verification: dict) -> None:
    print(
        f"Base verificada: {connection['base']}/{connection['esquema']} "
        f"(puerto {connection['puerto']})"
    )
    print("Conteos iniciales:")
    print(json.dumps(initial, ensure_ascii=False, indent=2, sort_keys=True))
    if stats is not None:
        print("Resultado de la carga:")
        print(json.dumps(stats.payload(), ensure_ascii=False, indent=2, sort_keys=True))
    print("Conteos finales:")
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    print("Verificación:")
    print(json.dumps(verification, ensure_ascii=False, indent=2, sort_keys=True))
    print("Usuarios demo: " + ", ".join(item[0] for item in USER_DATA))
    print(
        f"La contraseña se toma de {PASSWORD_ENV}; no se guarda en el repositorio."
    )


def run(verify_only: bool = False) -> None:
    with app.app_context():
        connection, initial = preflight()
        if verify_only:
            verification = verify_demo_data()
            final = row_counts()
            print_report(connection, initial, None, final, verification)
            return

        password = demo_password()
        try:
            stats, _orders = create_demo_data(password)
            verification = verify_demo_data()
            db.session.commit()
        except Exception:
            db.session.rollback()
            print("ERROR: carga revertida; PostgreSQL no conservó inserciones parciales.")
            raise

        final = row_counts()
        print_report(connection, initial, stats, final, verification)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga datos ficticios e idempotentes en polirestaurante/public."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Comprueba los datos demo existentes sin insertar ni modificar registros.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args().verify_only)
