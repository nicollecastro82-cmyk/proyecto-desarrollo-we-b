"""Consola CRUD para las cinco funcionalidades desarrolladas por Yina.

La consola usa el cliente interno de Flask. De esta forma, cada opción ejecuta los
mismos endpoints, validaciones y operaciones PostgreSQL que se usan desde Postman,
sin duplicar la lógica de negocio de los blueprints REST.
"""

import json
import sys
from getpass import getpass
from urllib.parse import urlencode

from app import app


OMITIDO = object()
cliente_api = app.test_client()


def titulo(texto):
    print(f"\n{texto}")


def mostrar_respuesta(respuesta):
    print(f"\nHTTP {respuesta.status_code}")
    contenido = respuesta.get_json(silent=True)
    if contenido is not None:
        print(json.dumps(contenido, ensure_ascii=False, indent=2))
    elif respuesta.get_data(as_text=True):
        print(respuesta.get_data(as_text=True))
    return contenido


def solicitar_api(metodo, ruta, datos=None):
    """Ejecuta una ruta Flask real y muestra el código HTTP y el JSON."""
    respuesta = cliente_api.open(ruta, method=metodo, json=datos)
    mostrar_respuesta(respuesta)
    return respuesta


def construir_ruta(ruta, **parametros):
    valores = {
        clave: valor
        for clave, valor in parametros.items()
        if valor is not OMITIDO and valor is not None and valor != ""
    }
    return f"{ruta}?{urlencode(valores)}" if valores else ruta


def leer_texto(etiqueta, obligatorio=True):
    while True:
        valor = input(f"{etiqueta}: ").strip()
        if valor or not obligatorio:
            return valor
        print("El valor es obligatorio.")


def leer_texto_opcional(etiqueta, permitir_nulo=False):
    ayuda = " (Enter conserva)"
    if permitir_nulo:
        ayuda = " (Enter conserva, - elimina el valor)"
    valor = input(f"{etiqueta}{ayuda}: ").strip()
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
        sufijo = " [s/n]"
        if predeterminado is True:
            sufijo = " [S/n]"
        elif predeterminado is False:
            sufijo = " [s/N]"
        elif not obligatorio:
            sufijo = " [s/n, Enter conserva]"
        valor = input(f"{etiqueta}{sufijo}: ").strip().lower()
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


def agregar_si_informado(datos, clave, valor):
    if valor is not OMITIDO:
        datos[clave] = valor


def ejecutar_submenu(nombre, opciones):
    while True:
        titulo(nombre)
        for clave, (descripcion, _) in opciones.items():
            print(f"{clave}. {descripcion}")
        print("0. Volver al menú principal")
        opcion = input("\nSelecciona una opción: ").strip()
        if opcion == "0":
            return
        seleccion = opciones.get(opcion)
        if seleccion is None:
            print("Opción no válida.")
            continue
        seleccion[1]()


# ---------------------------------------------------------------------------
# 1. Categorías
# ---------------------------------------------------------------------------


def crear_categoria():
    datos = {
        "nombre": leer_texto("Nombre"),
        "activo": leer_booleano("¿Crear activa?", predeterminado=True),
    }
    solicitar_api("POST", "/api/categorias", datos)


def listar_categorias(incluir_inactivas=False):
    ruta = construir_ruta(
        "/api/categorias",
        incluir_inactivas="true" if incluir_inactivas else OMITIDO,
    )
    solicitar_api("GET", ruta)


def buscar_categorias():
    texto = leer_texto("Texto a buscar")
    solicitar_api("GET", construir_ruta("/api/categorias", q=texto))


def consultar_categoria():
    categoria_id = leer_entero("ID de la categoría")
    solicitar_api("GET", f"/api/categorias/{categoria_id}")


