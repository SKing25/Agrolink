#include <painlessMesh.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <stdarg.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555

#define WIFI_SSID "Laptop-Santiago"
#define WIFI_PASSWORD "salchipapa123"
#define MQTT_SERVER "10.42.0.1"
#define MQTT_PORT 1883
#define MQTT_TOPIC "dht22/datos"
#define LED_PIN 2

Scheduler userScheduler;
painlessMesh mesh;
WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastIPReport = 0;

// ============================================
// TELNET SHELL
// ============================================
WiFiServer telnetServer(23);
WiFiClient telnetClient;

class TelnetShell {
private:
  WiFiClient* client;
  
  struct Command {
    String name;
    String description;
    void (*handler)(TelnetShell*, const String&);
  };
  
  static const int MAX_COMMANDS = 20;
  Command commands[MAX_COMMANDS];
  int commandCount = 0;

public:
  TelnetShell() : client(nullptr) {}
  
  void setClient(WiFiClient* c) {
    client = c;
  }
  
  bool isConnected() {
    return client && client->connected();
  }
  
  void registerCommand(const String& name, const String& desc, void (*handler)(TelnetShell*, const String&)) {
    if (commandCount < MAX_COMMANDS) {
      commands[commandCount].name = name;
      commands[commandCount].description = desc;
      commands[commandCount].handler = handler;
      commandCount++;
    }
  }
  
  void print(const char* format, ...) {
    if (!isConnected()) return;
    
    char buffer[256];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    
    client->print(buffer);
  }
  
  void println(const char* format, ...) {
    if (!isConnected()) return;
    
    char buffer[256];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    
    client->println(buffer);
  }
  
  void processInput(String input) {
    input.trim();
    if (input.length() == 0) return;
    
    int spacePos = input.indexOf(' ');
    String cmd = (spacePos > 0) ? input.substring(0, spacePos) : input;
    String args = (spacePos > 0) ? input.substring(spacePos + 1) : "";
    
    cmd.toLowerCase();
    
    for (int i = 0; i < commandCount; i++) {
      if (commands[i].name.equalsIgnoreCase(cmd)) {
        commands[i].handler(this, args);
        return;
      }
    }
    
    println("Comando desconocido: %s", cmd.c_str());
    println("Escribe 'help' para ver comandos disponibles");
  }
  
  void showHelp() {
    println("\r\n=== COMANDOS DISPONIBLES ===");
    for (int i = 0; i < commandCount; i++) {
      println("  %-12s - %s", commands[i].name.c_str(), commands[i].description.c_str());
    }
    println("");
  }
  
  void loop() {
    if (!telnetServer) return;
    
    // Aceptar nuevas conexiones
    if (!telnetClient || !telnetClient.connected()) {
      telnetClient = telnetServer.available();
      if (telnetClient && telnetClient.connected()) {
        setClient(&telnetClient);
        println("\r\n=== ESP32 GATEWAY - Telnet Shell ===");
        println("Escribe 'help' para ver comandos\r\n");
        print("> ");
      }
    }
    
    // Procesar entrada
    if (isConnected() && telnetClient.available()) {
      String line = telnetClient.readStringUntil('\n');
      line.trim();
      if (line.length() > 0) {
        processInput(line);
        print("> ");
      }
    }
  }
};

TelnetShell shell;

// ============================================
// ESTRUCTURAS PARA DIAGNÓSTICOS
// ============================================
struct PendingPing {
  uint32_t targetNode;
  uint32_t seq;
  unsigned long sentTime;
  bool active;
};

PendingPing pendingPing = {0, 0, 0, false};

// Información de nodos
struct NodeInfo {
  uint32_t nodeId;
  String nodeType;
  String sensors;
  unsigned long lastSeen;
};

NodeInfo nodeInfoMap[20];
int nodeInfoCount = 0;

