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
    obtener_campos_nodo,
    eliminar_dato,
    obtener_ultima_ubicacion,
    set_gateway_ip,
    get_gateway_ip
)
import folium  # Reimportado para crear_mapa en la página principal

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
        gateway_ip = get_gateway_ip()
        return render_template('index.html',
                               total_registros=total_registros,
                               ultimo_dato=ultimo_dato,
                               nodos=nodos,
                               mapa=mapa_html, # PROBANDO MAPITA
                               gateway_ip=gateway_ip
                               )

    except Exception as e:
        return f"Servidor AgroLink activo. Error: {str(e)}"


def obtener_ubicaciones_nodos():
    """Devuelve dict {nodeId: {lat, lon}} para todos los nodos con ubicación."""
    locs = {}
    for nid in obtener_nodos_unicos():
        loc = obtener_ultima_ubicacion(nid)
        if loc and loc.get('lat') is not None and loc.get('lon') is not None:
            locs[nid] = {'lat': loc['lat'], 'lon': loc['lon']}
    return locs


@app.route('/nodo/<string:node_id>')
def ver_por_nodo(node_id: str):
    try:
        datos = obtener_datos_paginados(limit=100, offset=0, node_id=node_id)
        dato = obtener_ultimo_dato(node_id=node_id)
        total_registros = contar_registros(node_id=node_id)
        nodos = obtener_nodos_unicos()
        campos = obtener_campos_nodo(node_id)
        ubicacion = obtener_ultima_ubicacion(node_id)
        ubicaciones_todos = obtener_ubicaciones_nodos()

        # Centro inicial para Leaflet
        if ubicacion and ubicacion.get('lat') and ubicacion.get('lon'):
            centro_lat = ubicacion['lat']
            centro_lon = ubicacion['lon']
        else:
            centro_lat, centro_lon = 4.660753, -74.059945

        datos_dict = [d.to_dict() for d in datos]

        return render_template('nodo.html',
                               node_id=node_id,
                               datos=datos,
                               datos_json=datos_dict,
                               total_registros=total_registros,
                               ultimo_dato=dato,
                               nodos=nodos,
                               campos=campos,
                               ubicacion=ubicacion,
                               centro_lat=centro_lat,
                               centro_lon=centro_lon,
                               ubicaciones_todos=ubicaciones_todos
                               )
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/ver')
def ver_datos():
    try:
        # Enviar los últimos 100 datos y la lista de nodos al template para que pueda renderizar y recibir actualizaciones
        datos = obtener_todos_datos(limit=100)
        nodos = obtener_nodos_unicos()
        gateway_ip = get_gateway_ip()
        return render_template('tabla.html', datos=datos, nodos=nodos, gateway_ip=gateway_ip)
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

        # Si es un mensaje de gateway con IP y sin sensores, manejar primero
        if data.get('nodeId', '').lower() == 'gateway' and 'ip' in data and all(k not in data for k in ['temperatura','temperature','temp','t','humedad','humidity','hum','h','soil_moisture','light','luz','lux','l','percentage','luz_porcentaje','light_percentage','porcentaje','pct','lat','latitude','latitud','lon','longitude','longitud','lng']):
            ip_val = str(data.get('ip')) if data.get('ip') else None
            if ip_val:
                if set_gateway_ip(ip_val):
                    socketio.emit('gateway_ip', {'ip': ip_val})
                    return jsonify({"status": "ok", "mensaje": "Gateway IP actualizada"}), 200
                else:
                    return jsonify({"status": "error", "mensaje": "No se pudo actualizar la Gateway IP"}), 500
            else:
                return jsonify({"status": "error", "mensaje": "IP vacía"}), 400

        # Normalizar nombres de campos - temperatura
        if 'temperatura' not in data:
            for alt in ('temperature', 'temp', 't'):
                if alt in data:
                    try:
                        data['temperatura'] = float(data.pop(alt))
                    except Exception:
                        data.setdefault('temperatura', data.pop(alt))
                    break

        # Normalizar humedad (aire)
        if 'humedad' not in data:
            for alt in ('humidity', 'hum', 'h'):
                if alt in data:
                    try:
                        data['humedad'] = float(data.pop(alt))
                    except Exception:
                        data.setdefault('humedad', data.pop(alt))
                    break

        # Normalizar luz
        if 'light' not in data:
            for alt in ('luz', 'lux', 'l'):
                if alt in data:
                    try:
                        data['light'] = float(data.pop(alt))
                    except Exception:
                        data.setdefault('light', data.pop(alt))
                    break

        # Normalizar porcentaje de luz
        if 'percentage' not in data:
            for alt in ('luz_porcentaje', 'light_percentage', 'porcentaje', 'pct'):
                if alt in data:
                    try:
                        data['percentage'] = float(data.pop(alt))
                    except Exception:
                        data.setdefault('percentage', data.pop(alt))
                    break

        # Normalizar lat/lon
        if 'lat' not in data:
            for alt in ('latitude', 'latitud', 'y'):
                if alt in data:
                    try:
                        data['lat'] = float(data.pop(alt))
                    except Exception:
                        data.setdefault('lat', data.pop(alt))
                    break
        if 'lon' not in data:
            for alt in ('longitude', 'longitud', 'lng', 'x'):
                if alt in data:
                    try:
                        data['lon'] = float(data.pop(alt))
                    except Exception:
                        data.setdefault('lon', data.pop(alt))
                    break

        # Normalizar IP de la gateway
        gateway_ip_payload = None
        for k in ('gateway_ip', 'ip', 'gatewayIP'):
            if k in data and data.get(k):
                gateway_ip_payload = str(data.get(k))
                break

        # Extraer todos los valores posibles
        temperatura = data.get('temperatura')
        humedad = data.get('humedad')
        soil_moisture = data.get('soil_moisture')
        light = data.get('light')
        percentage = data.get('percentage')
        lat = data.get('lat')
        lon = data.get('lon')
        node_id = data.get('nodeId') or data.get('node_id') or 'unknown'
        timestamp = data.get('timestamp')

        # Si el payload es solo para actualizar IP de gateway
        if gateway_ip_payload and all(v is None for v in [temperatura, humedad, soil_moisture, light, percentage, lat, lon, timestamp]):
            ok = set_gateway_ip(gateway_ip_payload)
            if ok:
                # Emitir a todos los clientes la IP actualizada
                try:
                    socketio.emit('gateway_ip', {'ip': gateway_ip_payload})
                except Exception:
                    pass
                return jsonify({"status": "ok", "mensaje": "Gateway IP actualizada"}), 200
            else:
                return jsonify({"status": "error", "mensaje": "No se pudo actualizar la Gateway IP"}), 500

        # Guardar en base de datos usando la función del módulo database
        nuevo_dato = guardar_dato_sensor(
            temperatura=temperatura,
            humedad=humedad,
            soil_moisture=soil_moisture,
            light=light,
            percentage=percentage,
            node_id=node_id,
            timestamp=timestamp,
            lat=lat,
            lon=lon
        )

        print(f"Dato guardado en BD: ID={nuevo_dato.id}")  # Debug

        # Emitir evento en tiempo real a todos los clientes conectados
        try:
            payload = nuevo_dato.to_dict()
            socketio.emit('nuevo_dato', payload)
            if payload.get('lat') is not None and payload.get('lon') is not None and payload.get('nodeId'):
                print(f"Emitiendo ubicacion_nodo: {payload.get('nodeId')} {payload.get('lat')},{payload.get('lon')}")
                socketio.emit('ubicacion_nodo', {
                    'nodeId': payload.get('nodeId'),
                    'lat': payload.get('lat'),
                    'lon': payload.get('lon'),
                    'fecha': payload.get('fecha_creacion')
                })
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
            'mensaje': f'Conectado al servidor AgroLink. {len(ultimos_datos)} registros enviados.',
            'gateway_ip': get_gateway_ip()
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