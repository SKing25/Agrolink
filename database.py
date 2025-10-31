"""
Módulo de base de datos para AgroLink
Contiene modelos SQLAlchemy y funciones de acceso a datos
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from sqlalchemy import func

db = SQLAlchemy()


# ==================== MODELO DE DATOS ====================

class DatosSensor(db.Model):
    """Modelo para almacenar datos de sensores DHT22"""
    id = db.Column(db.Integer, primary_key=True)
    temperatura = db.Column(db.Float, nullable=False)
    humedad = db.Column(db.Float, nullable=False)
    nodeId = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.Integer, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Convierte el objeto a diccionario para serialización JSON"""
        return {
            'id': self.id,
            'temperatura': self.temperatura,
            'humedad': self.humedad,
            'nodeId': self.nodeId,
            'timestamp': self.timestamp,
            'fecha_creacion': self.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S %Z')
        }


# ==================== FUNCIONES DE ACCESO A DATOS ====================

def inicializar_db(app):
    """Inicializa la base de datos con la aplicación Flask"""
    db.init_app(app)
    with app.app_context():
        db.create_all()


def guardar_dato_sensor(temperatura, humedad, node_id='unknown', timestamp=None):
    """
    Guarda un nuevo dato de sensor en la base de datos
    
    Args:
        temperatura: Temperatura en °C
        humedad: Humedad en %
        node_id: ID del nodo sensor
        timestamp: Timestamp Unix (opcional)
    
    Returns:
        DatosSensor: El objeto guardado
    
    Raises:
        Exception: Si hay error al guardar
    """
    try:
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        
        nuevo_dato = DatosSensor(
            temperatura=float(temperatura),
            humedad=float(humedad),
            nodeId=node_id,
            timestamp=timestamp
        )
        
        db.session.add(nuevo_dato)
        db.session.commit()
        
        return nuevo_dato
    except Exception as e:
        db.session.rollback()
        raise e


def obtener_todos_datos(limit=100):
    """
    Obtiene los últimos N datos ordenados por fecha
    
    Args:
        limit: Número máximo de registros a retornar
    
    Returns:
        list: Lista de objetos DatosSensor
    """
    return DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).limit(limit).all()


def obtener_datos_paginados(limit=100, offset=0, node_id=None):
    """
    Obtiene datos con paginación y filtro opcional por nodo
    
    Args:
        limit: Número de registros por página
        offset: Desplazamiento desde el inicio
        node_id: Filtrar por ID de nodo (opcional)
    
    Returns:
        list: Lista de objetos DatosSensor
    """
    query = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc())
    
    if node_id:
        query = query.filter_by(nodeId=node_id)
    
    return query.offset(offset).limit(limit).all()


def obtener_datos_por_fecha(fecha_inicio, fecha_fin):
    """
    Obtiene datos dentro de un rango de fechas
    
    Args:
        fecha_inicio: datetime objeto de inicio
        fecha_fin: datetime objeto de fin
    
    Returns:
        list: Lista de objetos DatosSensor
    """
    return DatosSensor.query.filter(
        DatosSensor.fecha_creacion.between(fecha_inicio, fecha_fin)
    ).order_by(DatosSensor.fecha_creacion).all()


def obtener_estadisticas():
    """
    Calcula estadísticas de temperatura y humedad
    
    Returns:
        dict: Diccionario con promedios, máximos y mínimos
    """
    stats = db.session.query(
        func.avg(DatosSensor.temperatura).label('temp_promedio'),
        func.max(DatosSensor.temperatura).label('temp_maxima'),
        func.min(DatosSensor.temperatura).label('temp_minima'),
        func.avg(DatosSensor.humedad).label('hum_promedio'),
        func.max(DatosSensor.humedad).label('hum_maxima'),
        func.min(DatosSensor.humedad).label('hum_minima'),
        func.count(DatosSensor.id).label('total_registros')
    ).one()
    
    ultimo_registro = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).first()
    
    return {
        'temperatura': {
            'promedio': float(stats.temp_promedio) if stats.temp_promedio else 0,
            'maxima': float(stats.temp_maxima) if stats.temp_maxima else 0,
            'minima': float(stats.temp_minima) if stats.temp_minima else 0
        },
        'humedad': {
            'promedio': float(stats.hum_promedio) if stats.hum_promedio else 0,
            'maxima': float(stats.hum_maxima) if stats.hum_maxima else 0,
            'minima': float(stats.hum_minima) if stats.hum_minima else 0
        },
        'total_registros': stats.total_registros,
        'ultimo_registro': ultimo_registro.to_dict() if ultimo_registro else None
    }


def contar_registros(node_id=None):
    """
    Cuenta el total de registros, opcionalmente filtrado por nodo
    
    Args:
        node_id: Filtrar por ID de nodo (opcional)
    
    Returns:
        int: Número de registros
    """
    query = DatosSensor.query
    if node_id:
        query = query.filter_by(nodeId=node_id)
    return query.count()


def obtener_ultimo_dato(node_id=None):
    """
    Obtiene el último dato registrado
    
    Args:
        node_id: Filtrar por ID de nodo (opcional)
    
    Returns:
        DatosSensor: Último registro o None
    """
    query = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc())
    if node_id:
        query = query.filter_by(nodeId=node_id)
    return query.first()


def obtener_nodos_unicos():
    """
    Obtiene lista de IDs de nodos únicos
    
    Returns:
        list: Lista de strings con IDs de nodos
    """
    return [row[0] for row in db.session.query(DatosSensor.nodeId).distinct().order_by(DatosSensor.nodeId.asc()).all() if row[0]]


def eliminar_dato(dato_id):
    """
    Elimina un dato por ID
    
    Args:
        dato_id: ID del registro a eliminar
    
    Returns:
        bool: True si se eliminó, False si no se encontró
    
    Raises:
        Exception: Si hay error al eliminar
    """
    try:
        dato = DatosSensor.query.get(dato_id)
        if not dato:
            return False
        
        db.session.delete(dato)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise e

