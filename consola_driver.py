"""CRUD directo con el driver psycopg, sin Flask ni SQLAlchemy ORM."""

import json
import os
import sys
from decimal import Decimal, InvalidOperation
from getpass import getpass

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

from functionalities import FUNCTIONALITY_NAMES, functionality_label
from order_rules import (
    CANCELLATION_ROLES,
    DELIVERY_ROLES,
    KITCHEN_ROLES,
    ORDER_TRANSITIONS,
)


load_dotenv()

OMITIDO = object()
ROLES_SISTEMA = {"ADMINISTRADOR", "COCINA", "MESERO", "CLIENTE", "DOMICILIARIO"}


def url_para_psycopg():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL en el archivo .env.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def conectar():
    """Abre una conexión usando exclusivamente el driver psycopg."""
    return psycopg.connect(url_para_psycopg(), row_factory=dict_row)


def configurar_terminal():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def titulo(texto):
    print(f"\n{texto}")


def mostrar(datos):
    print(json.dumps(datos, ensure_ascii=False, indent=2, default=str))


def mensaje_error(error):
    detalle = getattr(error.diag, "message_primary", None)
    return detalle or str(error)


def consultar(conexion, consulta, parametros=(), uno=False):
    try:
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchone() if uno else cursor.fetchall()
        mostrar(resultado)
        return resultado
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")
        return None


def escribir(conexion, consulta, parametros=(), mensaje="Operación realizada."):
    try:
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchone() if cursor.description else None
        conexion.commit()
        if resultado is None:
            print("No se encontró el registro o la operación no estaba permitida.")
        else:
            print(mensaje)
            mostrar(resultado)
        return resultado
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")
        return None


def leer_texto(etiqueta, obligatorio=True):
    while True:
        valor = input(f"{etiqueta}: ").strip()
        if valor or not obligatorio:
            return valor
        print("El valor es obligatorio.")


def leer_texto_opcional(etiqueta, permitir_nulo=False):
    ayuda = "Enter conserva"
    if permitir_nulo:
        ayuda += ", - elimina el valor"
    valor = input(f"{etiqueta} ({ayuda}): ").strip()
    if not valor:
        return OMITIDO
    if permitir_nulo and valor == "-":
        return None
    return valor


def leer_entero(etiqueta, obligatorio=True):
    while True:
        valor = input(f"{etiqueta}: ").strip()
        if not valor and not obligatorio:
            return OMITIDO
        try:
            numero = int(valor)
        except ValueError:
            print("Debes escribir un número entero.")
            continue
        if numero <= 0:
            print("El número debe ser mayor que cero.")
            continue
        return numero


def leer_booleano(etiqueta, obligatorio=True, predeterminado=None):
    while True:
        ayuda = "s/n"
        if predeterminado is True:
            ayuda = "S/n"
        elif predeterminado is False:
            ayuda = "s/N"
        elif not obligatorio:
            ayuda = "s/n, Enter conserva"
        valor = input(f"{etiqueta} [{ayuda}]: ").strip().lower()
        if not valor:
            if predeterminado is not None:
                return predeterminado
            if not obligatorio:
                return OMITIDO
        if valor in {"s", "si", "sí", "true", "1"}:
            return True
        if valor in {"n", "no", "false", "0"}:
            return False
        print("Responde s para sí o n para no.")


def confirmar(mensaje):
    return leer_booleano(mensaje, predeterminado=False)


def actualizar_campos(
    conexion, tabla, clave_primaria, registro_id, campos, retorno, conversiones=None
):
    campos = {clave: valor for clave, valor in campos.items() if valor is not OMITIDO}
    if not campos:
        print("No se ingresaron cambios.")
        return None

    conversiones = conversiones or {}
    asignaciones = []
    valores = []
    for columna, valor in campos.items():
        marcador = sql.Placeholder()
        if columna in conversiones:
            marcador = sql.SQL("{}::{}").format(
                marcador, sql.Identifier(conversiones[columna])
            )
        asignaciones.append(
            sql.SQL("{} = {}").format(sql.Identifier(columna), marcador)
        )
        valores.append(valor)

    consulta = sql.SQL("UPDATE {} SET {} WHERE {} = %s RETURNING {}").format(
        sql.Identifier(tabla),
        sql.SQL(", ").join(asignaciones),
        sql.Identifier(clave_primaria),
        sql.SQL(", ").join(sql.Identifier(columna) for columna in retorno),
    )
    valores.append(registro_id)
    return escribir(conexion, consulta, valores, "Registro actualizado.")


def ejecutar_submenu(conexion, nombre, opciones):
    while True:
        titulo(nombre)
        for clave, (descripcion, _) in opciones.items():
            print(f"{clave}. {descripcion}")
        print("0. Volver")
        opcion = input("\nSelecciona una opción: ").strip()
        if opcion == "0":
            return
        seleccion = opciones.get(opcion)
        if seleccion is None:
            print("Opción no válida.")
            continue
        seleccion[1](conexion)


# Categoría -----------------------------------------------------------------


def driver_crear_categoria(conexion):
    nombre = leer_texto("Nombre")
    activo = leer_booleano("¿Crear activa?", predeterminado=True)
    escribir(
        conexion,
        """
        INSERT INTO categoria (nombre, activo)
        SELECT %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM categoria WHERE LOWER(nombre) = LOWER(%s)
        )
        RETURNING id_categoria, nombre, activo
        """,
        (nombre, activo, nombre),
        "Categoría creada.",
    )


def driver_listar_categorias(conexion, incluir_inactivas=False):
    condicion = "" if incluir_inactivas else " WHERE activo IS TRUE"
    consultar(
        conexion,
        "SELECT id_categoria, nombre, activo FROM categoria"
        + condicion
        + " ORDER BY id_categoria",
    )


def driver_consultar_categoria(conexion):
    consultar(
        conexion,
        "SELECT id_categoria, nombre, activo FROM categoria WHERE id_categoria = %s",
        (leer_entero("ID de la categoría"),),
        uno=True,
    )


def driver_actualizar_categoria(conexion):
    categoria_id = leer_entero("ID de la categoría")
    actualizar_campos(
        conexion,
        "categoria",
        "id_categoria",
        categoria_id,
        {
            "nombre": leer_texto_opcional("Nuevo nombre"),
            "activo": leer_booleano("¿Activa?", obligatorio=False),
        },
        ("id_categoria", "nombre", "activo"),
    )


def driver_eliminar_categoria(conexion):
    categoria_id = leer_entero("ID de la categoría")
    print("DELETE administrativo: la categoría se conserva como inactiva.")
    if confirmar("¿Desactivar esta categoría?"):
        escribir(
            conexion,
            "UPDATE categoria SET activo = FALSE WHERE id_categoria = %s "
            "RETURNING id_categoria, nombre, activo",
            (categoria_id,),
            "Categoría desactivada.",
        )


def menu_driver_categorias(conexion):
    ejecutar_submenu(
        conexion,
        "01. GESTIONAR CATEGORÍAS - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Crear", driver_crear_categoria),
            "2": ("READ - Listar activas", driver_listar_categorias),
            "3": (
                "READ - Listar todas",
                lambda con: driver_listar_categorias(con, True),
            ),
            "4": ("READ - Consultar por ID", driver_consultar_categoria),
            "5": ("UPDATE - Actualizar", driver_actualizar_categoria),
            "6": ("DELETE lógico - Desactivar", driver_eliminar_categoria),
        },
    )


