from extensions import db


class Producto(db.Model):
    """Producto del catálogo.

    Los atributos conservan los nombres usados por la API de Productos, mientras
    que los nombres físicos de las columnas respetan el modelo relacional oficial.
    """

    __tablename__ = "producto"

    id_producto = db.Column(db.Integer, primary_key=True)
    nombre = db.Column("nombre_producto", db.String(120), nullable=False, unique=True)
    descripcion = db.Column("descripcion_producto", db.String(500))
    precio = db.Column("precio_producto", db.Numeric(12, 2), nullable=False)
    activo = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    disponible = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    id_categoria = db.Column(
        db.Integer,
        db.ForeignKey("categoria.id_categoria", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    categoria = db.relationship("Categoria")
    detalles = db.relationship("DetallePedido", back_populates="producto")
