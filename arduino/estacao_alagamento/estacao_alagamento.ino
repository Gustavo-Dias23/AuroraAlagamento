/*
 * estacao_alagamento.ino
 * ---------------------------------------------------------------
 * Aurora - Estacao de monitoramento de alagamento em ciclovias
 * Global Solution 2026.2 - CitizenTech - Project-Based Maker Lab
 *
 * Hardware:
 *   - Arduino Uno
 *   - Sensor ultrassonico HC-SR04  (Trig D7, Echo D8)
 *       apontado para o chao: mede o nivel da agua acumulada
 *   - LED (D6) com resistor de 220R   -> sinal luminoso de alerta
 *   - Servo SG90 (D9)                 -> a cabeca balanca para chamar atencao
 *
 * O notebook (Python) le o sensor, decide o nivel de risco e manda
 * o nivel para ca. O Arduino cuida do LED e do servo.
 *
 * Se o notebook parar de responder por 15 s, o Arduino entra em
 * MODO LOCAL: mede sozinho e aciona o alerta com limiares fixos.
 * Assim a estacao continua protegendo a ciclovia mesmo sem o PC.
 *
 * Protocolo serial (9600 bps), uma linha de resposta por comando:
 *   PING          -> PONG
 *   LER           -> D:<distancia em cm>   (D:-1 = falha do sensor)
 *   CALIBRAR      -> BASE:<cm>   (distancia do piso seco)  ou ERRO:SENSOR
 *   NIVEL:<0-3>   -> OK   (0 seco | 1 poca | 2 alagado | 3 falha)
 *   GESTO         -> OK   (balanca a cabeca)
 * ---------------------------------------------------------------
 */

#include <Servo.h>

// ---------------- Pinos ----------------
const int PINO_TRIG  = 7;
const int PINO_ECHO  = 8;
const int PINO_SERVO = 9;
const int PINO_LED   = 6;

// ---------------- Servo ----------------
// Mude para false se nao quiserem usar o servo
const bool USAR_SERVO = true;
const int ANGULO_CENTRO = 90;
const int AMPLITUDE_GESTO = 30;   // graus para cada lado

// ---------------- Modo local (sem notebook) ----------------
const unsigned long TEMPO_SEM_PC_MS = 15000;
const unsigned long INTERVALO_LOCAL_MS = 1000;
const float LAMINA_POCA_CM    = 1.0;
const float LAMINA_ALAGADO_CM = 3.0;

// ---------------- Niveis ----------------
const int SECO = 0, POCA = 1, ALAGADO = 2, FALHA = 3;

// Padroes do LED: duracoes em ms, alternando ACESO, APAGADO, ACESO...
const unsigned int PADRAO_SECO[]    = {60, 2940};            // "estou ligada"
const unsigned int PADRAO_POCA[]    = {500, 500};            // pisca devagar
const unsigned int PADRAO_ALAGADO[] = {150, 150};            // pisca rapido
const unsigned int PADRAO_FALHA[]   = {100, 150, 100, 1200}; // pisca duplo

// ---------------- Estado ----------------
Servo servoCabeca;
int nivelAtual = SECO;
float distanciaBase = -1;          // distancia ate o piso seco (cm)
unsigned long ultimoComando = 0;
unsigned long ultimaLeituraLocal = 0;
bool modoLocal = false;

const unsigned int *padrao = PADRAO_SECO;
int tamanhoPadrao = 2;
int passoPadrao = 0;
unsigned long inicioPasso = 0;

// ======================================================
// SENSOR ULTRASSONICO
// ======================================================
float medirUmaVez() {
  digitalWrite(PINO_TRIG, LOW);
  delayMicroseconds(3);
  digitalWrite(PINO_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIG, LOW);
  unsigned long duracao = pulseIn(PINO_ECHO, HIGH, 30000UL);  // ~5 m de alcance
  if (duracao == 0) return -1;
  return duracao * 0.0343 / 2.0;
}

// Mediana de 5 leituras: descarta picos e deixa a medida estavel
float medirDistancia() {
  float valores[5];
  int n = 0;
  for (int i = 0; i < 5; i++) {
    float d = medirUmaVez();
    if (d >= 2.0 && d <= 400.0) valores[n++] = d;
    delay(15);
  }
  if (n < 3) return -1;            // leituras demais falharam

  for (int i = 1; i < n; i++) {    // ordena (insertion sort)
    float atual = valores[i];
    int j = i - 1;
    while (j >= 0 && valores[j] > atual) {
      valores[j + 1] = valores[j];
      j--;
    }
    valores[j + 1] = atual;
  }
  return valores[n / 2];
}

