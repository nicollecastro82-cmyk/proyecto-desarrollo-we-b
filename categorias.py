import os

import click
import psycopg
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from psycopg import sql
from sqlalchemy import func
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

db = SQLAlchemy()


class Categoria(db.Model):
    __tablename__ = "categoria"

    id_categoria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5433/polirestaurante",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    register_commands(app)
    return app


def validar_nombre(nombre):
    if not nombre:
        return "El nombre de la categoría es obligatorio."
    if len(nombre) > 100:
        return "El nombre no puede superar los 100 caracteres."
    return None


def nombre_duplicado(nombre, excluir_id=None):
    consulta = db.select(Categoria).where(func.lower(Categoria.nombre) == nombre.lower())
    if excluir_id is not None:
        consulta = consulta.where(Categoria.id_categoria != excluir_id)
    return db.session.scalar(consulta) is not None


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Crea la base PostgreSQL y las tablas de la aplicación."""
        database_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])

        if database_url.get_backend_name() != "postgresql":
            db.create_all()
            click.echo("Tablas creadas correctamente.")
            return

        database_name = database_url.database
        if not database_name:
            raise click.ClickException("DATABASE_URL debe incluir el nombre de la base de datos.")

        connection_options = {
            "dbname": "postgres",
            "user": database_url.username,
            "password": database_url.password,
            "host": database_url.host or "localhost",
            "port": database_url.port or 5432,
            "autocommit": True,
        }

        try:
            with psycopg.connect(**connection_options) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (database_name,),
                    )
                    if cursor.fetchone() is None:
                        cursor.execute(
                            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
                        )
                        click.echo(f"Base de datos '{database_name}' creada.")
                    else:
                        click.echo(f"La base de datos '{database_name}' ya existe.")

            db.create_all()
        except (psycopg.Error, SQLAlchemyError) as error:
            raise click.ClickException(
                "No fue posible preparar PostgreSQL. Revisa DATABASE_URL y que el servidor esté activo. "
                f"Detalle: {error}"
            ) from error

        click.echo("Tabla 'categoria' creada correctamente.")


app = create_app()
