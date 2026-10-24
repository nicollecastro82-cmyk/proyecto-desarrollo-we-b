from flask import Blueprint, jsonify, request

from mesas import (
    ESTADOS_VALIDOS,
    actualizar_mesa,
    cambiar_estado,
    consultar_mesa,
    crear_mesa,
    eliminar_mesa,
    listar_mesas,
    normalizar_estado,
)


mesas_bp = Blueprint("mesas", __name__)


def mesa_a_dict(mesa):
    estado = mesa.estado.value if hasattr(mesa.estado, "value") else str(mesa.estado)
    return {
        "id_mesa": mesa.id_mesa,
        "numero_mesa": mesa.numero_mesa,
        "estado": estado,
    }


def respuesta_error(mensaje):
    if mensaje.startswith("No existe"):
        codigo = 404
    elif mensaje.startswith(("Ya existe", "La mesa")):
        codigo = 409
    elif mensaje.startswith("No fue posible"):
        codigo = 500
    else:
        codigo = 400
    return jsonify({"error": mensaje}), codigo


def leer_cuerpo():
    if not request.is_json:
        return None
    cuerpo = request.get_json(silent=True)
    return cuerpo if isinstance(cuerpo, dict) else None


def leer_numero(cuerpo):
    if cuerpo is None:
        return None
    numero = cuerpo.get("numero_mesa")
    if isinstance(numero, bool) or not isinstance(numero, int):
        return None
    return numero


@mesas_bp.post("/mesas")
def registrar_mesa():
    numero = leer_numero(leer_cuerpo())
    if numero is None:
        return respuesta_error("El número de la mesa es obligatorio y debe ser un entero.")

    mesa, error = crear_mesa(numero)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 201


@mesas_bp.get("/mesas")
def consultar_mesas():
    estado = request.args.get("estado")
    mesas, error = listar_mesas(estado)
    if error:
        return respuesta_error(error)
    return jsonify([mesa_a_dict(mesa) for mesa in mesas]), 200


@mesas_bp.get("/mesas/<int:id_mesa>")
def consultar_mesa_por_id(id_mesa):
    mesa, error = consultar_mesa(id_mesa)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 200


@mesas_bp.put("/mesas/<int:id_mesa>")
def modificar_mesa(id_mesa):
    numero = leer_numero(leer_cuerpo())
    if numero is None:
        return respuesta_error("El número de la mesa es obligatorio y debe ser un entero.")

    mesa, error = actualizar_mesa(id_mesa, numero)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 200


@mesas_bp.patch("/mesas/<int:id_mesa>/estado")
def modificar_estado(id_mesa):
    cuerpo = leer_cuerpo()
    estado = cuerpo.get("estado") if cuerpo is not None else None
    if normalizar_estado(estado) is None:
        return respuesta_error(f"El estado debe ser uno de: {', '.join(ESTADOS_VALIDOS)}.")

    mesa, error = cambiar_estado(id_mesa, estado)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 200

@mesas_bp.delete("/mesas/<int:id_mesa>")
def borrar_mesa(id_mesa):
    numero, error = eliminar_mesa(id_mesa)
    if error:
        return respuesta_error(error)
    return jsonify({"mensaje": f"Mesa {numero} eliminada."}), 200

if __name__ == "__main__":
    from app import create_app

    create_app().run(debug=True)
