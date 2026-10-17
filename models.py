import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, func

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


class Pago(db.Model):
    __tablename__ = "pago"

    id_pago = db.Column(db.Integer, primary_key=True)
    # La FK a pedido se añadirá al integrar el modelo compartido de la otra integrante.
    id_pedido = db.Column(db.Integer, nullable=False, unique=True, index=True)
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
    # La FK a pedido se añadirá al integrar el modelo compartido de la otra integrante.
    id_pedido = db.Column(db.Integer, nullable=False, unique=True, index=True)
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
