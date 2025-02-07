#ifndef MAIN_H
#define MAIN_H

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <bsec2.h>
#include "commMux.h"  // Your commMux functions for multiplexer control

// ------------------------------------------------------------
// Constants
// ------------------------------------------------------------
#define NUM_SENSORS 8
#define PANIC_LED   LED_BUILTIN
#define ERROR_DUR   1000
#define BUTTON_PIN1 32
#define BUTTON_PIN2 14
#define DEBOUNCE_DELAY 50

#define CMD_START    "START"
#define CMD_STOP     "STOP"
#define CMD_SEC_PREFIX "SEC_"
#define CMD_GETHEAT  "GETHEAT"  // For BSEC, this will output the current subscription profile

#define MEAS_DUR 140  // minimum time (ms) between logging samples

// (Optional) Temperature offset definitions – adjust these if needed
#define TEMP_OFFSET_ULP 0
#define TEMP_OFFSET_LP  0

// ------------------------------------------------------------
// Structure to hold a BSEC subscription profile
// ------------------------------------------------------------
struct BsecProfile {
    String id;
    const bsec_sensor_configuration_t* sensorList;
    uint8_t numSensors;
    uint8_t sampleRate; // e.g. BSEC_SAMPLE_RATE_ULP or BSEC_SAMPLE_RATE_LP
};

// ------------------------------------------------------------
// External declarations
// ------------------------------------------------------------
extern Bsec2 bsecSensors[NUM_SENSORS];
extern commMux communicationSetups[NUM_SENSORS];
extern BsecProfile bsecProfiles[4];

extern int buttonOneValue;
extern uint8_t currentBsecProfileIndex;
extern unsigned long lastLogged;
extern bool dataCollectionStarted;
extern bool stopDataCollection;
extern unsigned long lastDataSendTime;
extern unsigned long dataInterval;

extern bool button1State, lastButton1State;
extern bool button2State, lastButton2State;
extern unsigned long lastDebounceTime1, lastDebounceTime2;

// ------------------------------------------------------------
// Function prototypes
// ------------------------------------------------------------
void setupSensors(void);
void handleSerialCommands(void);
void handleButtonPresses(void);
void collectAndOutputData(void);
void cycleBsecProfileAssignment(void);
void errLeds(void);
void checkBsecStatus(Bsec2 sensor);

#endif // MAIN_H
