import os

import click
import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from api_utils import ApiError
from extensions import db
from models import TipoUsuario
from routes import register_blueprints


load_dotenv()

DEFAULT_ROLES = ("ADMINISTRADOR", "COCINA", "MESERO", "CLIENTE", "DOMICILIARIO")


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5433/polirestaurante",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_commands(app)

    @app.get("/api/salud")
    def health():
        db.session.execute(text("SELECT 1"))
        return jsonify({"estado": "ok", "base_datos": "conectada"})

    return app


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        payload = {"error": {"codigo": error.code, "mensaje": error.message}}
        if error.details is not None:
            payload["error"]["detalles"] = error.details
        return jsonify(payload), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(
            {"error": {"codigo": error.name.upper().replace(" ", "_"), "mensaje": error.description}}
        ), error.code

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        db.session.rollback()
        app.logger.exception("Error de base de datos", exc_info=error)
        return jsonify(
            {
                "error": {
                    "codigo": "DATABASE_ERROR",
                    "mensaje": "No fue posible completar la operación en la base de datos.",
                }
            }
        ), 500


def seed_default_roles():
    existing = {
        value.upper()
        for value in db.session.scalars(db.select(TipoUsuario.descripcion)).all()
    }
    for role in DEFAULT_ROLES:
        if role not in existing:
            db.session.add(TipoUsuario(descripcion=role))
    db.session.commit()


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Crea la base PostgreSQL, las tablas propias y los roles iniciales."""
        database_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])

        if database_url.get_backend_name() == "postgresql":
            database_name = database_url.database
            if not database_name:
                raise click.ClickException(
                    "DATABASE_URL debe incluir el nombre de la base de datos."
                )
            options = {
                "dbname": "postgres",
                "user": database_url.username,
                "password": database_url.password,
                "host": database_url.host or "localhost",
                "port": database_url.port or 5432,
                "autocommit": True,
            }
            try:
                with psycopg.connect(**options) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT 1 FROM pg_database WHERE datname = %s",
                            (database_name,),
                        )
                        if cursor.fetchone() is None:
                            cursor.execute(
                                sql.SQL("CREATE DATABASE {}").format(
                                    sql.Identifier(database_name)
                                )
                            )
                            click.echo(f"Base de datos '{database_name}' creada.")
            except psycopg.Error as error:
                raise click.ClickException(
                    "No fue posible conectar con PostgreSQL. Revisa DATABASE_URL. "
                    f"Detalle: {error}"
                ) from error

        try:
            db.create_all()
            seed_default_roles()
        except SQLAlchemyError as error:
            db.session.rollback()
            raise click.ClickException(f"No fue posible crear las tablas: {error}") from error

        click.echo("Tablas propias y roles iniciales preparados correctamente.")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
