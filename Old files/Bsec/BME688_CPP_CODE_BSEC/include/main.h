
#ifndef MAIN_H
#define MAIN_H

#include "commMux.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <SdFat.h>
#include <memory>
#include <bsec2.h>
#include <bsec_selectivity.h>

// -------------------------
// Constants and Definitions
// -------------------------
#define NUM_SENSORS 8
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
#define MEAS_DUR 140  

// SD Card Definitions
#define SD_PIN_CS 33
#define CONFIG_FILE_NAME "/config.json"

// BSEC configuration settings (adjust as needed)
#define SAMPLE_RATE BSEC_SAMPLE_RATE_LP

// -------------------------
// Structures
// -------------------------

// Heater profile structure (for BSEC2)
struct HeaterProfile {
  String id;
  uint16_t temps[MAX_HEATER_PROFILE_LENGTH];
  uint16_t durations[MAX_HEATER_PROFILE_LENGTH];
  uint8_t length;
};

// Duty-cycle structures
struct DutyCycleProfile {
  String id;
  uint8_t numberScanningCycles;
  uint8_t numberSleepingCycles;
};

struct DutyCycleState {
  DutyCycleProfile* profile;
  bool isScanning;
  uint8_t cyclesLeft;
  unsigned long lastCycleChangeTime;
};

// Sensor configuration (from SD card)
struct SensorConfig {
  uint8_t sensorIndex;
  String heaterProfile;       // must match a HeaterProfile id
  String dutyCycleProfile;    // must match a DutyCycleProfile id
};

// -------------------------
// External Variable Declarations
// -------------------------
extern HeaterProfile heaterProfiles[4];
extern DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
extern DutyCycleState dutyCycleStates[NUM_SENSORS];

extern SensorConfig sensorConfigs[NUM_SENSORS];
extern uint8_t numSensorConfigs;
extern uint8_t numDutyCycleProfilesLoaded;

// BSEC2 sensor objects and communication setups
extern Bsec2 bsecSensors[NUM_SENSORS];
extern commMux communicationSetups[NUM_SENSORS];
extern uint8_t bsecMemBlock[NUM_SENSORS][BSEC_INSTANCE_SIZE];

// Global button and data collection variables
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

// Hardcoded mapping for cycling heater profiles
extern const uint8_t heaterProfileAssignmentsTable[4][NUM_SENSORS];

// SD card object
extern SdFat sd;

// New global: per-sensor last update time (in ms)
extern unsigned long lastSensorUpdate[NUM_SENSORS];

// -------------------------
// Function Prototypes
// -------------------------
void errLeds(void);
bool setHeaterProfile(uint8_t profileIndex, Bsec2 &sensor);
void getHeaterProfiles(void);
void initializeHeaterProfiles(void);
void initializeDutyCycleProfiles(void);
void initializeSensorDutyCycles(void);
void loadDynamicConfig(void);
void assignDynamicSensorConfigs(void);
void assignHardcodedSensorConfigs(void);
void cycleHeaterProfileAssignment(void);
void handleSerialCommands(void);
void handleButtonPresses(void);
void collectAndOutputData(void);
void updateDutyCycleStates(void);
void getDutyCycleProfiles(void);
void controlSensorOpModes(void);
void updateSensors(void);
void reportSensorsStatus(void);

// Error reporting and LED functions
String getBsecErrorMessage(int code);
String getBmeErrorMessage(int code);
void blinkWarningLED(void);
void blinkErrorLED(void);
void reportBsecStatus(Bsec2 bsec);
void newDataCallback(bme68x_data data, bsecOutputs outputs, Bsec2 bsec);

#endif // MAIN_H
