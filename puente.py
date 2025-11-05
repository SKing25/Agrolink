import paho.mqtt.client as mqtt
import requests
import json
import re

BROKER = "localhost"   
PORT = 1883
TOPIC = "dht22/datos/+" 

SERVER_URL = "https://agrolink.app/datos"

def parse_message(payload):
    try:
        data = json.loads(payload)
        if "temperature" in data and "humidity" in data:
            return {
                "temperatura": data["temperature"],
                "humedad": data["humidity"]
            }
        return data
    except json.JSONDecodeError:
        try:
            match = re.search(r"Temp:([-+]?\d+\.\d+)C Hum:([-+]?\d+\.\d+)%", payload)
            if match:
                temp = float(match.group(1))
                hum = float(match.group(2))
                return {"temperatura": temp, "humedad": hum}
        except Exception as e:
            print(f"Error parseando string: {e}")
        
        return {"mensaje": payload}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado a Mosquitto")
        client.subscribe(TOPIC)
        print(f"Suscrito al tópico: {TOPIC}")
    else:
        print(f"Error de conexión con código {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        print(f"Mensaje de {topic}: {payload}")

        # Parsear el mensaje (JSON o string)
        data = parse_message(payload)
        
        # Agregar información adicional
        node_id = topic.split("/")[-1] if "/" in topic else "unknown"
        data["nodeId"] = node_id
        data["timestamp"] = int(time.time())

        print(f"Datos parseados: {data}")

        # Enviar a servidor Flask
        response = requests.post(SERVER_URL, json=data, timeout=10)
        if response.status_code == 200:
            print("Datos enviados al servidor Render")
        else:
            print(f"Error al enviar: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Error procesando mensaje: {e}")

# Importar time para timestamp
import time

# Configuración del cliente MQTT
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("Iniciando puente MQTT -> Servidor")
print(f"Broker: {BROKER}:{PORT}")
print(f"Servidor: {SERVER_URL}")

# Conexión al broker
try:
    client.connect(BROKER, PORT, 60)
    print("Iniciando loop...")
    client.loop_forever()
except KeyboardInterrupt:
    print("\nPuente detenido por usuario")
except Exception as e:
    print(f"Error en puente: {e}")