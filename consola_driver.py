"""CRUD directo con el driver psycopg, sin Flask ni SQLAlchemy ORM."""

import json
import os
import sys
from getpass import getpass

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash


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
        "DRIVER PSYCOPG - CRUD DE CATEGORÍAS",
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


# Roles y usuarios -----------------------------------------------------------


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
        "DRIVER PSYCOPG - CRUD DE ROLES",
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
        "DRIVER PSYCOPG - CRUD DE USUARIOS",
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


def menu_driver_usuarios_roles(conexion):
    ejecutar_submenu(
        conexion,
        "DRIVER PSYCOPG - USUARIOS Y ROLES",
        {
            "1": ("Tabla tipo_usuario", menu_driver_roles),
            "2": ("Tabla usuario", menu_driver_usuarios),
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
        "DRIVER PSYCOPG - CRUD DE HORARIOS",
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
                "SELECT id_pedido, tipo, estado FROM pedido WHERE id_pedido = %s",
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
    if obtener_pedido(conexion, pedido_id) is None:
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
            leer_texto("Valor"),
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
    actualizar_campos(
        conexion,
        "pago",
        "id_pago",
        pago_id,
        {
            "metodo": leer_texto_opcional("Nuevo método EFECTIVO/PSE"),
            "valor": leer_texto_opcional("Nuevo valor"),
            "referencia_transaccion": leer_texto_opcional("Nueva referencia", True),
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
        "DRIVER PSYCOPG - CRUD DE PAGOS",
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
    escribir(
        conexion,
        """
        UPDATE entrega
        SET estado = %s::estado_entrega,
            fecha_asignacion = CASE WHEN %s = 'ASIGNADA' THEN CURRENT_TIMESTAMP
                                    ELSE fecha_asignacion END,
            fecha_recogida = CASE WHEN %s = 'RECOGIDA' THEN CURRENT_TIMESTAMP
                                  ELSE fecha_recogida END,
            fecha_entrega = CASE WHEN %s = 'ENTREGADA' THEN CURRENT_TIMESTAMP
                                 ELSE fecha_entrega END
        WHERE id_entrega = %s
        RETURNING id_entrega, id_pedido, id_domiciliario, estado,
                  fecha_asignacion, fecha_recogida, fecha_entrega
        """,
        (estado, estado, estado, estado, entrega_id),
        "Estado de entrega actualizado.",
    )


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
        "DRIVER PSYCOPG - CRUD DE ENTREGAS",
        {
            "1": ("CREATE - Crear", driver_crear_entrega),
            "2": ("READ - Listar", driver_listar_entregas),
            "3": ("READ - Consultar por ID", driver_consultar_entrega),
            "4": ("UPDATE - Actualizar", driver_actualizar_entrega),
            "5": ("UPDATE - Cambiar estado", driver_cambiar_estado_entrega),
            "6": ("DELETE - Eliminar pendiente", driver_eliminar_entrega),
        },
    )


def ejecutar_menu_driver():
    titulo("TAREA 1 - CRUD DIRECTO CON EL DRIVER PSYCOPG")
    try:
        conexion = conectar()
    except (psycopg.Error, RuntimeError) as error:
        print(f"No fue posible conectar con PostgreSQL: {error}")
        return

    try:
        consultar(conexion, "SELECT current_database() AS base_datos", uno=True)
        opciones = {
            "1": ("Categorías", menu_driver_categorias),
            "2": ("Usuarios y roles", menu_driver_usuarios_roles),
            "3": ("Horarios de empleados", menu_driver_horarios),
            "4": ("Pagos", menu_driver_pagos),
            "5": ("Entregas a domicilio", menu_driver_entregas),
        }
        ejecutar_submenu(conexion, "ELIGE LA TABLA O FUNCIONALIDAD", opciones)
    except (KeyboardInterrupt, EOFError):
        print("\nConsola del driver finalizada.")
    finally:
        conexion.close()


if __name__ == "__main__":
    configurar_terminal()
    ejecutar_menu_driver()