void updateNodeInfo(uint32_t nodeId, const String& type, const String& sensors) {
  // Buscar si ya existe
  for (int i = 0; i < nodeInfoCount; i++) {
    if (nodeInfoMap[i].nodeId == nodeId) {
      nodeInfoMap[i].nodeType = type;
      nodeInfoMap[i].sensors = sensors;
      nodeInfoMap[i].lastSeen = millis();
      return;
    }
  }
  
  // Agregar nuevo
  if (nodeInfoCount < 20) {
    nodeInfoMap[nodeInfoCount].nodeId = nodeId;
    nodeInfoMap[nodeInfoCount].nodeType = type;
    nodeInfoMap[nodeInfoCount].sensors = sensors;
    nodeInfoMap[nodeInfoCount].lastSeen = millis();
    nodeInfoCount++;
  }
}

String getNodeInfo(uint32_t nodeId) {
  for (int i = 0; i < nodeInfoCount; i++) {
    if (nodeInfoMap[i].nodeId == nodeId) {
      return nodeInfoMap[i].nodeType + " (" + nodeInfoMap[i].sensors + ")";
    }
  }
  return "Desconocido";
}

// ============================================
// COMANDOS TELNET
// ============================================
void cmdHelp(TelnetShell* sh, const String& args) {
  sh->showHelp();
}

void cmdStatus(TelnetShell* sh, const String& args) {
  IPAddress ip = mesh.getStationIP();
  sh->println("\r\n=== ESTADO DEL GATEWAY ===");
  sh->println("Node ID: %u", mesh.getNodeId());
  sh->println("IP WiFi: %s", ip.toString().c_str());
  sh->println("Nodos conectados: %d", mesh.getNodeList().size());
  sh->println("MQTT: %s", client.connected() ? "CONECTADO" : "DESCONECTADO");
  sh->println("");
}

void cmdNodes(TelnetShell* sh, const String& args) {
  auto nodes = mesh.getNodeList();
  sh->println("\r\n=== NODOS EN EL MESH ===");
  sh->println("Total: %d nodos", nodes.size());
  
  if (args == "refresh") {
    // Solicitar información actualizada a todos los nodos
    String msg = "{\"type\":\"INFO_REQ\"}";
    mesh.sendBroadcast(msg);
    sh->println("Solicitando información a los nodos...\n");
    return;
  }
  
  for (auto node : nodes) {
    String info = getNodeInfo(node);
    sh->println("  - %u: %s", node, info.c_str());
  }
  sh->println("\nUsa 'nodes refresh' para actualizar información");
}

void cmdLed(TelnetShell* sh, const String& args) {
  if (args == "on") {
    digitalWrite(LED_PIN, HIGH);
    sh->println("LED encendido");
  } else if (args == "off") {
    digitalWrite(LED_PIN, LOW);
    sh->println("LED apagado");
  } else {
    sh->println("Uso: led [on|off]");
  }
}

void cmdMqtt(TelnetShell* sh, const String& args) {
  sh->println("\r\n=== ESTADO MQTT ===");
  sh->println("Servidor: %s:%d", MQTT_SERVER, MQTT_PORT);
  sh->println("Estado: %s", client.connected() ? "CONECTADO" : "DESCONECTADO");
  sh->println("Topic base: %s", MQTT_TOPIC);
  sh->println("");
}

void cmdMesh(TelnetShell* sh, const String& args) {
  sh->println("\r\n=== RED MESH ===");
  sh->println("SSID: %s", MESH_PREFIX);
  sh->println("Puerto: %d", MESH_PORT);
  sh->println("Nodos: %d", mesh.getNodeList().size());
  sh->println("");
}

void cmdReboot(TelnetShell* sh, const String& args) {
  sh->println("Reiniciando...");
  delay(1000);
  ESP.restart();
}

void sendPing(uint32_t sourceNode, uint32_t targetNode) {
  if (pendingPing.active) {
    shell.println("Ya hay un PING pendiente");
    return;
  }
  
  pendingPing.targetNode = targetNode;
  pendingPing.seq++;
  pendingPing.sentTime = millis();
  pendingPing.active = true;
  
  // Enviar comando de PING al nodo origen para que haga ping al destino
  String msg = "{\"type\":\"PING_CMD\",\"from\":" + String(sourceNode) + 
               ",\"to\":" + String(targetNode) + 
               ",\"seq\":" + String(pendingPing.seq) + "}";
  
  mesh.sendBroadcast(msg);
  shell.println("Ordenando a nodo %u hacer PING a nodo %u (seq=%u)", 
                sourceNode, targetNode, pendingPing.seq);
}

