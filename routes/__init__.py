from api_mesas import mesas_bp
from main import productos_bp
from routes.categorias import categorias_bp
from routes.entregas import entregas_bp
from routes.horarios import horarios_bp
from routes.pagos import pagos_bp
from routes.pedidos import cocina_bp, pedidos_bp
from routes.usuarios import usuarios_bp


def register_blueprints(app):
    app.register_blueprint(categorias_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(horarios_bp)
    app.register_blueprint(pagos_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(cocina_bp)
    app.register_blueprint(entregas_bp)
    app.register_blueprint(mesas_bp)
    app.register_blueprint(productos_bp)
