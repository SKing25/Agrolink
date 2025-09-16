# Informe Técnico: Sistema IoT con Red Mesh ESP32 y Monitoreo de Sensores DHT22

## Resumen Ejecutivo

Este proyecto implementa un sistema completo de Internet de las Cosas (IoT) para monitoreo ambiental utilizando sensores DHT22 conectados a través de una red mesh de ESP32. El sistema recolecta datos de temperatura y humedad, los transmite a través de MQTT y los almacena en un servidor web en la nube para visualización y análisis.

## Arquitectura del Sistema

```
[ESP32 DHT22] --> [Red Mesh] --> [ESP32 Gateway] --> [Mosquitto MQTT] --> [Puente Python] --> [Servidor Flask/Render]
```

### Componentes principales:
1. **Nodo Sensor (ESP32 + DHT22)**: Recolección de datos ambientales
2. **Gateway ESP32**: Puente entre red mesh y conectividad externa
3. **Broker MQTT (Mosquitto)**: Middleware de mensajería
4. **Puente Python**: Procesamiento y reenvío de datos
5. **Servidor Web Flask**: Almacenamiento y visualización de datos

## Conceptos Fundamentales

### Red Mesh
Una red mesh es una topología de red donde cada nodo se conecta directamente con varios otros nodos, creando múltiples rutas para la transmisión de datos. En este proyecto:

- **Ventajas**: Redundancia, autoconfiguración, escalabilidad
- **Protocolo**: PainlessMesh sobre ESP32
- **Alcance**: Cada nodo extiende el área de cobertura
- **Autorecuperación**: Si un nodo falla, la red se reconfigura automáticamente

### MQTT (Message Queuing Telemetry Transport)
Protocolo de comunicación ligero diseñado para dispositivos IoT:

- **Patrón Publish/Subscribe**: Los dispositivos publican mensajes a topics específicos
- **Broker**: Servidor central (Mosquitto) que gestiona la distribución de mensajes
- **QoS**: Niveles de calidad de servicio para garantizar entrega
- **Eficiencia**: Bajo consumo de ancho de banda y batería

### Mosquitto
Broker MQTT open source que implementa las versiones 3.1, 3.1.1 y 5.0 del protocolo:

- **Funciones**: Recepción, filtrado y distribución de mensajes
- **Configuración**: Servidor local en IP 10.42.0.1
- **Topics**: Estructura jerárquica para organizar mensajes (dht22/datos/+)

### Broker (Intermediario de Mensajes)
Un broker es un servidor intermediario que facilita la comunicación entre diferentes sistemas:

- **Función principal**: Recibir, almacenar temporalmente y distribuir mensajes
- **Desacoplamiento**: Los emisores no necesitan conocer a los receptores directamente
- **Escalabilidad**: Permite múltiples productores y consumidores simultáneos
- **Ejemplo en el proyecto**: Mosquitto actúa como broker MQTT entre ESP32 Gateway y aplicaciones Python

### Middleware (Capa Intermedia)
Software que actúa como puente entre diferentes aplicaciones, sistemas operativos o bases de datos:

- **Propósito**: Facilitar la comunicación e integración entre sistemas heterogéneos
- **Características**: Transparencia, interoperabilidad, servicios distribuidos
- **Tipos**: Message-oriented middleware (MOM), database middleware, web middleware
- **En este proyecto**: MQTT actúa como middleware de mensajería IoT

### WiFi vs MQTT: Infraestructura vs Protocolo

#### WiFi: La Infraestructura de Conectividad
**WiFi proporciona:**
1. **Conectividad física inalámbrica** entre ESP32 Gateway y la computadora
2. **Asignación de IP** al ESP32 Gateway (ej: 10.42.0.100)
3. **Acceso a la red local** creada por el hotspot "Laptop-Santiago"
4. **Canal de comunicación** bidireccional

```
ESP32 Gateway ←--[Ondas WiFi 2.4GHz]--→ Laptop (Hotspot)
IP: 10.42.0.100                         IP: 10.42.0.1
```

#### MQTT: El Protocolo de Datos
**MQTT utiliza la conectividad WiFi para:**
1. **Transportar mensajes** estructurados
2. **Organizar datos** por topics
3. **Gestionar suscripciones** y publicaciones
4. **Manejar la lógica** de entrega de mensajes

