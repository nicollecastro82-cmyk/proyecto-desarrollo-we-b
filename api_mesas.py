from flask import jsonify, request

from mesas import (
    ESTADOS_VALIDOS,
    actualizar_mesa,
    app,
    cambiar_estado,
    consultar_mesa,
    crear_mesa,
    listar_mesas,
)


def mesa_a_dict(mesa):
    return {
        "id_mesa": mesa.id_mesa,
        "numero_mesa": mesa.numero_mesa,
        "estado": mesa.estado,
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
    cuerpo = request.get_json(silent=True)
    return cuerpo if isinstance(cuerpo, dict) else {}


def leer_numero(cuerpo):
    numero = cuerpo.get("numero_mesa")
    if isinstance(numero, bool) or not isinstance(numero, int):
        return None
    return numero


@app.post("/mesas")
def registrar_mesa():
    numero = leer_numero(leer_cuerpo())
    if numero is None:
        return respuesta_error("El número de la mesa es obligatorio y debe ser un entero.")

    mesa, error = crear_mesa(numero)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 201


@app.get("/mesas")
def consultar_mesas():
    estado = request.args.get("estado")
    mesas, error = listar_mesas(estado)
    if error:
        return respuesta_error(error)
    return jsonify([mesa_a_dict(m) for m in mesas]), 200


@app.get("/mesas/<int:id_mesa>")
def consultar_mesa_por_id(id_mesa):
    mesa, error = consultar_mesa(id_mesa)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 200


@app.put("/mesas/<int:id_mesa>")
def modificar_mesa(id_mesa):
    numero = leer_numero(leer_cuerpo())
    if numero is None:
        return respuesta_error("El número de la mesa es obligatorio y debe ser un entero.")

    mesa, error = actualizar_mesa(id_mesa, numero)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 200


@app.patch("/mesas/<int:id_mesa>/estado")
def modificar_estado(id_mesa):
    estado = leer_cuerpo().get("estado")
    if estado not in ESTADOS_VALIDOS:
        return respuesta_error(f"El estado debe ser uno de: {', '.join(ESTADOS_VALIDOS)}.")

    mesa, error = cambiar_estado(id_mesa, estado)
    if error:
        return respuesta_error(error)
    return jsonify(mesa_a_dict(mesa)), 200


if __name__ == "__main__":
    app.run(debug=True)