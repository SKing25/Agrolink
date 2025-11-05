from flask import Flask, request, jsonify, render_template
from datetime import datetime
from flask_socketio import SocketIO, emit
from database import (
    inicializar_db,
    guardar_dato_sensor,
    obtener_todos_datos,
    obtener_datos_paginados,
    obtener_datos_por_fecha,
    obtener_estadisticas,
    contar_registros,
    obtener_ultimo_dato,
    obtener_nodos_unicos,
    eliminar_dato
)
import folium

app = Flask(__name__)

# Configurar base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///datos_sensores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar base de datos
inicializar_db(app)

# Forzar modo threading para evitar cargar eventlet/gevent (corrige error ssl.wrap_socket)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# PROBANDO MAPITA
def crear_mapa(latitud, longitud):
    m = folium.Map(location=[latitud, longitud], zoom_start=20)
    folium.Marker([latitud, longitud], popup='La checho').add_to(m)
    return m._repr_html_()


# ==================== RUTAS HTTP ====================

@app.route('/')
def home():
    try:
        total_registros = contar_registros()
        ultimo_dato = obtener_ultimo_dato()
        nodos = obtener_nodos_unicos()
        mapa_html = crear_mapa(4.660753, -74.059945)  # PROBANDO MAPITA
        return render_template('index.html',
                               total_registros=total_registros,
                               ultimo_dato=ultimo_dato,
                               nodos=nodos,
                               mapa=mapa_html # PROBANDO MAPITA
                               )

    except Exception as e:
        return f"Servidor AgroLink activo. Error: {str(e)}"


@app.route('/nodo/<string:node_id>')
def ver_por_nodo(node_id: str):
    try:
        dato = obtener_ultimo_dato(node_id=node_id)
        total_registros = contar_registros(node_id=node_id)
        nodos = obtener_nodos_unicos()

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
        # Enviar los últimos 100 datos y la lista de nodos al template para que pueda renderizar y recibir actualizaciones
        datos = obtener_todos_datos(limit=100)
        nodos = obtener_nodos_unicos()
        return render_template('dht22.html', datos=datos, nodos=nodos)
    except Exception as e:
        return f"Error: {e}", 500


# Archivo: app.py

@app.route('/datos', methods=['POST'])
def recibir_datos():
    try:
        data = request.get_json(silent=True)
        print(f"Datos recibidos: {data}")  # Debug

        if not data:
            return jsonify({"status": "error", "mensaje": "No se recibió JSON"}), 400

        # Aceptar temperatura y/o humedad opcionales
        temperatura = data.get('temperatura')
        humedad = data.get('humedad')
        node_id = data.get('nodeId') or data.get('node_id') or 'unknown'
        timestamp = data.get('timestamp')

        # Validar que venga al menos uno
        if temperatura is None and humedad is None:
            return jsonify({"status": "error", "mensaje": "Falta temperatura y humedad"}), 400

        # Guardar en base de datos usando la función del módulo database
        nuevo_dato = guardar_dato_sensor(
            temperatura=temperatura,
            humedad=humedad,
            node_id=node_id,
            timestamp=timestamp
        )

        print(f"Dato guardado en BD: ID={nuevo_dato.id}")  # Debug

        # Emitir evento en tiempo real a todos los clientes conectados
        try:
            payload = nuevo_dato.to_dict()
            # Filtrar claves con valor None (no enviar temperatura/humedad si no vinieron)
            payload_filtrado = {k: v for k, v in payload.items() if not (k in ('temperatura','humedad') and v is None)}
            # Emitir a todos los clientes conectados (sin usar parámetro 'broadcast' para compatibilidad)
            socketio.emit('nuevo_dato', payload_filtrado)
        except Exception as _e:
            print(f"Advertencia: no se pudo emitir por SocketIO: {_e}")

        return jsonify({
            "status": "ok",
            "mensaje": "Dato guardado en BD",
            "id": nuevo_dato.id
        }), 200

    except Exception as e:
        print(f"Error guardando dato: {e}")  # Debug
        return jsonify({"status": "error", "mensaje": str(e)}), 500


@app.route('/api/datos')
def api_datos():
    try:
        limit = request.args.get('limit', 100, type=int)
        datos = obtener_todos_datos(limit=limit)
        return jsonify([dato.to_dict() for dato in datos])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== HANDLERS DE EVENTOS SOCKET.IO ====================

@socketio.on('connect')
def handle_connect():
    """Maneja la conexión de un nuevo cliente"""
    print('Cliente conectado')
    try:
        ultimos_datos = obtener_todos_datos(limit=10)
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

        datos = obtener_datos_paginados(limit=limit, offset=offset, node_id=node_id)

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

        datos = obtener_datos_por_fecha(fecha_inicio, fecha_fin)

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
        estadisticas = obtener_estadisticas()
        emit('resultado_estadisticas', estadisticas)
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

        eliminado = eliminar_dato(id_dato)
        if not eliminado:
            emit('error', {'mensaje': f'Dato con ID {id_dato} no encontrado'})
            return

        emit('dato_eliminado', {
            'id': id_dato,
            'mensaje': f'Dato con ID {id_dato} eliminado correctamente'
        })

        # Notificar a todos los clientes que se ha eliminado un dato
        socketio.emit('actualizacion_datos', {
            'accion': 'eliminar',
            'id': id_dato
        })

    except Exception as e:
        emit('error', {'mensaje': f'Error al eliminar dato: {str(e)}'})


# ==================== PUNTO DE ENTRADA PRINCIPAL ====================

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)