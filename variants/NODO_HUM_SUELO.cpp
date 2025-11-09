#include <painlessMesh.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

#define SOIL_PIN 34  

// Calibración del sensor (ajusta según tu sensor)
#define SOIL_DRY 3200    // Valor en aire (seco)
#define SOIL_WET 1200    // Valor en agua (húmedo)

Scheduler userScheduler;
painlessMesh mesh;

Task taskSendData(TASK_SECOND * 10, TASK_FOREVER, []() {
  int rawValue = analogRead(SOIL_PIN);
  
  // Invertir la escala (valores más altos = más seco)
  // Mapear a porcentaje 0-100% (0% = seco, 100% = húmedo)
  int percentage = map(rawValue, SOIL_DRY, SOIL_WET, 0, 100);
  
  // Limitar entre 0-100%
  percentage = constrain(percentage, 0, 100);

  String msg = "{\"soil_moisture\":" + String(percentage) + "}";
  
  mesh.sendBroadcast(msg);
  Serial.println("Enviado: " + msg);
    Serial.printf("Nodos conectados: %d\n", mesh.getNodeList().size());
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
  Serial.println("\n=== INICIANDO NODO HUMEDAD DE SUELO (SEN0193) ===");
  
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
  mesh.update();
  userScheduler.execute();
}