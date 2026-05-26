#include <SoftwareSerial.h>
SoftwareSerial xbee(0, 1);

// Définition des broches (Pins)
const int trig1 = 5;
const int echo1 = 8;
const int trig2 = 6;
const int echo2 = 9;
const int PIN_DIR = 11;
const int PIN_PUL = 12;

int TEMP01 = 60;
const int led1 = 2;
const int led2 = 3;
long duration;
int distance1;
int distance2;

unsigned long led1StartTime = 0;
bool led1TimerActive = false;
unsigned long previousMicros = 0;
bool motorState = false;
bool attenteNouveauCube = false;
int nbMessagesEnvoyes = 0;



int mesurerDistance(int trigPin, int echoPin) {

  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000);
  int distance = duration * 0.034 / 2;

  return distance;
}

void setup() {
  xbee.begin(9600);     // Communication XBee
 
  pinMode(trig1, OUTPUT);
  pinMode(echo1, INPUT);
  pinMode(trig2, OUTPUT);
  pinMode(echo2, INPUT);
  pinMode(led1, OUTPUT);  
  pinMode(led2, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_PUL, OUTPUT);

  digitalWrite(PIN_DIR, LOW);
}

void loop() {
  unsigned long currentTime = millis();

  distance1 = mesurerDistance(trig1, echo1);
  distance2 = mesurerDistance(trig2, echo2);

  bool detect1 = (distance1 > 0 && distance1 < 20);
  bool detect2 = (distance2 > 0 && distance2 < 20);
 

  // ===== PRIORITÉ CAPTEUR 2 (Point de saisie Dobot) ====
if (detect2) {
    // On force l'arrêt des actions du capteur 1
    motorState = false; 
    digitalWrite(led1, LOW);
    digitalWrite(led2, HIGH);
    
    // Envoi unique via XBee grâce au verrou
    if (nbMessagesEnvoyes == 0) {
        xbee.println("OBJET"); 
        Serial.println("Signal XBee envoyé : OBJET");
        nbMessagesEnvoyes = 1; // Verrouille l'envoi
    }
    
    led1TimerActive = false; // Désactive le timer de sécurité du moteur
} 

// 2. CONDITION SECONDAIRE : CAPTEUR 2 LIBRE
else {
    // Dès que le capteur 2 est libre, on éteint sa LED et on déverrouille le XBee
    digitalWrite(led2, LOW);
    nbMessagesEnvoyes = 0; 

    // On traite maintenant le Capteur 1 (Entrée convoyeur)
    if (detect1) { attenteNouveauCube = true;
        digitalWrite(led1, HIGH);
        motorState = true;      // Le moteur démarre
        led1TimerActive = false; // On annule le timer car un objet est présent
    } 
    
    // 3. GESTION DU DÉPART (Si detect1 et detect2 sont faux)
     else {
      if (!led1TimerActive) {
        led1TimerActive = true;
        led1StartTime = currentTime;
      }

      // Après 30 secondes sans détection sur capteur 1, on coupe le moteur
      if (led1TimerActive && (currentTime - led1StartTime >= 20000)) {
        digitalWrite(led1, LOW);
        motorState = true;
      }
    }
}

  // ===== PILOTAGE DU MOTEUR =====
    if (motorState) {

   

      for (int iNbSteps = 0; iNbSteps < 6400; iNbSteps++) {

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