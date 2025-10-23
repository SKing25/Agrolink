#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  for (int pin = 0; pin <= 39; pin++) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);
    delay(100);
    digitalWrite(pin, LOW);
    delay(100);
    Serial.print("Tested pin: ");
    Serial.println(pin);
  }
}

void loop() {
  // Nada aquí
}