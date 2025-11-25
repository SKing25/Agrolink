#include <painlessMesh.h>
#include <ArduinoJson.h>
#include <TinyGPS++.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

#define SOIL_PIN 34  
#define GPS_BAUDRATE 9600

// Calibración del sensor (ajusta según tu sensor)
#define SOIL_DRY 3200    // Valor en aire (seco)
#define SOIL_WET 1200    // Valor en agua (húmedo)

Scheduler userScheduler;
painlessMesh mesh;
TinyGPSPlus gps;
HardwareSerial gpsSerial(2);  // Serial2 para GPS

Task taskSendData(TASK_SECOND * 10, TASK_FOREVER, []() {
  int rawValue = analogRead(SOIL_PIN);
  
  // Invertir la escala (valores más altos = más seco)
  // Mapear a porcentaje 0-100% (0% = seco, 100% = húmedo)
  int percentage = map(rawValue, SOIL_DRY, SOIL_WET, 0, 100);
  
  // Limitar entre 0-100%
  percentage = constrain(percentage, 0, 100);

  // Construir JSON con humedad + GPS
  String msg = "{\"soil_moisture\":" + String(percentage);
  
  // Agregar coordenadas GPS
  if (gps.location.isValid()) {
    msg += ",\"lat\":" + String(gps.location.lat(), 6);
    msg += ",\"lon\":" + String(gps.location.lng(), 6);
    Serial.printf("GPS OK - Sat: %d\n", gps.satellites.value());
  } else {
    msg += ",\"lat\":\"no data\"";
    msg += ",\"lon\":\"no data\"";
    Serial.printf("GPS sin fix - Sat: %d, Chars: %d\n", 
                  gps.satellites.value(), gps.charsProcessed());
  }
  
  msg += "}";
  
  mesh.sendBroadcast(msg);
  Serial.println("Enviado: " + msg);
    Serial.printf("Nodos conectados: %d\n", mesh.getNodeList().size());
});

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
      infoMsg["node_type"] = "Nodo Hum. Suelo";
      infoMsg["sensors"] = "SEN0193 + GPS";
      
      String out;
      serializeJson(infoMsg, out);
      mesh.sendBroadcast(out);
      
      Serial.println("[INFO_REQ] Enviando información al gateway");
      return;
    }
  }
  
  // Mensaje normal (datos de sensor)
  Serial.printf("[INFO] Mensaje no de control: %s\n", msg.c_str());
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
  Serial.println("\n=== INICIANDO NODO HUMEDAD DE SUELO (SEN0193) + GPS ===");
  
  // Inicializar GPS
  gpsSerial.begin(GPS_BAUDRATE, SERIAL_8N1, 16, 17);
  
  pinMode(SOIL_PIN, INPUT);
  analogSetAttenuation(ADC_11db);  // Rango completo 0-3.3V
    
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  
  Serial.printf("NODE ID: %u\n", mesh.getNodeId());
  
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);

  userScheduler.addTask(taskSendData);
  taskSendData.enable();
  
  Serial.printf("NODE ID: %u\n", mesh.getNodeId());
}

void loop() {
  // Leer datos del GPS continuamente
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
  
  mesh.update();
  userScheduler.execute();
  
  // Monitorear timeout de ping (5 segundos)
  if (nodePing.active && (millis() - nodePing.sentTime > 5000)) {
    Serial.printf("[PING] TIMEOUT: No se recibió PONG de nodo %u\n", nodePing.targetNode);
    nodePing.active = false;
  }
}