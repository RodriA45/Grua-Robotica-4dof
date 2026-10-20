/*
 * ============================================================================
 * CONTROL DE BRAZO ROBÓTICO / GRÚA (4 GDL) POR PUERTO SERIAL (USB)
 * ============================================================================
 * 
 * Servos:
 *  - Base (Giro horizontal):       Pin 9
 *  - Hombro (Brazo inferior):      Pin 10
 *  - Codo (Brazo superior):        Pin 11
 *  - Pinza (Gripper apertura):     Pin 6
 * 
 * Protocolo de comunicación (9600 baudios):
 *  Envía por Serial una línea con los 4 ángulos deseados separados por coma:
 *      <Base,Hombro,Codo,Pinza>
 *      Ejemplo: "90,110,80,45\n" o "<90,110,80,45>\n"
 * 
 * Movimiento Suave (Interpolación):
 *  Los servos no saltan de golpe; se mueven paso a paso a una velocidad
 *  controlada para evitar tirones mecánicos y caídas de tensión.
 * ============================================================================
 */

#include <Servo.h>

// Definición de Pines de los Servos
const int PIN_BASE   = 9;
const int PIN_HOMBRO = 10;
const int PIN_CODO   = 11;
const int PIN_PINZA  = 6;

// Objetos Servo
Servo servoBase;
Servo servoHombro;
Servo servoCodo;
Servo servoPinza;

// LÍMITES DE SEGURIDAD (en grados)
// Ajusta estos valores según la mecánica de tu brazo impreso en 3D
const int BASE_MIN   = 0,   BASE_MAX   = 180;
const int HOMBRO_MIN = 20,  HOMBRO_MAX = 160;
const int CODO_MIN   = 20,  CODO_MAX   = 160;
const int PINZA_MIN  = 15,  PINZA_MAX  = 115; // PINZA_MIN cerrada, PINZA_MAX abierta

// Posiciones objetivo (Target) y actuales
float targetBase   = 90;
float targetHombro = 90;
float targetCodo   = 90;
float targetPinza  = 90;

float currentBase   = 90;
float currentHombro = 90;
float currentCodo   = 90;
float currentPinza  = 90;

// Parámetros de velocidad de movimiento suave
// Grados máximos por paso
const float VELOCIDAD_PASO = 1.2; 
unsigned long ultimoPaso = 0;
const unsigned long INTERVALO_PASO_MS = 15; // Actualiza cada 15ms (~60Hz)

// Buffer para lectura serial
String inputString = "";
bool stringComplete = false;

void setup() {
  Serial.begin(9600);
  inputString.reserve(64);

  // Vincular servos a los pines
  servoBase.attach(PIN_BASE);
  servoHombro.attach(PIN_HOMBRO);
  servoCodo.attach(PIN_CODO);
  servoPinza.attach(PIN_PINZA);

  // Posición inicial de inicio (Home)
  servoBase.write((int)currentBase);
  servoHombro.write((int)currentHombro);
  servoCodo.write((int)currentCodo);
  servoPinza.write((int)currentPinza);

  Serial.println(F("OK: Grua lista. Esperando datos <B,H,C,P>..."));
}

void loop() {
  // 1. Leer del puerto Serial (funciona en cualquier clon o placa de Arduino)
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n' || inChar == '\r') {
      if (inputString.length() > 0) {
        procesarComando(inputString);
        inputString = "";
      }
    } else {
      inputString += inChar;
    }
  }

  // 2. Mover suavemente los servos hacia los ángulos objetivo
  unsigned long ahora = millis();
  if (ahora - ultimoPaso >= INTERVALO_PASO_MS) {
    ultimoPaso = ahora;
    actualizarServosSuave();
  }
}


// Procesa una cadena como "<90,120,80,45>" o "90,120,80,45"
void procesarComando(String cmd) {
  cmd.trim();
  if (cmd.startsWith("<") && cmd.endsWith(">")) {
    cmd = cmd.substring(1, cmd.length() - 1);
  }

  // Si envían "HOME", vuelve al centro
  if (cmd.equalsIgnoreCase("HOME")) {
    targetBase = 90;
    targetHombro = 90;
    targetCodo = 90;
    targetPinza = 90;
    Serial.println(F("ACK: HOME"));
    return;
  }

  // Separar los 4 valores por comas
  int c1 = cmd.indexOf(',');
  int c2 = cmd.indexOf(',', c1 + 1);
  int c3 = cmd.indexOf(',', c2 + 1);

  if (c1 > 0 && c2 > 0 && c3 > 0) {
    float b = cmd.substring(0, c1).toFloat();
    float h = cmd.substring(c1 + 1, c2).toFloat();
    float c = cmd.substring(c2 + 1, c3).toFloat();
    float p = cmd.substring(c3 + 1).toFloat();

    // Aplicar límites de seguridad
    targetBase   = constrain(b, BASE_MIN, BASE_MAX);
    targetHombro = constrain(h, HOMBRO_MIN, HOMBRO_MAX);
    targetCodo   = constrain(c, CODO_MIN, CODO_MAX);
    targetPinza  = constrain(p, PINZA_MIN, PINZA_MAX);

    // Confirmación opcional
    // Serial.print(F("ACK: "));
    // Serial.println(cmd);
  }
}

// Aproxima gradualmente cada ángulo a su objetivo
void actualizarServosSuave() {
  bool huboCambio = false;

  currentBase   = acercar(currentBase, targetBase, VELOCIDAD_PASO, huboCambio);
  currentHombro = acercar(currentHombro, targetHombro, VELOCIDAD_PASO, huboCambio);
  currentCodo   = acercar(currentCodo, targetCodo, VELOCIDAD_PASO, huboCambio);
  currentPinza  = acercar(currentPinza, targetPinza, VELOCIDAD_PASO * 1.5, huboCambio); // Pinza un poco más rápida

  if (huboCambio) {
    servoBase.write((int)currentBase);
    servoHombro.write((int)currentHombro);
    servoCodo.write((int)currentCodo);
    servoPinza.write((int)currentPinza);
  }
}

float acercar(float actual, float objetivo, float maxPaso, bool &cambio) {
  float diff = objetivo - actual;
  if (abs(diff) < 0.2) {
    return actual;
  }
  cambio = true;
  if (diff > maxPaso) {
    return actual + maxPaso;
  } else if (diff < -maxPaso) {
    return actual - maxPaso;
  } else {
    return objetivo;
  }
}
