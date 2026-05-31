/*
   ______            __                  _            __                __________
  / ____/_  ______ _/ /__________ _   __(_)__  ____  / /_____  _____   / ____/  _/
 / /   / / / / __ `/ __/ ___/ __ \ | / / / _ \/ __ \/ __/ __ \/ ___/  / /    / /  
/ /___/ /_/ / /_/ / /_/ /  / /_/ / |/ / /  __/ / / / /_/ /_/ (__  )  / /____/ /   
\____/\__,_/\__,_/\__/_/   \____/|___/_/\___/\_/ /_/\__/\____/____/   \____/___/   
                                                                                
    __             ___              __             ______   __   
   / /_  __  __   /   |  ____  ____/ /__  _____   / ____/  / /   
  / __ \/ / / /  / /| | / __ \/ __  / _ \/ ___/  / /_     / /    
 / /_/ / /_/ /  / ___ |/ / / / /_/ /  __/ /     / __/  _ / /____ 
/_.___/\__, /  /_/  |_/_/ /_/\__,_/\___/\_/     /_/    (_)_____(_)
      /____/   
                                           
 Smarthome Serial Communication Project
 
 This project integrates all the smarthome lessons into a single Arduino sketch.
 It uses Serial communication for requests and results.

 CopyRight Ander F.L. <ander_frago@cuatrovientos.org> June 2024
*/

// Included Libraries
#include <LiquidCrystal_I2C.h>
#include <Servo.h>
#include <SPI.h>
#include <RFID.h>
#include <dht.h>
#include <Keypad.h>

// Pin Definitions
#define redLED 13
#define greenLED 10
#define buzzer 5
#define flame_sensor A1
#define sound_sensor A2
#define motion_sensor 4
#define whiteLED 9
#define yellowLED 12
#define Trig_PIN 25
#define Echo_PIN 26
#define SERVO_PIN 3
#define RFID_SDA 48
#define RFID_RST 49
#define DHT11_PIN 2
#define redPin_RGB 24
#define greenPin_RGB 23
#define bluePin_RGB 22

// LCD Display
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Servo Motor
Servo head;

// RFID
unsigned char my_rfid[] = {227, 10, 252, 39, 50}; // replace with your RFID value
RFID rfid(RFID_SDA, RFID_RST);

// DHT Sensor
dht DHT;

// Keypad
const byte ROWS = 4;
const byte COLS = 4;
char hexaKeys[ROWS][COLS] = {
  {'1', '2', '3', 'A'},
  {'4', '5', '6', 'B'},
  {'7', '8', '9', 'C'},
  {'*', '0', '#', 'D'}
};
byte rowPins[ROWS] = {33, 35, 37, 39};
byte colPins[COLS] = {41, 43, 45, 47};
Keypad customKeypad = Keypad(makeKeymap(hexaKeys), rowPins, colPins, ROWS, COLS);

String command = "";

void setup() {
  // Initialize Serial
  Serial.begin(9600);
  command.reserve(256);

  // Initialize Pins
  pinMode(redLED, OUTPUT);
  pinMode(greenLED, OUTPUT);
  pinMode(buzzer, OUTPUT);
  pinMode(flame_sensor, INPUT);
  pinMode(sound_sensor, INPUT);
  pinMode(motion_sensor, INPUT);
  pinMode(whiteLED, OUTPUT);
  pinMode(yellowLED, OUTPUT);
  pinMode(Trig_PIN, OUTPUT);
  pinMode(Echo_PIN, INPUT);
  pinMode(redPin_RGB, OUTPUT);
  pinMode(greenPin_RGB, OUTPUT);
  pinMode(bluePin_RGB, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.print("Smarthome Ready!");

  // Initialize SPI and RFID
  SPI.begin();
  rfid.init();

  Serial.println("Smarthome Ready. Enter commands via Serial monitor.");
}

void loop() {
  // Handle Serial Commands
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      executeCommand(command);
      command = "";
    } else {
      command += c;
    }
  }

  // Handle Keypad Input
  handleKeypad();
  
  // Handle RFID
  handleRFID();
}

void executeCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  Serial.print("Executing command: ");
  Serial.println(cmd);

  if (cmd.startsWith("led")) {
    handleLedCommand(cmd);
  } else if (cmd.startsWith("rgb")) {
    handleRgbCommand(cmd);
  } else if (cmd.startsWith("all")) {
    handleAllCommand(cmd);
  } else if (cmd.startsWith("buzzer")) {
    handleBuzzerCommand(cmd);
  } else if (cmd.startsWith("sensors")) {
    readAllSensors();
  } else if (cmd.startsWith("servo")) {
    handleServoCommand(cmd);
  } else if (cmd.startsWith("lcd")) {
    handleLcdCommand(cmd);
  } else {
    Serial.println("Unknown command");
  }
}

void handleLedCommand(String cmd) {
  bool turnOn  = cmd.indexOf("on")  > 0;
  bool turnOff = cmd.indexOf("off") > 0;

  if (cmd.indexOf("all") > 0) {
    setAllLights(turnOn, turnOff);
    return;
  }
  if (cmd.indexOf("red") > 0)    applyLed(redLED,    "LedRojo",     turnOn, turnOff);
  if (cmd.indexOf("green") > 0)  applyLed(greenLED,  "LedVerde",    turnOn, turnOff);
  if (cmd.indexOf("yellow") > 0) applyLed(yellowLED, "LedAmarillo", turnOn, turnOff);
  if (cmd.indexOf("white") > 0)  applyLed(whiteLED,  "LedBlanco",   turnOn, turnOff);
  if (cmd.indexOf("rgb") > 0)    handleLedRgbHex(cmd);
}

void handleAllCommand(String cmd) {
  bool turnOn  = cmd.indexOf("on")  > 0;
  bool turnOff = cmd.indexOf("off") > 0;
  setAllLights(turnOn, turnOff);
}

void setAllLights(bool turnOn, bool turnOff) {
  if (turnOn) {
    digitalWrite(redLED, HIGH);
    digitalWrite(greenLED, HIGH);
    digitalWrite(yellowLED, HIGH);
    digitalWrite(whiteLED, HIGH);
    color(255, 255, 255);
    Serial.println("Result: All lights ON");
  } else if (turnOff) {
    digitalWrite(redLED, LOW);
    digitalWrite(greenLED, LOW);
    digitalWrite(yellowLED, LOW);
    digitalWrite(whiteLED, LOW);
    color(0, 0, 0);
    Serial.println("Result: All lights OFF");
  }
}

void applyLed(int pin, const char* label, bool turnOn, bool turnOff) {
  if (turnOn) {
    digitalWrite(pin, HIGH);
    Serial.print("Result: ");
    Serial.print(label);
    Serial.println(" ON");
  } else if (turnOff) {
    digitalWrite(pin, LOW);
    Serial.print("Result: ");
    Serial.print(label);
    Serial.println(" OFF");
  }
}

void handleLedRgbHex(String cmd) {
  int hashPos = cmd.indexOf('#');
  if (hashPos == -1 || cmd.length() < (unsigned)(hashPos + 7)) return;

  String hexColor = cmd.substring(hashPos + 1, hashPos + 7);
  int r = strtol(hexColor.substring(0, 2).c_str(), NULL, 16);
  int g = strtol(hexColor.substring(2, 4).c_str(), NULL, 16);
  int b = strtol(hexColor.substring(4, 6).c_str(), NULL, 16);
  color(r, g, b);
  Serial.print("Result: RGB set to #");
  Serial.println(hexColor);
}

void handleRgbCommand(String cmd) {
  if (cmd.indexOf("red") > 0) {
    color(255, 0, 0);
    Serial.println("Result: RGB set to RED");
  } else if (cmd.indexOf("green") > 0) {
    color(0, 255, 0);
    Serial.println("Result: RGB set to GREEN");
  } else if (cmd.indexOf("blue") > 0) {
    color(0, 0, 255);
    Serial.println("Result: RGB set to BLUE");
  }
}

void handleBuzzerCommand(String cmd) {
  if (cmd.indexOf("on") > 0) {
    digitalWrite(buzzer, HIGH);
    Serial.println("Result: Buzzer is ON");
  } else if (cmd.indexOf("off") > 0) {
    digitalWrite(buzzer, LOW);
    Serial.println("Result: Buzzer is OFF");
  }
}