```
ESP32 ──[WiFi]──→ Laptop
   │                │
   └─[MQTT Protocol]─→ Mosquitto Broker
```

#### Relación entre WiFi y MQTT (Capas de Red):
```
┌─────────────────────────────────────┐
│ APLICACIÓN: Datos del DHT22         │
├─────────────────────────────────────┤
│ MQTT: Protocolo de mensajería       │ ← Organiza QUÉ enviar
├─────────────────────────────────────┤
│ TCP: Conexión confiable             │
├─────────────────────────────────────┤
│ IP: Enrutamiento (10.42.0.X)       │
├─────────────────────────────────────┤
│ WiFi: Transmisión inalámbrica       │ ← Define CÓMO enviar
└─────────────────────────────────────┘
```

### Función Específica de Mosquitto como Broker

#### ¿Qué hace Mosquitto exactamente?

**Mosquitto actúa como intermediario de mensajería (Message Broker):**

1. **Recepción de Mensajes**
   - Recibe datos del ESP32 Gateway vía protocolo MQTT
   - Acepta conexiones en el puerto 1883
   - Procesa mensajes en tiempo real

2. **Organización por Topics**
   ```
   dht22/
     └── datos/
         ├── 2123456789/  ← Nodo ESP32 #1
         ├── 2123456790/  ← Nodo ESP32 #2
         └── +           ← Wildcard para todos
   ```

3. **Distribución a Suscriptores**
   - El Puente Python se suscribe a `dht22/datos/+`
   - Mosquitto envía automáticamente cada mensaje nuevo al puente
   - Soporte para múltiples suscriptores simultáneos

4. **Desacoplamiento de Componentes**
   ```
   ESP32 Gateway ──[publica]──> MOSQUITTO ──[distribuye]──> Puente Python
   ```

#### Ventajas del patrón Broker:

**Sin Mosquitto (conexión directa):**
- ESP32 necesita IP fija del script Python
- Solo 1 aplicación puede recibir datos
- Si Python se cae, ESP32 no sabe qué hacer
- Manejo complejo de conexiones TCP

**Con Mosquitto (patrón broker):**
- ESP32 solo necesita IP del broker
- Múltiples aplicaciones pueden recibir datos simultáneamente
- Tolerancia a fallos: si una app falla, las demás continúan
- Protocolo MQTT optimizado para IoT

## Análisis Detallado del Código

### 1. Nodo Sensor DHT22 (NODO_DHT22.cpp)

**Propósito**: Recolectar datos ambientales y transmitirlos a través de la red mesh.

#### Configuración de Red Mesh
```cpp
#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555
```

#### Componentes Principales

**Inicialización del Sensor**:
```cpp
DHT dht(DHTPIN, DHTTYPE);
```
- Configura el sensor DHT22 en el pin 4
- Inicializa la comunicación serie para lecturas de temperatura y humedad

**Tarea Programada**:
```cpp
Task taskSendData(TASK_SECOND * 10, TASK_FOREVER, []() {
    // Lectura y transmisión cada 10 segundos
});
```

**Proceso de Lectura y Transmisión**:
1. Lee temperatura y humedad del sensor DHT22
2. Valida que las lecturas no sean NaN (Not a Number)
3. Construye mensaje JSON con los datos
4. Transmite vía broadcast a toda la red mesh
5. Registra estadísticas de nodos conectados

**Callbacks de Conexión**:
- `newConnectionCallback`: Detecta nuevos nodos en la red
- `changedConnectionCallback`: Monitorea cambios en la topología
- `receivedCallback`: Procesa mensajes recibidos de otros nodos

### 2. Gateway ESP32 (GATEWAY.cpp)

**Propósito**: Actuar como puente entre la red mesh interna y la conectividad externa (WiFi/MQTT).

#### Configuración Dual
El gateway maneja dos conexiones simultáneas:
1. **Red Mesh**: Para comunicación con sensores
2. **WiFi Externo**: Para conectividad a Internet

```cpp
mesh.stationManual(WIFI_SSID, WIFI_PASSWORD);
```

#### Funcionalidades Principales

**Recepción de Datos Mesh**:
```cpp
void receivedCallback(uint32_t from, String &msg) {
    // Procesa datos del nodo sensor
    // Publica a MQTT con topic específico por nodo
}
```

