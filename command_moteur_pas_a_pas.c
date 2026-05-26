#include <SoftwareSerial.h>

SoftwareSerial xbee(0, 1);

// ===== PINS =====
const int capteurIR = 7;

const int PIN_DIR = 11;
const int PIN_PUL = 12;

int TEMP01 = 60;

// ===== VARIABLES =====
bool motorState = true;
int nbMessagesEnvoyes = 0;

// ===== SETUP =====
void setup() {

  Serial.begin(9600);
  xbee.begin(9600);

  pinMode(capteurIR, INPUT);

  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_PUL, OUTPUT);

  digitalWrite(PIN_DIR, LOW);
}

// ===== LOOP =====
void loop() {

  // ===== CAPTEUR IR =====
  bool detect2 = digitalRead(capteurIR) == LOW;

  // ===== LOGIQUE =====
  if (detect2) {

    // Arrêt moteur
    motorState = false;

    // Envoi unique du message
    if (nbMessagesEnvoyes == 0) {

      xbee.println("OBJET");
      Serial.println("Signal XBee envoyé : OBJET");

      nbMessagesEnvoyes = 1;
    }
  }

  else {

    // Redémarrage moteur
    motorState = true;

    // Réinitialisation du verrou
    nbMessagesEnvoyes = 0;
  }

  // ===== MOTEUR =====
  if (motorState) {

    for (int i = 0; i < 3000; i++) {

      digitalWrite(PIN_PUL, HIGH);
      delayMicroseconds(TEMP01);

      digitalWrite(PIN_PUL, LOW);
      delayMicroseconds(TEMP01);
    }
  }

  else {

    digitalWrite(PIN_PUL, LOW);
  }

  delay(50);
}
