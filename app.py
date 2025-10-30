from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask_socketio import SocketIO, emit

app = Flask(__name__)

# Configurar base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///datos_sensores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# Forzar modo threading para evitar cargar eventlet/gevent (corrige error ssl.wrap_socket)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='gevent')


# ==================== MODELO DE DATOS ====================

class DatosSensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperatura = db.Column(db.Float, nullable=False)
    humedad = db.Column(db.Float, nullable=False)
    nodeId = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.Integer, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'temperatura': self.temperatura,
            'humedad': self.humedad,
            'nodeId': self.nodeId,
            'timestamp': self.timestamp,
            'fecha_creacion': self.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S %Z')
        }


# Crear tablas al iniciar
with app.app_context():
    db.create_all()


# ==================== RUTAS HTTP ====================

@app.route('/')
def home():
    try:
        total_registros = DatosSensor.query.count()
        ultimo_dato = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).first()
        # Obtener lista de nodos únicos para la barra de navegación
        nodos = [row[0] for row in db.session.query(DatosSensor.nodeId).distinct().order_by(DatosSensor.nodeId.asc()).all() if row[0]]

        return render_template('index.html',
                               total_registros=total_registros,
                               ultimo_dato=ultimo_dato,
                               nodos=nodos
                               )
    except Exception as e:
        return f"Servidor AgroLink activo. Error: {str(e)}"


@app.route('/nodo/<string:node_id>')
def ver_por_nodo(node_id: str):
    try:
        # Datos más recientes de ese nodo
        dato = DatosSensor.query.filter_by(nodeId=node_id).order_by(DatosSensor.fecha_creacion.desc()).first()
        total_registros = DatosSensor.query.filter_by(nodeId=node_id).count()
        # Lista de nodos para mantener el menú
        nodos = [row[0] for row in db.session.query(DatosSensor.nodeId).distinct().order_by(DatosSensor.nodeId.asc()).all() if row[0]]

        return render_template('index.html',
                               total_registros=total_registros,
                               ultimo_dato=dato,
                               nodos=nodos
                               )
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/ver')
def ver_datos():
    try:
        return render_template('dht22.html')
    except Exception as e:
        return f"Error: {e}", 500


# Archivo: app.py

@app.route('/datos', methods=['POST'])
def recibir_datos():
    try:
        data = request.json
        print(f"Datos recibidos: {data}")  # Debug

        if not data:
            return jsonify({"status": "error", "mensaje": "No se recibió JSON"}), 400

        # Validar campos requeridos
        if 'temperatura' not in data or 'humedad' not in data:
            return jsonify({"status": "error", "mensaje": "Faltan campos temperatura/humedad"}), 400

        # Crear nuevo registro
        nuevo_dato = DatosSensor(
            temperatura=float(data['temperatura']),
            humedad=float(data['humedad']),
            nodeId=data.get('nodeId', 'unknown'),
            timestamp=data.get('timestamp', int(datetime.now().timestamp()))
        )

        # Guardar en base de datos
        db.session.add(nuevo_dato)
        db.session.commit()

        print(f"Dato guardado en BD: ID={nuevo_dato.id}")  # Debug

        # Emitir evento en tiempo real a todos los clientes conectados
        try:
            socketio.emit('nuevo_dato', nuevo_dato.to_dict())
        except Exception as _e:
            print(f"Advertencia: no se pudo emitir por SocketIO: {_e}")

        return jsonify({
            "status": "ok",
            "mensaje": "Dato guardado en BD",
            "id": nuevo_dato.id
        }), 200

    except Exception as e:
        print(f"Error guardando dato: {e}")  # Debug
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": str(e)}), 500


@app.route('/api/datos')
def api_datos():
    try:
        limit = request.args.get('limit', 100, type=int)
        datos = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).limit(limit).all()
        return jsonify([dato.to_dict() for dato in datos])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== HANDLERS DE EVENTOS SOCKET.IO ====================

