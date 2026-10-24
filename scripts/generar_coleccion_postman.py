"""Genera la colección Postman principal con exactamente 15 carpetas."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from functionalities import FUNCTIONALITY_NAMES, functionality_label  # noqa: E402


OUTPUT = ROOT / "postman" / "PoliRestaurante-15-Funcionalidades.postman_collection.json"


def checks(status_code, *extra):
    return [
        f"pm.test('Estado {status_code}', () => pm.response.to.have.status({status_code}));",
        *extra,
    ]


def request(name, method, path, body=None, before=(), after=()):
    request_data = {"method": method, "url": "{{baseUrl}}" + path}
    if body is not None:
        request_data["header"] = [{"key": "Content-Type", "value": "application/json"}]
        request_data["body"] = {"mode": "raw", "raw": body}
    events = []
    if before:
        events.append(
            {
                "listen": "prerequest",
                "script": {"type": "text/javascript", "exec": list(before)},
            }
        )
    if after:
        events.append(
            {
                "listen": "test",
                "script": {"type": "text/javascript", "exec": list(after)},
            }
        )
    item = {"name": name, "request": request_data}
    if events:
        item["event"] = events
    return item


def folder(number, items):
    return {"name": functionality_label(number), "item": items}


def build_collection():
    folders = []

    folders.append(
        folder(
            1,
            [
                request(
                    "Precondición - Comprobar Flask y PostgreSQL",
                    "GET",
                    "/api/salud",
                    after=checks(
                        200,
                        "pm.test('Base conectada', () => pm.expect(pm.response.json().base_datos).to.eql('conectada'));",
                    ),
                ),
                request(
                    "POST Crear categoría",
                    "POST",
                    "/api/categorias",
                    '{"nombre":"{{categoryName}}","activo":true}',
                    before=("pm.environment.set('categoryName', 'Categoria Principal ' + Date.now());",),
                    after=checks(
                        201,
                        "if (pm.response.code === 201) pm.environment.set('categoryId', pm.response.json().datos.id_categoria);",
                    ),
                ),
                request(
                    "GET Listar categorías activas",
                    "GET",
                    "/api/categorias",
                    after=checks(
                        200,
                        "const own = Number(pm.environment.get('categoryId'));",
                        "const categories = pm.response.json().datos;",
                        "const demoMap = {'Entradas [DEMO]':'demoCategoryEntradasId','Platos fuertes [DEMO]':'demoCategoryPlatosId','Bebidas [DEMO]':'demoCategoryBebidasId','Postres [DEMO]':'demoCategoryPostresId'};",
                        "Object.entries(demoMap).forEach(([name,key]) => { const c=categories.find(x => x.nombre===name && x.activo); if(c) pm.environment.set(key,c.id_categoria); });",
                        "const demoCategories = categories.filter(c => Object.prototype.hasOwnProperty.call(demoMap,c.nombre) && c.activo);",
                        "pm.test('Existen las cuatro categorías demo', () => pm.expect(demoCategories.length).to.eql(4));",
                        "const selected = categories.find(c => c.nombre === 'Entradas [DEMO]') || categories.find(c => c.activo && c.id_categoria !== own);",
                        "pm.test('Existe categoría activa para Producto', () => pm.expect(selected).to.exist);",
                        "if (selected) pm.environment.set('productCategoryId', selected.id_categoria);",
                    ),
                ),
                request(
                    "GET Consultar categoría por ID",
                    "GET",
                    "/api/categorias/{{categoryId}}",
                    after=checks(200),
                ),
                request(
                    "PUT Actualizar categoría",
                    "PUT",
                    "/api/categorias/{{categoryId}}",
                    '{"nombre":"{{categoryName}} actualizada","activo":true}',
                    after=checks(200),
                ),
                request(
                    "PATCH Cambiar estado de categoría",
                    "PATCH",
                    "/api/categorias/{{categoryId}}/estado",
                    '{"activo":true}',
                    after=checks(200),
                ),
                request(
                    "ERROR Nombre de categoría vacío",
                    "POST",
                    "/api/categorias",
                    '{"nombre":""}',
                    after=checks(400),
                ),
                request(
                    "DELETE Desactivar categoría",
                    "DELETE",
                    "/api/categorias/{{categoryId}}",
                    after=checks(200),
                ),
            ],
        )
    )

    folders.append(
        folder(
            2,
            [
                request(
                    "Precondición - Consultar categoría activa existente",
                    "GET",
                    "/api/categorias/{{productCategoryId}}",
                    after=checks(
                        200,
                        "pm.test('Categoría activa', () => pm.expect(pm.response.json().datos.activo).to.eql(true));",
                    ),
                ),
                request(
                    "POST Crear producto para CRUD",
                    "POST",
                    "/productos",
                    '{"nombre":"{{productCrudName}}","descripcion":"Producto CRUD Postman","precio":25000,"id_categoria":{{productCategoryId}}}',
                    before=("pm.environment.set('productCrudName', 'Producto CRUD ' + Date.now());",),
                    after=checks(
                        201,
                        "if (pm.response.code === 201) pm.environment.set('productCrudId', pm.response.json().id_producto);",
                    ),
                ),
                request(
                    "GET Listar productos del menú",
                    "GET",
                    "/productos?id_categoria={{productCategoryId}}",
                    after=checks(
                        200,
                        "const demo=pm.response.json().find(p=>p.nombre==='Empanadas colombianas [DEMO]');",
                        "pm.test('Producto demo disponible',()=>pm.expect(demo).to.exist);",
                        "if(demo)pm.environment.set('demoProductId',demo.id_producto);",
                    ),
                ),
                request(
                    "GET Consultar producto por ID",
                    "GET",
                    "/productos/{{productCrudId}}",
                    after=checks(200),
                ),
                request(
                    "PUT Actualizar producto",
                    "PUT",
                    "/productos/{{productCrudId}}",
                    '{"descripcion":"Producto CRUD actualizado","precio":"26000.50"}',
                    after=checks(200),
                ),
                request(
                    "ERROR Nombre de producto duplicado",
                    "POST",
                    "/productos",
                    '{"nombre":"{{productCrudName}}","precio":25000,"id_categoria":{{productCategoryId}}}',
                    after=checks(409),
                ),
                request(
                    "PATCH Cambiar disponibilidad",
                    "PATCH",
                    "/productos/{{productCrudId}}/disponibilidad",
                    '{"disponible":false}',
                    after=checks(200),
                ),
                request(
                    "DELETE Desactivar producto CRUD",
                    "DELETE",
                    "/productos/{{productCrudId}}",
                    after=checks(200),
                ),
                request(
                    "POST Preparar producto activo para pedidos",
                    "POST",
                    "/productos",
                    '{"nombre":"{{productName}}","descripcion":"Producto para pedidos","precio":"12500.00","id_categoria":{{productCategoryId}}}',
                    before=("pm.environment.set('productName', 'Producto Pedidos ' + Date.now());",),
                    after=checks(
                        201,
                        "if (pm.response.code === 201) pm.environment.set('productId', pm.response.json().id_producto);",
                    ),
                ),
            ],
        )
    )

    folders.append(
        folder(
            3,
            [
                request(
                    "POST Registrar mesa para CRUD",
                    "POST",
                    "/mesas",
                    '{"numero_mesa":{{mesaCrudNumber}}}',
                    before=(
                        "const n = 100000 + Math.floor(Math.random() * 300000);",
                        "pm.environment.set('mesaCrudNumber', n);",
                        "pm.environment.set('mesaCrudUpdatedNumber', n + 1);",
                    ),
                    after=checks(
                        201,
                        "if (pm.response.code === 201) pm.environment.set('mesaCrudId', pm.response.json().id_mesa);",
                    ),
                ),
                request(
                    "GET Listar mesas",
                    "GET",
                    "/mesas",
                    after=checks(
                        200,
                        "const mesas=pm.response.json();",
                        "const libre=mesas.find(m=>m.numero_mesa===9104 && m.estado==='LIBRE');",
                        "const ocupada=mesas.find(m=>m.numero_mesa===9101 && m.estado==='OCUPADA');",
                        "pm.test('Mesas demo coherentes',()=>{pm.expect(libre).to.exist;pm.expect(ocupada).to.exist;});",
                        "if(libre)pm.environment.set('demoMesaLibreId',libre.id_mesa);",
                        "if(ocupada)pm.environment.set('demoMesaOcupadaId',ocupada.id_mesa);",
                    ),
                ),
                request(
                    "GET Consultar mesa por ID",
                    "GET",
                    "/mesas/{{mesaCrudId}}",
                    after=checks(200),
                ),
                request(
                    "PUT Actualizar mesa",
                    "PUT",
                    "/mesas/{{mesaCrudId}}",
                    '{"numero_mesa":{{mesaCrudUpdatedNumber}}}',
                    after=checks(200),
                ),
                request(
                    "ERROR Estado de mesa inválido",
                    "PATCH",
                    "/mesas/{{mesaCrudId}}/estado",
                    '{"estado":"RESERVADA"}',
                    after=checks(400),
                ),
                request(
                    "PATCH Cambiar estado de mesa CRUD",
                    "PATCH",
                    "/mesas/{{mesaCrudId}}/estado",
                    '{"estado":"FUERA_DE_SERVICIO"}',
                    after=checks(200),
                ),
                request(
                    "POST Preparar mesa libre para pedidos",
                    "POST",
                    "/mesas",
                    '{"numero_mesa":{{mesaNumber}}}',
                    before=("pm.environment.set('mesaNumber', 500000 + Math.floor(Math.random() * 300000));",),
                    after=checks(
                        201,
                        "if (pm.response.code === 201) pm.environment.set('mesaId', pm.response.json().id_mesa);",
                    ),
                ),
            ],
        )
    )

    folders.append(
        folder(
            4,
            [
                request(
                    "Precondición - Obtener roles base",
                    "GET",
                    "/api/tipos-usuario",
                    after=checks(
                        200,
                        "const roles = pm.response.json().datos;",
                        "const map = {MESERO:'employeeRoleId',COCINA:'kitchenRoleId',CLIENTE:'clientRoleId',DOMICILIARIO:'courierRoleId'};",
                        "Object.entries(map).forEach(([name,key]) => { const r=roles.find(x => x.descripcion === name); if(r) pm.environment.set(key,r.id_tipo_usuario); });",
                    ),
                ),
                request(
                    "POST Registrar usuario para CRUD",
                    "POST",
                    "/api/usuarios",
                    '{"id_tipo_usuario":{{employeeRoleId}},"nombre":"Usuario CRUD","usuario_login":"{{userCrudLogin}}","contrasena":"ClaveSegura123","correo":"{{userCrudEmail}}"}',
                    before=(
                        "const run=Date.now();",
                        "pm.environment.set('userCrudLogin','usuario_crud_'+run);",
                        "pm.environment.set('userCrudEmail','usuario_crud_'+run+'@example.com');",
                    ),
                    after=checks(
                        201,
                        "if(pm.response.code===201) pm.environment.set('userCrudId',pm.response.json().datos.id_usuario);",
                    ),
                ),
                request(
                    "GET Listar usuarios",
                    "GET",
                    "/api/usuarios",
                    after=checks(
                        200,
                        "const users=pm.response.json().datos;",
                        "const demoMap={demo_admin:'demoAdminId',demo_cocina:'demoKitchenId',demo_mesero_1:'demoWaiterId',demo_cliente_1:'demoClientId',demo_domiciliario:'demoCourierId'};",
                        "Object.entries(demoMap).forEach(([login,key])=>{const u=users.find(x=>x.usuario_login===login);if(u)pm.environment.set(key,u.id_usuario);});",
                        "pm.test('Actores demo disponibles',()=>Object.keys(demoMap).forEach(login=>pm.expect(users.some(u=>u.usuario_login===login)).to.eql(true)));",
                    ),
                ),
                request(
                    "GET Consultar usuario por ID",
                    "GET",
                    "/api/usuarios/{{userCrudId}}",
                    after=checks(200),
                ),
                request(
                    "PUT Actualizar usuario",
                    "PUT",
                    "/api/usuarios/{{userCrudId}}",
                    '{"id_tipo_usuario":{{employeeRoleId}},"nombre":"Usuario CRUD actualizado","usuario_login":"{{userCrudLogin}}","correo":"{{userCrudEmail}}","telefono":"3110000000","activo":true}',
                    after=checks(200),
                ),
                request(
                    "PATCH Cambiar estado de usuario",
                    "PATCH",
                    "/api/usuarios/{{userCrudId}}/estado",
                    '{"activo":true}',
                    after=checks(200),
                ),
                request(
                    "ERROR Usuario duplicado",
                    "POST",
                    "/api/usuarios",
                    '{"id_tipo_usuario":{{employeeRoleId}},"nombre":"Duplicado","usuario_login":"{{userCrudLogin}}","contrasena":"ClaveSegura123"}',
                    after=checks(409),
                ),
                request(
                    "DELETE Desactivar usuario CRUD",
                    "DELETE",
                    "/api/usuarios/{{userCrudId}}",
                    after=checks(200),
                ),
                *actor_requests(),
            ],
        )
    )

    folders.append(
        folder(
            5,
            [
                request("GET Listar roles", "GET", "/api/tipos-usuario", after=checks(200)),
                request(
                    "POST Crear rol",
                    "POST",
                    "/api/tipos-usuario",
                    '{"descripcion":"{{roleName}}"}',
                    before=("pm.environment.set('roleName','ROL_POSTMAN_'+Date.now());",),
                    after=checks(
                        201,
                        "if(pm.response.code===201) pm.environment.set('roleId',pm.response.json().datos.id_tipo_usuario);",
                    ),
                ),
                request(
                    "GET Consultar rol por ID",
                    "GET",
                    "/api/tipos-usuario/{{roleId}}",
                    after=checks(200),
                ),
                request(
                    "PUT Actualizar rol",
                    "PUT",
                    "/api/tipos-usuario/{{roleId}}",
                    '{"descripcion":"{{roleName}}_ACTUALIZADO"}',
                    after=checks(200),
                ),
                request(
                    "ERROR No eliminar rol base",
                    "DELETE",
                    "/api/tipos-usuario/{{employeeRoleId}}",
                    after=checks(409),
                ),
                request(
                    "DELETE Eliminar rol sin usuarios",
                    "DELETE",
                    "/api/tipos-usuario/{{roleId}}",
                    after=checks(200),
                ),
            ],
        )
    )

    folders.append(
        folder(
            6,
            [
                request(
                    "POST Iniciar sesión con credenciales correctas",
                    "POST",
                    "/api/auth/login",
                    '{"usuario_login":"{{employeeLogin}}","contrasena":"ClaveSegura123"}',
                    after=checks(200),
                ),
                request(
                    "ERROR Credenciales incorrectas",
                    "POST",
                    "/api/auth/login",
                    '{"usuario_login":"{{employeeLogin}}","contrasena":"Incorrecta"}',
                    after=checks(401),
                ),
                request(
                    "Precondición - Desactivar temporalmente usuario",
                    "PATCH",
                    "/api/usuarios/{{userId}}/estado",
                    '{"activo":false}',
                    after=checks(200),
                ),
                request(
                    "ERROR Usuario inactivo",
                    "POST",
                    "/api/auth/login",
                    '{"usuario_login":"{{employeeLogin}}","contrasena":"ClaveSegura123"}',
                    after=checks(403),
                ),
                request(
                    "Restaurar usuario activo para pedidos",
                    "PATCH",
                    "/api/usuarios/{{userId}}/estado",
                    '{"activo":true}',
                    after=checks(200),
                ),
            ],
        )
    )

    folders.append(folder(7, schedule_requests()))
    folders.append(folder(8, salon_order_requests()))
    folders.append(folder(9, delivery_order_requests()))
    folders.append(folder(10, detail_requests()))
    folders.append(folder(11, kitchen_requests()))
    folders.append(folder(12, status_requests()))
    folders.append(folder(13, payment_requests()))
    folders.append(folder(14, delivery_requests()))
    folders.append(folder(15, history_requests()))

    assert len(folders) == 15
    assert [item["name"] for item in folders] == [
        functionality_label(number) for number in range(1, 16)
    ]

    return {
        "info": {
            "_postman_id": "6fbfeaec-827f-4c90-9524-15f7648d0426",
            "name": "PoliRestaurante — 15 Funcionalidades",
            "description": (
                "Colección principal organizada 1 a 1 con los menús Driver y ORM. "
                "Ejecutar en el orden guardado con el ambiente PoliRestaurante local."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": folders,
    }


def actor_requests():
    definitions = (
        ("Mesero", "employeeRoleId", "employee", "userId"),
        ("Cocina", "kitchenRoleId", "kitchen", "kitchenId"),
        ("Cliente", "clientRoleId", "client", "clientId"),
        ("Domiciliario", "courierRoleId", "courier", "courierId"),
    )
    items = []
    for label, role_key, prefix, id_key in definitions:
        items.append(
            request(
                f"Preparar usuario {label} para el flujo integrado",
                "POST",
                "/api/usuarios",
                (
                    '{"id_tipo_usuario":{{'
                    + role_key
                    + '}},"nombre":"'
                    + label
                    + ' Postman","usuario_login":"{{'
                    + prefix
                    + 'Login}}","contrasena":"ClaveSegura123","correo":"{{'
                    + prefix
                    + 'Email}}"}'
                ),
                before=(
                    "const run=Date.now();",
                    f"pm.environment.set('{prefix}Login','{prefix}_postman_'+run);",
                    f"pm.environment.set('{prefix}Email','{prefix}_postman_'+run+'@example.com');",
                ),
                after=checks(
                    201,
                    f"if(pm.response.code===201) pm.environment.set('{id_key}',pm.response.json().datos.id_usuario);",
                ),
            )
        )
    return items


def schedule_requests():
    body = '{"id_usuario":{{userId}},"fecha":"2099-10-24","hora_inicio":"08:00","hora_fin":"16:00","observacion":"Horario Postman"}'
    return [
        request(
            "POST Crear horario",
            "POST",
            "/api/horarios",
            body,
            after=checks(
                201,
                "if(pm.response.code===201) pm.environment.set('scheduleId',pm.response.json().datos.id_horario);",
            ),
        ),
        request("GET Listar horarios", "GET", "/api/horarios?id_usuario={{userId}}", after=checks(200)),
        request("GET Consultar horario por ID", "GET", "/api/horarios/{{scheduleId}}", after=checks(200)),
        request(
            "PUT Actualizar horario",
            "PUT",
            "/api/horarios/{{scheduleId}}",
            '{"id_usuario":{{userId}},"fecha":"2099-10-24","hora_inicio":"08:00","hora_fin":"17:00","observacion":"Actualizado"}',
            after=checks(200),
        ),
        request(
            "ERROR Rango de horas inválido",
            "POST",
            "/api/horarios",
            '{"id_usuario":{{userId}},"fecha":"2099-10-25","hora_inicio":"18:00","hora_fin":"08:00"}',
            after=checks(400),
        ),
        request("DELETE Eliminar horario", "DELETE", "/api/horarios/{{scheduleId}}", after=checks(200)),
    ]


def salon_order_requests():
    return [
        request(
            "POST Registrar pedido en salón",
            "POST",
            "/api/pedidos",
            '{"tipo":"SALON","id_mesa":{{mesaId}},"id_mesero":{{userId}},"observaciones":"Pedido Postman"}',
            after=checks(
                201,
                "if(pm.response.code===201) pm.environment.set('salonOrderId',pm.response.json().datos.id_pedido);",
            ),
        ),
        request(
            "GET Listar pedidos",
            "GET",
            "/api/pedidos",
            after=checks(
                200,
                "const orders=pm.response.json().datos;",
                "const demoMap={'[DEMO:PEDIDO_SALON_PENDIENTE]':'demoSalonPendingId','[DEMO:PEDIDO_SALON_EN_PREPARACION]':'demoSalonPreparingId','[DEMO:PEDIDO_SALON_ENTREGADO]':'demoSalonDeliveredId','[DEMO:PEDIDO_DOMICILIO_PENDIENTE]':'demoDeliveryPendingId','[DEMO:PEDIDO_DOMICILIO_LISTO]':'demoDeliveryReadyId','[DEMO:PEDIDO_DOMICILIO_ENTREGADO]':'demoDeliveryDeliveredId','[DEMO:PEDIDO_PARA_LLEVAR_CANCELADO]':'demoCancelledOrderId'};",
                "Object.entries(demoMap).forEach(([marker,key])=>{const p=orders.find(x=>(x.observaciones||'').startsWith(marker));if(p)pm.environment.set(key,p.id_pedido);});",
                "pm.test('Siete pedidos demo disponibles',()=>Object.keys(demoMap).forEach(marker=>pm.expect(orders.some(p=>(p.observaciones||'').startsWith(marker))).to.eql(true)));",
            ),
        ),
        request("GET Consultar pedido", "GET", "/api/pedidos/{{salonOrderId}}", after=checks(200)),
        request(
            "PUT Actualizar observaciones",
            "PUT",
            "/api/pedidos/{{salonOrderId}}",
            '{"observaciones":"Pedido actualizado desde Postman"}',
            after=checks(200),
        ),
        request(
            "ERROR Mesa ocupada",
            "POST",
            "/api/pedidos",
            '{"tipo":"SALON","id_mesa":{{mesaId}},"id_mesero":{{userId}}}',
            after=checks(409),
        ),
        request(
            "POST Preparar pedido para cancelación",
            "POST",
            "/api/pedidos",
            '{"tipo":"PARA_LLEVAR","id_mesero":{{userId}},"observaciones":"Cancelar"}',
            after=checks(
                201,
                "if(pm.response.code===201) pm.environment.set('cancelOrderId',pm.response.json().datos.id_pedido);",
            ),
        ),
        request(
            "DELETE Cancelar pedido lógicamente",
            "DELETE",
            "/api/pedidos/{{cancelOrderId}}",
            '{"id_usuario_cambio":{{userId}},"observacion":"Cancelación controlada"}',
            after=checks(200),
        ),
    ]


def delivery_order_requests():
    return [
        request(
            "POST Registrar pedido a domicilio",
            "POST",
            "/api/pedidos",
            '{"tipo":"DOMICILIO","id_cliente":{{clientId}},"direccion_entrega":"Calle 10 # 20-30","telefono_contacto":"3001234567"}',
            after=checks(
                201,
                "if(pm.response.code===201){const p=pm.response.json().datos;pm.environment.set('deliveryOrderId',p.id_pedido);pm.environment.set('deliveryId',p.entrega.id_entrega);}",
            ),
        ),
        request("GET Consultar pedido a domicilio", "GET", "/api/pedidos/{{deliveryOrderId}}", after=checks(200)),
        request(
            "PUT Actualizar observaciones de domicilio",
            "PUT",
            "/api/pedidos/{{deliveryOrderId}}",
            '{"observaciones":"Domicilio actualizado"}',
            after=checks(200),
        ),
        request(
            "ERROR Domicilio sin cliente ni dirección",
            "POST",
            "/api/pedidos",
            '{"tipo":"DOMICILIO"}',
            after=checks(400),
        ),
    ]


def detail_requests():
    def add(name, order_variable, detail_variable, total_variable, quantity=1):
        return request(
            name,
            "POST",
            f"/api/pedidos/{{{{{order_variable}}}}}/detalles",
            '{"id_producto":{{productId}},"cantidad":' + str(quantity) + '}',
            after=checks(
                201,
                f"if(pm.response.code===201){{const r=pm.response.json();pm.environment.set('{detail_variable}',r.datos.id_detalle);pm.environment.set('{total_variable}',r.valor_total);}}",
            ),
        )

    return [
        add(
            "POST Agregar producto al pedido de salón",
            "salonOrderId",
            "detailId",
            "salonOrderTotal",
        ),
        request("GET Consultar detalle", "GET", "/api/pedidos/{{salonOrderId}}/detalles", after=checks(200)),
        request(
            "PUT Actualizar cantidad",
            "PUT",
            "/api/pedidos/{{salonOrderId}}/detalles/{{detailId}}",
            '{"cantidad":2,"comentarios":"Dos porciones"}',
            after=checks(
                200,
                "if(pm.response.code===200)pm.environment.set('salonOrderTotal',pm.response.json().valor_total);",
            ),
        ),
        request(
            "PATCH Actualizar comentarios",
            "PATCH",
            "/api/pedidos/{{salonOrderId}}/detalles/{{detailId}}",
            '{"comentarios":"Sin salsas"}',
            after=checks(200),
        ),
        request(
            "ERROR Cantidad no positiva",
            "PUT",
            "/api/pedidos/{{salonOrderId}}/detalles/{{detailId}}",
            '{"cantidad":0}',
            after=checks(400),
        ),
        request(
            "DELETE Quitar producto",
            "DELETE",
            "/api/pedidos/{{salonOrderId}}/detalles/{{detailId}}",
            after=checks(200),
        ),
        add(
            "POST Volver a agregar producto al salón",
            "salonOrderId",
            "detailId",
            "salonOrderTotal",
            2,
        ),
        request(
            "ERROR Producto duplicado en el pedido",
            "POST",
            "/api/pedidos/{{salonOrderId}}/detalles",
            '{"id_producto":{{productId}},"cantidad":1}',
            after=checks(409),
        ),
        add(
            "POST Agregar producto al domicilio",
            "deliveryOrderId",
            "deliveryDetailId",
            "deliveryOrderTotal",
        ),
    ]


def kitchen_requests():
    return [
        request("GET Pedidos activos de Cocina", "GET", "/api/cocina/pedidos", after=checks(200)),
        request("GET Filtrar Cocina por PENDIENTE", "GET", "/api/cocina/pedidos?estado=PENDIENTE", after=checks(200)),
        request("GET Filtrar Cocina por EN_PREPARACION", "GET", "/api/cocina/pedidos?estado=EN_PREPARACION", after=checks(200)),
        request("ERROR Estado de Cocina inválido", "GET", "/api/cocina/pedidos?estado=DESCONOCIDO", after=checks(400)),
    ]


def status_requests():
    def change(name, order_key, state, user_key, expected=200):
        return request(
            name,
            "PATCH",
            f"/api/pedidos/{{{{{order_key}}}}}/estado",
            '{"estado":"' + state + '","id_usuario_cambio":{{' + user_key + '}}}',
            after=checks(expected),
        )

    return [
        change("ERROR Cliente no puede preparar", "salonOrderId", "EN_PREPARACION", "clientId", 403),
        change("PATCH Salón EN_PREPARACION", "salonOrderId", "EN_PREPARACION", "kitchenId"),
        change("PATCH Salón LISTO", "salonOrderId", "LISTO", "kitchenId"),
        change("PATCH Salón ENTREGADO", "salonOrderId", "ENTREGADO", "userId"),
        change("PATCH Domicilio EN_PREPARACION", "deliveryOrderId", "EN_PREPARACION", "kitchenId"),
        change("PATCH Domicilio LISTO", "deliveryOrderId", "LISTO", "kitchenId"),
        change("ERROR Transición inválida", "salonOrderId", "EN_PREPARACION", "kitchenId", 409),
    ]


def payment_requests():
    return [
        request(
            "GET Listar pagos",
            "GET",
            "/api/pagos",
            after=checks(
                200,
                "const payments=pm.response.json().datos;",
                "const approved=payments.find(p=>p.id_pedido===Number(pm.environment.get('demoSalonDeliveredId')));",
                "const pending=payments.find(p=>p.id_pedido===Number(pm.environment.get('demoDeliveryReadyId')));",
                "pm.test('Pagos demo disponibles',()=>{pm.expect(approved).to.exist;pm.expect(pending).to.exist;});",
                "if(approved)pm.environment.set('demoPaymentId',approved.id_pago);",
                "if(pending)pm.environment.set('demoPendingPaymentId',pending.id_pago);",
            ),
        ),
        request(
            "ERROR Valor diferente al total",
            "POST",
            "/api/pagos",
            '{"id_pedido":{{salonOrderId}},"metodo":"EFECTIVO","valor":1}',
            after=checks(409),
        ),
        request(
            "POST Registrar pago",
            "POST",
            "/api/pagos",
            '{"id_pedido":{{salonOrderId}},"metodo":"EFECTIVO","valor":{{salonOrderTotal}}}',
            after=checks(
                201,
                "if(pm.response.code===201)pm.environment.set('paymentId',pm.response.json().datos.id_pago);",
            ),
        ),
        request("GET Consultar pago", "GET", "/api/pagos/{{paymentId}}", after=checks(200)),
        request(
            "PUT Actualizar pago pendiente",
            "PUT",
            "/api/pagos/{{paymentId}}",
            '{"metodo":"EFECTIVO","valor":{{salonOrderTotal}}}',
            after=checks(200),
        ),
        request(
            "PATCH Aprobar pago",
            "PATCH",
            "/api/pagos/{{paymentId}}/estado",
            '{"estado":"APROBADO","id_usuario_confirma":{{userId}}}',
            after=checks(200),
        ),
        request("ERROR No eliminar pago finalizado", "DELETE", "/api/pagos/{{paymentId}}", after=checks(409)),
    ]


def delivery_requests():
    return [
        request(
            "GET Listar entregas",
            "GET",
            "/api/entregas",
            after=checks(
                200,
                "const deliveries=pm.response.json().datos;",
                "const pending=deliveries.find(e=>e.id_pedido===Number(pm.environment.get('demoDeliveryPendingId')));",
                "const ready=deliveries.find(e=>e.id_pedido===Number(pm.environment.get('demoDeliveryReadyId')));",
                "const delivered=deliveries.find(e=>e.id_pedido===Number(pm.environment.get('demoDeliveryDeliveredId')));",
                "pm.test('Entregas demo disponibles',()=>{pm.expect(pending).to.exist;pm.expect(ready).to.exist;pm.expect(delivered).to.exist;});",
                "if(pending)pm.environment.set('demoDeliveryId',pending.id_entrega);",
                "if(ready)pm.environment.set('demoReadyDeliveryId',ready.id_entrega);",
                "if(delivered)pm.environment.set('demoDeliveredDeliveryId',delivered.id_entrega);",
            ),
        ),
        request("GET Consultar entrega", "GET", "/api/entregas/{{deliveryId}}", after=checks(200)),
        request(
            "ERROR No asignar un pedido de salón",
            "PATCH",
            "/api/pedidos/{{salonOrderId}}/domiciliario",
            '{"id_domiciliario":{{courierId}}}',
            after=checks(422),
        ),
        request(
            "PUT Actualizar datos de entrega",
            "PUT",
            "/api/entregas/{{deliveryId}}",
            '{"direccion_entrega":"Carrera 20 # 30-40","telefono_contacto":"3111234567","observacion":"Portería"}',
            after=checks(200),
        ),
        request(
            "PATCH Asignar domiciliario",
            "PATCH",
            "/api/pedidos/{{deliveryOrderId}}/domiciliario",
            '{"id_domiciliario":{{courierId}}}',
            after=checks(200),
        ),
        request("PATCH Marcar entrega RECOGIDA", "PATCH", "/api/entregas/{{deliveryId}}/estado", '{"estado":"RECOGIDA"}', after=checks(200)),
        request("PATCH Marcar entrega EN_CAMINO", "PATCH", "/api/entregas/{{deliveryId}}/estado", '{"estado":"EN_CAMINO"}', after=checks(200)),
        request("PATCH Confirmar entrega ENTREGADA", "PATCH", "/api/entregas/{{deliveryId}}/estado", '{"estado":"ENTREGADA"}', after=checks(200)),
        request("ERROR No eliminar entrega finalizada", "DELETE", "/api/entregas/{{deliveryId}}", after=checks(409)),
    ]


def history_requests():
    return [
        request(
            "GET Historial completo de pedido demo",
            "GET",
            "/api/pedidos/{{demoDeliveryDeliveredId}}/historial",
            after=checks(
                200,
                "const states=pm.response.json().datos.map(x=>x.estado);",
                "pm.test('Historial demo completo',()=>pm.expect(states).to.eql(['PENDIENTE','EN_PREPARACION','LISTO','ENTREGADO']));",
            ),
        ),
        request("GET Estado actual del pedido de salón", "GET", "/api/pedidos/{{salonOrderId}}", after=checks(200)),
        request("GET Historial del pedido de salón", "GET", "/api/pedidos/{{salonOrderId}}/historial", after=checks(200)),
        request("GET Estado actual del domicilio", "GET", "/api/pedidos/{{deliveryOrderId}}", after=checks(200)),
        request(
            "GET Historial del domicilio",
            "GET",
            "/api/pedidos/{{deliveryOrderId}}/historial",
            after=checks(
                200,
                "pm.test('Incluye estado ENTREGADO',()=>pm.expect(pm.response.json().datos.map(x=>x.estado)).to.include('ENTREGADO'));",
            ),
        ),
        request("ERROR Pedido inexistente", "GET", "/api/pedidos/2147483647", after=checks(404)),
    ]


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(build_collection(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Colección generada: {OUTPUT}")