void cmdPing(TelnetShell* sh, const String& args) {
  if (args.length() == 0) {
    sh->println("Uso: ping <nodo_destino>");
    sh->println("  O: ping <nodo_origen> <nodo_destino>");
    sh->println("Ejemplos:");
    sh->println("  ping 67890         (Gateway hace ping a 67890)");
    sh->println("  ping 12345 67890   (Nodo 12345 hace ping a 67890)");
    return;
  }
  
  // Parsear argumentos
  int spacePos = args.indexOf(' ');
  
  // Caso 1: Solo un argumento - Gateway hace ping al nodo
  if (spacePos < 0) {
    uint32_t targetNode = args.toInt();
    if (targetNode == 0) {
      sh->println("Error: ID de nodo inválido");
      return;
    }
    
    // Gateway hace ping directo al nodo
    if (pendingPing.active) {
      sh->println("Ya hay un PING pendiente");
      return;
    }
    
    pendingPing.targetNode = targetNode;
    pendingPing.seq++;
    pendingPing.sentTime = millis();
    pendingPing.active = true;
    
    String msg = "{\"type\":\"PING\",\"from\":" + String(mesh.getNodeId()) + 
                 ",\"to\":" + String(targetNode) + 
                 ",\"seq\":" + String(pendingPing.seq) + "}";
    
    mesh.sendBroadcast(msg);
    sh->println("PING enviado a nodo %u (seq=%u)", targetNode, pendingPing.seq);
    return;
  }
  
  // Caso 2: Dos argumentos - Un nodo hace ping a otro
  String sourceStr = args.substring(0, spacePos);
  String targetStr = args.substring(spacePos + 1);
  
  uint32_t sourceNode = sourceStr.toInt();
  uint32_t targetNode = targetStr.toInt();
  
  if (sourceNode == 0 || targetNode == 0) {
    sh->println("Error: IDs de nodo inválidos");
    return;
  }
  
  sendPing(sourceNode, targetNode);
}

