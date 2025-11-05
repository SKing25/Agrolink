#include <painlessMesh.h>
#include <DHT.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

#define DHTPIN 4
#define DHTTYPE DHT22

Scheduler userScheduler;
painlessMesh mesh;
DHT dht(DHTPIN, DHTTYPE);

Task taskSendData(TASK_SECOND * 10, TASK_FOREVER, []() {
  float temp = dht.readTemperature();

  if (!isnan(temp)) {
    String msg = "{\"temperatura\":" + String(temp) + "}";
    mesh.sendBroadcast(msg);
    Serial.println("Enviado: " + msg);
    Serial.printf("Nodos conectados: %d\n", mesh.getNodeList().size());
  } else {
    Serial.println("Error leyendo DHT22 (TEMPERATURA)");
  }
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
  Serial.println("=== INICIANDO NODO DHT22 (TEMPERATURA) ===");
  
  dht.begin();
  Serial.println("DHT22 (TEMPERATURA) iniciado");

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