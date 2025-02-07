#ifndef MAIN_H
#define MAIN_H

#include "commMux.h"
#include <bsec2.h>
#include <Arduino.h>

// ------------------------------------------------------------
// Constants & Defines
// ------------------------------------------------------------
#define NUM_SENSORS        8
#define FIELDS_PER_SENSOR  6
#define TOTAL_FIELDS       (NUM_SENSORS * FIELDS_PER_SENSOR)

#define PANIC_LED          LED_BUILTIN
#define ERROR_DUR          1000

#define BUTTON_PIN1        32
#define BUTTON_PIN2        14
#define DEBOUNCE_DELAY     50

#define CMD_START          "START"
#define CMD_STOP           "STOP"
#define CMD_SEC_PREFIX     "SEC_"
#define CMD_GETHEAT        "GETHEAT"

#define MAX_HEATER_PROFILE_LENGTH 10
#define NUM_DUTY_CYCLE_PROFILES   1

// How often (ms) we grab BSEC data in collectAndOutputData()
#define MEAS_DUR  140

// ------------------------------------------------------------
// Struct Definitions
// ------------------------------------------------------------
struct HeaterProfile {
    String   id;
    uint16_t temps[MAX_HEATER_PROFILE_LENGTH];
    uint16_t durProf[MAX_HEATER_PROFILE_LENGTH];
    uint8_t  length;
};

struct DutyCycleProfile {
    String  id;
    uint8_t numberScanningCycles;
    uint8_t numberSleepingCycles;
};

struct DutyCycleState {
    DutyCycleProfile* profile;
    bool    isScanning;
    uint8_t cyclesLeft;
    unsigned long lastCycleChangeTime;
};

// ------------------------------------------------------------
// External Variable Declarations
// ------------------------------------------------------------

// Heater Profiles
extern HeaterProfile     heaterProfiles[4];

// Duty Cycle
extern DutyCycleProfile  dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
extern DutyCycleState    dutyCycleStates[NUM_SENSORS];

// BSEC2 sensor objects
extern Bsec2             bsecSensors[NUM_SENSORS];

// I2C/SPI comm multiplexer configurations
extern commMux           communicationSetups[NUM_SENSORS];

// Button / label info
extern int               buttonOneValue;
extern bool              button1State;
extern bool              lastButton1State;
extern bool              button2State;
extern bool              lastButton2State;
extern unsigned long     lastDebounceTime1;
extern unsigned long     lastDebounceTime2;

// Data collection control
extern bool              stopDataCollection;
extern bool              jsonClosed;
extern bool              dataCollectionStarted;
extern unsigned long     dataInterval;
extern unsigned long     lastDataSendTime;
extern bool              firstDataSent;

// Tracks heater profile cycling
extern bool              customHeaterActive;
extern uint8_t           currentHeaterProfileIndex;
extern uint32_t          lastLogged;

// ------------------------------------------------------------
// Function Prototypes
// ------------------------------------------------------------
void errLeds(void);

bool setHeaterProfile(uint8_t profileIndex, Bsec2 &sensor);

void getHeaterProfiles();
void initializeHeaterProfiles();

void initializeDutyCycleProfiles();
void initializeSensorDutyCycles();
void updateDutyCycleStates();

void handleSerialCommands();
void handleButtonPresses();
void cycleHeaterProfileAssignment();

void collectAndOutputData();

#endif // MAIN_H