void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Datos recibidos desde nodo %u: %s\n", from, msg.c_str());

  // Parsear JSON para detectar mensajes de control
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, msg);
  
  if (err == DeserializationError::Ok && doc.containsKey("type")) {
    String msgType = doc["type"].as<String>();
    
    // PONG: Respuesta a PING
    if (msgType == "PONG" && pendingPing.active) {
      uint32_t seq = doc["seq"].as<uint32_t>();
      if (seq == pendingPing.seq) {
        uint32_t fromNode = doc["from"].as<uint32_t>();
        
        // Verificar si tiene RTT (ping entre nodos)
        if (doc.containsKey("rtt")) {
          uint32_t toNode = doc["to"].as<uint32_t>();
          uint32_t rtt = doc["rtt"].as<uint32_t>();
          shell.println("PONG: Nodo %u -> Nodo %u RTT=%ums (seq=%u)", 
                        pendingPing.targetNode, toNode, rtt, seq);
        } else {
          // Ping directo de gateway
          unsigned long rtt = millis() - pendingPing.sentTime;
          shell.println("PONG desde nodo %u RTT=%lums (seq=%u)", 
                        fromNode, rtt, seq);
        }
        
        pendingPing.active = false;
      }
      return;
    }
    
    // INFO: Respuesta con información del nodo
    if (msgType == "INFO") {
      String nodeType = doc["node_type"].as<String>();
      String sensors = doc["sensors"].as<String>();
      updateNodeInfo(from, nodeType, sensors);
      Serial.printf("[INFO] Nodo %u: %s (%s)\n", from, nodeType.c_str(), sensors.c_str());
      return;
    }
  }

  // Publicar datos de sensores en MQTT
  if (client.connected()) {
    String topic = String(MQTT_TOPIC) + "/" + String(from);
    if (client.publish(topic.c_str(), msg.c_str())) {
      Serial.println("Publicado en MQTT: " + msg);
    } else {
      Serial.println("Error al publicar en MQTT");
    }
  } else {
    Serial.println("MQTT desconectado - reintentando...");
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
  while (!client.connected()) {
    Serial.print("Conectando a MQTT...");
    String clientId = "ESP32Gateway-" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      Serial.println("MQTT Conectado!");
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

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);

  Serial.printf("NODE ID: %u\n", mesh.getNodeId());
  
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);

  mesh.stationManual(WIFI_SSID, WIFI_PASSWORD);
  mesh.setHostname("ESP32-Gateway");

  client.setServer(MQTT_SERVER, MQTT_PORT);
  
  // Iniciar servidor Telnet
  telnetServer.begin();
  telnetServer.setNoDelay(true);
  Serial.println("Servidor Telnet iniciado en puerto 23");
  
  // Registrar comandos Telnet
  shell.registerCommand("help", "Muestra esta ayuda", cmdHelp);
  shell.registerCommand("status", "Estado del gateway", cmdStatus);
  shell.registerCommand("nodes", "Lista nodos conectados", cmdNodes);
  shell.registerCommand("led", "Control LED (on/off)", cmdLed);
  shell.registerCommand("mqtt", "Estado MQTT", cmdMqtt);
  shell.registerCommand("mesh", "Info de la red mesh", cmdMesh);
  shell.registerCommand("ping", "Ping a un nodo", cmdPing);
  shell.registerCommand("reboot", "Reiniciar gateway", cmdReboot);
  
  Serial.println("Gateway configurado - Esperando conexiones mesh...");
}

void loop() {
  static unsigned long lastStatus = 0;
  mesh.update();
  
  // Procesar conexiones Telnet
  shell.loop();
  
  if (millis() - lastStatus > 30000) {
    lastStatus = millis();
    IPAddress ip = mesh.getStationIP();
    Serial.printf("Estado: IP=%s, Nodos=%d, MQTT=%s\n", 
                  ip.toString().c_str(), 
                  mesh.getNodeList().size(),
                  client.connected() ? "BIEN" : "MAL");
  }
  
  // Enviar IP del gateway cada 60 segundos via MQTT
  if (millis() - lastIPReport > 60000 || lastIPReport == 0) {
    lastIPReport = millis();
    IPAddress ip = mesh.getStationIP();
    
    if (ip != IPAddress(0,0,0,0) && client.connected()) {
      StaticJsonDocument<200> doc;
      doc["nodeId"] = "gateway";
      doc["ip"] = ip.toString();
      doc["nodes"] = mesh.getNodeList().size();
      
      String payload;
      serializeJson(doc, payload);
      
      String topic = String(MQTT_TOPIC) + "/gateway";
      Serial.printf("[IP] Publicando: %s -> %s\n", topic.c_str(), payload.c_str());
      
      if (client.publish(topic.c_str(), payload.c_str())) {
        Serial.printf("[IP] IP enviada via MQTT: %s\n", ip.toString().c_str());
      } else {
        Serial.println("[IP] Error al publicar");
      }
    } else {
      Serial.printf("[IP] Saltando envío - IP: %s, MQTT: %s\n",
                    ip.toString().c_str(),
                    client.connected() ? "OK" : "DESCONECTADO");
    }
  }
  
  // Solo intentar MQTT si hay conexión WiFi
  if(mesh.getStationIP() != IPAddress(0,0,0,0)) {
    if (!client.connected()) {
      reconnect();
    }
    client.loop();
  }

  // Monitorear timeouts de comandos de diagnóstico
  unsigned long now = millis();
  
  // Timeout para PING (5 segundos)
  if (pendingPing.active && (now - pendingPing.sentTime > 5000)) {
    shell.println("TIMEOUT: No se recibió PONG");
    pendingPing.active = false;
  }
}