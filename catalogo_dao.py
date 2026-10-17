from sqlalchemy import func, or_

from extensions import db
from models import Categoria
from producto import Producto


class CatalogoDAO:
    def guardar_producto(self, producto):
        db.session.add(producto)
        db.session.commit()
        return producto

    def buscar_producto_por_id(self, id_producto):
        return db.session.get(Producto, id_producto)

    def buscar_categoria_por_id(self, id_categoria):
        return db.session.get(Categoria, id_categoria)

    def nombre_duplicado(self, nombre, excluir_id=None):
        consulta = db.select(Producto).where(
            func.lower(Producto.nombre) == nombre.lower()
        )
        if excluir_id is not None:
            consulta = consulta.where(Producto.id_producto != excluir_id)
        return db.session.scalar(consulta) is not None

    def listar_productos_disponibles(self, id_categoria=None):
        consulta = (
            db.select(Producto)
            .join(Producto.categoria)
            .where(
                Producto.activo.is_(True),
                Producto.disponible.is_(True),
                Categoria.activo.is_(True),
            )
        )
        if id_categoria is not None:
            consulta = consulta.where(Producto.id_categoria == id_categoria)
        return db.session.scalars(consulta.order_by(Producto.id_producto)).all()

    def buscar_productos_disponibles(self, texto):
        patron = f"%{texto}%"
        return db.session.scalars(
            db.select(Producto)
            .join(Producto.categoria)
            .where(
                Producto.activo.is_(True),
                Producto.disponible.is_(True),
                Categoria.activo.is_(True),
                or_(Producto.nombre.ilike(patron), Categoria.nombre.ilike(patron)),
            )
            .order_by(Producto.id_producto)
        ).all()