# Funcionalidades 04 y 05: Usuarios / Roles ---------------------------------


def driver_crear_rol(conexion):
    escribir(
        conexion,
        "INSERT INTO tipo_usuario (descripcion) VALUES (UPPER(%s)) "
        "RETURNING id_tipo_usuario, descripcion",
        (leer_texto("Descripción"),),
        "Rol creado.",
    )


def driver_listar_roles(conexion):
    consultar(
        conexion,
        "SELECT id_tipo_usuario, descripcion FROM tipo_usuario "
        "ORDER BY id_tipo_usuario",
    )


def driver_consultar_rol(conexion):
    consultar(
        conexion,
        "SELECT id_tipo_usuario, descripcion FROM tipo_usuario "
        "WHERE id_tipo_usuario = %s",
        (leer_entero("ID del rol"),),
        uno=True,
    )


def driver_actualizar_rol(conexion):
    rol_id = leer_entero("ID del rol")
    actual = consultar(
        conexion,
        "SELECT descripcion FROM tipo_usuario WHERE id_tipo_usuario = %s",
        (rol_id,),
        uno=True,
    )
    if not actual or actual["descripcion"] in ROLES_SISTEMA:
        print("Los roles base no pueden modificarse.")
        return
    escribir(
        conexion,
        "UPDATE tipo_usuario SET descripcion = UPPER(%s) "
        "WHERE id_tipo_usuario = %s RETURNING id_tipo_usuario, descripcion",
        (leer_texto("Nueva descripción"), rol_id),
        "Rol actualizado.",
    )


def driver_eliminar_rol(conexion):
    rol_id = leer_entero("ID del rol")
    actual = consultar(
        conexion,
        "SELECT descripcion FROM tipo_usuario WHERE id_tipo_usuario = %s",
        (rol_id,),
        uno=True,
    )
    if not actual or actual["descripcion"] in ROLES_SISTEMA:
        print("Los roles base no pueden eliminarse.")
        return
    if confirmar("¿Eliminar este rol sin usuarios asignados?"):
        escribir(
            conexion,
            "DELETE FROM tipo_usuario WHERE id_tipo_usuario = %s "
            "RETURNING id_tipo_usuario, descripcion",
            (rol_id,),
            "Rol eliminado.",
        )


def menu_driver_roles(conexion):
    ejecutar_submenu(
        conexion,
        "05. GESTIONAR ROLES - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Crear", driver_crear_rol),
            "2": ("READ - Listar", driver_listar_roles),
            "3": ("READ - Consultar por ID", driver_consultar_rol),
            "4": ("UPDATE - Actualizar", driver_actualizar_rol),
            "5": ("DELETE - Eliminar", driver_eliminar_rol),
        },
    )


def driver_crear_usuario(conexion):
    rol_id = leer_entero("ID del rol")
    nombre = leer_texto("Nombre completo")
    login = leer_texto("Usuario de acceso").lower()
    contrasena_hash = generate_password_hash(getpass("Contraseña (mínimo 8): "))
    correo = leer_texto("Correo (opcional)", obligatorio=False) or None
    telefono = leer_texto("Teléfono (opcional)", obligatorio=False) or None
    activo = leer_booleano("¿Crear activo?", predeterminado=True)
    escribir(
        conexion,
        """
        INSERT INTO usuario
            (id_tipo_usuario, nombre, usuario_login, contrasena_hash,
             correo, telefono, activo)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id_usuario, id_tipo_usuario, nombre, usuario_login,
                  correo, telefono, activo
        """,
        (rol_id, nombre, login, contrasena_hash, correo, telefono, activo),
        "Usuario creado.",
    )


def driver_listar_usuarios(conexion, incluir_inactivos=False):
    condicion = "" if incluir_inactivos else " WHERE u.activo IS TRUE"
    consultar(
        conexion,
        """
        SELECT u.id_usuario, u.id_tipo_usuario, t.descripcion AS tipo_usuario,
               u.nombre, u.usuario_login, u.correo, u.telefono, u.activo
        FROM usuario AS u
        JOIN tipo_usuario AS t ON t.id_tipo_usuario = u.id_tipo_usuario
        """
        + condicion
        + " ORDER BY u.id_usuario",
    )


def driver_consultar_usuario(conexion):
    consultar(
        conexion,
        """
        SELECT u.id_usuario, u.id_tipo_usuario, t.descripcion AS tipo_usuario,
               u.nombre, u.usuario_login, u.correo, u.telefono, u.activo
        FROM usuario AS u
        JOIN tipo_usuario AS t ON t.id_tipo_usuario = u.id_tipo_usuario
        WHERE u.id_usuario = %s
        """,
        (leer_entero("ID del usuario"),),
        uno=True,
    )


def driver_actualizar_usuario(conexion):
    usuario_id = leer_entero("ID del usuario")
    nueva_contrasena = getpass("Nueva contraseña (Enter conserva): ")
    campos = {
        "id_tipo_usuario": leer_entero("Nuevo ID de rol (Enter conserva)", False),
        "nombre": leer_texto_opcional("Nuevo nombre"),
        "usuario_login": leer_texto_opcional("Nuevo usuario de acceso"),
        "correo": leer_texto_opcional("Nuevo correo", True),
        "telefono": leer_texto_opcional("Nuevo teléfono", True),
        "activo": leer_booleano("¿Activo?", obligatorio=False),
        "contrasena_hash": (
            generate_password_hash(nueva_contrasena) if nueva_contrasena else OMITIDO
        ),
    }
    actualizar_campos(
        conexion,
        "usuario",
        "id_usuario",
        usuario_id,
        campos,
        (
            "id_usuario",
            "id_tipo_usuario",
            "nombre",
            "usuario_login",
            "correo",
            "telefono",
            "activo",
        ),
    )


def driver_eliminar_usuario(conexion):
    usuario_id = leer_entero("ID del usuario")
    print("DELETE administrativo: el usuario se conserva como inactivo.")
    if confirmar("¿Desactivar este usuario?"):
        escribir(
            conexion,
            "UPDATE usuario SET activo = FALSE WHERE id_usuario = %s "
            "RETURNING id_usuario, nombre, usuario_login, activo",
            (usuario_id,),
            "Usuario desactivado.",
        )


def menu_driver_usuarios(conexion):
    ejecutar_submenu(
        conexion,
        "04. GESTIONAR USUARIOS - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Crear", driver_crear_usuario),
            "2": ("READ - Listar activos", driver_listar_usuarios),
            "3": (
                "READ - Listar todos",
                lambda con: driver_listar_usuarios(con, True),
            ),
            "4": ("READ - Consultar por ID", driver_consultar_usuario),
            "5": ("UPDATE - Actualizar", driver_actualizar_usuario),
            "6": ("DELETE lógico - Desactivar", driver_eliminar_usuario),
        },
    )


# Horarios ------------------------------------------------------------------


def driver_crear_horario(conexion):
    escribir(
        conexion,
        """
        INSERT INTO horario_empleado
            (id_usuario, fecha, hora_inicio, hora_fin, observacion)
        VALUES (%s, %s::date, %s::time, %s::time, %s)
        RETURNING id_horario, id_usuario, fecha, hora_inicio, hora_fin, observacion
        """,
        (
            leer_entero("ID del empleado"),
            leer_texto("Fecha AAAA-MM-DD"),
            leer_texto("Hora inicial HH:MM"),
            leer_texto("Hora final HH:MM"),
            leer_texto("Observación (opcional)", False) or None,
        ),
        "Horario creado.",
    )


