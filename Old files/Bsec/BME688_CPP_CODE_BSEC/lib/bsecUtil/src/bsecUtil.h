#ifndef BSEC_UTIL_H
#define BSEC_UTIL_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <SdFat.h>
#include <SPI.h>
#include <memory>
#include <bsec2.h>

// -------------------------
// Configuration Constants
// -------------------------
#define SD_PIN_CS 33
#define CONFIG_FILE_NAME "/config.json"
#define MAX_HEATER_PROFILE_LENGTH 10
#define NUM_HEATER_PROFILES 4
#define NUM_DUTY_CYCLE_PROFILES 1

// -------------------------
// Error Reporting Constants
// -------------------------
#define PANIC_LED   13
#define ERROR_DUR   1000
#define NUM_SENSORS 8

// -------------------------
// Structure Definitions
// -------------------------
struct HeaterProfile {
  String id;
  uint16_t temps[MAX_HEATER_PROFILE_LENGTH];
  uint16_t durations[MAX_HEATER_PROFILE_LENGTH];
  uint8_t length;
};

struct DutyCycleProfile {
  String id;
  uint8_t numberScanningCycles;
  uint8_t numberSleepingCycles;
};

struct DutyCycleState {
  const DutyCycleProfile *profile;
  bool isScanning;
  uint8_t cyclesLeft;
  unsigned long lastCycleChangeTime;
};

// -------------------------
// Global Variables for Configuration
// -------------------------
extern HeaterProfile cachedHeaterProfiles[NUM_HEATER_PROFILES];
extern DutyCycleProfile cachedDutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
extern SdFat sd;  // Static instance for all SD functions
extern bool configLoaded;

// -------------------------
// Configuration Management Functions
// -------------------------
bool loadConfigFromSD();
bool applyCachedHeaterProfile(Bsec2 &sensor, uint8_t profileIndex);
void applyCachedDutyCycleProfile(DutyCycleState &state, uint8_t profileIndex);
void applyCachedDutyCycleProfileToAll(DutyCycleState dutyStates[], uint8_t numSensors, uint8_t profileIndex);

// -------------------------
// Error Reporting & Utility Functions
// -------------------------
String getBsecErrorMessage(int code);
String getBmeErrorMessage(int code);
void blinkWarningLED(void);
void blinkErrorLED(void);
void reportBsecStatus(Bsec2 bsec);
void reportAllSensorsStatus(Bsec2 sensors[], uint8_t sensorCount);

#endif // BSEC_UTIL_H
