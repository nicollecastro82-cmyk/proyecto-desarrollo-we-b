"""Consola ORM integrada para las 15 funcionalidades de PoliRestaurante.

La consola usa el cliente interno de Flask. De esta forma, cada opción ejecuta los
mismos endpoints, validaciones y operaciones PostgreSQL que se usan desde Postman,
sin duplicar la lógica de negocio de los blueprints REST.
"""

import json
import sys
from getpass import getpass
from urllib.parse import urlencode

from app import app
from functionalities import FUNCTIONALITY_NAMES, functionality_label


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
# 01. Gestionar categorías
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
        "01. GESTIONAR CATEGORÍAS - ORM",
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
# 04 y 05. Gestionar usuarios / Gestionar roles
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
        "05. GESTIONAR ROLES - ORM",
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
        "04. GESTIONAR USUARIOS - ORM",
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
        },
    )


# ---------------------------------------------------------------------------
# 07. Gestionar horarios
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
        "07. GESTIONAR HORARIOS - ORM",
        {
            "1": ("Crear horario", crear_horario),
            "2": ("Listar y filtrar horarios", listar_horarios),
            "3": ("Consultar horario por ID", consultar_horario),
            "4": ("Actualizar horario", actualizar_horario),
            "5": ("Eliminar horario", eliminar_horario),
        },
    )


# ---------------------------------------------------------------------------
# 13. Gestionar pagos
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
        "13. GESTIONAR PAGOS - ORM",
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
# 14. Gestionar domicilios y entregas
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
        "14. GESTIONAR DOMICILIOS Y ENTREGAS - ORM",
        {
            "1": ("Asignar pedido a domiciliario", asignar_domiciliario_pedido),
            "2": ("Crear entrega", crear_entrega),
            "3": ("Listar y filtrar entregas", listar_entregas),
            "4": ("Consultar entrega por ID", consultar_entrega),
            "5": ("Actualizar entrega", actualizar_entrega),
            "6": ("Cambiar estado de entrega", cambiar_estado_entrega),
            "7": ("Eliminar entrega pendiente", eliminar_entrega),
        },
    )


# ---------------------------------------------------------------------------
# Productos, Mesas y flujo de Pedidos (ORM mediante los servicios Flask)
# ---------------------------------------------------------------------------


def crear_producto():
    datos = {
        "nombre": leer_texto("Nombre"),
        "precio": leer_texto("Precio"),
        "id_categoria": leer_entero("ID de la categoría"),
    }
    descripcion = leer_texto("Descripción (opcional)", obligatorio=False)
    if descripcion:
        datos["descripcion"] = descripcion
    solicitar_api("POST", "/productos", datos)


def listar_productos():
    categoria_id = leer_entero("ID de categoría (Enter = todas)", obligatorio=False)
    buscar = leer_texto("Texto a buscar (Enter = todos)", obligatorio=False)
    solicitar_api(
        "GET", construir_ruta("/productos", id_categoria=categoria_id, buscar=buscar)
    )


def consultar_producto():
    producto_id = leer_entero("ID del producto")
    solicitar_api("GET", f"/productos/{producto_id}")


