import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, UniqueConstraint, func

from extensions import db


class MetodoPago(str, enum.Enum):
    EFECTIVO = "EFECTIVO"
    PSE = "PSE"


class EstadoPago(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class EstadoEntrega(str, enum.Enum):
    PENDIENTE_ASIGNACION = "PENDIENTE_ASIGNACION"
    ASIGNADA = "ASIGNADA"
    RECOGIDA = "RECOGIDA"
    EN_CAMINO = "EN_CAMINO"
    ENTREGADA = "ENTREGADA"
    CON_INCIDENCIA = "CON_INCIDENCIA"


class TipoPedido(str, enum.Enum):
    SALON = "SALON"
    PARA_LLEVAR = "PARA_LLEVAR"
    DOMICILIO = "DOMICILIO"


class EstadoPedido(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    EN_PREPARACION = "EN_PREPARACION"
    LISTO = "LISTO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class Categoria(db.Model):
    __tablename__ = "categoria"

    id_categoria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False, unique=True)
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    def to_dict(self):
        return {
            "id_categoria": self.id_categoria,
            "nombre": self.nombre,
            "activo": self.activo,
        }


class TipoUsuario(db.Model):
    __tablename__ = "tipo_usuario"

    id_tipo_usuario = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(50), nullable=False, unique=True)

    usuarios = db.relationship("Usuario", back_populates="tipo_usuario", lazy="selectin")

    def to_dict(self):
        return {
            "id_tipo_usuario": self.id_tipo_usuario,
            "descripcion": self.descripcion,
        }


class Usuario(db.Model):
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    id_tipo_usuario = db.Column(
        db.Integer,
        db.ForeignKey("tipo_usuario.id_tipo_usuario", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nombre = db.Column(db.String(120), nullable=False)
    usuario_login = db.Column(db.String(80), nullable=False, unique=True)
    contrasena_hash = db.Column(db.String(255), nullable=False)
    correo = db.Column(db.String(120), unique=True)
    telefono = db.Column(db.String(20))
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    tipo_usuario = db.relationship("TipoUsuario", back_populates="usuarios")
    horarios = db.relationship("HorarioEmpleado", back_populates="usuario", lazy="selectin")
    pagos_confirmados = db.relationship("Pago", back_populates="usuario_confirma")
    entregas_asignadas = db.relationship("Entrega", back_populates="domiciliario")
    pedidos_atendidos = db.relationship(
        "Pedido",
        foreign_keys="Pedido.id_mesero",
        back_populates="mesero",
        lazy="selectin",
    )
    pedidos_realizados = db.relationship(
        "Pedido",
        foreign_keys="Pedido.id_cliente",
        back_populates="cliente",
        lazy="selectin",
    )
    cambios_estado = db.relationship(
        "HistorialEstado", back_populates="usuario_cambio", lazy="selectin"
    )

    def to_dict(self):
        return {
            "id_usuario": self.id_usuario,
            "id_tipo_usuario": self.id_tipo_usuario,
            "tipo_usuario": self.tipo_usuario.descripcion if self.tipo_usuario else None,
            "nombre": self.nombre,
            "usuario_login": self.usuario_login,
            "correo": self.correo,
            "telefono": self.telefono,
            "activo": self.activo,
        }


class HorarioEmpleado(db.Model):
    __tablename__ = "horario_empleado"

    id_horario = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha = db.Column(db.Date, nullable=False, index=True)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    observacion = db.Column(db.String(250))

    usuario = db.relationship("Usuario", back_populates="horarios")

    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="ck_horario_horas_validas"),
    )

    def to_dict(self):
        return {
            "id_horario": self.id_horario,
            "id_usuario": self.id_usuario,
            "fecha": self.fecha.isoformat(),
            "hora_inicio": self.hora_inicio.isoformat(timespec="minutes"),
            "hora_fin": self.hora_fin.isoformat(timespec="minutes"),
            "observacion": self.observacion,
        }


class Pedido(db.Model):
    __tablename__ = "pedido"

    id_pedido = db.Column(db.Integer, primary_key=True)
    id_mesa = db.Column(
        db.Integer,
        db.ForeignKey("mesa.id_mesa", ondelete="RESTRICT"),
        index=True,
    )
    id_mesero = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        index=True,
    )
    id_cliente = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        index=True,
    )
    tipo = db.Column(db.Enum(TipoPedido, name="tipo_pedido"), nullable=False)
    estado = db.Column(
        db.Enum(EstadoPedido, name="estado_pedido"),
        nullable=False,
        default=EstadoPedido.PENDIENTE,
        server_default=EstadoPedido.PENDIENTE.value,
        index=True,
    )
    valor_total = db.Column(
        db.Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    observaciones = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
    )
    fecha_ultima_actualizacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=func.now(),
    )

    mesa = db.relationship("Mesa", back_populates="pedidos")
    mesero = db.relationship(
        "Usuario", foreign_keys=[id_mesero], back_populates="pedidos_atendidos"
    )
    cliente = db.relationship(
        "Usuario", foreign_keys=[id_cliente], back_populates="pedidos_realizados"
    )
    pago = db.relationship("Pago", back_populates="pedido", uselist=False)
    entrega = db.relationship("Entrega", back_populates="pedido", uselist=False)
    detalles = db.relationship(
        "DetallePedido",
        back_populates="pedido",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DetallePedido.id_detalle",
    )
    historial = db.relationship(
        "HistorialEstado",
        back_populates="pedido",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HistorialEstado.fecha",
    )

    __table_args__ = (
        CheckConstraint(
            "valor_total >= 0", name="ck_pedido_valor_total_no_negativo"
        ),
    )

    def to_dict(self):
        return {
            "id_pedido": self.id_pedido,
            "id_mesa": self.id_mesa,
            "id_mesero": self.id_mesero,
            "id_cliente": self.id_cliente,
            "tipo": self.tipo.value,
            "estado": self.estado.value,
            "valor_total": str(self.valor_total),
            "observaciones": self.observaciones,
            "fecha_creacion": self.fecha_creacion.isoformat(),
            "fecha_ultima_actualizacion": self.fecha_ultima_actualizacion.isoformat(),
        }


