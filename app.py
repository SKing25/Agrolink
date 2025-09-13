from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# almacenamiento temporal en memoria
datos_recibidos = []

@app.route("/")
def home():
    return "Servidor Flask activo 🚀"

@app.route("/datos", methods=["POST"])
def recibir_datos():
    contenido = request.json
    print("Dato recibido:", contenido)
    datos_recibidos.append(contenido)
    return jsonify({"status": "ok", "recibido": contenido})

@app.route("/ver", methods=["GET"])
def ver_datos():
    return render_template('dht22.html', datos=datos_recibidos)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)