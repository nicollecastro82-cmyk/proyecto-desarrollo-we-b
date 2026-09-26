from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from categorias import Categoria, app, db, nombre_duplicado, validar_nombre


def mostrar_categoria(categoria):
    estado = "Activa" if categoria.activo else "Inactiva"
    print(
        f"ID: {categoria.id_categoria} | "
        f"Nombre: {categoria.nombre} | "
        f"Estado: {estado}"
    )


def crear_categoria():
    nombre = input("Nombre de la categoría: ").strip()
    error = validar_nombre(nombre)

    if error:
        print(f"Error: {error}")
        return
    if nombre_duplicado(nombre):
        print("Error: ya existe una categoría con ese nombre.")
        return

    categoria = Categoria(nombre=nombre, activo=True)
    db.session.add(categoria)

    try:
        db.session.commit()
        print(f"Categoría creada con el ID {categoria.id_categoria}.")
    except IntegrityError:
        db.session.rollback()
        print("Error: ya existe una categoría con ese nombre.")


def listar_categorias():
    categorias = db.session.scalars(
        db.select(Categoria)
        .where(Categoria.activo.is_(True))
        .order_by(Categoria.id_categoria)
    ).all()

    if not categorias:
        print("No hay categorías activas registradas.")
        return

    print("\nCATEGORÍAS ACTIVAS")
    for categoria in categorias:
        mostrar_categoria(categoria)


def buscar_categorias():
    texto = input("Texto que deseas buscar: ").strip()
    categorias = db.session.scalars(
        db.select(Categoria)
        .where(
            Categoria.nombre.ilike(f"%{texto}%"),
            Categoria.activo.is_(True),
        )
        .order_by(Categoria.id_categoria)
    ).all()

    if not categorias:
        print("No se encontraron categorías activas.")
        return

    for categoria in categorias:
        mostrar_categoria(categoria)


def pedir_categoria():
    valor = input("ID de la categoría: ").strip()

    if not valor.isdigit():
        print("Error: el ID debe ser un número entero.")
        return None

    categoria = db.session.get(Categoria, int(valor))
    if categoria is None:
        print("Error: categoría no encontrada.")
        return None
    return categoria


def modificar_categoria():
    categoria = pedir_categoria()
    if categoria is None:
        return

    print(f"Nombre actual: {categoria.nombre}")
    nombre = input("Nuevo nombre: ").strip()
    error = validar_nombre(nombre)

    if error:
        print(f"Error: {error}")
        return
    if nombre_duplicado(nombre, excluir_id=categoria.id_categoria):
        print("Error: ya existe una categoría con ese nombre.")
        return

    categoria.nombre = nombre
    try:
        db.session.commit()
        print("Categoría modificada correctamente.")
    except IntegrityError:
        db.session.rollback()
        print("Error: ya existe una categoría con ese nombre.")


def cambiar_estado_categoria():
    categoria = pedir_categoria()
    if categoria is None:
        return

    categoria.activo = not categoria.activo
    db.session.commit()
    estado = "activada" if categoria.activo else "desactivada"
    print(f"Categoría {estado} correctamente.")


def mostrar_menu():
    print(
        """
POLIRESTAURANTE: CATEGORIAS
1. Crear categoría
2. Consultar categorías activas
3. Buscar categoría activa
4. Modificar categoría
5. Activar o desactivar categoría
0. Salir
"""
    )


def ejecutar_menu():
    opciones = {
        "1": crear_categoria,
        "2": listar_categorias,
        "3": buscar_categorias,
        "4": modificar_categoria,
        "5": cambiar_estado_categoria,
    }

    with app.app_context():
        while True:
            mostrar_menu()
            opcion = input("Selecciona una opción: ").strip()

            if opcion == "0":
                print("Programa finalizado.")
                break

            operacion = opciones.get(opcion)
            if operacion is None:
                print("Opción no válida.")
                continue

            try:
                operacion()
            except SQLAlchemyError as error:
                db.session.rollback()
                print(f"Error al trabajar con PostgreSQL: {error}")


if __name__ == "__main__":
    ejecutar_menu()