def actualizar_producto():
    producto_id = leer_entero("ID del producto")
    datos = {}
    agregar_si_informado(datos, "nombre", leer_texto_opcional("Nuevo nombre"))
    agregar_si_informado(datos, "descripcion", leer_texto_opcional("Descripción", True))
    agregar_si_informado(datos, "precio", leer_texto_opcional("Nuevo precio"))
    agregar_si_informado(
        datos,
        "id_categoria",
        leer_entero("Nuevo ID de categoría (Enter conserva)", obligatorio=False),
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api("PATCH", f"/productos/{producto_id}", datos)


def cambiar_disponibilidad_producto():
    producto_id = leer_entero("ID del producto")
    disponible = leer_booleano("¿Debe quedar disponible?")
    solicitar_api(
        "PATCH",
        f"/productos/{producto_id}/disponibilidad",
        {"disponible": disponible},
    )


def eliminar_producto():
    producto_id = leer_entero("ID del producto")
    if confirmar("¿Desactivar lógicamente este producto?"):
        solicitar_api("DELETE", f"/productos/{producto_id}")


def menu_productos():
    ejecutar_submenu(
        "02. GESTIONAR PRODUCTOS Y MENÚ - ORM",
        {
            "1": ("Crear producto", crear_producto),
            "2": ("Listar y buscar productos disponibles", listar_productos),
            "3": ("Consultar producto por ID", consultar_producto),
            "4": ("Actualizar producto o precio", actualizar_producto),
            "5": ("Cambiar disponibilidad", cambiar_disponibilidad_producto),
            "6": ("Desactivar producto", eliminar_producto),
        },
    )


def crear_mesa():
    solicitar_api("POST", "/mesas", {"numero_mesa": leer_entero("Número de mesa")})


def listar_mesas():
    estado = leer_texto("Estado (Enter = todos)", obligatorio=False)
    solicitar_api("GET", construir_ruta("/mesas", estado=estado))


def consultar_mesa():
    mesa_id = leer_entero("ID de la mesa")
    solicitar_api("GET", f"/mesas/{mesa_id}")


def actualizar_mesa():
    mesa_id = leer_entero("ID de la mesa")
    solicitar_api(
        "PUT", f"/mesas/{mesa_id}", {"numero_mesa": leer_entero("Nuevo número")}
    )


def cambiar_estado_mesa():
    mesa_id = leer_entero("ID de la mesa")
    estado = leer_texto("Estado (LIBRE, OCUPADA o FUERA_DE_SERVICIO)")
    solicitar_api("PATCH", f"/mesas/{mesa_id}/estado", {"estado": estado})


def menu_mesas():
    ejecutar_submenu(
        "03. GESTIONAR MESAS - ORM",
        {
            "1": ("Registrar mesa", crear_mesa),
            "2": ("Listar mesas", listar_mesas),
            "3": ("Consultar mesa por ID", consultar_mesa),
            "4": ("Actualizar número", actualizar_mesa),
            "5": ("Cambiar estado", cambiar_estado_mesa),
        },
    )


def registrar_pedido_salon():
    datos = {
        "tipo": "SALON",
        "id_mesa": leer_entero("ID de la mesa libre"),
        "id_mesero": leer_entero("ID del mesero"),
    }
    observaciones = leer_texto("Observaciones (opcional)", obligatorio=False)
    if observaciones:
        datos["observaciones"] = observaciones
    solicitar_api("POST", "/api/pedidos", datos)


def registrar_pedido_domicilio():
    datos = {
        "tipo": "DOMICILIO",
        "id_cliente": leer_entero("ID del cliente"),
        "direccion_entrega": leer_texto("Dirección de entrega"),
        "telefono_contacto": leer_texto("Teléfono de contacto"),
    }
    observaciones = leer_texto("Observaciones (opcional)", obligatorio=False)
    if observaciones:
        datos["observaciones"] = observaciones
    solicitar_api("POST", "/api/pedidos", datos)


def listar_pedidos():
    estado = leer_texto("Estado (Enter = todos)", obligatorio=False)
    tipo = leer_texto("Tipo (Enter = todos)", obligatorio=False)
    solicitar_api("GET", construir_ruta("/api/pedidos", estado=estado, tipo=tipo))


def consultar_pedido():
    pedido_id = leer_entero("ID del pedido")
    solicitar_api("GET", f"/api/pedidos/{pedido_id}")


def actualizar_observaciones_pedido():
    pedido_id = leer_entero("ID del pedido")
    observaciones = leer_texto("Nuevas observaciones")
    solicitar_api(
        "PATCH", f"/api/pedidos/{pedido_id}", {"observaciones": observaciones}
    )


def cancelar_pedido():
    pedido_id = leer_entero("ID del pedido")
    datos = {
        "id_usuario_cambio": leer_entero("ID del usuario responsable"),
        "observacion": leer_texto("Motivo de cancelación"),
    }
    if confirmar("¿Cancelar este pedido?"):
        solicitar_api("DELETE", f"/api/pedidos/{pedido_id}", datos)


def menu_pedidos_salon():
    ejecutar_submenu(
        "08. REGISTRAR PEDIDOS EN SALÓN - ORM",
        {
            "1": ("Registrar pedido en salón", registrar_pedido_salon),
            "2": ("Listar pedidos", listar_pedidos),
            "3": ("Consultar pedido", consultar_pedido),
            "4": ("Actualizar observaciones", actualizar_observaciones_pedido),
            "5": ("Cancelar pedido", cancelar_pedido),
        },
    )


def menu_pedidos_domicilio():
    ejecutar_submenu(
        "09. REGISTRAR PEDIDOS A DOMICILIO - ORM",
        {
            "1": ("Registrar pedido a domicilio", registrar_pedido_domicilio),
            "2": ("Listar pedidos", listar_pedidos),
            "3": ("Consultar pedido", consultar_pedido),
            "4": ("Actualizar observaciones", actualizar_observaciones_pedido),
            "5": ("Cancelar pedido", cancelar_pedido),
        },
    )


def agregar_detalle_pedido():
    pedido_id = leer_entero("ID del pedido")
    datos = {
        "id_producto": leer_entero("ID del producto"),
        "cantidad": leer_entero("Cantidad"),
    }
    comentarios = leer_texto("Comentarios (opcional)", obligatorio=False)
    if comentarios:
        datos["comentarios"] = comentarios
    solicitar_api("POST", f"/api/pedidos/{pedido_id}/detalles", datos)


def listar_detalles_pedido():
    pedido_id = leer_entero("ID del pedido")
    solicitar_api("GET", f"/api/pedidos/{pedido_id}/detalles")


def actualizar_detalle_pedido():
    pedido_id = leer_entero("ID del pedido")
    detalle_id = leer_entero("ID del detalle")
    datos = {}
    agregar_si_informado(
        datos, "cantidad", leer_entero("Nueva cantidad (Enter conserva)", False)
    )
    agregar_si_informado(
        datos, "comentarios", leer_texto_opcional("Comentarios", True)
    )
    if not datos:
        print("No se ingresaron cambios.")
        return
    solicitar_api(
        "PATCH", f"/api/pedidos/{pedido_id}/detalles/{detalle_id}", datos
    )


def eliminar_detalle_pedido():
    pedido_id = leer_entero("ID del pedido")
    detalle_id = leer_entero("ID del detalle")
    if confirmar("¿Quitar este producto del pedido?"):
        solicitar_api("DELETE", f"/api/pedidos/{pedido_id}/detalles/{detalle_id}")


def menu_detalles_pedido():
    ejecutar_submenu(
        "10. GESTIONAR DETALLE DEL PEDIDO - ORM",
        {
            "1": ("Agregar producto", agregar_detalle_pedido),
            "2": ("Consultar detalles", listar_detalles_pedido),
            "3": ("Modificar cantidad o comentarios", actualizar_detalle_pedido),
            "4": ("Quitar producto", eliminar_detalle_pedido),
        },
    )


def consultar_pedidos_cocina():
    estado = leer_texto("Estado (Enter = pendientes activos)", obligatorio=False)
    solicitar_api("GET", construir_ruta("/api/cocina/pedidos", estado=estado))


def actualizar_estado_pedido():
    pedido_id = leer_entero("ID del pedido")
    datos = {
        "estado": leer_texto("Nuevo estado"),
        "id_usuario_cambio": leer_entero("ID del usuario responsable"),
    }
    observacion = leer_texto("Observación (opcional)", obligatorio=False)
    if observacion:
        datos["observacion"] = observacion
    solicitar_api("PATCH", f"/api/pedidos/{pedido_id}/estado", datos)


def asignar_domiciliario_pedido():
    pedido_id = leer_entero("ID del pedido LISTO")
    domiciliario_id = leer_entero("ID del domiciliario")
    solicitar_api(
        "PATCH",
        f"/api/pedidos/{pedido_id}/domiciliario",
        {"id_domiciliario": domiciliario_id},
    )


def consultar_historial_pedido():
    pedido_id = leer_entero("ID del pedido")
    solicitar_api("GET", f"/api/pedidos/{pedido_id}/historial")


def menu_login():
    ejecutar_submenu(
        "06. INICIAR SESIÓN - ORM",
        {"1": ("Verificar credenciales", probar_login)},
    )


def menu_cocina():
    ejecutar_submenu(
        "11. CONSULTAR Y FILTRAR PEDIDOS EN COCINA - ORM",
        {"1": ("Consultar y filtrar pedidos", consultar_pedidos_cocina)},
    )


def menu_estado_preparacion():
    ejecutar_submenu(
        "12. ACTUALIZAR ESTADO DE PREPARACIÓN - ORM",
        {
            "1": ("Consultar pedido", consultar_pedido),
            "2": ("Actualizar estado", actualizar_estado_pedido),
        },
    )


def menu_historial_pedidos():
    ejecutar_submenu(
        "15. CONSULTAR ESTADO E HISTORIAL DE PEDIDOS - ORM",
        {
            "1": ("Consultar estado actual", consultar_pedido),
            "2": ("Consultar historial", consultar_historial_pedido),
        },
    )


def opciones_principales_orm():
    operaciones = (
        menu_categorias,
        menu_productos,
        menu_mesas,
        menu_usuarios,
        menu_roles,
        menu_login,
        menu_horarios,
        menu_pedidos_salon,
        menu_pedidos_domicilio,
        menu_detalles_pedido,
        menu_cocina,
        menu_estado_preparacion,
        menu_pagos,
        menu_entregas,
        menu_historial_pedidos,
    )
    return {
        f"{number:02d}": operation
        for number, operation in enumerate(operaciones, start=1)
    }


def mostrar_menu_principal():
    print("\n========== POLIRESTAURANTE ==========")
    print("          SQLALCHEMY ORM")
    print("=====================================")
    for number in range(1, 16):
        print(functionality_label(number))
    print("\n00. Salir")


def ejecutar_menu_orm():
    titulo("TAREA 2 - CRUD CON SQLALCHEMY ORM")
    print("Comprobando conexión con Flask y PostgreSQL...")
    salud = solicitar_api("GET", "/api/salud")
    if salud.status_code != 200:
        print("No se abrirá el menú hasta corregir la conexión con PostgreSQL.")
        return

    opciones = opciones_principales_orm()
    try:
        while True:
            mostrar_menu_principal()
            opcion = input("\nSelecciona la funcionalidad: ").strip()
            if opcion in {"00", "0"}:
                print("Consola finalizada.")
                return
            if opcion.isdigit():
                opcion = f"{int(opcion):02d}"
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