**Gestión de Conexión MQTT**:
- Reconexión automática en caso de fallo
- Publicación de datos con identificador de nodo fuente
- Monitoreo de estado de conexión

**Monitoreo de Red**:
- Estado de IP asignada
- Número de nodos mesh conectados
- Estado de conexión MQTT
- Informes periódicos cada 30 segundos

### 3. Puente Python (puente.py)

**Propósito**: Intermediario entre el broker MQTT local y el servidor web remoto.

#### Funcionalidades de Procesamiento

**Parser Flexible de Mensajes**:
```python
def parse_message(payload):
    # Maneja tanto formato JSON como string
    # Convierte "temperature"/"humidity" a "temperatura"/"humedad"
```

**Enriquecimiento de Datos**:
- Extrae ID del nodo desde el topic MQTT
- Agrega timestamp Unix
- Valida estructura de datos antes del envío

**Gestión de Conexiones**:
- Suscripción a topics con wildcard (+)
- Manejo de errores de conexión MQTT
- Reintentos automáticos para requests HTTP

#### Flujo de Procesamiento
1. Recibe mensaje MQTT del topic `dht22/datos/+`
2. Decodifica payload JSON
3. Extrae nodeId del topic
4. Agrega metadatos (timestamp)
5. Envía datos al servidor Flask vía HTTP POST

### 4. Servidor Flask (app.py implementado)

**Propósito**: Almacenamiento persistente y visualización web de datos.

#### Modelo de Base de Datos
```python
class DatosSensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperatura = db.Column(db.Float, nullable=False)
    humedad = db.Column(db.Float, nullable=False)
    nodeId = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.Integer, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
```

#### Endpoints REST API

**POST /datos**: Recepción de datos del puente
- Validación de campos requeridos
- Inserción en base de datos SQLite
- Respuesta JSON con confirmación

**GET /ver**: Interfaz web de visualización
- Recupera últimos 100 registros
- Renderiza tabla HTML con auto-refresh

**GET /api/datos**: API JSON para integración
- Retorna datos en formato JSON
- Permite integración con otras aplicaciones

## El Viaje del Dato: Desde el Sensor hasta la Nube

Este proyecto demuestra un flujo completo de datos IoT que atraviesa múltiples capas tecnológicas. A continuación se detalla el recorrido paso a paso que realiza cada medición desde su origen hasta su visualización final.

### Etapa 1: Captura de Datos Físicos
**Ubicación**: ESP32 con sensor DHT22  
**Duración**: ~2 segundos  
**Tecnología**: Protocolo One-Wire

1. **Activación del sensor**: El ESP32 envía una señal de inicio al DHT22
2. **Medición física**: El sensor DHT22 realiza mediciones de:
   - Temperatura ambiente (precisión ±0.5°C)
   - Humedad relativa (precisión ±2-5% RH)
3. **Digitalización**: Conversión analógico-digital interna del sensor
4. **Transmisión serie**: Datos enviados al ESP32 vía protocolo propietario DHT
5. **Validación**: ESP32 verifica checksums y detecta errores de lectura

**Formato de datos en esta etapa**: Valores float en memoria del ESP32
```cpp
float temp = 22.7;  // Grados Celsius
float hum = 54.2;   // Porcentaje de humedad
```

### Etapa 2: Procesamiento Local y Empaquetado
**Ubicación**: ESP32 Nodo Sensor  
**Duración**: ~500 ms  
**Tecnología**: C++ en microcontrolador

1. **Validación de datos**: Verificación de valores NaN (Not a Number)
2. **Construcción de mensaje**: Creación de estructura JSON
3. **Preparación para transmisión**: Serialización del objeto JSON a string
4. **Identificación de destino**: Configuración para broadcast mesh

**Transformación de datos**:
```cpp
// De valores separados a JSON estructurado
String msg = "{\"temperature\":" + String(temp) + ",\"humidity\":" + String(hum) + "}";
// Resultado: {"temperature":22.7,"humidity":54.2}
```

### Etapa 3: Transmisión por Red Mesh
**Ubicación**: Entre nodos ESP32  
**Duración**: ~100-500 ms  
**Tecnología**: WiFi 802.11 con protocolo PainlessMesh

