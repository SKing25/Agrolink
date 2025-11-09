#include <painlessMesh.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

#define TEMT6000_PIN 34

Scheduler userScheduler;
painlessMesh mesh;

Task taskSendData(TASK_SECOND * 10, TASK_FOREVER, []() {
  int rawValue = analogRead(TEMT6000_PIN);
  
  // Convertir a voltaje (ESP32: 0-4095 = 0-3.3V)
  float voltage = (rawValue / 4095.0) * 3.3;
  
  // Convertir a lux aproximado (TEMT6000: 10mV por lux típicamente)
  float lux = voltage * 100;  // 1V = 100 lux aproximadamente
  
  // Calcular porcentaje (0-100%)
  float percentage = (rawValue / 4095.0) * 100;

  String msg = "{\"light\":" + String(lux, 2) + 
               ",\"percentage\":" + String(percentage, 1) + "}";
  mesh.sendBroadcast(msg);
  Serial.println("Enviado: " + msg);
  Serial.printf("Nodos conectados: %d\n", mesh.getNodeList());
});

void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Mensaje recibido de %u: %s\n", from, msg.c_str());
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
  Serial.println("\n=== INICIANDO NODO LUZ (TEMT6000) ===");
  
  pinMode(TEMT6000_PIN, INPUT);
  analogSetAttenuation(ADC_11db);  // Rango completo 0-3.3V
    
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  
  Serial.printf("NODE ID: %u\n", mesh.getNodeId());
  
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);

  userScheduler.addTask(taskSendData);
  taskSendData.enable();
  
  Serial.println("Mesh configurado - Enviando datos cada 10s");
}

void loop() {
  mesh.update();
  userScheduler.execute();
}