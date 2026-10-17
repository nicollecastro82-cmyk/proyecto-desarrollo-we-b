from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from api_utils import ApiError, bool_value, json_body, positive_int, text_value
from catalogo_dao import CatalogoDAO
from producto import Producto


productos_bp = Blueprint("productos", __name__)
dao = CatalogoDAO()


def producto_a_dict(producto):
    return {
        "id_producto": producto.id_producto,
        "nombre": producto.nombre,
        "descripcion": producto.descripcion,
        "precio": str(producto.precio),
        "activo": producto.activo,
        "disponible": producto.disponible,
        "categoria": {
            "id_categoria": producto.categoria.id_categoria,
            "nombre": producto.categoria.nombre,
        },
    }


def convertir_precio(valor):
    if isinstance(valor, bool):
        raise ApiError(
            "El precio debe ser un número mayor que cero.",
            400,
            "INVALID_PRODUCT_PRICE",
        )
    try:
        precio = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ApiError(
            "El precio debe ser un número mayor que cero.",
            400,
            "INVALID_PRODUCT_PRICE",
        ) from error
    if (
        not precio.is_finite()
        or precio <= 0
        or precio > Decimal("9999999999.99")
    ):
        raise ApiError(
            "El precio debe ser un número mayor que cero.",
            400,
            "INVALID_PRODUCT_PRICE",
        )
    return precio


def validar_categoria(id_categoria):
    category_id = positive_int(id_categoria, "id_categoria")
    categoria = dao.buscar_categoria_por_id(category_id)
    if categoria is None or not categoria.activo:
        raise ApiError(
            "La categoría no existe o está inactiva.",
            422,
            "CATEGORY_UNAVAILABLE",
        )
    return categoria


def obtener_producto_o_error(id_producto):
    producto = dao.buscar_producto_por_id(id_producto)
    if producto is None:
        raise ApiError("Producto no encontrado.", 404, "PRODUCT_NOT_FOUND")
    return producto


def validar_nombre(nombre, excluir_id=None):
    nombre = text_value(nombre, "nombre", 120)
    if dao.nombre_duplicado(nombre, excluir_id=excluir_id):
        raise ApiError(
            "Ya existe un producto con ese nombre.",
            409,
            "PRODUCT_NAME_EXISTS",
        )
    return nombre


@productos_bp.post("/productos")
def crear_producto():
    datos = json_body(
        {"nombre", "descripcion", "precio", "id_categoria"},
        {"nombre", "precio", "id_categoria"},
    )
    categoria = validar_categoria(datos["id_categoria"])
    producto = Producto(
        nombre=validar_nombre(datos["nombre"]),
        descripcion=text_value(
            datos.get("descripcion"), "descripcion", 500, required=False
        ),
        precio=convertir_precio(datos["precio"]),
        id_categoria=categoria.id_categoria,
    )
    dao.guardar_producto(producto)
    return jsonify(producto_a_dict(producto)), 201


@productos_bp.get("/productos")
def listar_productos():
    buscar = request.args.get("buscar", "").strip()
    raw_category_id = request.args.get("id_categoria")
    category_id = None
    if raw_category_id is not None:
        try:
            category_id = int(raw_category_id)
        except ValueError as error:
            raise ApiError(
                "El parámetro id_categoria debe ser un entero positivo.",
                400,
                "VALIDATION_ERROR",
            ) from error
        positive_int(category_id, "id_categoria")

    if buscar:
        if len(buscar) > 120:
            raise ApiError(
                "El parámetro buscar no puede superar 120 caracteres.",
                400,
                "VALIDATION_ERROR",
            )
        productos = dao.buscar_productos_disponibles(buscar)
    else:
        productos = dao.listar_productos_disponibles(category_id)
    return jsonify([producto_a_dict(producto) for producto in productos])


@productos_bp.get("/productos/<int:id_producto>")
def obtener_producto(id_producto):
    return jsonify(producto_a_dict(obtener_producto_o_error(id_producto)))


@productos_bp.put("/productos/<int:id_producto>")
@productos_bp.patch("/productos/<int:id_producto>")
def modificar_producto(id_producto):
    producto = obtener_producto_o_error(id_producto)
    datos = json_body({"nombre", "descripcion", "precio", "id_categoria"})

    if "nombre" in datos:
        producto.nombre = validar_nombre(datos["nombre"], excluir_id=id_producto)
    if "descripcion" in datos:
        producto.descripcion = text_value(
            datos["descripcion"], "descripcion", 500, required=False
        )
    if "precio" in datos:
        producto.precio = convertir_precio(datos["precio"])
    if "id_categoria" in datos:
        producto.id_categoria = validar_categoria(datos["id_categoria"]).id_categoria

    dao.guardar_producto(producto)
    return jsonify(producto_a_dict(producto))


@productos_bp.patch("/productos/<int:id_producto>/disponibilidad")
def cambiar_disponibilidad(id_producto):
    producto = obtener_producto_o_error(id_producto)
    datos = json_body({"disponible"}, {"disponible"})
    disponible = bool_value(datos["disponible"], "disponible")
    if disponible and not producto.activo:
        raise ApiError(
            "Un producto inactivo no se puede marcar como disponible.",
            409,
            "PRODUCT_INACTIVE",
        )
    producto.disponible = disponible
    dao.guardar_producto(producto)
    return jsonify(producto_a_dict(producto))


@productos_bp.delete("/productos/<int:id_producto>")
def eliminar_producto(id_producto):
    producto = obtener_producto_o_error(id_producto)
    producto.activo = False
    producto.disponible = False
    dao.guardar_producto(producto)
    return jsonify(
        {
            "mensaje": "Producto desactivado correctamente.",
            "datos": producto_a_dict(producto),
        }
    )


if __name__ == "__main__":
    from app import create_app

    create_app().run(debug=True)