def driver_listar_horarios(conexion):
    consultar(
        conexion,
        """
        SELECT h.id_horario, h.id_usuario, u.nombre AS empleado, h.fecha,
               h.hora_inicio, h.hora_fin, h.observacion
        FROM horario_empleado AS h
        JOIN usuario AS u ON u.id_usuario = h.id_usuario
        ORDER BY h.fecha, h.hora_inicio
        """,
    )


def driver_consultar_horario(conexion):
    consultar(
        conexion,
        "SELECT id_horario, id_usuario, fecha, hora_inicio, hora_fin, observacion "
        "FROM horario_empleado WHERE id_horario = %s",
        (leer_entero("ID del horario"),),
        uno=True,
    )


def driver_actualizar_horario(conexion):
    horario_id = leer_entero("ID del horario")
    actualizar_campos(
        conexion,
        "horario_empleado",
        "id_horario",
        horario_id,
        {
            "id_usuario": leer_entero("Nuevo ID de empleado (Enter conserva)", False),
            "fecha": leer_texto_opcional("Nueva fecha AAAA-MM-DD"),
            "hora_inicio": leer_texto_opcional("Nueva hora inicial HH:MM"),
            "hora_fin": leer_texto_opcional("Nueva hora final HH:MM"),
            "observacion": leer_texto_opcional("Nueva observación", True),
        },
        ("id_horario", "id_usuario", "fecha", "hora_inicio", "hora_fin", "observacion"),
        {"fecha": "date", "hora_inicio": "time", "hora_fin": "time"},
    )


def driver_eliminar_horario(conexion):
    horario_id = leer_entero("ID del horario")
    if confirmar("¿Eliminar definitivamente este horario?"):
        escribir(
            conexion,
            "DELETE FROM horario_empleado WHERE id_horario = %s "
            "RETURNING id_horario, id_usuario, fecha, hora_inicio, hora_fin",
            (horario_id,),
            "Horario eliminado.",
        )


def menu_driver_horarios(conexion):
    ejecutar_submenu(
        conexion,
        "07. GESTIONAR HORARIOS - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Crear", driver_crear_horario),
            "2": ("READ - Listar", driver_listar_horarios),
            "3": ("READ - Consultar por ID", driver_consultar_horario),
            "4": ("UPDATE - Actualizar", driver_actualizar_horario),
            "5": ("DELETE - Eliminar", driver_eliminar_horario),
        },
    )


# Consulta de la entidad compartida Pedido ----------------------------------


def obtener_pedido(conexion, pedido_id):
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id_pedido, tipo, estado, valor_total "
                "FROM pedido WHERE id_pedido = %s",
                (pedido_id,),
            )
            pedido = cursor.fetchone()
        if pedido is None:
            print("Pedido no encontrado.")
        return pedido
    except psycopg.Error as error:
        conexion.rollback()
        print(f"No fue posible consultar Pedido: {mensaje_error(error)}")
        return None


# Pagos ---------------------------------------------------------------------


def driver_crear_pago(conexion):
    pedido_id = leer_entero("ID del pedido")
    pedido = obtener_pedido(conexion, pedido_id)
    if pedido is None:
        return
    valor_texto = leer_texto("Valor")
    try:
        valor = Decimal(valor_texto).quantize(Decimal("0.01"))
    except InvalidOperation:
        print("El valor debe ser numérico.")
        return
    if valor != pedido["valor_total"] or valor <= 0:
        print(f"El valor debe coincidir con el total: {pedido['valor_total']}.")
        return
    escribir(
        conexion,
        """
        INSERT INTO pago
            (id_pedido, metodo, estado, valor, referencia_transaccion)
        VALUES (%s, %s::metodo_pago, 'PENDIENTE', %s, %s)
        RETURNING id_pago, id_pedido, id_usuario_confirma, metodo, estado,
                  valor, referencia_transaccion, fecha_creacion, fecha_pago
        """,
        (
            pedido_id,
            leer_texto("Método (EFECTIVO o PSE)").upper(),
            valor,
            leer_texto("Referencia (opcional)", False) or None,
        ),
        "Pago creado.",
    )


def driver_listar_pagos(conexion):
    consultar(
        conexion,
        """
        SELECT id_pago, id_pedido, id_usuario_confirma, metodo, estado, valor,
               referencia_transaccion, fecha_creacion, fecha_pago
        FROM pago ORDER BY id_pago
        """,
    )


def driver_consultar_pago(conexion):
    consultar(
        conexion,
        """
        SELECT id_pago, id_pedido, id_usuario_confirma, metodo, estado, valor,
               referencia_transaccion, fecha_creacion, fecha_pago
        FROM pago WHERE id_pago = %s
        """,
        (leer_entero("ID del pago"),),
        uno=True,
    )


