#ifndef MAIN_H
#define MAIN_H

#include "commMux.h"
#include <bsec2.h>          // Updated to include BSEC2 library
#include <Arduino.h>

// Constants
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
#define MAX_HEATER_PROFILE_LENGTH 10
#define NUM_DUTY_CYCLE_PROFILES 1
#define MEAS_DUR 140

// Struct Definitions
struct HeaterProfile {
    String id;
    uint16_t temps[MAX_HEATER_PROFILE_LENGTH];
    uint16_t durProf[MAX_HEATER_PROFILE_LENGTH];
    uint8_t length;
};

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

// External Variable Declarations
extern HeaterProfile heaterProfiles[4];
extern DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
extern DutyCycleState dutyCycleStates[NUM_SENSORS];
extern Bsec2 envSensors[NUM_SENSORS];  // Replaced Bme68x with Bsec2
extern commMux communicationSetups[NUM_SENSORS];

// Changed to int for unbounded label tag
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

// Function Prototypes
void errLeds(void);
bool setHeaterProfile(uint8_t profileIndex, uint8_t sensorIndex); // Updated for BSEC2
void checkBsecStatus(Bsec2 &bsec);
void getHeaterProfiles();
void initializeHeaterProfiles();
void initializeDutyCycleProfiles();
void initializeSensorDutyCycles();
void handleSerialCommands();
void handleButtonPresses();
void collectAndOutputData();
void updateDutyCycleStates();
void cycleHeaterProfileAssignment();
#endif // MAIN_H