// ======================================================
// ATUADORES
// ======================================================
void moverServo(int destino) {
  destino = constrain(destino, 0, 180);
  int atual = servoCabeca.read();
  int passo = (destino > atual) ? 1 : -1;
  while (atual != destino) {
    atual += passo;
    servoCabeca.write(atual);
    delay(6);
  }
}

// Balanca a cabeca de um lado para o outro para chamar atencao
void gesto() {
  if (!USAR_SERVO) return;
  for (int i = 0; i < 2; i++) {
    moverServo(ANGULO_CENTRO - AMPLITUDE_GESTO);
    moverServo(ANGULO_CENTRO + AMPLITUDE_GESTO);
  }
  moverServo(ANGULO_CENTRO);
}

void definirNivel(int nivel) {
  if (nivel < SECO || nivel > FALHA) return;
  if (nivel == nivelAtual) return;
  nivelAtual = nivel;

  switch (nivel) {
    case SECO:    padrao = PADRAO_SECO;    tamanhoPadrao = 2; break;
    case POCA:    padrao = PADRAO_POCA;    tamanhoPadrao = 2; break;
    case ALAGADO: padrao = PADRAO_ALAGADO; tamanhoPadrao = 2; break;
    case FALHA:   padrao = PADRAO_FALHA;   tamanhoPadrao = 4; break;
  }
  passoPadrao = 0;
  inicioPasso = millis();
  digitalWrite(PINO_LED, HIGH);
}

// LED sem delay(): avanca o padrao conforme o tempo passa
void atualizarLed() {
  if (millis() - inicioPasso < padrao[passoPadrao]) return;
  passoPadrao = (passoPadrao + 1) % tamanhoPadrao;
  inicioPasso = millis();
  digitalWrite(PINO_LED, (passoPadrao % 2 == 0) ? HIGH : LOW);
}

// ======================================================
// MODO LOCAL: decide sozinho quando o notebook some
// ======================================================
void decidirLocalmente() {
  if (millis() - ultimaLeituraLocal < INTERVALO_LOCAL_MS) return;
  ultimaLeituraLocal = millis();

  float distancia = medirDistancia();
  if (distancia < 0 || distanciaBase < 0) {
    definirNivel(FALHA);
    return;
  }

  float lamina = distanciaBase - distancia;
  int novo = SECO;
  if (lamina >= LAMINA_ALAGADO_CM)   novo = ALAGADO;
  else if (lamina >= LAMINA_POCA_CM) novo = POCA;

  bool piorou = novo > nivelAtual && novo != FALHA;
  definirNivel(novo);
  if (piorou) gesto();               // chama atencao quando o risco aumenta
}

// ======================================================
// COMANDOS SERIAIS
// ======================================================
int extrairNumero(String comando) {
  int separador = comando.indexOf(':');
  if (separador < 0) return -1;
  return comando.substring(separador + 1).toInt();
}

void processarComando(String comando) {
  if (comando == "PING") {
    Serial.println("PONG");
  }
  else if (comando == "LER") {
    Serial.print("D:");
    Serial.println(medirDistancia(), 1);
  }
  else if (comando == "CALIBRAR") {
    float distancia = medirDistancia();
    if (distancia < 0) {
      Serial.println("ERRO:SENSOR");
    } else {
      distanciaBase = distancia;
      Serial.print("BASE:");
      Serial.println(distanciaBase, 1);
    }
  }
  else if (comando.startsWith("NIVEL:")) {
    definirNivel(extrairNumero(comando));
    Serial.println("OK");
  }
  else if (comando == "GESTO") {
    gesto();
    Serial.println("OK");
  }
  else {
    Serial.println("ERRO:COMANDO");
  }
}

// ======================================================
// SETUP E LOOP
// ======================================================
void setup() {
  Serial.begin(9600);
  pinMode(PINO_TRIG, OUTPUT);
  pinMode(PINO_ECHO, INPUT);
  pinMode(PINO_LED, OUTPUT);

  if (USAR_SERVO) {
    servoCabeca.attach(PINO_SERVO);
    servoCabeca.write(ANGULO_CENTRO);
  }

  delay(300);
  distanciaBase = medirDistancia();   // calibra com o piso seco ao ligar
  ultimoComando = millis();
  inicioPasso = millis();
}

void loop() {
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();
    comando.toUpperCase();
    if (comando.length() > 0) {
      ultimoComando = millis();
      modoLocal = false;
      processarComando(comando);
    }
  }

  // Sem noticias do notebook: assume o controle
  if (!modoLocal && millis() - ultimoComando > TEMPO_SEM_PC_MS) {
    modoLocal = true;
  }
  if (modoLocal) {
    decidirLocalmente();
  }

  atualizarLed();
}