def driver_actualizar_pago(conexion):
    pago_id = leer_entero("ID del pago")
    nuevo_metodo = leer_texto_opcional("Nuevo método EFECTIVO/PSE")
    nuevo_valor = leer_texto_opcional("Nuevo valor")
    nueva_referencia = leer_texto_opcional("Nueva referencia", True)
    if nuevo_valor is not OMITIDO:
        try:
            valor = Decimal(nuevo_valor).quantize(Decimal("0.01"))
        except InvalidOperation:
            print("El valor debe ser numérico.")
            return
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pe.valor_total
                    FROM pago AS pa JOIN pedido AS pe
                      ON pe.id_pedido = pa.id_pedido
                    WHERE pa.id_pago = %s AND pa.estado = 'PENDIENTE'
                    """,
                    (pago_id,),
                )
                order = cursor.fetchone()
            if order is None or valor != order["valor_total"]:
                print("El valor debe coincidir con el total del pedido.")
                return
            nuevo_valor = valor
        except psycopg.Error as error:
            conexion.rollback()
            print(f"Error de PostgreSQL: {mensaje_error(error)}")
            return
    actualizar_campos(
        conexion,
        "pago",
        "id_pago",
        pago_id,
        {
            "metodo": nuevo_metodo,
            "valor": nuevo_valor,
            "referencia_transaccion": nueva_referencia,
        },
        ("id_pago", "id_pedido", "metodo", "estado", "valor", "referencia_transaccion"),
        {"metodo": "metodo_pago"},
    )


def driver_cambiar_estado_pago(conexion):
    pago_id = leer_entero("ID del pago")
    estado = leer_texto("Nuevo estado (APROBADO o RECHAZADO)").upper()
    usuario_id = leer_entero("ID del usuario que confirma", obligatorio=False)
    usuario_id = None if usuario_id is OMITIDO else usuario_id
    escribir(
        conexion,
        """
        UPDATE pago
        SET estado = %s::estado_pago,
            id_usuario_confirma = COALESCE(%s, id_usuario_confirma),
            fecha_pago = CASE WHEN %s = 'APROBADO' THEN CURRENT_TIMESTAMP ELSE NULL END
        WHERE id_pago = %s AND estado = 'PENDIENTE'
        RETURNING id_pago, id_pedido, id_usuario_confirma, metodo, estado,
                  valor, referencia_transaccion, fecha_creacion, fecha_pago
        """,
        (estado, usuario_id, estado, pago_id),
        "Estado del pago actualizado.",
    )


def driver_eliminar_pago(conexion):
    pago_id = leer_entero("ID del pago")
    if confirmar("¿Eliminar este pago PENDIENTE?"):
        escribir(
            conexion,
            "DELETE FROM pago WHERE id_pago = %s AND estado = 'PENDIENTE' "
            "RETURNING id_pago, id_pedido, metodo, estado, valor",
            (pago_id,),
            "Pago pendiente eliminado.",
        )


def menu_driver_pagos(conexion):
    ejecutar_submenu(
        conexion,
        "13. GESTIONAR PAGOS - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Crear", driver_crear_pago),
            "2": ("READ - Listar", driver_listar_pagos),
            "3": ("READ - Consultar por ID", driver_consultar_pago),
            "4": ("UPDATE - Actualizar", driver_actualizar_pago),
            "5": ("UPDATE - Aprobar o rechazar", driver_cambiar_estado_pago),
            "6": ("DELETE - Eliminar pendiente", driver_eliminar_pago),
        },
    )


# Entregas ------------------------------------------------------------------


def driver_crear_entrega(conexion):
    pedido_id = leer_entero("ID del pedido")
    pedido = obtener_pedido(conexion, pedido_id)
    if pedido is None:
        return
    if str(pedido["tipo"]).upper() != "DOMICILIO":
        print("Solo un pedido de tipo DOMICILIO puede tener entrega.")
        return
    domiciliario = leer_entero("ID del domiciliario (Enter = sin asignar)", False)
    domiciliario = None if domiciliario is OMITIDO else domiciliario
    estado = "ASIGNADA" if domiciliario else "PENDIENTE_ASIGNACION"
    escribir(
        conexion,
        """
        INSERT INTO entrega
            (id_pedido, id_domiciliario, direccion_entrega, telefono_contacto,
             estado, fecha_asignacion, observacion)
        VALUES (%s, %s, %s, %s, %s::estado_entrega,
                CASE WHEN %s IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END, %s)
        RETURNING id_entrega, id_pedido, id_domiciliario, direccion_entrega,
                  telefono_contacto, estado, fecha_asignacion, observacion
        """,
        (
            pedido_id,
            domiciliario,
            leer_texto("Dirección"),
            leer_texto("Teléfono"),
            estado,
            domiciliario,
            leer_texto("Observación (opcional)", False) or None,
        ),
        "Entrega creada.",
    )


def driver_listar_entregas(conexion):
    consultar(
        conexion,
        """
        SELECT id_entrega, id_pedido, id_domiciliario, direccion_entrega,
               telefono_contacto, estado, fecha_asignacion, fecha_recogida,
               fecha_entrega, observacion
        FROM entrega ORDER BY id_entrega
        """,
    )


def driver_consultar_entrega(conexion):
    consultar(
        conexion,
        """
        SELECT id_entrega, id_pedido, id_domiciliario, direccion_entrega,
               telefono_contacto, estado, fecha_asignacion, fecha_recogida,
               fecha_entrega, observacion
        FROM entrega WHERE id_entrega = %s
        """,
        (leer_entero("ID de la entrega"),),
        uno=True,
    )


def driver_actualizar_entrega(conexion):
    entrega_id = leer_entero("ID de la entrega")
    actualizar_campos(
        conexion,
        "entrega",
        "id_entrega",
        entrega_id,
        {
            "id_domiciliario": leer_entero(
                "Nuevo ID de domiciliario (Enter conserva)", False
            ),
            "direccion_entrega": leer_texto_opcional("Nueva dirección"),
            "telefono_contacto": leer_texto_opcional("Nuevo teléfono"),
            "observacion": leer_texto_opcional("Nueva observación", True),
        },
        (
            "id_entrega",
            "id_pedido",
            "id_domiciliario",
            "direccion_entrega",
            "telefono_contacto",
            "estado",
            "observacion",
        ),
    )


def driver_cambiar_estado_entrega(conexion):
    entrega_id = leer_entero("ID de la entrega")
    estado = leer_texto(
        "Nuevo estado (ASIGNADA, RECOGIDA, EN_CAMINO, ENTREGADA o CON_INCIDENCIA)"
    ).upper()
    transitions = {
        "PENDIENTE_ASIGNACION": {"ASIGNADA"},
        "ASIGNADA": {"RECOGIDA", "CON_INCIDENCIA"},
        "RECOGIDA": {"EN_CAMINO", "CON_INCIDENCIA"},
        "EN_CAMINO": {"ENTREGADA", "CON_INCIDENCIA"},
        "ENTREGADA": set(),
        "CON_INCIDENCIA": {"ASIGNADA"},
    }
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.id_pedido, e.id_domiciliario, e.estado,
                       p.estado AS estado_pedido
                FROM entrega AS e JOIN pedido AS p ON p.id_pedido = e.id_pedido
                WHERE e.id_entrega = %s FOR UPDATE
                """,
                (entrega_id,),
            )
            delivery = cursor.fetchone()
            if delivery is None:
                print("Entrega no encontrada.")
                conexion.rollback()
                return
            current = str(delivery["estado"])
            if estado not in transitions[current]:
                print(f"No se permite pasar de {current} a {estado}.")
                conexion.rollback()
                return
            if estado == "ASIGNADA" and str(delivery["estado_pedido"]) != "LISTO":
                print("El pedido debe estar LISTO antes de asignar la entrega.")
                conexion.rollback()
                return
            if estado == "ASIGNADA" and delivery["id_domiciliario"] is None:
                print("Primero debes asignar un domiciliario.")
                conexion.rollback()
                return
            cursor.execute(
                """
                UPDATE entrega
                SET estado = %s::estado_entrega,
                    fecha_asignacion = CASE WHEN %s = 'ASIGNADA'
                        THEN CURRENT_TIMESTAMP ELSE fecha_asignacion END,
                    fecha_recogida = CASE WHEN %s = 'RECOGIDA'
                        THEN CURRENT_TIMESTAMP ELSE fecha_recogida END,
                    fecha_entrega = CASE WHEN %s = 'ENTREGADA'
                        THEN CURRENT_TIMESTAMP ELSE fecha_entrega END
                WHERE id_entrega = %s
                RETURNING id_entrega, id_pedido, id_domiciliario, estado,
                          fecha_asignacion, fecha_recogida, fecha_entrega
                """,
                (estado, estado, estado, estado, entrega_id),
            )
            updated = cursor.fetchone()
            if estado == "ENTREGADA":
                cursor.execute(
                    "UPDATE pedido SET estado = 'ENTREGADO' "
                    "WHERE id_pedido = %s",
                    (delivery["id_pedido"],),
                )
                cursor.execute(
                    """
                    INSERT INTO historial_estado
                        (id_pedido, id_usuario_cambio, estado, observacion)
                    VALUES (%s, %s, 'ENTREGADO',
                            'Entrega finalizada por el domiciliario.')
                    """,
                    (delivery["id_pedido"], delivery["id_domiciliario"]),
                )
        conexion.commit()
        print("Estado de entrega actualizado.")
        mostrar(updated)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_eliminar_entrega(conexion):
    entrega_id = leer_entero("ID de la entrega")
    if confirmar("¿Eliminar esta entrega PENDIENTE_ASIGNACION?"):
        escribir(
            conexion,
            "DELETE FROM entrega WHERE id_entrega = %s "
            "AND estado = 'PENDIENTE_ASIGNACION' "
            "RETURNING id_entrega, id_pedido, estado",
            (entrega_id,),
            "Entrega pendiente eliminada.",
        )


