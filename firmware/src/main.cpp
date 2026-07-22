#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MotorShield.h>

Adafruit_MotorShield AFMS = Adafruit_MotorShield(); 
Adafruit_DCMotor *rightMotor = AFMS.getMotor(1); // M1 Slot
Adafruit_DCMotor *leftMotor = AFMS.getMotor(2);  // M2 Slot

void setup() {
  Serial.begin(115200);
  AFMS.begin();
  
  // ensure clean startup state
  leftMotor->run(RELEASE);
  rightMotor->run(RELEASE);
}

void loop() {
  if (Serial.available() > 0) {
    // read incoming string data until a newline character
    String inputString = Serial.readStringUntil('\n');
    inputString.trim();
    
    // find the comma separator
    int commaIndex = inputString.indexOf(',');
    if (commaIndex != -1) {
      // parse out the target speeds from the string segments
      int leftSpeed = inputString.substring(0, commaIndex).toInt();
      int rightSpeed = inputString.substring(commaIndex + 1).toInt();
      
      // ---- control left motor ----
      if (leftSpeed == 0) {
        leftMotor->run(RELEASE);
      } else if (leftSpeed > 0) {
        leftMotor->setSpeed(constrain(leftSpeed, 0, 255));
        leftMotor->run(FORWARD);
      } else {
        leftMotor->setSpeed(constrain(abs(leftSpeed), 0, 255));
        leftMotor->run(BACKWARD);
      }
      
      // ---- control right motor ----
      if (rightSpeed == 0) {
        rightMotor->run(RELEASE);
      } else if (rightSpeed > 0) {
        rightMotor->setSpeed(constrain(rightSpeed, 0, 255));
        rightMotor->run(FORWARD);
      } else {
        rightMotor->setSpeed(constrain(abs(rightSpeed), 0, 255));
        rightMotor->run(BACKWARD);
      }
    }
  }
}