void handleServoCommand(String cmd) {
  if (cmd.indexOf("open") > 0) {
    open_door();
    Serial.println("Result: Servo OPEN");
  } else if (cmd.indexOf("half") > 0) {
    half_open();
    Serial.println("Result: Servo HALF-OPEN");
  } else if (cmd.indexOf("close") > 0) {
    close_door();
    Serial.println("Result: Servo CLOSE");
  }
}

void handleLcdCommand(String cmd) {
  int firstQuote = cmd.indexOf('"');
  int secondQuote = cmd.lastIndexOf('"');
  if (firstQuote == -1 || secondQuote == -1 || firstQuote == secondQuote) return;

  String msg = cmd.substring(firstQuote + 1, secondQuote);
  lcd.clear();
  lcd.backlight();
  lcd.print(msg);
  Serial.println("Result: LCD message sent");
}

void readAllSensors() {
  // Flame Sensor
  int flame_status = digitalRead(flame_sensor);
  if (flame_status == 1) {
    Serial.println("Result: Safe (No Fire)");
  } else {
    Serial.println("Result: Fire Detected!");
  }

  // Sound Sensor
  int SoundStatus = digitalRead(sound_sensor);
  if (SoundStatus == 1) {
    Serial.println("Result: No Noise!");
  } else {
    Serial.println("Result: Noise Detected!");
  }

  // Motion Sensor
  int gasStatus = digitalRead(motion_sensor);
  if (gasStatus == 0) {
    Serial.println("Result: No Intruder!");
  } else {
    Serial.println("Result: Intruder Detected!");
  }

  // Ultrasonic Sensor
  int distance_val = watch();
  Serial.print("Result: Distance: ");
  Serial.print(distance_val);
  Serial.println(" cm");

  // DHT11 Sensor
  DHT.read11(DHT11_PIN);
  Serial.print("Result: Humidity: ");
  Serial.print(DHT.humidity, 1);
  Serial.println("%");
  Serial.print("Result: Temperature: ");
  Serial.print(DHT.temperature, 1);
  Serial.println("C");
}

void handleKeypad() {
  char customKey = customKeypad.getKey();
  if (customKey == '*') {
    close_door();
    Serial.println("Keypad: Door Closed");
  }
  if (customKey == '#') {
    open_door();
    Serial.println("Keypad: Door Opened");
  }
  if (customKey == '0') {
    half_open();
    Serial.println("Keypad: Door Half-Opened");
  }
}

void handleRFID() {
  if (rfid.isCard()) {
    if (rfid.readCardSerial()) {
      if (compare_rfid(rfid.serNum, my_rfid)) {
        open_door();
        Serial.println("RFID: Access Granted");
      } else {
        close_door();
        digitalWrite(buzzer, HIGH);
        delay(1000);
        digitalWrite(buzzer, LOW);
        Serial.println("RFID: Access Denied");
      }
    }
    rfid.halt();
  }
}

// Helper functions
void color(unsigned char red, unsigned char green, unsigned char blue) {
  analogWrite(redPin_RGB, red);
  analogWrite(greenPin_RGB, green);
  analogWrite(bluePin_RGB, blue);
}

void open_door() {
  head.attach(SERVO_PIN);
  delay(300);
  head.write(180);
  delay(400);
  head.detach();
  digitalWrite(SERVO_PIN, LOW);
  digitalWrite(greenLED, HIGH);
  digitalWrite(redLED, LOW);
}

void half_open() {
  head.attach(SERVO_PIN);
  delay(300);
  head.write(90);
  delay(400);
  head.detach();
  digitalWrite(SERVO_PIN, LOW);
  digitalWrite(greenLED, LOW);
  digitalWrite(redLED, LOW);
}

void close_door() {
  head.attach(SERVO_PIN);
  delay(300);
  head.write(0);
  delay(400);
  head.detach();
  digitalWrite(SERVO_PIN, LOW);
  digitalWrite(greenLED, LOW);
  digitalWrite(redLED, HIGH);
}

boolean compare_rfid(unsigned char x[], unsigned char y[]) {
  for (int i = 0; i < 5; i++) {
    if (x[i] != y[i]) return false;
  }
  return true;
}

int watch() {
  long echo_distance;
  digitalWrite(Trig_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(Trig_PIN, HIGH);
  delayMicroseconds(15);
  digitalWrite(Trig_PIN, LOW);
  echo_distance = pulseIn(Echo_PIN, HIGH);
  echo_distance = echo_distance * 0.01657;
  return round(echo_distance);
}