def actualizar_categoria():
    categoria_id = leer_entero("ID de la categoría")
    datos = {}
    agregar_si_informado(datos, "nombre", leer_texto_opcional("Nuevo nombre"))
    agregar_si_informado(
        datos, "activo", leer_booleano("¿Activa?", obligatorio=False)
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api("PATCH", f"/api/categorias/{categoria_id}", datos)


def cambiar_estado_categoria():
    categoria_id = leer_entero("ID de la categoría")
    activo = leer_booleano("¿La categoría debe quedar activa?")
    solicitar_api(
        "PATCH", f"/api/categorias/{categoria_id}/estado", {"activo": activo}
    )


def eliminar_categoria():
    categoria_id = leer_entero("ID de la categoría")
    print("La eliminación es lógica: el registro se conserva como inactivo.")
    if confirmar("¿Desactivar esta categoría?"):
        solicitar_api("DELETE", f"/api/categorias/{categoria_id}")


def menu_categorias():
    ejecutar_submenu(
        "1. CRUD DE CATEGORÍAS",
        {
            "1": ("Crear categoría", crear_categoria),
            "2": ("Listar categorías activas", listar_categorias),
            "3": (
                "Listar categorías activas e inactivas",
                lambda: listar_categorias(True),
            ),
            "4": ("Consultar categoría por ID", consultar_categoria),
            "5": ("Buscar categoría activa por nombre", buscar_categorias),
            "6": ("Actualizar categoría", actualizar_categoria),
            "7": ("Activar o desactivar categoría", cambiar_estado_categoria),
            "8": ("Eliminar lógicamente (desactivar)", eliminar_categoria),
        },
    )


# ---------------------------------------------------------------------------
# 2. Usuarios y roles
# ---------------------------------------------------------------------------


def crear_rol():
    solicitar_api(
        "POST",
        "/api/tipos-usuario",
        {"descripcion": leer_texto("Descripción del rol")},
    )


def listar_roles():
    solicitar_api("GET", "/api/tipos-usuario")


def consultar_rol():
    rol_id = leer_entero("ID del rol")
    solicitar_api("GET", f"/api/tipos-usuario/{rol_id}")


def actualizar_rol():
    rol_id = leer_entero("ID del rol")
    solicitar_api(
        "PATCH",
        f"/api/tipos-usuario/{rol_id}",
        {"descripcion": leer_texto("Nueva descripción")},
    )


def eliminar_rol():
    rol_id = leer_entero("ID del rol")
    print("Los roles base y los roles con usuarios asignados no se pueden eliminar.")
    if confirmar("¿Eliminar este rol?"):
        solicitar_api("DELETE", f"/api/tipos-usuario/{rol_id}")


def menu_roles():
    ejecutar_submenu(
        "USUARIOS Y ROLES - CRUD DE ROLES",
        {
            "1": ("Crear rol", crear_rol),
            "2": ("Listar roles", listar_roles),
            "3": ("Consultar rol por ID", consultar_rol),
            "4": ("Actualizar rol", actualizar_rol),
            "5": ("Eliminar rol", eliminar_rol),
        },
    )


def crear_usuario():
    rol_id = leer_entero("ID del rol")
    nombre = leer_texto("Nombre completo")
    usuario_login = leer_texto("Usuario de acceso")
    contrasena = getpass("Contraseña (mínimo 8 caracteres): ")
    datos = {
        "id_tipo_usuario": rol_id,
        "nombre": nombre,
        "usuario_login": usuario_login,
        "contrasena": contrasena,
        "activo": leer_booleano("¿Crear activo?", predeterminado=True),
    }
    correo = leer_texto("Correo (opcional)", obligatorio=False)
    telefono = leer_texto("Teléfono (opcional)", obligatorio=False)
    if correo:
        datos["correo"] = correo
    if telefono:
        datos["telefono"] = telefono
    solicitar_api("POST", "/api/usuarios", datos)


def listar_usuarios(incluir_inactivos=False):
    filtro_rol = leer_entero("ID de rol para filtrar (Enter = todos)", obligatorio=False)
    texto = leer_texto("Texto a buscar (Enter = todos)", obligatorio=False)
    ruta = construir_ruta(
        "/api/usuarios",
        incluir_inactivos="true" if incluir_inactivos else OMITIDO,
        id_tipo_usuario=filtro_rol,
        q=texto,
    )
    solicitar_api("GET", ruta)


def consultar_usuario():
    usuario_id = leer_entero("ID del usuario")
    solicitar_api("GET", f"/api/usuarios/{usuario_id}")


def actualizar_usuario():
    usuario_id = leer_entero("ID del usuario")
    datos = {}
    agregar_si_informado(
        datos, "id_tipo_usuario", leer_entero("Nuevo ID de rol (Enter conserva)", False)
    )
    agregar_si_informado(datos, "nombre", leer_texto_opcional("Nuevo nombre"))
    agregar_si_informado(
        datos, "usuario_login", leer_texto_opcional("Nuevo usuario de acceso")
    )
    agregar_si_informado(
        datos, "correo", leer_texto_opcional("Nuevo correo", permitir_nulo=True)
    )
    agregar_si_informado(
        datos, "telefono", leer_texto_opcional("Nuevo teléfono", permitir_nulo=True)
    )
    nueva_contrasena = getpass("Nueva contraseña (Enter conserva): ")
    if nueva_contrasena:
        datos["contrasena"] = nueva_contrasena
    agregar_si_informado(
        datos, "activo", leer_booleano("¿Activo?", obligatorio=False)
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api("PATCH", f"/api/usuarios/{usuario_id}", datos)


def cambiar_estado_usuario():
    usuario_id = leer_entero("ID del usuario")
    activo = leer_booleano("¿El usuario debe quedar activo?")
    solicitar_api(
        "PATCH", f"/api/usuarios/{usuario_id}/estado", {"activo": activo}
    )


def eliminar_usuario():
    usuario_id = leer_entero("ID del usuario")
    print("La eliminación es lógica: el usuario se conserva como inactivo.")
    if confirmar("¿Desactivar este usuario?"):
        solicitar_api("DELETE", f"/api/usuarios/{usuario_id}")


def probar_login():
    datos = {
        "usuario_login": leer_texto("Usuario de acceso"),
        "contrasena": getpass("Contraseña: "),
    }
    solicitar_api("POST", "/api/auth/login", datos)


def menu_usuarios():
    ejecutar_submenu(
        "USUARIOS Y ROLES - CRUD DE USUARIOS",
        {
            "1": ("Crear usuario", crear_usuario),
            "2": ("Listar usuarios activos", listar_usuarios),
            "3": (
                "Listar usuarios activos e inactivos",
                lambda: listar_usuarios(True),
            ),
            "4": ("Consultar usuario por ID", consultar_usuario),
            "5": ("Actualizar usuario", actualizar_usuario),
            "6": ("Activar o desactivar usuario", cambiar_estado_usuario),
            "7": ("Eliminar lógicamente (desactivar)", eliminar_usuario),
            "8": ("Probar inicio de sesión", probar_login),
        },
    )


def menu_usuarios_roles():
    ejecutar_submenu(
        "2. GESTIÓN DE USUARIOS Y ROLES",
        {
            "1": ("Administrar roles (tabla tipo_usuario)", menu_roles),
            "2": ("Administrar usuarios (tabla usuario)", menu_usuarios),
        },
    )


# ---------------------------------------------------------------------------
# 3. Horarios de empleados
# ---------------------------------------------------------------------------


def crear_horario():
    datos = {
        "id_usuario": leer_entero("ID del empleado"),
        "fecha": leer_texto("Fecha (AAAA-MM-DD)"),
        "hora_inicio": leer_texto("Hora de inicio (HH:MM)"),
        "hora_fin": leer_texto("Hora de fin (HH:MM)"),
    }
    observacion = leer_texto("Observación (opcional)", obligatorio=False)
    if observacion:
        datos["observacion"] = observacion
    solicitar_api("POST", "/api/horarios", datos)


def listar_horarios():
    usuario_id = leer_entero("ID de empleado (Enter = todos)", obligatorio=False)
    fecha = leer_texto("Fecha AAAA-MM-DD (Enter = todas)", obligatorio=False)
    solicitar_api(
        "GET",
        construir_ruta("/api/horarios", id_usuario=usuario_id, fecha=fecha),
    )


def consultar_horario():
    horario_id = leer_entero("ID del horario")
    solicitar_api("GET", f"/api/horarios/{horario_id}")


def actualizar_horario():
    horario_id = leer_entero("ID del horario")
    datos = {}
    agregar_si_informado(
        datos,
        "id_usuario",
        leer_entero("Nuevo ID de empleado (Enter conserva)", obligatorio=False),
    )
    agregar_si_informado(datos, "fecha", leer_texto_opcional("Nueva fecha AAAA-MM-DD"))
    agregar_si_informado(
        datos, "hora_inicio", leer_texto_opcional("Nueva hora de inicio HH:MM")
    )
    agregar_si_informado(
        datos, "hora_fin", leer_texto_opcional("Nueva hora de fin HH:MM")
    )
    agregar_si_informado(
        datos,
        "observacion",
        leer_texto_opcional("Nueva observación", permitir_nulo=True),
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api("PATCH", f"/api/horarios/{horario_id}", datos)


def eliminar_horario():
    horario_id = leer_entero("ID del horario")
    if confirmar("¿Eliminar definitivamente este horario?"):
        solicitar_api("DELETE", f"/api/horarios/{horario_id}")


def menu_horarios():
    ejecutar_submenu(
        "3. CRUD DE HORARIOS DE EMPLEADOS",
        {
            "1": ("Crear horario", crear_horario),
            "2": ("Listar y filtrar horarios", listar_horarios),
            "3": ("Consultar horario por ID", consultar_horario),
            "4": ("Actualizar horario", actualizar_horario),
            "5": ("Eliminar horario", eliminar_horario),
        },
    )


# ---------------------------------------------------------------------------
# 4. Pagos
# ---------------------------------------------------------------------------


def crear_pago():
    datos = {
        "id_pedido": leer_entero("ID del pedido"),
        "metodo": leer_texto("Método (EFECTIVO o PSE)"),
        "valor": leer_texto("Valor del pago"),
    }
    referencia = leer_texto("Referencia de transacción (opcional)", obligatorio=False)
    if referencia:
        datos["referencia_transaccion"] = referencia
    solicitar_api("POST", "/api/pagos", datos)


def listar_pagos():
    pedido_id = leer_entero("ID de pedido (Enter = todos)", obligatorio=False)
    estado = leer_texto(
        "Estado PENDIENTE/APROBADO/RECHAZADO (Enter = todos)", obligatorio=False
    )
    solicitar_api(
        "GET", construir_ruta("/api/pagos", id_pedido=pedido_id, estado=estado)
    )


def consultar_pago():
    pago_id = leer_entero("ID del pago")
    solicitar_api("GET", f"/api/pagos/{pago_id}")


def actualizar_pago():
    pago_id = leer_entero("ID del pago")
    datos = {}
    agregar_si_informado(
        datos, "metodo", leer_texto_opcional("Nuevo método EFECTIVO/PSE")
    )
    agregar_si_informado(datos, "valor", leer_texto_opcional("Nuevo valor"))
    agregar_si_informado(
        datos,
        "referencia_transaccion",
        leer_texto_opcional("Nueva referencia", permitir_nulo=True),
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api("PATCH", f"/api/pagos/{pago_id}", datos)


def cambiar_estado_pago():
    pago_id = leer_entero("ID del pago")
    datos = {"estado": leer_texto("Nuevo estado (APROBADO o RECHAZADO)")}
    usuario_id = leer_entero(
        "ID del usuario que confirma (Enter si no aplica)", obligatorio=False
    )
    referencia = leer_texto(
        "Referencia de transacción (Enter si no aplica)", obligatorio=False
    )
    agregar_si_informado(datos, "id_usuario_confirma", usuario_id)
    if referencia:
        datos["referencia_transaccion"] = referencia
    solicitar_api("PATCH", f"/api/pagos/{pago_id}/estado", datos)


def eliminar_pago():
    pago_id = leer_entero("ID del pago")
    print("Solo se puede eliminar definitivamente un pago PENDIENTE.")
    if confirmar("¿Eliminar este pago pendiente?"):
        solicitar_api("DELETE", f"/api/pagos/{pago_id}")


def menu_pagos():
    ejecutar_submenu(
        "4. CRUD DE PAGOS",
        {
            "1": ("Crear pago", crear_pago),
            "2": ("Listar y filtrar pagos", listar_pagos),
            "3": ("Consultar pago por ID", consultar_pago),
            "4": ("Actualizar pago pendiente", actualizar_pago),
            "5": ("Aprobar o rechazar pago", cambiar_estado_pago),
            "6": ("Eliminar pago pendiente", eliminar_pago),
        },
    )


# ---------------------------------------------------------------------------
# 5. Entregas a domicilio
# ---------------------------------------------------------------------------


def crear_entrega():
    datos = {
        "id_pedido": leer_entero("ID del pedido a domicilio"),
        "direccion_entrega": leer_texto("Dirección de entrega"),
        "telefono_contacto": leer_texto("Teléfono de contacto"),
    }
    domiciliario_id = leer_entero(
        "ID del domiciliario (Enter = sin asignar)", obligatorio=False
    )
    observacion = leer_texto("Observación (opcional)", obligatorio=False)
    agregar_si_informado(datos, "id_domiciliario", domiciliario_id)
    if observacion:
        datos["observacion"] = observacion
    solicitar_api("POST", "/api/entregas", datos)


def listar_entregas():
    pedido_id = leer_entero("ID de pedido (Enter = todos)", obligatorio=False)
    domiciliario_id = leer_entero(
        "ID de domiciliario (Enter = todos)", obligatorio=False
    )
    estado = leer_texto("Estado (Enter = todos)", obligatorio=False)
    solicitar_api(
        "GET",
        construir_ruta(
            "/api/entregas",
            id_pedido=pedido_id,
            id_domiciliario=domiciliario_id,
            estado=estado,
        ),
    )


def consultar_entrega():
    entrega_id = leer_entero("ID de la entrega")
    solicitar_api("GET", f"/api/entregas/{entrega_id}")


def actualizar_entrega():
    entrega_id = leer_entero("ID de la entrega")
    datos = {}
    agregar_si_informado(
        datos,
        "id_domiciliario",
        leer_entero("Nuevo ID de domiciliario (Enter conserva)", obligatorio=False),
    )
    agregar_si_informado(
        datos, "direccion_entrega", leer_texto_opcional("Nueva dirección")
    )
    agregar_si_informado(
        datos, "telefono_contacto", leer_texto_opcional("Nuevo teléfono")
    )
    agregar_si_informado(
        datos,
        "observacion",
        leer_texto_opcional("Nueva observación", permitir_nulo=True),
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api("PATCH", f"/api/entregas/{entrega_id}", datos)


def cambiar_estado_entrega():
    entrega_id = leer_entero("ID de la entrega")
    print(
        "Estados: PENDIENTE_ASIGNACION, ASIGNADA, RECOGIDA, "
        "EN_CAMINO, ENTREGADA, CON_INCIDENCIA"
    )
    datos = {"estado": leer_texto("Nuevo estado")}
    domiciliario_id = leer_entero(
        "ID de domiciliario (Enter si no aplica)", obligatorio=False
    )
    observacion = leer_texto("Observación (Enter si no aplica)", obligatorio=False)
    agregar_si_informado(datos, "id_domiciliario", domiciliario_id)
    if observacion:
        datos["observacion"] = observacion
    solicitar_api("PATCH", f"/api/entregas/{entrega_id}/estado", datos)


def eliminar_entrega():
    entrega_id = leer_entero("ID de la entrega")
    print("Solo se puede eliminar una entrega PENDIENTE_ASIGNACION.")
    if confirmar("¿Eliminar definitivamente esta entrega?"):
        solicitar_api("DELETE", f"/api/entregas/{entrega_id}")


def menu_entregas():
    ejecutar_submenu(
        "5. CRUD DE ENTREGAS A DOMICILIO",
        {
            "1": ("Crear entrega", crear_entrega),
            "2": ("Listar y filtrar entregas", listar_entregas),
            "3": ("Consultar entrega por ID", consultar_entrega),
            "4": ("Actualizar entrega", actualizar_entrega),
            "5": ("Cambiar estado de entrega", cambiar_estado_entrega),
            "6": ("Eliminar entrega pendiente", eliminar_entrega),
        },
    )


def mostrar_menu_principal():
    titulo("POLIRESTAURANTE - CONSOLA CRUD DE YINA")
    print("1. Gestionar categorías                 [tabla categoria]")
    print("2. Gestionar usuarios y roles          [usuario / tipo_usuario]")
    print("3. Gestionar horarios de empleados     [horario_empleado]")
    print("4. Gestionar pagos                      [pago]")
    print("5. Gestionar entregas a domicilio      [entrega]")
    print("0. Salir")


def ejecutar_menu_orm():
    titulo("TAREA 2 - CRUD CON SQLALCHEMY ORM")
    print("Comprobando conexión con Flask y PostgreSQL...")
    salud = solicitar_api("GET", "/api/salud")
    if salud.status_code != 200:
        print("No se abrirá el menú hasta corregir la conexión con PostgreSQL.")
        return

    opciones = {
        "1": menu_categorias,
        "2": menu_usuarios_roles,
        "3": menu_horarios,
        "4": menu_pagos,
        "5": menu_entregas,
    }
    try:
        while True:
            mostrar_menu_principal()
            opcion = input("\nSelecciona la funcionalidad: ").strip()
            if opcion == "0":
                print("Consola finalizada.")
                return
            operacion = opciones.get(opcion)
            if operacion is None:
                print("Opción no válida.")
                continue
            operacion()
    except (KeyboardInterrupt, EOFError):
        print("\nConsola ORM finalizada.")


def configurar_terminal():
    # Evita caracteres dañados en la terminal de Windows al mostrar tildes y ñ.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def ejecutar_menu():
    try:
        while True:
            titulo("POLIRESTAURANTE - DOS TAREAS CRUD")
            print("1. CRUD directo con el driver psycopg")
            print("2. CRUD mediante SQLAlchemy ORM")
            print("0. Salir")
            opcion = input("\nSelecciona la tarea: ").strip()
            if opcion == "0":
                print("Consola finalizada.")
                return
            if opcion == "1":
                from consola_driver import ejecutar_menu_driver

                ejecutar_menu_driver()
            elif opcion == "2":
                ejecutar_menu_orm()
            else:
                print("Opción no válida.")
    except (KeyboardInterrupt, EOFError):
        print("\nConsola finalizada.")


if __name__ == "__main__":
    configurar_terminal()
    ejecutar_menu()
