from decimal import Decimal, InvalidOperation

from flask import jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from catalogo_dao import CatalogoDAO
from categorias import app, db
from producto import Producto

dao = CatalogoDAO()


def producto_a_dict(p):
    return {
        "id_producto": p.id_producto,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "precio": float(p.precio),
        "disponible": p.disponible,
        "categoria": {
            "id_categoria": p.categoria.id_categoria,
            "nombre": p.categoria.nombre,
        },
    }


def error(mensaje, codigo):
    return jsonify({"error": mensaje}), codigo


def convertir_precio(valor):
    try:
        precio = Decimal(str(valor))
    except InvalidOperation:
        return None
    return precio if precio > 0 else None


def validar_categoria(id_categoria):
    if not isinstance(id_categoria, int):
        return None
    categoria = dao.buscar_categoria_por_id(id_categoria)
    if categoria is None or not categoria.activo:
        return None
    return categoria


# 1. Crear producto
@app.post("/productos")
def crear_producto():
    datos = request.get_json(silent=True) or {}
    nombre = str(datos.get("nombre", "")).strip()

    if not nombre or len(nombre) > 100:
        return error("El nombre es obligatorio y máximo de 100 caracteres.", 400)
    if dao.nombre_duplicado(nombre):
        return error("Ya existe un producto con ese nombre.", 409)

    precio = convertir_precio(datos.get("precio"))
    if precio is None:
        return error("El precio debe ser un número mayor que cero.", 400)

    categoria = validar_categoria(datos.get("id_categoria"))
    if categoria is None:
        return error("La categoría no existe o está inactiva.", 400)

    producto = Producto(
        nombre=nombre,
        descripcion=datos.get("descripcion"),
        precio=precio,
        id_categoria=categoria.id_categoria,
    )
    dao.guardar_producto(producto)
    return jsonify(producto_a_dict(producto)), 201


# 2. Consultar productos disponibles (opcional: ?id_categoria=1 o ?buscar=texto)
@app.get("/productos")
def listar_productos():
    buscar = request.args.get("buscar", "").strip()
    id_categoria = request.args.get("id_categoria", type=int)

    if buscar:
        productos = dao.buscar_productos_disponibles(buscar)
    else:
        productos = dao.listar_productos_disponibles(id_categoria)

    return jsonify([producto_a_dict(p) for p in productos])


# Consultar un producto por ID
@app.get("/productos/<int:id_producto>")
def obtener_producto(id_producto):
    producto = dao.buscar_producto_por_id(id_producto)
    if producto is None:
        return error("Producto no encontrado.", 404)
    return jsonify(producto_a_dict(producto))


# 3. Modificar producto (se envía solo lo que cambia)
@app.put("/productos/<int:id_producto>")
def modificar_producto(id_producto):
    producto = dao.buscar_producto_por_id(id_producto)
    if producto is None:
        return error("Producto no encontrado.", 404)

    datos = request.get_json(silent=True) or {}

    if "nombre" in datos:
        nombre = str(datos["nombre"]).strip()
        if not nombre or len(nombre) > 100:
            return error("El nombre es obligatorio y máximo de 100 caracteres.", 400)
        if dao.nombre_duplicado(nombre, excluir_id=id_producto):
            return error("Ya existe un producto con ese nombre.", 409)
        producto.nombre = nombre

    if "descripcion" in datos:
        producto.descripcion = datos["descripcion"]

    if "precio" in datos:
        precio = convertir_precio(datos["precio"])
        if precio is None:
            return error("El precio debe ser un número mayor que cero.", 400)
        producto.precio = precio

    if "id_categoria" in datos:
        categoria = validar_categoria(datos["id_categoria"])
        if categoria is None:
            return error("La categoría no existe o está inactiva.", 400)
        producto.id_categoria = categoria.id_categoria

    dao.guardar_producto(producto)
    return jsonify(producto_a_dict(producto))


# 4. Activar o desactivar disponibilidad
@app.patch("/productos/<int:id_producto>/disponibilidad")
def cambiar_disponibilidad(id_producto):
    producto = dao.buscar_producto_por_id(id_producto)
    if producto is None:
        return error("Producto no encontrado.", 404)

    datos = request.get_json(silent=True) or {}
    disponible = datos.get("disponible")
    if not isinstance(disponible, bool):
        return error('Envía {"disponible": true} o {"disponible": false}.', 400)

    producto.disponible = disponible
    dao.guardar_producto(producto)
    return jsonify(producto_a_dict(producto))


# 5. "Eliminar": no se borra, se desactiva
@app.delete("/productos/<int:id_producto>")
def eliminar_producto(id_producto):
    producto = dao.buscar_producto_por_id(id_producto)
    if producto is None:
        return error("Producto no encontrado.", 404)

    producto.disponible = False
    dao.guardar_producto(producto)
    return jsonify({"mensaje": "Producto desactivado correctamente."})


@app.errorhandler(SQLAlchemyError)
def error_base_datos(e):
    db.session.rollback()
    return error(f"Error con PostgreSQL: {e}", 500)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # crea la tabla producto si no existe
    app.run(debug=True)