1. **Encapsulación mesh**: Mensaje envuelto en cabeceras de red mesh
2. **Enrutamiento automático**: PainlessMesh determina la ruta óptima
3. **Transmisión inalámbrica**: Envío vía radiofrecuencia 2.4GHz
4. **Retransmisión**: Posibles saltos entre nodos intermedios si existen
5. **Recepción en gateway**: ESP32 Gateway recibe el mensaje broadcast

**Características de la transmisión**:
- Protocolo: ESP-NOW sobre WiFi
- Alcance: ~30-100 metros por salto
- Velocidad: ~1-2 Mbps
- Redundancia: Múltiples rutas disponibles

### Etapa 4: Puente a Infraestructura Tradicional
**Ubicación**: ESP32 Gateway  
**Duración**: ~200 ms  
**Tecnología**: WiFi cliente + MQTT

1. **Recepción mesh**: Callback `receivedCallback()` procesa mensaje entrante
2. **Identificación de origen**: Extracción del nodeId del remitente
3. **Conexión dual**: Gateway mantiene conexión a red mesh Y WiFi externo
4. **Construcción de topic**: Creación de topic MQTT específico por nodo
5. **Publicación MQTT**: Envío a broker Mosquitto local

**Transformación de protocolo**:
```cpp
// De mensaje mesh a publicación MQTT
String topic = "dht22/datos/" + String(from);  // from = nodeId
client.publish(topic.c_str(), msg.c_str());
```

### Etapa 5: Distribución por Middleware MQTT
**Ubicación**: Servidor local (10.42.0.1)  
**Duración**: ~50 ms  
**Tecnología**: Broker Mosquitto

1. **Recepción en broker**: Mosquitto recibe mensaje del ESP32 Gateway
2. **Gestión de topics**: Organización jerárquica de mensajes
3. **Distribución a suscriptores**: Notificación a todos los clientes suscritos
4. **Persistencia temporal**: Retención de último mensaje por topic
5. **Entrega garantizada**: Confirmación de recepción según QoS configurado

**Estructura de topics**:
```
dht22/
  └── datos/
      ├── 2123456789/  ← NodeID específico
      ├── 2123456790/
      └── ...
```

### Etapa 6: Procesamiento y Transformación
**Ubicación**: Computadora local  
**Duración**: ~100-300 ms  
**Tecnología**: Python con paho-mqtt y requests

1. **Suscripción MQTT**: Cliente Python escucha topic `dht22/datos/+`
2. **Recepción de mensaje**: Callback `on_message()` activado
3. **Decodificación**: Conversión de bytes a string UTF-8
4. **Parsing JSON**: Deserialización del mensaje JSON
5. **Enriquecimiento**: Adición de metadatos (timestamp, nodeId)
6. **Validación**: Verificación de campos requeridos
7. **Preparación HTTP**: Serialización para envío web

**Enriquecimiento de datos**:
```python
# Mensaje original: {"temperature":22.7,"humidity":54.2}
# Después del procesamiento:
{
    "temperatura": 22.7,
    "humedad": 54.2,
    "nodeId": "2123456789",
    "timestamp": 1726329600
}
```

### Etapa 7: Transmisión a la Nube
**Ubicación**: Internet  
**Duración**: ~200-1000 ms  
**Tecnología**: HTTP/HTTPS sobre TCP/IP

1. **Establecimiento de conexión**: TCP handshake con servidor Render
2. **Negociación TLS**: Cifrado HTTPS para seguridad
3. **Envío HTTP POST**: Datos JSON en body de request
4. **Enrutamiento ISP**: Paso por múltiples routers hasta datacenter
5. **Balanceador de carga**: Distribución en infraestructura Render
6. **Recepción en servidor**: Flask recibe request en endpoint `/datos`

**Cabeceras HTTP**:
```http
POST /datos HTTP/1.1
Host: agrolink-hd2p.onrender.com
Content-Type: application/json
Content-Length: 98

{"temperatura":22.7,"humedad":54.2,"nodeId":"2123456789","timestamp":1726329600}
```

### Etapa 8: Persistencia en Base de Datos
**Ubicación**: Servidor Render (Cloud)  
**Duración**: ~50-200 ms  
**Tecnología**: Flask + SQLAlchemy + SQLite

