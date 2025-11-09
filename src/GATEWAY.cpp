#include <painlessMesh.h>
#include <WiFi.h>
#include <PubSubClient.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

#define WIFI_SSID "Laptop-Santiago"
#define WIFI_PASSWORD "salchipapa123"
#define MQTT_SERVER "10.42.0.1"
#define MQTT_PORT 1883
#define MQTT_TOPIC "dht22/datos"

Scheduler userScheduler;
painlessMesh mesh;
WiFiClient espClient;
PubSubClient client(espClient);

// Buffer para mensajes cuando MQTT está desconectado
struct Message {
  uint32_t nodeId;
  String data;
};
Message messageBuffer[10];
int bufferIndex = 0;

void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Datos recibidos desde nodo %u: %s\n", from, msg.c_str());

  if (client.connected()) {
    String topic = String(MQTT_TOPIC) + "/" + String(from);
    if (client.publish(topic.c_str(), msg.c_str())) {
      Serial.println("Publicado en MQTT: " + msg);
    } else {
      Serial.println("Error al publicar en MQTT");
    }
  } else {
    Serial.println("MQTT desconectado - guardando");
    if (bufferIndex < 10) {
      messageBuffer[bufferIndex].nodeId = from;
      messageBuffer[bufferIndex].data = msg;
      bufferIndex++;
    }
  }
}

void newConnectionCallback(uint32_t nodeId) {
  Serial.printf("Nueva conexión mesh, nodeId = %u\n", nodeId);
  Serial.printf("Total nodos conectados: %d\n", mesh.getNodeList().size());
}

void changedConnectionCallback() {
  Serial.printf("Conexiones cambiadas. Nodos actuales: %d\n", mesh.getNodeList().size());
  
  auto nodes = mesh.getNodeList();
  if (nodes.size() > 0) {
    Serial.print("Nodos conectados: ");
    for (auto node : nodes) {
      Serial.printf("%u ", node);
    }
    Serial.println();
  } else {
    Serial.println("No hay nodos conectados al mesh");
  }
}

void reconnect() {
  int attempts = 0;
  while (!client.connected() && attempts < 3) {
    attempts++;
    Serial.printf("MQTT (%d/3)...", attempts);
    String clientId = "ESP32Gateway-" + String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("✅");
      
      // Enviar buffer
      for (int i = 0; i < bufferIndex; i++) {
        String topic = String(MQTT_TOPIC) + "/" + String(messageBuffer[i].nodeId);
        client.publish(topic.c_str(), messageBuffer[i].data.c_str());
      }
      if (bufferIndex > 0) {
        Serial.printf("Enviados %d del buffer\n", bufferIndex);
        bufferIndex = 0;
      }
      return;
    } else {
      Serial.printf("Fallo MQTT, rc=%d reintentando en 5s\n", client.state());
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== INICIANDO ESP32 GATEWAY ===");

  // Iniciar mesh primero
  mesh.setDebugMsgTypes(ERROR | STARTUP);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);

  Serial.printf("NODE ID: %u\n", mesh.getNodeId());
  
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);

  // Usar stationManual para conectar a WiFi externo
  mesh.stationManual(WIFI_SSID, WIFI_PASSWORD);
  mesh.setHostname("ESP32-Gateway");

  client.setServer(MQTT_SERVER, MQTT_PORT);
  
  Serial.println("Gateway configurado - Esperando WiFi y conexiones mesh...");
}

void loop() {
  static unsigned long lastStatus = 0;
  static unsigned long lastMQTT = 0;
  
  mesh.update();
  
  // Verificar MQTT cada 5 segundos
  if (millis() - lastMQTT > 5000) {
    lastMQTT = millis();
    IPAddress ip = mesh.getStationIP();
    if(ip != IPAddress(0,0,0,0)) {
      if (!client.connected()) {
        Serial.printf("WiFi IP: %s - Intentando MQTT...\n", ip.toString().c_str());
        reconnect();
      }
    } else {
      Serial.println("Sin IP WiFi - esperando conexión...");
    }
  }
  
  if (client.connected()) {
    client.loop();
  }
  
  // Estado cada 30 segundos
  if (millis() - lastStatus > 30000) {
    lastStatus = millis();
    IPAddress ip = mesh.getStationIP();
    Serial.printf("IP=%s, Nodos=%d, MQTT=%s, Buffer=%d\n", 
                  ip.toString().c_str(),
                  mesh.getNodeList().size(),
                  client.connected() ? "BIEN" : "MAL",
                  bufferIndex);
  }
}