class DetallePedido(db.Model):
    __tablename__ = "detalle_pedido"

    id_detalle = db.Column(db.Integer, primary_key=True)
    id_pedido = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id_pedido", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_producto = db.Column(
        db.Integer,
        db.ForeignKey("producto.id_producto", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    comentarios = db.Column(db.String(500))

    pedido = db.relationship("Pedido", back_populates="detalles")
    producto = db.relationship("Producto", back_populates="detalles")

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_cantidad_positiva"),
        CheckConstraint(
            "precio_unitario >= 0", name="ck_detalle_precio_no_negativo"
        ),
        UniqueConstraint(
            "id_pedido", "id_producto", name="uq_detalle_pedido_producto"
        ),
    )

    def to_dict(self):
        return {
            "id_detalle": self.id_detalle,
            "id_pedido": self.id_pedido,
            "id_producto": self.id_producto,
            "producto": self.producto.nombre if self.producto else None,
            "cantidad": self.cantidad,
            "precio_unitario": str(self.precio_unitario),
            "subtotal": str(self.cantidad * self.precio_unitario),
            "comentarios": self.comentarios,
        }


class HistorialEstado(db.Model):
    __tablename__ = "historial_estado"

    id_historial = db.Column(db.Integer, primary_key=True)
    id_pedido = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id_pedido", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_usuario_cambio = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        index=True,
    )
    estado = db.Column(db.Enum(EstadoPedido, name="estado_pedido"), nullable=False)
    fecha = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
        index=True,
    )
    observacion = db.Column(db.String(500))

    pedido = db.relationship("Pedido", back_populates="historial")
    usuario_cambio = db.relationship("Usuario", back_populates="cambios_estado")

    def to_dict(self):
        return {
            "id_historial": self.id_historial,
            "id_pedido": self.id_pedido,
            "id_usuario_cambio": self.id_usuario_cambio,
            "usuario_cambio": (
                self.usuario_cambio.nombre if self.usuario_cambio else None
            ),
            "estado": self.estado.value,
            "fecha": self.fecha.isoformat(),
            "observacion": self.observacion,
        }


class Pago(db.Model):
    __tablename__ = "pago"

    id_pago = db.Column(db.Integer, primary_key=True)
    id_pedido = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id_pedido", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    id_usuario_confirma = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        index=True,
    )
    metodo = db.Column(db.Enum(MetodoPago, name="metodo_pago"), nullable=False)
    estado = db.Column(
        db.Enum(EstadoPago, name="estado_pago"),
        nullable=False,
        default=EstadoPago.PENDIENTE,
        server_default=EstadoPago.PENDIENTE.value,
    )
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    referencia_transaccion = db.Column(db.String(150), unique=True)
    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
    )
    fecha_pago = db.Column(db.DateTime)

    usuario_confirma = db.relationship("Usuario", back_populates="pagos_confirmados")
    pedido = db.relationship("Pedido", back_populates="pago")

    __table_args__ = (CheckConstraint("valor > 0", name="ck_pago_valor_positivo"),)

    def to_dict(self):
        return {
            "id_pago": self.id_pago,
            "id_pedido": self.id_pedido,
            "id_usuario_confirma": self.id_usuario_confirma,
            "metodo": self.metodo.value,
            "estado": self.estado.value,
            "valor": str(self.valor),
            "referencia_transaccion": self.referencia_transaccion,
            "fecha_creacion": self.fecha_creacion.isoformat(),
            "fecha_pago": self.fecha_pago.isoformat() if self.fecha_pago else None,
        }


class Entrega(db.Model):
    __tablename__ = "entrega"

    id_entrega = db.Column(db.Integer, primary_key=True)
    id_pedido = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id_pedido", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    id_domiciliario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        index=True,
    )
    direccion_entrega = db.Column(db.String(250), nullable=False)
    telefono_contacto = db.Column(db.String(20), nullable=False)
    estado = db.Column(
        db.Enum(EstadoEntrega, name="estado_entrega"),
        nullable=False,
        default=EstadoEntrega.PENDIENTE_ASIGNACION,
        server_default=EstadoEntrega.PENDIENTE_ASIGNACION.value,
    )
    fecha_asignacion = db.Column(db.DateTime)
    fecha_recogida = db.Column(db.DateTime)
    fecha_entrega = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))

    domiciliario = db.relationship("Usuario", back_populates="entregas_asignadas")
    pedido = db.relationship("Pedido", back_populates="entrega")

    def to_dict(self):
        return {
            "id_entrega": self.id_entrega,
            "id_pedido": self.id_pedido,
            "id_domiciliario": self.id_domiciliario,
            "direccion_entrega": self.direccion_entrega,
            "telefono_contacto": self.telefono_contacto,
            "estado": self.estado.value,
            "fecha_asignacion": (
                self.fecha_asignacion.isoformat() if self.fecha_asignacion else None
            ),
            "fecha_recogida": self.fecha_recogida.isoformat() if self.fecha_recogida else None,
            "fecha_entrega": self.fecha_entrega.isoformat() if self.fecha_entrega else None,
            "observacion": self.observacion,
        }