1. **Recepción en Flask**: Endpoint `/datos` procesa request POST
2. **Validación de datos**: Verificación de campos requeridos
3. **Creación de objeto**: Instanciación de modelo `DatosSensor`
4. **Transacción de BD**: Inserción en tabla SQLite
5. **Confirmación**: Commit de transacción
6. **Respuesta HTTP**: Confirmación 200 OK al cliente

**Modelo de datos persistido**:
```sql
INSERT INTO datos_sensor (
    temperatura, humedad, nodeId, timestamp, fecha_creacion
) VALUES (
    22.7, 54.2, '2123456789', 1726329600, '2025-09-14 15:20:00'
);
```

### Etapa 9: Visualización Web
**Ubicación**: Navegador del usuario  
**Duración**: ~500-2000 ms  
**Tecnología**: HTTP + HTML + JavaScript

1. **Request del navegador**: GET a `/ver` desde cualquier ubicación
2. **Consulta a BD**: Flask recupera últimos 100 registros
3. **Renderizado**: Jinja2 genera HTML con datos
4. **Transmisión HTTP**: Página enviada al navegador
5. **Renderizado local**: Browser muestra tabla de datos
6. **Auto-refresh**: JavaScript recarga página cada 30 segundos

### Resumen del Viaje Completo

**Tiempo total**: 3-6 segundos (desde medición hasta visualización)  
**Distancia física**: Desde sensor local hasta datacenter (potencialmente miles de km)  
**Transformaciones de protocolo**: 6 diferentes (DHT → ESP32 → Mesh → MQTT → HTTP → SQL)  
**Puntos de validación**: 4 capas de verificación de datos  
**Tecnologías involucradas**: 8+ diferentes sistemas

**Cronología típica**:
```
T+0.0s: DHT22 inicia medición
T+2.0s: Datos listos en ESP32
T+2.5s: Transmisión mesh completa
T+2.7s: Publicación MQTT realizada
T+2.8s: Python procesa mensaje
T+3.8s: HTTP POST enviado a nube
T+4.0s: Datos persistidos en BD
T+4.1s: Usuario puede ver datos en web
```

Este flujo demuestra la complejidad y elegancia de los sistemas IoT modernos, donde una simple medición de temperatura atraviesa múltiples dominios tecnológicos para convertirse en información accesible globalmente.

## Flujo de Datos Completo

### 1. Recolección
- DHT22 mide temperatura y humedad cada 10 segundos
- ESP32 sensor procesa lecturas y valida datos
- Construye mensaje JSON estructurado

### 2. Transmisión Mesh
- Broadcast del mensaje a todos los nodos mesh
- Gateway recibe datos con identificador de nodo fuente
- Red mesh proporciona redundancia y extensión de alcance

### 3. Puente MQTT
- Gateway publica datos a broker Mosquitto
- Topic específico por nodo: `dht22/datos/{nodeId}`
- Protocolo MQTT garantiza entrega confiable

### 4. Procesamiento Intermedio
- Puente Python suscrito a topics con wildcard
- Transformación de formato de datos
- Enriquecimiento con metadatos adicionales

### 5. Almacenamiento Persistente
- Servidor Flask recibe datos vía HTTP POST
- Validación e inserción en base de datos SQLite
- Respuesta de confirmación al puente

## Confirmación del Flujo de Datos del Sistema

### Flujo Completo Verificado:

#### 1. ESP32 DHT22 → ESP32 Gateway (Red Mesh)
```
[ESP32 DHT22] ──(Red Mesh)──→ [ESP32 Gateway]
```
- ESP32 con DHT22 captura temperatura y humedad cada 10 segundos
- Envía datos vía **red mesh inalámbrica** al Gateway usando PainlessMesh
- No requiere WiFi externo, solo conectividad mesh local
- Formato: JSON con temperature y humidity

#### 2. ESP32 Gateway → Computadora (WiFi + MQTT)
```
[ESP32 Gateway] ──(WiFi + MQTT)──→ [Computadora con Mosquitto]
```
- Gateway **DEBE** estar conectado al mismo WiFi que la computadora
- En este proyecto: ambos conectados a hotspot "Laptop-Santiago" (10.42.0.1)
- Gateway actúa como **traductor** entre red mesh y WiFi externo
- Envía datos vía **protocolo MQTT** a Mosquitto (puerto 1883)
- Topic utilizado: `dht22/datos/{nodeId}`