def menu_driver_entregas(conexion):
    ejecutar_submenu(
        conexion,
        "14. GESTIONAR DOMICILIOS Y ENTREGAS - DRIVER PSYCOPG",
        {
            "1": ("Asignar pedido a domiciliario", driver_asignar_domiciliario),
            "2": ("CREATE - Crear entrega", driver_crear_entrega),
            "3": ("READ - Listar entregas", driver_listar_entregas),
            "4": ("READ - Consultar entrega por ID", driver_consultar_entrega),
            "5": ("UPDATE - Actualizar entrega", driver_actualizar_entrega),
            "6": ("UPDATE - Cambiar estado", driver_cambiar_estado_entrega),
            "7": ("DELETE - Eliminar pendiente", driver_eliminar_entrega),
        },
    )


# Productos -----------------------------------------------------------------


def driver_crear_producto(conexion):
    nombre = leer_texto("Nombre")
    descripcion = leer_texto("Descripción (opcional)", False) or None
    precio = leer_texto("Precio")
    categoria_id = leer_entero("ID de la categoría")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT activo FROM categoria WHERE id_categoria = %s",
                (categoria_id,),
            )
            categoria = cursor.fetchone()
            if categoria is None or not categoria["activo"]:
                print("La categoría no existe o está inactiva.")
                return
            cursor.execute(
                """
                INSERT INTO producto
                    (nombre_producto, descripcion_producto, precio_producto,
                     activo, disponible, id_categoria)
                VALUES (%s, %s, %s, TRUE, TRUE, %s)
                RETURNING id_producto, nombre_producto, descripcion_producto,
                          precio_producto, activo, disponible, id_categoria
                """,
                (nombre, descripcion, precio, categoria_id),
            )
            producto = cursor.fetchone()
        conexion.commit()
        print("Producto creado.")
        mostrar(producto)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_listar_productos(conexion):
    consultar(
        conexion,
        """
        SELECT p.id_producto, p.nombre_producto, p.descripcion_producto,
               p.precio_producto, p.activo, p.disponible, p.id_categoria,
               c.nombre AS categoria
        FROM producto AS p
        JOIN categoria AS c ON c.id_categoria = p.id_categoria
        WHERE p.activo IS TRUE AND p.disponible IS TRUE AND c.activo IS TRUE
        ORDER BY p.id_producto
        """,
    )


def driver_consultar_producto(conexion):
    consultar(
        conexion,
        """
        SELECT p.id_producto, p.nombre_producto, p.descripcion_producto,
               p.precio_producto, p.activo, p.disponible, p.id_categoria,
               c.nombre AS categoria
        FROM producto AS p
        JOIN categoria AS c ON c.id_categoria = p.id_categoria
        WHERE p.id_producto = %s
        """,
        (leer_entero("ID del producto"),),
        uno=True,
    )


def driver_actualizar_producto(conexion):
    producto_id = leer_entero("ID del producto")
    actualizar_campos(
        conexion,
        "producto",
        "id_producto",
        producto_id,
        {
            "nombre_producto": leer_texto_opcional("Nuevo nombre"),
            "descripcion_producto": leer_texto_opcional("Descripción", True),
            "precio_producto": leer_texto_opcional("Nuevo precio"),
            "id_categoria": leer_entero(
                "Nuevo ID de categoría (Enter conserva)", obligatorio=False
            ),
        },
        (
            "id_producto",
            "nombre_producto",
            "descripcion_producto",
            "precio_producto",
            "activo",
            "disponible",
            "id_categoria",
        ),
    )


def driver_cambiar_disponibilidad_producto(conexion):
    producto_id = leer_entero("ID del producto")
    disponible = leer_booleano("¿Debe quedar disponible?")
    escribir(
        conexion,
        "UPDATE producto SET disponible = %s "
        "WHERE id_producto = %s AND activo IS TRUE "
        "RETURNING id_producto, nombre_producto, activo, disponible",
        (disponible, producto_id),
        "Disponibilidad actualizada.",
    )


def driver_eliminar_producto(conexion):
    producto_id = leer_entero("ID del producto")
    if confirmar("¿Desactivar lógicamente este producto?"):
        escribir(
            conexion,
            "UPDATE producto SET activo = FALSE, disponible = FALSE "
            "WHERE id_producto = %s "
            "RETURNING id_producto, nombre_producto, activo, disponible",
            (producto_id,),
            "Producto desactivado.",
        )


def menu_driver_productos(conexion):
    ejecutar_submenu(
        conexion,
        "02. GESTIONAR PRODUCTOS Y MENÚ - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Crear", driver_crear_producto),
            "2": ("READ - Listar menú disponible", driver_listar_productos),
            "3": ("READ - Consultar por ID", driver_consultar_producto),
            "4": ("UPDATE - Actualizar producto o precio", driver_actualizar_producto),
            "5": ("UPDATE - Cambiar disponibilidad", driver_cambiar_disponibilidad_producto),
            "6": ("DELETE lógico - Desactivar", driver_eliminar_producto),
        },
    )


# Mesas ---------------------------------------------------------------------


def driver_crear_mesa(conexion):
    escribir(
        conexion,
        "INSERT INTO mesa (numero_mesa, estado) VALUES (%s, 'LIBRE') "
        "RETURNING id_mesa, numero_mesa, estado",
        (leer_entero("Número de mesa"),),
        "Mesa creada.",
    )


def driver_listar_mesas(conexion):
    consultar(
        conexion,
        "SELECT id_mesa, numero_mesa, estado FROM mesa ORDER BY numero_mesa",
    )


def driver_consultar_mesa(conexion):
    consultar(
        conexion,
        "SELECT id_mesa, numero_mesa, estado FROM mesa WHERE id_mesa = %s",
        (leer_entero("ID de la mesa"),),
        uno=True,
    )


def driver_actualizar_mesa(conexion):
    escribir(
        conexion,
        "UPDATE mesa SET numero_mesa = %s WHERE id_mesa = %s "
        "RETURNING id_mesa, numero_mesa, estado",
        (leer_entero("Nuevo número"), leer_entero("ID de la mesa")),
        "Mesa actualizada.",
    )


def driver_cambiar_estado_mesa(conexion):
    estado = leer_texto("Estado (LIBRE, OCUPADA o FUERA_DE_SERVICIO)").upper()
    escribir(
        conexion,
        "UPDATE mesa SET estado = %s::estado_mesa WHERE id_mesa = %s "
        "RETURNING id_mesa, numero_mesa, estado",
        (estado, leer_entero("ID de la mesa")),
        "Estado de mesa actualizado.",
    )


def menu_driver_mesas(conexion):
    ejecutar_submenu(
        conexion,
        "03. GESTIONAR MESAS - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Registrar", driver_crear_mesa),
            "2": ("READ - Listar", driver_listar_mesas),
            "3": ("READ - Consultar por ID", driver_consultar_mesa),
            "4": ("UPDATE - Cambiar número", driver_actualizar_mesa),
            "5": ("UPDATE - Cambiar estado", driver_cambiar_estado_mesa),
        },
    )


