from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# Configurar base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///datos_sensores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Modelo de base de datos
class DatosSensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperatura = db.Column(db.Float, nullable=False)
    humedad = db.Column(db.Float, nullable=False)
    nodeId = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.Integer, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'temperatura': self.temperatura,
            'humedad': self.humedad,
            'nodeId': self.nodeId,
            'timestamp': self.timestamp,
            'fecha_creacion': self.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')
        }


# Crear tablas al iniciar
with app.app_context():
    db.create_all()


# Endpoint para recibir datos desde el puente MQTT
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

        return jsonify({
            "status": "ok",
            "mensaje": "Dato guardado en BD",
            "id": nuevo_dato.id
        }), 200

    except Exception as e:
        print(f"Error guardando dato: {e}")  # Debug
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": str(e)}), 500


# Endpoint para visualizar en tabla
@app.route('/ver')
def ver_datos():
    try:
        # Obtener últimos 100 registros
        datos = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).limit(100).all()
        datos_dict = [dato.to_dict() for dato in datos]
        return render_template('dht22.html', datos=datos_dict)
    except Exception as e:
        print(f"Error obteniendo datos: {e}")
        return f"Error: {e}", 500


# Endpoint API para obtener datos en JSON
@app.route('/api/datos')
def api_datos():
    try:
        datos = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).limit(100).all()
        return jsonify([dato.to_dict() for dato in datos])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    try:
        total_registros = DatosSensor.query.count()
        ultimo_dato = DatosSensor.query.order_by(DatosSensor.fecha_creacion.desc()).first()

        return f"""
        <h1>Servidor AgroLink Activo</h1>
        <p>Total registros: {total_registros}</p>
        <p>Ultimo dato: {ultimo_dato.fecha_creacion if ultimo_dato else 'Sin datos'}</p>
        <p><a href="/ver">Ver datos en tabla</a></p>
        <p><a href="/api/datos">API JSON</a></p>
        """
    except:
        return "Servidor Flask activo. Visita /ver para ver datos."


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)