#### 3. Mosquitto → Python → Nube
```
[Mosquitto] ──(MQTT Subscribe)──→ [Python] ──(HTTP POST)──→ [Servidor Render]
```
- **Mosquitto** recibe y organiza los datos MQTT por topics
- **Código Python** se suscribe automáticamente a `dht22/datos/+`
- **Python** transforma datos y los envía al servidor Flask vía HTTPS
- **Servidor Flask** almacena en base de datos SQLite y presenta vía web

### Diagrama de Arquitectura Completa:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ ESP32 DHT22 │    │ESP32 Gateway│    │ Computadora │    │   Python    │    │ Servidor    │
│             │    │             │    │ (Mosquitto) │    │   Puente    │    │   Render    │
│ 1. Captura ──┼────→ 2. Mesh    ──┼────→ 3. MQTT    ──┼────→ 4. HTTP   ──┼────→ 5. SQLite │
│   DHT22     │    │   WiFi      │    │   Broker    │    │   Bridge    │    │   Flask     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                     │                     │                     │                     │
   Sensor                 Dual                  WiFi +              localhost              Cloud
   Físico              Conectividad             MQTT                 Client               Database
```

### Requisitos de Conectividad:

#### ✅ Configuración Necesaria:
1. **ESP32 DHT22**: Solo red mesh "MeshNetwork" (sin WiFi externo)
2. **ESP32 Gateway**: Red mesh + WiFi "Laptop-Santiago" (conectividad dual)
3. **Computadora**: WiFi "Laptop-Santiago" + Mosquitto en puerto 1883
4. **Script Python**: Mismo equipo que Mosquitto + acceso a Internet
5. **Servidor Render**: Accesible vía HTTPS desde Internet

#### ❌ Lo que NO se requiere:
- ESP32 DHT22 no necesita WiFi externo ni acceso a Internet
- Gateway no necesita acceso directo a Internet (solo WiFi local)
- Solo la computadora necesita conexión completa a Internet

### Tecnologías por Capa:

| Capa | Tecnología | Función | Ubicación |
|------|------------|---------|-----------|
| **Sensado** | DHT22 + ESP32 | Captura datos ambientales | Local |
| **Red Local** | PainlessMesh | Comunicación entre ESP32s | Local |
| **Gateway** | WiFi + MQTT | Puente mesh ↔ exterior | Local |
| **Middleware** | Mosquitto | Broker de mensajes | Local |
| **Procesamiento** | Python + paho-mqtt | Transformación de datos | Local |
| **Transporte** | HTTP/HTTPS | Envío a nube | Internet |
| **Persistencia** | Flask + SQLite | Almacenamiento | Nube |
| **Presentación** | HTML + CSS | Visualización web | Nube |

### Puntos Críticos del Sistema:

1. **Gateway ESP32**: Punto único de fallo entre mesh y exterior
2. **Conectividad WiFi**: Ambos (Gateway y PC) deben estar en misma red
3. **Mosquitto**: Debe estar ejecutándose antes que el script Python
4. **Internet**: Requerido solo para envío final a Render

Este diseño proporciona una arquitectura escalable donde cada componente tiene responsabilidades específicas y bien definidas.

## Consideraciones Técnicas

### Escalabilidad
- La red mesh soporta múltiples nodos sensor
- Cada nodo se identifica únicamente
- Base de datos diseñada para crecimiento

### Confiabilidad
- Reconexión automática en todos los niveles
- Validación de datos en múltiples puntos
- Manejo de errores y logging detallado

### Seguridad
- Contraseña para red mesh
- Comunicación local para MQTT
- HTTPS para servidor remoto (Render)

### Eficiencia Energética
- Transmisión cada 10 segundos (configurable)
- Protocolo MQTT optimizado para IoT
- Operación de baja potencia en ESP32

## Conclusiones

El sistema implementado demuestra una arquitectura robusta para monitoreo IoT con las siguientes características:

1. **Modularidad**: Cada componente tiene responsabilidades específicas
2. **Escalabilidad**: Fácil adición de nuevos sensores
3. **Confiabilidad**: Múltiples niveles de redundancia
4. **Accesibilidad**: Datos disponibles via web desde cualquier ubicación
5. **Mantenibilidad**: Código bien estructurado y documentado

Este enfoque proporciona una base sólida para sistemas de monitoreo ambiental distribuidos, con potencial de expansión para incluir diferentes tipos de sensores y aplicaciones de análisis más avanzadas.

## Guía de Implementación Paso a Paso

Esta sección detalla el proceso completo de implementación del sistema, desde la programación de los ESP32 hasta el despliegue del servidor en la nube.

### Paso 1: Programación del ESP32 con Sensor DHT22

#### 1.1 Preparación del Hardware
- **Componentes**: ESP32, sensor DHT22, resistencia pull-up 10kΩ, cables
- **Conexiones**:
  ```
  DHT22 VCC  → ESP32 3.3V
  DHT22 DATA → ESP32 Pin 4 (con resistencia pull-up)
  DHT22 GND  → ESP32 GND
  ```

#### 1.2 Configuración del Código (NODO_DHT22.cpp)
```cpp
#include <painlessMesh.h>
#include <DHT.h>