# Autenticación -------------------------------------------------------------


def driver_iniciar_sesion(conexion):
    login = leer_texto("Usuario de acceso").lower()
    password = getpass("Contraseña: ")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id_usuario, u.nombre, u.usuario_login, u.contrasena_hash,
                       u.activo, t.descripcion AS rol
                FROM usuario AS u
                JOIN tipo_usuario AS t
                  ON t.id_tipo_usuario = u.id_tipo_usuario
                WHERE LOWER(u.usuario_login) = LOWER(%s)
                """,
                (login,),
            )
            user = cursor.fetchone()
        if user is None or not check_password_hash(user["contrasena_hash"], password):
            print("Credenciales inválidas.")
            return
        if not user["activo"]:
            print("El usuario está inactivo.")
            return
        user.pop("contrasena_hash", None)
        print("Credenciales válidas.")
        mostrar(user)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


# Pedidos, detalle, Cocina e historial --------------------------------------


def driver_listar_pedidos(conexion):
    estado = leer_texto("Estado (Enter = todos)", False).upper()
    consulta = """
        SELECT id_pedido, id_mesa, id_mesero, id_cliente, tipo, estado,
               valor_total, observaciones, fecha_creacion,
               fecha_ultima_actualizacion
        FROM pedido
    """
    parametros = ()
    if estado:
        consulta += " WHERE estado = %s::estado_pedido"
        parametros = (estado,)
    consulta += " ORDER BY fecha_creacion, id_pedido"
    consultar(conexion, consulta, parametros)


def driver_consultar_pedido(conexion):
    consultar(
        conexion,
        """
        SELECT id_pedido, id_mesa, id_mesero, id_cliente, tipo, estado,
               valor_total, observaciones, fecha_creacion,
               fecha_ultima_actualizacion
        FROM pedido WHERE id_pedido = %s
        """,
        (leer_entero("ID del pedido"),),
        uno=True,
    )


def driver_registrar_pedido_salon(conexion):
    mesa_id = leer_entero("ID de la mesa libre")
    mesero_id = leer_entero("ID del mesero")
    observaciones = leer_texto("Observaciones (opcional)", False) or None
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM mesa WHERE id_mesa = %s FOR UPDATE", (mesa_id,)
            )
            mesa = cursor.fetchone()
            if mesa is None or str(mesa["estado"]) != "LIBRE":
                print("La mesa no existe o no está libre.")
                conexion.rollback()
                return
            cursor.execute(
                """
                SELECT t.descripcion, u.activo
                FROM usuario AS u JOIN tipo_usuario AS t
                  ON t.id_tipo_usuario = u.id_tipo_usuario
                WHERE u.id_usuario = %s
                """,
                (mesero_id,),
            )
            mesero = cursor.fetchone()
            if mesero is None or not mesero["activo"] or mesero["descripcion"] != "MESERO":
                print("El usuario no es un mesero activo.")
                conexion.rollback()
                return
            cursor.execute(
                """
                INSERT INTO pedido
                    (id_mesa, id_mesero, tipo, estado, valor_total, observaciones)
                VALUES (%s, %s, 'SALON', 'PENDIENTE', 0, %s)
                RETURNING id_pedido, id_mesa, id_mesero, tipo, estado, valor_total
                """,
                (mesa_id, mesero_id, observaciones),
            )
            order = cursor.fetchone()
            cursor.execute("UPDATE mesa SET estado = 'OCUPADA' WHERE id_mesa = %s", (mesa_id,))
            cursor.execute(
                """
                INSERT INTO historial_estado
                    (id_pedido, id_usuario_cambio, estado, observacion)
                VALUES (%s, %s, 'PENDIENTE', 'Pedido registrado.')
                """,
                (order["id_pedido"], mesero_id),
            )
        conexion.commit()
        print("Pedido en salón registrado.")
        mostrar(order)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_registrar_pedido_domicilio(conexion):
    cliente_id = leer_entero("ID del cliente")
    direccion = leer_texto("Dirección de entrega")
    telefono = leer_texto("Teléfono de contacto")
    observaciones = leer_texto("Observaciones (opcional)", False) or None
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.descripcion, u.activo
                FROM usuario AS u JOIN tipo_usuario AS t
                  ON t.id_tipo_usuario = u.id_tipo_usuario
                WHERE u.id_usuario = %s
                """,
                (cliente_id,),
            )
            client = cursor.fetchone()
            if client is None or not client["activo"] or client["descripcion"] != "CLIENTE":
                print("El usuario no es un cliente activo.")
                conexion.rollback()
                return
            cursor.execute(
                """
                INSERT INTO pedido
                    (id_cliente, tipo, estado, valor_total, observaciones)
                VALUES (%s, 'DOMICILIO', 'PENDIENTE', 0, %s)
                RETURNING id_pedido, id_cliente, tipo, estado, valor_total
                """,
                (cliente_id, observaciones),
            )
            order = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO entrega
                    (id_pedido, direccion_entrega, telefono_contacto, estado)
                VALUES (%s, %s, %s, 'PENDIENTE_ASIGNACION')
                """,
                (order["id_pedido"], direccion, telefono),
            )
            cursor.execute(
                """
                INSERT INTO historial_estado
                    (id_pedido, id_usuario_cambio, estado, observacion)
                VALUES (%s, %s, 'PENDIENTE', 'Pedido registrado.')
                """,
                (order["id_pedido"], cliente_id),
            )
        conexion.commit()
        print("Pedido a domicilio registrado.")
        mostrar(order)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_actualizar_observaciones_pedido(conexion):
    escribir(
        conexion,
        "UPDATE pedido SET observaciones = %s "
        "WHERE id_pedido = %s AND estado = 'PENDIENTE' "
        "RETURNING id_pedido, tipo, estado, observaciones",
        (leer_texto("Nuevas observaciones"), leer_entero("ID del pedido")),
        "Pedido actualizado.",
    )


def driver_cancelar_pedido(conexion):
    pedido_id = leer_entero("ID del pedido")
    usuario_id = leer_entero("ID del usuario responsable")
    motivo = leer_texto("Motivo de cancelación")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.activo, t.descripcion AS rol
                FROM usuario AS u JOIN tipo_usuario AS t
                  ON t.id_tipo_usuario = u.id_tipo_usuario
                WHERE u.id_usuario = %s
                """,
                (usuario_id,),
            )
            actor = cursor.fetchone()
            if actor is None or not actor["activo"] or actor["rol"] not in CANCELLATION_ROLES:
                print("El usuario no puede cancelar pedidos.")
                conexion.rollback()
                return
            cursor.execute(
                """
                UPDATE pedido SET estado = 'CANCELADO'
                WHERE id_pedido = %s AND estado IN ('PENDIENTE', 'EN_PREPARACION')
                RETURNING id_pedido, id_mesa, tipo, estado
                """,
                (pedido_id,),
            )
            order = cursor.fetchone()
            if order is None:
                print("El pedido no existe o ya no puede cancelarse.")
                conexion.rollback()
                return
            cursor.execute(
                """
                INSERT INTO historial_estado
                    (id_pedido, id_usuario_cambio, estado, observacion)
                VALUES (%s, %s, 'CANCELADO', %s)
                """,
                (pedido_id, usuario_id, motivo),
            )
            if order["id_mesa"] is not None:
                cursor.execute(
                    "UPDATE mesa SET estado = 'LIBRE' WHERE id_mesa = %s",
                    (order["id_mesa"],),
                )
        conexion.commit()
        print("Pedido cancelado.")
        mostrar(order)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def menu_driver_pedidos_salon(conexion):
    ejecutar_submenu(
        conexion,
        "08. REGISTRAR PEDIDOS EN SALÓN - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Registrar pedido", driver_registrar_pedido_salon),
            "2": ("READ - Listar", driver_listar_pedidos),
            "3": ("READ - Consultar", driver_consultar_pedido),
            "4": ("UPDATE - Observaciones", driver_actualizar_observaciones_pedido),
            "5": ("DELETE lógico - Cancelar", driver_cancelar_pedido),
        },
    )


