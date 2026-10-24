"""Verifica sin modificar datos las 11 tablas del modelo oficial."""

from sqlalchemy import inspect, text

from app import app
from extensions import db


TABLAS_OFICIALES = {
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
}


def run():
    with app.app_context():
        inspector = inspect(db.engine)
        tablas = TABLAS_OFICIALES.intersection(inspector.get_table_names())
        faltantes = TABLAS_OFICIALES - tablas
        if faltantes:
            raise AssertionError(f"Faltan tablas: {sorted(faltantes)}")

        detalle_fk = {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys("detalle_pedido")
        }
        historial_fk = {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys("historial_estado")
        }
        assert (("id_pedido",), "pedido") in detalle_fk
        assert (("id_producto",), "producto") in detalle_fk
        assert (("id_pedido",), "pedido") in historial_fk
        assert (("id_usuario_cambio",), "usuario") in historial_fk

        trigger = db.session.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_trigger "
                "WHERE tgname = 'trg_detalle_recalcular_total' AND NOT tgisinternal"
                ")"
            )
        ).scalar_one()
        assert trigger

        print(f"OK: {len(tablas)} tablas oficiales verificadas.")
        print("OK: claves foraneas de detalle_pedido e historial_estado.")
        print("OK: trigger de recalculo del total del pedido.")


if __name__ == "__main__":
    run()
