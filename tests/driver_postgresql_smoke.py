"""Prueba las 15 funcionalidades con psycopg y SQL parametrizado real.

La transaccion completa se revierte al final, incluso si una comprobacion falla.
No importa Flask, SQLAlchemy ni los modelos ORM.
"""

from datetime import date, time
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash

from consola_driver import conectar
from functionalities import functionality_label


def run():
    suffix = uuid4().hex[:10]
    connection = conectar()
    completed = []

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT descripcion, id_tipo_usuario FROM tipo_usuario")
            roles = {row["descripcion"]: row["id_tipo_usuario"] for row in cursor}
            required = {"MESERO", "COCINA", "CLIENTE", "DOMICILIARIO"}
            if not required.issubset(roles):
                raise AssertionError("Faltan roles base para la prueba Driver.")

            cursor.execute(
                "INSERT INTO categoria (nombre, activo) VALUES (%s, TRUE) "
                "RETURNING id_categoria",
                (f"Driver categoria {suffix}",),
            )
            category_id = cursor.fetchone()["id_categoria"]
            cursor.execute(
                "UPDATE categoria SET nombre = %s WHERE id_categoria = %s",
                (f"Driver categoria actualizada {suffix}", category_id),
            )
            cursor.execute(
                "SELECT activo FROM categoria WHERE id_categoria = %s", (category_id,)
            )
            assert cursor.fetchone()["activo"]
            completed.append(functionality_label(1))

            cursor.execute(
                """
                INSERT INTO producto
                    (nombre_producto, descripcion_producto, precio_producto,
                     activo, disponible, id_categoria)
                VALUES (%s, %s, %s, TRUE, TRUE, %s)
                RETURNING id_producto
                """,
                (f"Driver producto {suffix}", "Temporal", "12500.00", category_id),
            )
            product_id = cursor.fetchone()["id_producto"]
            cursor.execute(
                "UPDATE producto SET precio_producto = %s WHERE id_producto = %s",
                ("13000.00", product_id),
            )
            cursor.execute(
                "SELECT disponible FROM producto WHERE id_producto = %s", (product_id,)
            )
            assert cursor.fetchone()["disponible"]
            completed.append(functionality_label(2))

            table_number = 800_000_000 + int(suffix[:6], 16) % 100_000_000
            cursor.execute(
                "INSERT INTO mesa (numero_mesa, estado) VALUES (%s, 'LIBRE') "
                "RETURNING id_mesa",
                (table_number,),
            )
            table_id = cursor.fetchone()["id_mesa"]
            cursor.execute(
                "UPDATE mesa SET numero_mesa = %s WHERE id_mesa = %s",
                (table_number + 1, table_id),
            )
            cursor.execute("SELECT estado FROM mesa WHERE id_mesa = %s", (table_id,))
            assert str(cursor.fetchone()["estado"]) == "LIBRE"
            completed.append(functionality_label(3))

            users = {}
            password = "ClaveSegura123"
            password_hash = generate_password_hash(password)
            for role in sorted(required):
                login = f"driver_{role.lower()}_{suffix}"
                cursor.execute(
                    """
                    INSERT INTO usuario
                        (id_tipo_usuario, nombre, usuario_login,
                         contrasena_hash, correo, activo)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    RETURNING id_usuario
                    """,
                    (
                        roles[role],
                        f"Driver {role}",
                        login,
                        password_hash,
                        f"{login}@example.com",
                    ),
                )
                users[role] = (cursor.fetchone()["id_usuario"], login)
            waiter_id = users["MESERO"][0]
            kitchen_id = users["COCINA"][0]
            client_id = users["CLIENTE"][0]
            courier_id = users["DOMICILIARIO"][0]
            cursor.execute(
                "UPDATE usuario SET telefono = %s WHERE id_usuario = %s",
                ("3000000000", waiter_id),
            )
            cursor.execute(
                "SELECT t.descripcion FROM usuario u JOIN tipo_usuario t "
                "ON t.id_tipo_usuario = u.id_tipo_usuario WHERE u.id_usuario = %s",
                (waiter_id,),
            )
            assert cursor.fetchone()["descripcion"] == "MESERO"
            completed.append(functionality_label(4))

            cursor.execute(
                "INSERT INTO tipo_usuario (descripcion) VALUES (%s) "
                "RETURNING id_tipo_usuario",
                (f"DRIVER_ROL_{suffix}".upper(),),
            )
            temporary_role_id = cursor.fetchone()["id_tipo_usuario"]
            cursor.execute(
                "UPDATE tipo_usuario SET descripcion = %s "
                "WHERE id_tipo_usuario = %s",
                (f"DRIVER_ROL_ACTUALIZADO_{suffix}".upper(), temporary_role_id),
            )
            cursor.execute(
                "DELETE FROM tipo_usuario WHERE id_tipo_usuario = %s "
                "RETURNING id_tipo_usuario",
                (temporary_role_id,),
            )
            assert cursor.fetchone()["id_tipo_usuario"] == temporary_role_id
            completed.append(functionality_label(5))

            cursor.execute(
                "SELECT contrasena_hash, activo FROM usuario WHERE usuario_login = %s",
                (users["MESERO"][1],),
            )
            login_row = cursor.fetchone()
            assert login_row["activo"] and check_password_hash(
                login_row["contrasena_hash"], password
            )
            completed.append(functionality_label(6))

            cursor.execute(
                """
                INSERT INTO horario_empleado
                    (id_usuario, fecha, hora_inicio, hora_fin, observacion)
                VALUES (%s, %s, %s, %s, %s) RETURNING id_horario
                """,
                (waiter_id, date(2099, 10, 24), time(8), time(16), "Temporal"),
            )
            schedule_id = cursor.fetchone()["id_horario"]
            cursor.execute(
                "UPDATE horario_empleado SET hora_fin = %s WHERE id_horario = %s",
                (time(17), schedule_id),
            )
            cursor.execute(
                "DELETE FROM horario_empleado WHERE id_horario = %s RETURNING id_horario",
                (schedule_id,),
            )
            assert cursor.fetchone()["id_horario"] == schedule_id
            completed.append(functionality_label(7))

            cursor.execute(
                """
                INSERT INTO pedido
                    (id_mesa, id_mesero, tipo, estado, valor_total, observaciones)
                VALUES (%s, %s, 'SALON', 'PENDIENTE', 0, %s)
                RETURNING id_pedido
                """,
                (table_id, waiter_id, "Pedido Driver"),
            )
            salon_id = cursor.fetchone()["id_pedido"]
            cursor.execute("UPDATE mesa SET estado = 'OCUPADA' WHERE id_mesa = %s", (table_id,))
            cursor.execute(
                "INSERT INTO historial_estado "
                "(id_pedido, id_usuario_cambio, estado, observacion) "
                "VALUES (%s, %s, 'PENDIENTE', %s)",
                (salon_id, waiter_id, "Pedido registrado"),
            )
            cursor.execute(
                "UPDATE pedido SET observaciones = %s WHERE id_pedido = %s",
                ("Pedido Driver actualizado", salon_id),
            )
            completed.append(functionality_label(8))

            cursor.execute(
                """
                INSERT INTO pedido
                    (id_cliente, tipo, estado, valor_total, observaciones)
                VALUES (%s, 'DOMICILIO', 'PENDIENTE', 0, %s)
                RETURNING id_pedido
                """,
                (client_id, "Domicilio Driver"),
            )
            delivery_order_id = cursor.fetchone()["id_pedido"]
            cursor.execute(
                """
                INSERT INTO entrega
                    (id_pedido, direccion_entrega, telefono_contacto, estado)
                VALUES (%s, %s, %s, 'PENDIENTE_ASIGNACION')
                RETURNING id_entrega
                """,
                (delivery_order_id, "Calle Driver", "3000000000"),
            )
            delivery_id = cursor.fetchone()["id_entrega"]
            cursor.execute(
                "INSERT INTO historial_estado "
                "(id_pedido, id_usuario_cambio, estado, observacion) "
                "VALUES (%s, %s, 'PENDIENTE', %s)",
                (delivery_order_id, client_id, "Pedido registrado"),
            )
            completed.append(functionality_label(9))

            def add_detail(order_id):
                cursor.execute(
                    """
                    INSERT INTO detalle_pedido
                        (id_pedido, id_producto, cantidad, precio_unitario)
                    VALUES (%s, %s, 1, 13000.00)
                    RETURNING id_detalle
                    """,
                    (order_id, product_id),
                )
                return cursor.fetchone()["id_detalle"]

            detail_id = add_detail(salon_id)
            cursor.execute(
                "UPDATE detalle_pedido SET cantidad = 2, comentarios = %s "
                "WHERE id_detalle = %s",
                ("Actualizado", detail_id),
            )
            cursor.execute(
                "SELECT valor_total FROM pedido WHERE id_pedido = %s", (salon_id,)
            )
            assert str(cursor.fetchone()["valor_total"]) == "26000.00"
            cursor.execute(
                "DELETE FROM detalle_pedido WHERE id_detalle = %s RETURNING id_detalle",
                (detail_id,),
            )
            assert cursor.fetchone()["id_detalle"] == detail_id
            detail_id = add_detail(salon_id)
            add_detail(delivery_order_id)
            completed.append(functionality_label(10))

            cursor.execute(
                "SELECT id_pedido FROM pedido "
                "WHERE estado = %s::estado_pedido ORDER BY fecha_creacion",
                ("PENDIENTE",),
            )
            pending_ids = {row["id_pedido"] for row in cursor}
            assert {salon_id, delivery_order_id}.issubset(pending_ids)
            completed.append(functionality_label(11))

            for order_id in (salon_id, delivery_order_id):
                for state in ("EN_PREPARACION", "LISTO"):
                    cursor.execute(
                        "UPDATE pedido SET estado = %s::estado_pedido "
                        "WHERE id_pedido = %s",
                        (state, order_id),
                    )
                    cursor.execute(
                        "INSERT INTO historial_estado "
                        "(id_pedido, id_usuario_cambio, estado) "
                        "VALUES (%s, %s, %s::estado_pedido)",
                        (order_id, kitchen_id, state),
                    )
            completed.append(functionality_label(12))

            cursor.execute(
                "SELECT valor_total FROM pedido WHERE id_pedido = %s", (salon_id,)
            )
            total = cursor.fetchone()["valor_total"]
            cursor.execute(
                """
                INSERT INTO pago (id_pedido, metodo, estado, valor)
                VALUES (%s, 'EFECTIVO', 'PENDIENTE', %s)
                RETURNING id_pago
                """,
                (salon_id, total),
            )
            payment_id = cursor.fetchone()["id_pago"]
            cursor.execute(
                "UPDATE pago SET estado = 'APROBADO', id_usuario_confirma = %s, "
                "fecha_pago = CURRENT_TIMESTAMP WHERE id_pago = %s",
                (waiter_id, payment_id),
            )
            cursor.execute("SELECT estado FROM pago WHERE id_pago = %s", (payment_id,))
            assert str(cursor.fetchone()["estado"]) == "APROBADO"
            completed.append(functionality_label(13))

            cursor.execute(
                """
                UPDATE entrega
                SET id_domiciliario = %s, estado = 'ASIGNADA',
                    fecha_asignacion = CURRENT_TIMESTAMP
                WHERE id_entrega = %s RETURNING id_domiciliario
                """,
                (courier_id, delivery_id),
            )
            assert cursor.fetchone()["id_domiciliario"] == courier_id

            for state in ("RECOGIDA", "EN_CAMINO", "ENTREGADA"):
                cursor.execute(
                    "UPDATE entrega SET estado = %s::estado_entrega "
                    "WHERE id_entrega = %s",
                    (state, delivery_id),
                )
            cursor.execute(
                "UPDATE pedido SET estado = 'ENTREGADO' WHERE id_pedido = %s",
                (delivery_order_id,),
            )
            cursor.execute(
                "INSERT INTO historial_estado "
                "(id_pedido, id_usuario_cambio, estado, observacion) "
                "VALUES (%s, %s, 'ENTREGADO', %s)",
                (delivery_order_id, courier_id, "Entrega finalizada"),
            )
            completed.append(functionality_label(14))

            cursor.execute(
                "SELECT estado, id_usuario_cambio FROM historial_estado "
                "WHERE id_pedido = %s ORDER BY fecha, id_historial",
                (delivery_order_id,),
            )
            history = list(cursor)
            assert [str(row["estado"]) for row in history] == [
                "PENDIENTE",
                "EN_PREPARACION",
                "LISTO",
                "ENTREGADO",
            ]
            assert history[-1]["id_usuario_cambio"] == courier_id
            completed.append(functionality_label(15))

            cursor.execute(
                "UPDATE producto SET disponible = FALSE, activo = FALSE "
                "WHERE id_producto = %s",
                (product_id,),
            )
            cursor.execute(
                "UPDATE categoria SET activo = FALSE WHERE id_categoria = %s",
                (category_id,),
            )

        if len(completed) != 15:
            raise AssertionError(f"Se comprobaron {len(completed)} funcionalidades.")
        for label in completed:
            print(f"OK DRIVER {label}")
        print("OK: 15 funcionalidades verificadas con psycopg; se hara rollback.")
    finally:
        connection.rollback()
        connection.close()
        print("Rollback OK: PostgreSQL no conserva datos de la prueba Driver.")


if __name__ == "__main__":
    run()