def menu_driver_pedidos_domicilio(conexion):
    ejecutar_submenu(
        conexion,
        "09. REGISTRAR PEDIDOS A DOMICILIO - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Registrar pedido", driver_registrar_pedido_domicilio),
            "2": ("READ - Listar", driver_listar_pedidos),
            "3": ("READ - Consultar", driver_consultar_pedido),
            "4": ("UPDATE - Observaciones", driver_actualizar_observaciones_pedido),
            "5": ("DELETE lógico - Cancelar", driver_cancelar_pedido),
        },
    )


def driver_agregar_detalle(conexion):
    pedido_id = leer_entero("ID del pedido")
    producto_id = leer_entero("ID del producto")
    cantidad = leer_entero("Cantidad")
    comentarios = leer_texto("Comentarios (opcional)", False) or None
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado FROM pedido WHERE id_pedido = %s", (pedido_id,))
            order = cursor.fetchone()
            if order is None or str(order["estado"]) != "PENDIENTE":
                print("El pedido no existe o ya no admite modificaciones.")
                conexion.rollback()
                return
            cursor.execute(
                """
                SELECT p.precio_producto
                FROM producto AS p JOIN categoria AS c
                  ON c.id_categoria = p.id_categoria
                WHERE p.id_producto = %s AND p.activo IS TRUE
                  AND p.disponible IS TRUE AND c.activo IS TRUE
                """,
                (producto_id,),
            )
            product = cursor.fetchone()
            if product is None:
                print("El producto no existe o no está disponible.")
                conexion.rollback()
                return
            cursor.execute(
                """
                INSERT INTO detalle_pedido
                    (id_pedido, id_producto, cantidad, precio_unitario, comentarios)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_detalle, id_pedido, id_producto, cantidad,
                          precio_unitario, comentarios
                """,
                (pedido_id, producto_id, cantidad, product["precio_producto"], comentarios),
            )
            detail = cursor.fetchone()
        conexion.commit()
        print("Producto agregado; el total fue recalculado por PostgreSQL.")
        mostrar(detail)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_listar_detalles(conexion):
    pedido_id = leer_entero("ID del pedido")
    consultar(
        conexion,
        """
        SELECT d.id_detalle, d.id_pedido, d.id_producto,
               p.nombre_producto, d.cantidad, d.precio_unitario,
               d.cantidad * d.precio_unitario AS subtotal, d.comentarios
        FROM detalle_pedido AS d
        JOIN producto AS p ON p.id_producto = d.id_producto
        WHERE d.id_pedido = %s ORDER BY d.id_detalle
        """,
        (pedido_id,),
    )


def driver_actualizar_detalle(conexion):
    escribir(
        conexion,
        "UPDATE detalle_pedido SET cantidad = %s, comentarios = %s "
        "WHERE id_detalle = %s "
        "RETURNING id_detalle, id_pedido, id_producto, cantidad, "
        "precio_unitario, comentarios",
        (
            leer_entero("Nueva cantidad"),
            leer_texto("Comentarios (opcional)", False) or None,
            leer_entero("ID del detalle"),
        ),
        "Detalle actualizado; total recalculado.",
    )


def driver_eliminar_detalle(conexion):
    detalle_id = leer_entero("ID del detalle")
    if confirmar("¿Quitar este producto del pedido?"):
        escribir(
            conexion,
            "DELETE FROM detalle_pedido WHERE id_detalle = %s "
            "RETURNING id_detalle, id_pedido, id_producto",
            (detalle_id,),
            "Detalle eliminado; total recalculado.",
        )


def menu_driver_detalles(conexion):
    ejecutar_submenu(
        conexion,
        "10. GESTIONAR DETALLE DEL PEDIDO - DRIVER PSYCOPG",
        {
            "1": ("CREATE - Agregar producto", driver_agregar_detalle),
            "2": ("READ - Consultar detalle", driver_listar_detalles),
            "3": ("UPDATE - Modificar cantidad", driver_actualizar_detalle),
            "4": ("DELETE - Quitar producto", driver_eliminar_detalle),
        },
    )


def driver_consultar_cocina(conexion):
    estado = leer_texto("Estado (Enter = activos)", False).upper()
    consulta = """
        SELECT pe.id_pedido, pe.tipo, pe.estado, pe.valor_total,
               pe.fecha_creacion,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'producto', pr.nombre_producto,
                           'cantidad', d.cantidad,
                           'comentarios', d.comentarios
                       ) ORDER BY d.id_detalle
                   ) FILTER (WHERE d.id_detalle IS NOT NULL),
                   '[]'::json
               ) AS detalles
        FROM pedido AS pe
        LEFT JOIN detalle_pedido AS d ON d.id_pedido = pe.id_pedido
        LEFT JOIN producto AS pr ON pr.id_producto = d.id_producto
    """
    parametros = ()
    if estado:
        consulta += " WHERE pe.estado = %s::estado_pedido"
        parametros = (estado,)
    else:
        consulta += " WHERE pe.estado IN ('PENDIENTE', 'EN_PREPARACION', 'LISTO')"
    consulta += " GROUP BY pe.id_pedido ORDER BY pe.fecha_creacion, pe.id_pedido"
    consultar(conexion, consulta, parametros)


