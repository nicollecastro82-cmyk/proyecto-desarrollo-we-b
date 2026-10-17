from routes.categorias import categorias_bp
from routes.entregas import entregas_bp
from routes.horarios import horarios_bp
from routes.pagos import pagos_bp
from routes.usuarios import usuarios_bp


def register_blueprints(app):
    app.register_blueprint(categorias_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(horarios_bp)
    app.register_blueprint(pagos_bp)
    app.register_blueprint(entregas_bp)
