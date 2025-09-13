from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Lista en memoria para guardar datos
datos_guardados = []

# Endpoint para recibir datos desde el puente MQTT
@app.route('/api/datos', methods=['POST'])
def recibir_datos():
    data = request.json
    if data:
        datos_guardados.append(data)
        return jsonify({"status": "ok", "mensaje": "Dato guardado"}), 200
    return jsonify({"status": "error", "mensaje": "No se recibió JSON"}), 400

# Endpoint para visualizar en tabla
@app.route('/ver')
def ver_datos():
    return render_template('dht22.html', datos=datos_guardados)

@app.route('/')
def home():
    return "Servidor Flask activo. Visita /ver para ver datos."

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