#define MESH_PREFIX "Mesh"
#define MESH_PASSWORD "12345678"
#define MESH_PORT 5555
#define DHTPIN 4
#define DHTTYPE DHT22

// Configuración y código del nodo sensor...
```

#### 1.3 Compilación y Carga
1. Abrir PlatformIO en VS Code
2. Crear nuevo proyecto ESP32
3. Agregar dependencias en `platformio.ini`:
   ```ini
   [env:esp32dev]
   platform = espressif32
   board = esp32dev
   framework = arduino
   lib_deps = 
       painlessmesh/painlessMesh
       adafruit/DHT sensor library
   ```
4. Copiar código a `src/main.cpp`
5. Compilar: `PlatformIO: Build`
6. Cargar: `PlatformIO: Upload`
7. Verificar funcionamiento: `PlatformIO: Serial Monitor`

### Paso 2: Programación del ESP32 Gateway

#### 2.1 Configuración del Hardware
- **Componentes**: ESP32 (sin sensores adicionales)
- **Ubicación**: Punto intermedio entre red mesh y computadora

#### 2.2 Configuración del Código (GATEWAY.cpp)
```cpp
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

// Configuración y código del gateway...
```

#### 2.3 Programación y Verificación
1. Usar el mismo proyecto PlatformIO
2. Modificar `src/main.cpp` con código del Gateway
3. Agregar dependencia MQTT en `platformio.ini`:
   ```ini
   lib_deps = 
       painlessmesh/painlessMesh
       knolleary/PubSubClient
   ```
4. Compilar y cargar al segundo ESP32
5. Verificar conexiones en Serial Monitor:
   - Conexión a red mesh
   - Conexión a WiFi "Laptop-Santiago"
   - Conexión a MQTT

### Paso 3: Configuración de Mosquitto en la Computadora

#### 3.1 Instalación de Mosquitto
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mosquitto mosquitto-clients

# Verificar instalación
mosquitto --version
```

#### 3.2 Configuración del Hotspot WiFi
1. Crear hotspot con nombre "Laptop-Santiago"
2. Configurar contraseña "salchipapa123"
3. Verificar IP asignada (debe ser 10.42.0.1)
```bash
# Verificar configuración de red
ip addr show
ifconfig
```

#### 3.3 Inicio del Broker Mosquitto
```bash
# Iniciar Mosquitto
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# Verificar que está corriendo
sudo systemctl status mosquitto

# Probar funcionamiento
mosquitto_sub -h localhost -t "test" &
mosquitto_pub -h localhost -t "test" -m "Hello World"
```

#### 3.4 Verificación de Recepción de Datos
```bash
# Escuchar datos del ESP32 Gateway
mosquitto_sub -h localhost -t "dht22/datos/+" -v

# Deberías ver mensajes como:
# dht22/datos/2123456789 {"temperature":22.7,"humidity":54.2}
```

### Paso 4: Implementación del Puente Python

#### 4.1 Instalación de Dependencias
```bash
# Crear entorno virtual (recomendado)
python3 -m venv mqtt_bridge_env
source mqtt_bridge_env/bin/activate

# Instalar librerías necesarias
pip install paho-mqtt requests
```

