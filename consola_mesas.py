from sqlalchemy.exc import SQLAlchemyError

from app import app
from extensions import db
from mesas import (
    ESTADOS_VALIDOS,
    EstadoMesa,
    actualizar_mesa,
    consultar_mesa,
    crear_mesa,
    liberar_mesa,
    listar_mesas,
    ocupar_mesa,
)


def mostrar_mesa(mesa):
    estado = mesa.estado.value if hasattr(mesa.estado, "value") else str(mesa.estado)
    print(
        f"ID: {mesa.id_mesa} | "
        f"Número: {mesa.numero_mesa} | "
        f"Estado: {estado}"
    )


def pedir_entero(texto):
    valor = input(texto).strip()
    if not valor.isdigit():
        print("Error: debes escribir un número entero.")
        return None
    return int(valor)


def registrar_mesa():
    numero = pedir_entero("Número de la mesa: ")
    if numero is None:
        return
    mesa, error = crear_mesa(numero)
    if error:
        print(f"Error: {error}")
        return
    print(f"Mesa {mesa.numero_mesa} creada con el ID {mesa.id_mesa}.")


def mostrar_mesas():
    estado = input(
        f"Filtrar por estado ({', '.join(ESTADOS_VALIDOS)}) o Enter para ver todas: "
    ).strip()
    mesas, error = listar_mesas(estado or None)
    if error:
        print(f"Error: {error}")
        return
    if not mesas:
        print("No hay mesas registradas con ese criterio.")
        return
    print("\nMESAS")
    for mesa in mesas:
        mostrar_mesa(mesa)


def buscar_mesa():
    id_mesa = pedir_entero("ID de la mesa: ")
    if id_mesa is None:
        return
    mesa, error = consultar_mesa(id_mesa)
    if error:
        print(f"Error: {error}")
        return
    mostrar_mesa(mesa)


def modificar_mesa():
    id_mesa = pedir_entero("ID de la mesa: ")
    if id_mesa is None:
        return
    mesa, error = consultar_mesa(id_mesa)
    if error:
        print(f"Error: {error}")
        return
    print(f"Número actual: {mesa.numero_mesa}")
    nuevo_numero = pedir_entero("Nuevo número: ")
    if nuevo_numero is None:
        return
    mesa, error = actualizar_mesa(id_mesa, nuevo_numero)
    if error:
        print(f"Error: {error}")
        return
    print("Mesa modificada correctamente.")


def ocupar_o_liberar_mesa():
    id_mesa = pedir_entero("ID de la mesa: ")
    if id_mesa is None:
        return
    mesa, error = consultar_mesa(id_mesa)
    if error:
        print(f"Error: {error}")
        return
    if mesa.estado == EstadoMesa.LIBRE:
        mesa, error = ocupar_mesa(id_mesa)
    else:
        mesa, error = liberar_mesa(id_mesa)
    if error:
        print(f"Error: {error}")
        return
    mostrar_mesa(mesa)


def mostrar_menu():
    print(
        """
POLIRESTAURANTE: MESAS
1. Registrar mesa
2. Consultar mesas
3. Consultar mesa por ID
4. Actualizar número de mesa
5. Ocupar o liberar mesa
0. Salir
"""
    )


def ejecutar_menu():
    opciones = {
        "1": registrar_mesa,
        "2": mostrar_mesas,
        "3": buscar_mesa,
        "4": modificar_mesa,
        "5": ocupar_o_liberar_mesa,
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
