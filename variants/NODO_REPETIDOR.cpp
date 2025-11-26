#include <painlessMesh.h>
#include <ArduinoJson.h>
#include <WiFi.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

Scheduler userScheduler;
painlessMesh mesh;

// Variables para manejar ping entre nodos
struct PendingPing {
  uint32_t targetNode;
  uint32_t seq;
  unsigned long sentTime;
  bool active;
};

PendingPing nodePing = {0, 0, 0, false};

void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("[RX] de %u: %s\n", from, msg.c_str());
  
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, msg);
  
  if (err == DeserializationError::Ok && doc.containsKey("type")) {
    String msgType = doc["type"].as<String>();
    uint32_t myId = mesh.getNodeId();
    
    // PING_CMD: Gateway ordena hacer ping a otro nodo
    if (msgType == "PING_CMD") {
      uint32_t sourceNode = doc["from"].as<uint32_t>();
      uint32_t targetNode = doc["to"].as<uint32_t>();
      uint32_t seq = doc["seq"].as<uint32_t>();
      
      // Solo procesar si soy el nodo origen
      if (sourceNode == myId) {
        if (nodePing.active) {
          Serial.println("[PING_CMD] Ya hay un ping pendiente, ignorado");
          return;
        }
        
        // Iniciar ping al nodo destino
        nodePing.targetNode = targetNode;
        nodePing.seq = seq;
        nodePing.sentTime = millis();
        nodePing.active = true;
        
        StaticJsonDocument<128> pingMsg;
        pingMsg["type"] = "PING";
        pingMsg["from"] = myId;
        pingMsg["to"] = targetNode;
        pingMsg["seq"] = seq;
        
        String out;
        serializeJson(pingMsg, out);
        mesh.sendBroadcast(out);
        
        Serial.printf("[PING_CMD] Haciendo PING a nodo %u (seq=%u)\n", targetNode, seq);
      }
      return;
    }
    
    // PING: Responder con PONG si es para mí
    if (msgType == "PING") {
      uint32_t targetNode = doc["to"].as<uint32_t>();
      uint32_t sourceNode = doc["from"].as<uint32_t>();
      uint32_t seq = doc["seq"].as<uint32_t>();
      
      if (targetNode == myId) {
        StaticJsonDocument<128> pongMsg;
        pongMsg["type"] = "PONG";
        pongMsg["from"] = myId;
        pongMsg["to"] = sourceNode;
        pongMsg["seq"] = seq;
        
        String out;
        serializeJson(pongMsg, out);
        mesh.sendBroadcast(out);
        
        Serial.printf("[PING] Recibido de %u seq=%u -> PONG enviado\n", sourceNode, seq);
      }
      return;
    }
    
    // PONG: Si tengo un ping pendiente, reportar RTT al gateway
    if (msgType == "PONG" && nodePing.active) {
      uint32_t targetNode = doc["from"].as<uint32_t>();
      uint32_t seq = doc["seq"].as<uint32_t>();
      
      if (targetNode == nodePing.targetNode && seq == nodePing.seq) {
        unsigned long rtt = millis() - nodePing.sentTime;
        
        // Enviar resultado al gateway
        StaticJsonDocument<128> reportMsg;
        reportMsg["type"] = "PONG";
        reportMsg["from"] = myId;
        reportMsg["to"] = targetNode;
        reportMsg["seq"] = seq;
        reportMsg["rtt"] = rtt;
        
        String out;
        serializeJson(reportMsg, out);
        mesh.sendBroadcast(out);
        
        Serial.printf("[PONG] Recibido de %u RTT=%lums (seq=%u)\n", targetNode, rtt, seq);
        nodePing.active = false;
      }
      return;
    }
    
    // INFO_REQ: Gateway solicita información del nodo
    if (msgType == "INFO_REQ") {
      StaticJsonDocument<128> infoMsg;
      infoMsg["type"] = "INFO";
      infoMsg["node_type"] = "Nodo Repetidor";
      infoMsg["sensors"] = "Ninguno";
      
      String out;
      serializeJson(infoMsg, out);
      mesh.sendBroadcast(out);
      
      Serial.println("[INFO_REQ] Enviando información al gateway");
      return;
    }
  }
  
  // Mensaje normal (ignorar, este nodo no procesa datos de sensores)
  Serial.printf("[INFO] Mensaje no procesado: %s\n", msg.c_str());
}

void newConnectionCallback(uint32_t nodeId) {
  Serial.printf("Nueva conexión: %u\n", nodeId);
}

void changedConnectionCallback() {
  Serial.printf("Conexiones: %d nodos\n", mesh.getNodeList().size());
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== INICIANDO NODO REPETIDOR ===");
  
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  
  Serial.printf("NODE ID: %u\n", mesh.getNodeId());
  
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);
  
  Serial.println("Nodo repetidor configurado - Sin sensores, solo diagnóstico mesh");
}

void loop() {
  mesh.update();
  
  // Monitorear timeout de ping (5 segundos)
  if (nodePing.active && (millis() - nodePing.sentTime > 5000)) {
    Serial.printf("[PING] TIMEOUT: No se recibió PONG de nodo %u\n", nodePing.targetNode);
    nodePing.active = false;
  }
}