#### 4.2 Configuración del Script (puente.py)
```python
import paho.mqtt.client as mqtt
import requests
import json
import time

BROKER = "localhost"
PORT = 1883
TOPIC = "dht22/datos/+"
SERVER_URL = "https://agrolink-hd2p.onrender.com/datos"

# Código completo del puente...
```

#### 4.3 Ejecución y Verificación
```bash
# Ejecutar el puente
python3 puente.py

# Verificar salida esperada:
# ✅ Conectado a Mosquitto
# 📡 Suscrito al tópico: dht22/datos/+
# 📥 Mensaje de dht22/datos/2123456789: {"temperature":22.7,"humidity":54.2}
# 🔄 Datos parseados: {...}
# ✅ Datos enviados al servidor Render
```

### Paso 5: Desarrollo y Despliegue del Servidor Flask

#### 5.1 Desarrollo Local del Servidor
```python
# app.py
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///datos_sensores.db'
db = SQLAlchemy(app)

# Código completo del servidor Flask...
```

#### 5.2 Preparación para Despliegue
1. Crear `requirements.txt`:
   ```txt
   Flask==2.3.3
   Flask-SQLAlchemy==3.0.5
   requests==2.31.0
   ```

2. Crear `templates/dht22.html` para visualización web

#### 5.3 Despliegue en Render
1. Crear cuenta en [Render.com](https://render.com)
2. Conectar repositorio GitHub con el código
3. Configurar Web Service:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Environment**: Python 3
4. Desplegar y obtener URL pública

#### 5.4 Actualización del Puente Python
```python
# Actualizar URL en puente.py
SERVER_URL = "https://tu-app-name.onrender.com/datos"
```

### Paso 6: Verificación del Sistema Completo

#### 6.1 Prueba End-to-End
1. **Verificar ESP32 DHT22**: Monitor serial muestra lectura de sensores
2. **Verificar ESP32 Gateway**: Monitor serial muestra recepción mesh y envío MQTT
3. **Verificar Mosquitto**: `mosquitto_sub` muestra mensajes entrantes
4. **Verificar Puente Python**: Script muestra envío exitoso a servidor
5. **Verificar Servidor**: Acceder a URL pública y ver datos en tabla

#### 6.2 Comandos de Diagnóstico
```bash
# Verificar conexión de red
ping 10.42.0.1

# Verificar Mosquitto
mosquitto_sub -h localhost -t "dht22/datos/+" -v

# Verificar servidor remoto
curl -X GET https://tu-app.onrender.com/api/datos

# Verificar logs del puente
python3 puente.py
```

#### 6.3 Métricas de Funcionamiento
- **Frecuencia de datos**: Cada 10 segundos desde ESP32 DHT22
- **Latencia típica**: 3-6 segundos desde sensor hasta visualización web
- **Disponibilidad**: 24/7 una vez configurado correctamente

### Paso 7: Mantenimiento y Monitoreo

#### 7.1 Logs y Debugging
- **ESP32**: Usar Serial Monitor para ver estado de conexiones
- **Mosquitto**: Logs en `/var/log/mosquitto/mosquitto.log`
- **Python**: Agregar logging detallado para troubleshooting
- **Render**: Usar dashboard de Render para monitoreo del servidor

#### 7.2 Posibles Problemas y Soluciones
| Problema | Causa Probable | Solución |
|----------|----------------|----------|
| No hay datos en web | Puente Python no corriendo | Reiniciar `python3 puente.py` |
| Gateway no conecta | WiFi incorrecto | Verificar credenciales y hotspot |
| Mesh no funciona | Configuraciones diferentes | Verificar MESH_PREFIX y PASSWORD |
| Servidor no responde | Render en sleep mode | Hacer request para "despertar" |

### Cronograma de Implementación

- **Día 1**: Programación y prueba de ESP32s (Pasos 1-2)
- **Día 2**: Configuración de infraestructura local (Paso 3)
- **Día 3**: Desarrollo del puente Python (Paso 4)
- **Día 4**: Desarrollo del servidor Flask (Paso 5)
- **Día 5**: Integración y pruebas (Pasos 6-7)

Este cronograma asume familiaridad básica con las tecnologías involucradas y puede ajustarse según la experiencia del implementador.
