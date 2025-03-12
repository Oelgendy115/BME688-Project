
// =========================
// main.h
// =========================

#ifndef MAIN_H
#define MAIN_H

#include "commMux.h"
#include <bme68xLibrary.h>
#include <Arduino.h>
#include <ArduinoJson.h>
#include <SdFat.h>
#include <memory>

// =========================
// Constants and Definitions
// =========================
#define NUM_SENSORS 8
#define FIELDS_PER_SENSOR 6
#define TOTAL_FIELDS (NUM_SENSORS * FIELDS_PER_SENSOR)
#define PANIC_LED   LED_BUILTIN
#define ERROR_DUR   1000
#define BUTTON_PIN1 32
#define BUTTON_PIN2 14
#define DEBOUNCE_DELAY 50
#define CMD_START "START"
#define CMD_STOP "STOP"
#define CMD_SEC_PREFIX "SEC_"
#define CMD_GETHEAT "GETHEAT"
#define CMD_GETDUTY "GETDUTY"
#define MAX_HEATER_PROFILE_LENGTH 10
#define NUM_DUTY_CYCLE_PROFILES 1
#define MEAS_DUR 140  // Measurement duration in milliseconds

// SD Card Definitions
#define SD_PIN_CS 33               // Chip Select pin for SD card
#define CONFIG_FILE_NAME "/config.json"

// =========================
// Data Structures
// =========================

// Wrapper for the native heater configuration.
struct HeaterConfig {
  String id;                      // Identifier from the configuration file.
  bme68x_heatr_conf conf;         // Native heater configuration structure.
};

// Structure for duty cycle profiles.
struct DutyCycleProfile {
  String id;
  uint8_t numberScanningCycles;
  uint8_t numberSleepingCycles;
};

// Structure for tracking the duty cycle state.
struct DutyCycleState {
  DutyCycleProfile* profile;
  bool isScanning;                // true = scanning, false = sleeping.
  uint8_t cyclesLeft;             // Number of cycles remaining in current state.
  unsigned long lastCycleChangeTime;
};

// Structure for sensor configuration loaded from JSON.
struct SensorConfig {
  uint8_t sensorIndex;
  String heaterProfile;       // Must match one of the HeaterConfig IDs.
  String dutyCycleProfile;    // Must match one of the DutyCycleProfile IDs.
};

// =========================
// External Variable Declarations
// =========================
extern HeaterConfig heaterConfigs[4];
extern DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
extern DutyCycleState dutyCycleStates[NUM_SENSORS];
extern SensorConfig sensorConfigs[NUM_SENSORS];
extern uint8_t numSensorConfigs;
extern uint8_t numDutyCycleProfilesLoaded;

extern Bme68x sensors[NUM_SENSORS];
extern bme68xData sensorData[NUM_SENSORS];
extern commMux communicationSetups[NUM_SENSORS];

extern int buttonOneValue;
extern uint8_t currentHeaterProfileIndex;
extern uint32_t lastLogged;

extern bool button1State;
extern bool lastButton1State;
extern bool button2State;
extern bool lastButton2State;
extern unsigned long lastDebounceTime1;
extern unsigned long lastDebounceTime2;

extern bool stopDataCollection;
extern bool jsonClosed;
extern bool dataCollectionStarted;

extern unsigned long lastDataSendTime;
extern bool firstDataSent;
extern unsigned long dataInterval;

// =========================
// Function Prototypes
// =========================
void errLeds(void);
bool setHeaterProfile(uint8_t profileIndex, Bme68x &sensor);
void getHeaterProfiles();
void initializeHeaterConfigs();
void initializeDutyCycleProfiles();
void initializeSensorDutyCycles();
void handleSerialCommands();
void handleButtonPresses();
void collectAndOutputData();
void updateDutyCycleStates();
void cycleHeaterProfileAssignment();
void loadDynamicConfig();
bool writeConfigToSD(const String &configData);
void uploadConfigFromSerial();
void assignDynamicSensorConfigs();
void assignHardcodedSensorConfigs();
void sendSensorStatusReport();
void getDutyCycleProfiles();

#endif // MAIN_H

// =========================
// End of main.h
// =========================