def driver_actualizar_estado_pedido(conexion):
    pedido_id = leer_entero("ID del pedido")
    nuevo_estado = leer_texto("Nuevo estado").upper()
    usuario_id = leer_entero("ID del usuario responsable")
    observacion = leer_texto("Observación (opcional)", False) or None
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id_mesa, id_mesero, id_cliente, tipo, estado "
                "FROM pedido WHERE id_pedido = %s FOR UPDATE",
                (pedido_id,),
            )
            order = cursor.fetchone()
            if order is None:
                print("Pedido no encontrado.")
                conexion.rollback()
                return
            actual = str(order["estado"])
            if nuevo_estado not in ORDER_TRANSITIONS.get(actual, set()):
                print(f"No se permite pasar de {actual} a {nuevo_estado}.")
                conexion.rollback()
                return
            cursor.execute(
                """
                SELECT u.activo, t.descripcion AS rol
                FROM usuario AS u JOIN tipo_usuario AS t
                  ON t.id_tipo_usuario = u.id_tipo_usuario
                WHERE u.id_usuario = %s
                """,
                (usuario_id,),
            )
            actor = cursor.fetchone()
            if actor is None or not actor["activo"]:
                print("El usuario responsable no existe o está inactivo.")
                conexion.rollback()
                return
            if nuevo_estado in {"EN_PREPARACION", "LISTO"}:
                roles_permitidos = KITCHEN_ROLES
            elif nuevo_estado == "ENTREGADO":
                roles_permitidos = (
                    DELIVERY_ROLES
                    if str(order["tipo"]) == "DOMICILIO"
                    else {"MESERO", "ADMINISTRADOR"}
                )
            elif nuevo_estado == "CANCELADO":
                roles_permitidos = CANCELLATION_ROLES
            else:
                roles_permitidos = {"ADMINISTRADOR"}
            if actor["rol"] not in roles_permitidos:
                print("El rol del usuario no permite este cambio de estado.")
                conexion.rollback()
                return
            if nuevo_estado in {"EN_PREPARACION", "LISTO"}:
                cursor.execute(
                    "SELECT count(*) AS total FROM detalle_pedido WHERE id_pedido = %s",
                    (pedido_id,),
                )
                if cursor.fetchone()["total"] == 0:
                    print("No se puede preparar un pedido sin productos.")
                    conexion.rollback()
                    return
            if nuevo_estado == "CANCELADO" and not observacion:
                print("La cancelación requiere una observación.")
                conexion.rollback()
                return
            cursor.execute(
                "UPDATE pedido SET estado = %s::estado_pedido "
                "WHERE id_pedido = %s RETURNING id_pedido, tipo, estado, valor_total",
                (nuevo_estado, pedido_id),
            )
            updated = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO historial_estado
                    (id_pedido, id_usuario_cambio, estado, observacion)
                VALUES (%s, %s, %s::estado_pedido, %s)
                """,
                (pedido_id, usuario_id, nuevo_estado, observacion),
            )
            if nuevo_estado in {"ENTREGADO", "CANCELADO"} and order["id_mesa"]:
                cursor.execute(
                    "UPDATE mesa SET estado = 'LIBRE' WHERE id_mesa = %s",
                    (order["id_mesa"],),
                )
        conexion.commit()
        print("Estado del pedido actualizado e historial registrado.")
        mostrar(updated)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_asignar_domiciliario(conexion):
    pedido_id = leer_entero("ID del pedido DOMICILIO y LISTO")
    domiciliario_id = leer_entero("ID del domiciliario")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT tipo, estado FROM pedido WHERE id_pedido = %s", (pedido_id,)
            )
            order = cursor.fetchone()
            if order is None or str(order["tipo"]) != "DOMICILIO" or str(order["estado"]) != "LISTO":
                print("El pedido debe existir, ser DOMICILIO y estar LISTO.")
                conexion.rollback()
                return
            cursor.execute(
                """
                SELECT t.descripcion, u.activo
                FROM usuario AS u JOIN tipo_usuario AS t
                  ON t.id_tipo_usuario = u.id_tipo_usuario
                WHERE u.id_usuario = %s
                """,
                (domiciliario_id,),
            )
            courier = cursor.fetchone()
            if courier is None or not courier["activo"] or courier["descripcion"] != "DOMICILIARIO":
                print("El usuario no es un domiciliario activo.")
                conexion.rollback()
                return
            cursor.execute(
                """
                UPDATE entrega
                SET id_domiciliario = %s, estado = 'ASIGNADA',
                    fecha_asignacion = CURRENT_TIMESTAMP
                WHERE id_pedido = %s
                RETURNING id_entrega, id_pedido, id_domiciliario, estado,
                          fecha_asignacion
                """,
                (domiciliario_id, pedido_id),
            )
            delivery = cursor.fetchone()
            if delivery is None:
                print("El pedido no tiene datos de entrega.")
                conexion.rollback()
                return
        conexion.commit()
        print("Domiciliario asignado.")
        mostrar(delivery)
    except psycopg.Error as error:
        conexion.rollback()
        print(f"Error de PostgreSQL: {mensaje_error(error)}")


def driver_consultar_historial(conexion):
    consultar(
        conexion,
        """
        SELECT h.id_historial, h.id_pedido, h.estado, h.fecha,
               h.id_usuario_cambio, u.nombre AS responsable, h.observacion
        FROM historial_estado AS h
        LEFT JOIN usuario AS u ON u.id_usuario = h.id_usuario_cambio
        WHERE h.id_pedido = %s
        ORDER BY h.fecha, h.id_historial
        """,
        (leer_entero("ID del pedido"),),
    )


def menu_driver_login(conexion):
    ejecutar_submenu(
        conexion,
        "06. INICIAR SESIÓN - DRIVER PSYCOPG",
        {"1": ("Verificar credenciales", driver_iniciar_sesion)},
    )


def menu_driver_cocina(conexion):
    ejecutar_submenu(
        conexion,
        "11. CONSULTAR Y FILTRAR PEDIDOS EN COCINA - DRIVER PSYCOPG",
        {"1": ("Consultar y filtrar pedidos", driver_consultar_cocina)},
    )


def menu_driver_estado_preparacion(conexion):
    ejecutar_submenu(
        conexion,
        "12. ACTUALIZAR ESTADO DE PREPARACIÓN - DRIVER PSYCOPG",
        {
            "1": ("Consultar pedido", driver_consultar_pedido),
            "2": ("Actualizar estado", driver_actualizar_estado_pedido),
        },
    )


def menu_driver_historial(conexion):
    ejecutar_submenu(
        conexion,
        "15. CONSULTAR ESTADO E HISTORIAL DE PEDIDOS - DRIVER PSYCOPG",
        {
            "1": ("Consultar estado actual", driver_consultar_pedido),
            "2": ("Consultar historial", driver_consultar_historial),
        },
    )


def opciones_principales_driver():
    operaciones = (
        menu_driver_categorias,
        menu_driver_productos,
        menu_driver_mesas,
        menu_driver_usuarios,
        menu_driver_roles,
        menu_driver_login,
        menu_driver_horarios,
        menu_driver_pedidos_salon,
        menu_driver_pedidos_domicilio,
        menu_driver_detalles,
        menu_driver_cocina,
        menu_driver_estado_preparacion,
        menu_driver_pagos,
        menu_driver_entregas,
        menu_driver_historial,
    )
    return {
        f"{number:02d}": (FUNCTIONALITY_NAMES[number - 1], operation)
        for number, operation in enumerate(operaciones, start=1)
    }


def mostrar_menu_principal_driver():
    print("\n========== POLIRESTAURANTE ==========")
    print("          DRIVER DE PYTHON")
    print("=====================================")
    for number in range(1, 16):
        print(functionality_label(number))
    print("\n00. Salir")


def ejecutar_menu_driver():
    try:
        conexion = conectar()
    except (psycopg.Error, RuntimeError) as error:
        print(f"No fue posible conectar con PostgreSQL: {error}")
        return

    try:
        consultar(conexion, "SELECT current_database() AS base_datos", uno=True)
        opciones = opciones_principales_driver()
        while True:
            mostrar_menu_principal_driver()
            opcion = input("\nSelecciona la funcionalidad: ").strip()
            if opcion in {"00", "0"}:
                print("Consola Driver finalizada.")
                return
            if opcion.isdigit():
                opcion = f"{int(opcion):02d}"
            seleccion = opciones.get(opcion)
            if seleccion is None:
                print("Opción no válida. Usa un número del 01 al 15.")
                continue
            seleccion[1](conexion)
    except (KeyboardInterrupt, EOFError):
        print("\nConsola del driver finalizada.")
    finally:
        conexion.close()


if __name__ == "__main__":
    configurar_terminal()
    ejecutar_menu_driver()