@socketio.on('connect')
def handle_connect():
    """Maneja la conexión de un nuevo cliente"""
    print('Cliente conectado')
    try:
        ultimos_datos = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).limit(10).all()
        emit('datos_iniciales', {
            'datos': [dato.to_dict() for dato in ultimos_datos],
            'mensaje': f'Conectado al servidor AgroLink. {len(ultimos_datos)} registros enviados.'
        })
    except Exception as e:
        emit('error', {'mensaje': f'Error al obtener datos iniciales: {str(e)}'})


@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado')


@socketio.on('solicitar_datos')
def handle_solicitar_datos(data):
    """Maneja solicitudes de datos históricos"""
    try:
        limit = data.get('limit', 100)
        offset = data.get('offset', 0)
        node_id = data.get('nodeId')

        query = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc())

        if node_id:
            query = query.filter_by(nodeId=node_id)

        datos = query.offset(offset).limit(limit).all()

        emit('resultado_datos', {
            'datos': [dato.to_dict() for dato in datos],
            'total': len(datos),
            'offset': offset,
            'limit': limit
        })
    except Exception as e:
        emit('error', {'mensaje': f'Error al obtener datos: {str(e)}'})


@socketio.on('filtrar_por_fecha')
def handle_filtrar_por_fecha(data):
    """Filtra datos por rango de fechas"""
    try:
        fecha_inicio = datetime.fromisoformat(data.get('fecha_inicio', ''))
        fecha_fin = datetime.fromisoformat(data.get('fecha_fin', ''))

        if not fecha_inicio or not fecha_fin:
            emit('error', {'mensaje': 'Formato de fechas inválido'})
            return

        datos = DatosSensor.query.filter(
            DatosSensor.fecha_creacion.between(fecha_inicio, fecha_fin)
        ).order_by(DatosSensor.fecha_creacion).all()

        emit('resultado_filtrado', {
            'datos': [dato.to_dict() for dato in datos],
            'total': len(datos),
            'fecha_inicio': fecha_inicio.isoformat(),
            'fecha_fin': fecha_fin.isoformat()
        })
    except Exception as e:
        emit('error', {'mensaje': f'Error al filtrar por fechas: {str(e)}'})


@socketio.on('obtener_estadisticas')
def handle_estadisticas(data):
    """Obtiene estadísticas de los datos de sensores"""
    try:
        from sqlalchemy import func

        # Calcular estadísticas
        stats = db.session.query(
            func.avg(DatosSensor.temperatura).label('temp_promedio'),
            func.max(DatosSensor.temperatura).label('temp_maxima'),
            func.min(DatosSensor.temperatura).label('temp_minima'),
            func.avg(DatosSensor.humedad).label('hum_promedio'),
            func.max(DatosSensor.humedad).label('hum_maxima'),
            func.min(DatosSensor.humedad).label('hum_minima'),
            func.count(DatosSensor.id).label('total_registros')
        ).one()

        # Obtener último registro
        ultimo_registro = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).first()

        emit('resultado_estadisticas', {
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
        })
    except Exception as e:
        emit('error', {'mensaje': f'Error al obtener estadísticas: {str(e)}'})


@socketio.on('eliminar_dato')
def handle_eliminar_dato(data):
    """Elimina un registro específico (solo para administradores)"""
    try:
        # Aquí se podría añadir verificación de autenticación
        id_dato = data.get('id')
        if not id_dato:
            emit('error', {'mensaje': 'ID no proporcionado'})
            return

        dato = DatosSensor.query.get(id_dato)
        if not dato:
            emit('error', {'mensaje': f'Dato con ID {id_dato} no encontrado'})
            return

        db.session.delete(dato)
        db.session.commit()

        emit('dato_eliminado', {
            'id': id_dato,
            'mensaje': f'Dato con ID {id_dato} eliminado correctamente'
        })

        # Notificar a todos los clientes que se ha eliminado un dato
        socketio.emit('actualizacion_datos', {
            'accion': 'eliminar',
            'id': id_dato
        }, broadcast=True)

    except Exception as e:
        db.session.rollback()
        emit('error', {'mensaje': f'Error al eliminar dato: {str(e)}'})


# ==================== PUNTO DE ENTRADA PRINCIPAL ====================

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)