#include "main.h"
#include <memory>  // For std::unique_ptr

// -------------------------
// Global Variables
// -------------------------

// Heater configurations (using the native bme68x_heatr_conf)
HeaterConfig heaterConfigs[4];

// Duty-cycle profile and state
DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
DutyCycleState dutyCycleStates[NUM_SENSORS];

// Sensor configurations loaded dynamically:
SensorConfig sensorConfigs[NUM_SENSORS];
uint8_t numSensorConfigs = 0;

// New: Count of duty cycle profiles loaded from SD card
uint8_t numDutyCycleProfilesLoaded = 0;

Bme68x sensors[NUM_SENSORS];
bme68xData sensorData[NUM_SENSORS] = {0};
commMux communicationSetups[NUM_SENSORS];

int buttonOneValue = 1;
uint8_t currentHeaterProfileIndex = 1;
uint32_t lastLogged = 0;

bool button1State = false;
bool lastButton1State = false;
bool button2State = false;
bool lastButton2State = false;
unsigned long lastDebounceTime1 = 0;
unsigned long lastDebounceTime2 = 0;

bool stopDataCollection = false;
bool jsonClosed = false;
bool dataCollectionStarted = false;

unsigned long lastDataSendTime = 0;
bool firstDataSent = false;
unsigned long dataInterval = 1000; // Default 1 second

// Hardcoded mapping fallback (if dynamic sensor config is not loaded)
static const uint8_t hardcodedHeaterMapping[NUM_SENSORS] = {0, 0, 1, 1, 2, 2, 3, 3};

// A 2D table used for cycling dynamic assignments (if desired)
static const uint8_t heaterProfileAssignmentsTable[4][NUM_SENSORS] = {
    {0, 0, 1, 1, 2, 2, 3, 3},
    {3, 3, 0, 0, 1, 1, 2, 2},
    {2, 2, 3, 3, 0, 0, 1, 1},
    {1, 1, 2, 2, 3, 3, 0, 0}
};

// Create an SdFat object for SD card access
SdFat sd;

// Since bme68x_heatr_conf contains pointer fields for heater arrays,
// we allocate static storage for up to 4 heater profiles.
static uint16_t heaterTemps[4][MAX_HEATER_PROFILE_LENGTH];
static uint16_t heaterDurations[4][MAX_HEATER_PROFILE_LENGTH];

// -------------------------
// Error Reporting Functions
// -------------------------
String getBmeErrorMessage(int code) {
  if (code == BME68X_OK)
    return "BME68X: No error.";
  else if (code == BME68X_E_NULL_PTR)
    return "BME68X: Null pointer error.";
  else if (code == BME68X_E_COM_FAIL)
    return "BME68X: Communication failure.";
  else if (code == BME68X_E_DEV_NOT_FOUND)
    return "BME68X: Device not found.";
  else if (code == BME68X_E_INVALID_LENGTH)
    return "BME68X: Invalid length parameter.";
  else if (code == BME68X_E_SELF_TEST)
    return "BME68X: Self test failure.";
  else if (code > BME68X_OK)
    return "BME68X: Warning (" + String(code) + ").";
  else
    return "BME68X: Unknown error (" + String(code) + ").";
}

void blinkWarningLED() {
  digitalWrite(PANIC_LED, HIGH);
  delay(200);
  digitalWrite(PANIC_LED, LOW);
  delay(2000);
}

void blinkErrorLED() {
  for (int i = 0; i < 2; i++){
    digitalWrite(PANIC_LED, HIGH);
    delay(200);
    digitalWrite(PANIC_LED, LOW);
    delay(200);
  }
  delay(2000);
}

void reportBmeStatus(Bme68x &sensor, uint8_t sensorIndex) {
  int status = sensor.checkStatus();
  Serial.print("Sensor ");
  Serial.print(sensorIndex);
  Serial.print(": ");
  if (status < BME68X_OK) {
    Serial.println(getBmeErrorMessage(status));
    blinkErrorLED();
  }
  else if (status > BME68X_OK) {
    Serial.println(getBmeErrorMessage(status));
    blinkWarningLED();
  }
  else {
    Serial.println("BME68X: OK.");
  }
}

// -------------------------
// Heater Profile Wrapper Function
// -------------------------
// This function wraps the native setHeaterProf() call and returns a bool.
bool setHeaterProfile(uint8_t profileIndex, Bme68x &sensor) {
    if (profileIndex >= 4) {
      Serial.println("ERROR: Invalid heater profile index " + String(profileIndex));
      return false;
    }
    HeaterConfig &hc = heaterConfigs[profileIndex];
    sensor.setHeaterProf(hc.conf.heatr_temp_prof, hc.conf.heatr_dur_prof, hc.conf.profile_len);
    
    // Allow a short delay for the settings to take effect.
    delay(100);
    
    int status = sensor.checkStatus();
    if (status == BME68X_ERROR) {
      Serial.print("ERROR: Setting heater profile failed for sensor. Error code: ");
      Serial.print(status);
      Serial.print(" - ");
      Serial.println(getBmeErrorMessage(status));
      blinkErrorLED();
      return false;
    }
    return true;
  }
  
  
// -------------------------
// Dynamic Configuration Loader (SD Card)
// -------------------------
void loadDynamicConfig() {
  Serial.println("Attempting to load dynamic configuration from SD card...");

  if (!sd.begin(SD_PIN_CS, SPI_EIGHTH_SPEED)) {
    Serial.println("SD card not found. Using hardcoded configuration.");
    return;
  }

  FsFile configFile = sd.open(CONFIG_FILE_NAME, O_RDONLY);
  if (!configFile) {
    Serial.println("Failed to open " CONFIG_FILE_NAME ". Using hardcoded configuration.");
    return;
  }

  size_t size = configFile.size();
  if (size == 0) {
    Serial.println("Config file empty. Using hardcoded configuration.");
    configFile.close();
    return;
  }

  std::unique_ptr<char[]> buf(new char[size]);
  configFile.readBytes(buf.get(), size);
  configFile.close();

  DynamicJsonDocument doc(4096);
  DeserializationError error = deserializeJson(doc, buf.get());
  if (error) {
    Serial.print("Failed to parse config file: ");
    Serial.println(error.f_str());
    return;
  }

  // Print the entire config file for debugging.
  Serial.println("---- SD Card Config File Contents ----");
  serializeJsonPretty(doc, Serial);
  Serial.println("\n---- End of Config File ----");

  JsonObject configBody = doc["configBody"];
  if (configBody.isNull()) {
    Serial.println("configBody not found in JSON. Using hardcoded configuration.");
    return;
  }

  // Load Heater Configurations from JSON
  JsonArray hpArray = configBody["heaterProfiles"].as<JsonArray>();
  if (!hpArray.isNull()) {
    uint8_t index = 0;
    for (JsonObject hp : hpArray) {
      if (index >= 4) break;
      heaterConfigs[index].id = hp["id"].as<String>();
      heaterConfigs[index].conf.heatr_temp_prof = heaterTemps[index];
      heaterConfigs[index].conf.heatr_dur_prof = heaterDurations[index];
      uint8_t step = 0;
      JsonArray tvArray = hp["temperatureTimeVectors"].as<JsonArray>();
      for (JsonArray vec : tvArray) {
        if (step >= MAX_HEATER_PROFILE_LENGTH) break;
        heaterTemps[index][step] = vec[0].as<uint16_t>();
        heaterDurations[index][step] = vec[1].as<uint16_t>();
        step++;
      }
      heaterConfigs[index].conf.profile_len = step;
      heaterConfigs[index].conf.enable = BME68X_ENABLE_HEATER;
      heaterConfigs[index].conf.shared_heatr_dur = MEAS_DUR;
      Serial.print("Loaded heater config: ");
      Serial.println(heaterConfigs[index].id);
      index++;
    }
  } else {
    Serial.println("No heaterProfiles found in config. Using hardcoded heater configuration.");
  }

  // Load Duty Cycle Profiles from JSON
  JsonArray dcpArray = configBody["dutyCycleProfiles"].as<JsonArray>();
  numDutyCycleProfilesLoaded = 0;
  if (!dcpArray.isNull()) {
    uint8_t index = 0;
    for (JsonObject dcp : dcpArray) {
      if (index >= NUM_DUTY_CYCLE_PROFILES) break;
      dutyCycleProfiles[index].id = dcp["id"].as<String>();
      dutyCycleProfiles[index].numberScanningCycles = dcp["numberScanningCycles"].as<uint8_t>();
      dutyCycleProfiles[index].numberSleepingCycles = dcp["numberSleepingCycles"].as<uint8_t>();
      Serial.print("Loaded duty cycle profile: ");
      Serial.println(dutyCycleProfiles[index].id);
      index++;
      numDutyCycleProfilesLoaded++;
    }
  } else {
    Serial.println("No dutyCycleProfiles found in config. Using hardcoded profiles.");
  }

  // Load Sensor Configurations from JSON for dynamic assignment.
  JsonArray sensorCfgArray = configBody["sensorConfigurations"].as<JsonArray>();
  if (!sensorCfgArray.isNull()) {
    numSensorConfigs = 0;
    for (JsonObject sc : sensorCfgArray) {
      if (numSensorConfigs >= NUM_SENSORS) break;
      sensorConfigs[numSensorConfigs].sensorIndex = sc["sensorIndex"].as<uint8_t>();
      sensorConfigs[numSensorConfigs].heaterProfile = sc["heaterProfile"].as<String>();
      sensorConfigs[numSensorConfigs].dutyCycleProfile = sc["dutyCycleProfile"].as<String>();
      Serial.print("Sensor config loaded: Sensor ");
      Serial.print(sensorConfigs[numSensorConfigs].sensorIndex);
      Serial.print(", Heater Profile: ");
      Serial.print(sensorConfigs[numSensorConfigs].heaterProfile);
      Serial.print(", Duty Cycle: ");
      Serial.println(sensorConfigs[numSensorConfigs].dutyCycleProfile);
      numSensorConfigs++;
    }
  } else {
    Serial.println("No sensorConfigurations found in config. Dynamic assignment not available.");
  }
  
  Serial.println("Dynamic configuration loaded from SD card.");
}

// -------------------------
// Fallback Hardcoded Heater Configuration
// -------------------------
void initializeHeaterConfigs() {
  // Heater config 0: heater_354
  heaterConfigs[0].id = "heater_354";
  heaterConfigs[0].conf.heatr_temp_prof = heaterTemps[0];
  heaterConfigs[0].conf.heatr_dur_prof = heaterDurations[0];
  uint16_t temp0[MAX_HEATER_PROFILE_LENGTH] = {320, 100, 100, 100, 200, 200, 200, 320, 320, 320};
  uint16_t dur0[MAX_HEATER_PROFILE_LENGTH]  = {5, 2, 10, 30, 5, 5, 5, 5, 5, 5};
  memcpy(heaterTemps[0], temp0, sizeof(temp0));
  memcpy(heaterDurations[0], dur0, sizeof(dur0));
  heaterConfigs[0].conf.profile_len = 10;
  heaterConfigs[0].conf.enable = BME68X_ENABLE_HEATER;
  heaterConfigs[0].conf.shared_heatr_dur = MEAS_DUR;

  // Heater config 1: heater_301
  heaterConfigs[1].id = "heater_301";
  heaterConfigs[1].conf.heatr_temp_prof = heaterTemps[1];
  heaterConfigs[1].conf.heatr_dur_prof = heaterDurations[1];
  uint16_t temp1[MAX_HEATER_PROFILE_LENGTH] = {100, 100, 200, 200, 200, 200, 320, 320, 320, 320};
  uint16_t dur1[MAX_HEATER_PROFILE_LENGTH]  = {2, 41, 2, 14, 14, 14, 2, 14, 14, 14};
  memcpy(heaterTemps[1], temp1, sizeof(temp1));
  memcpy(heaterDurations[1], dur1, sizeof(dur1));
  heaterConfigs[1].conf.profile_len = 10;
  heaterConfigs[1].conf.enable = BME68X_ENABLE_HEATER;
  heaterConfigs[1].conf.shared_heatr_dur = MEAS_DUR;

  // Heater config 2: heater_411
  heaterConfigs[2].id = "heater_411";
  heaterConfigs[2].conf.heatr_temp_prof = heaterTemps[2];
  heaterConfigs[2].conf.heatr_dur_prof = heaterDurations[2];
  uint16_t temp2[MAX_HEATER_PROFILE_LENGTH] = {100, 320, 170, 320, 240, 240, 240, 320, 320, 320};
  uint16_t dur2[MAX_HEATER_PROFILE_LENGTH]  = {43, 2, 43, 2, 2, 20, 21, 2, 20, 21};
  memcpy(heaterTemps[2], temp2, sizeof(temp2));
  memcpy(heaterDurations[2], dur2, sizeof(dur2));
  heaterConfigs[2].conf.profile_len = 10;
  heaterConfigs[2].conf.enable = BME68X_ENABLE_HEATER;
  heaterConfigs[2].conf.shared_heatr_dur = MEAS_DUR;

  // Heater config 3: heater_501
  heaterConfigs[3].id = "heater_501";
  heaterConfigs[3].conf.heatr_temp_prof = heaterTemps[3];
  heaterConfigs[3].conf.heatr_dur_prof = heaterDurations[3];
  uint16_t temp3[MAX_HEATER_PROFILE_LENGTH] = {210, 265, 265, 320, 320, 265, 210, 155, 100, 155};
  uint16_t dur3[MAX_HEATER_PROFILE_LENGTH]  = {24, 2, 22, 2, 22, 24, 24, 24, 24, 24};
  memcpy(heaterTemps[3], temp3, sizeof(temp3));
  memcpy(heaterDurations[3], dur3, sizeof(dur3));
  heaterConfigs[3].conf.profile_len = 10;
  heaterConfigs[3].conf.enable = BME68X_ENABLE_HEATER;
  heaterConfigs[3].conf.shared_heatr_dur = MEAS_DUR;

  Serial.println("Hardcoded heater configurations initialized.");
}

void initializeDutyCycleProfiles() {
  dutyCycleProfiles[0].id = "duty_1";
  dutyCycleProfiles[0].numberScanningCycles = 1;
  dutyCycleProfiles[0].numberSleepingCycles = 0;
  Serial.println("Hardcoded duty cycle profiles initialized.");
}

void initializeSensorDutyCycles() {
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    dutyCycleStates[i].profile = &dutyCycleProfiles[0];
    dutyCycleStates[i].isScanning = true;
    dutyCycleStates[i].cyclesLeft = dutyCycleProfiles[0].numberScanningCycles;
    dutyCycleStates[i].lastCycleChangeTime = millis();
  }
  Serial.println("Sensor duty cycles initialized (all use 'duty_1').");
}

// -------------------------
// Sensor Assignment Functions
// -------------------------

// Dynamic assignment using sensorConfigs loaded from the SD card.
void assignDynamicSensorConfigs() {
  Serial.println("Assigning sensor configurations dynamically...");
  for (uint8_t i = 0; i < numSensorConfigs; i++) {
    uint8_t sensorIdx = sensorConfigs[i].sensorIndex;
    int heaterIdx = -1;
    for (int j = 0; j < 4; j++) {
      if (heaterConfigs[j].id == sensorConfigs[i].heaterProfile) {
        heaterIdx = j;
        break;
      }
    }
    if (heaterIdx < 0) {
      Serial.print("Dynamic assignment: Heater profile ");
      Serial.print(sensorConfigs[i].heaterProfile);
      Serial.print(" not found for sensor ");
      Serial.println(sensorIdx);
    } else {
      if (!setHeaterProfile(heaterIdx, sensors[sensorIdx])) {
        Serial.print("Dynamic assignment: Failed to assign heater profile for sensor ");
        Serial.println(sensorIdx);
      } else {
        Serial.print("Sensor ");
        Serial.print(sensorIdx);
        Serial.print(" assigned heater profile ");
        Serial.println(heaterConfigs[heaterIdx].id);
      }
    }
    int dutyIdx = -1;
    for (int j = 0; j < numDutyCycleProfilesLoaded; j++) {
      if (dutyCycleProfiles[j].id == sensorConfigs[i].dutyCycleProfile) {
        dutyIdx = j;
        break;
      }
    }
    if (dutyIdx < 0) {
      Serial.print("Dynamic assignment: Duty cycle profile ");
      Serial.print(sensorConfigs[i].dutyCycleProfile);
      Serial.print(" not found for sensor ");
      Serial.println(sensorIdx);
    } else {
      dutyCycleStates[sensorIdx].profile = &dutyCycleProfiles[dutyIdx];
      Serial.print("Sensor ");
      Serial.print(sensorIdx);
      Serial.print(" assigned duty cycle profile ");
      Serial.println(dutyCycleProfiles[dutyIdx].id);
    }
  }
}

// Hardcoded assignment using a static mapping.
void assignHardcodedSensorConfigs() {
  Serial.println("Assigning sensor configurations using hardcoded mapping...");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    uint8_t profileIdx = hardcodedHeaterMapping[i];
    if (!setHeaterProfile(profileIdx, sensors[i])) {
      Serial.print("Hardcoded assignment: Failed to assign heater profile for sensor ");
      Serial.println(i);
      blinkErrorLED();
    } else {
      Serial.print("Sensor ");
      Serial.print(i);
      Serial.print(" assigned hardcoded heater profile index ");
      Serial.println(profileIdx);
    }
    dutyCycleStates[i].profile = &dutyCycleProfiles[0];
  }
}

// -------------------------
// Sensor Profile Assignment for Cycling (Button Press)
// -------------------------
void cycleHeaterProfileAssignment() {
  currentHeaterProfileIndex = (currentHeaterProfileIndex + 1) % 4;
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    uint8_t newProfile = heaterProfileAssignmentsTable[currentHeaterProfileIndex][i];
    if (!setHeaterProfile(newProfile, sensors[i])) {
      Serial.print("ERROR: Failed to set heater profile for sensor ");
      Serial.println(i);
      blinkErrorLED();
    }
    sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
    if (sensors[i].checkStatus() == BME68X_ERROR) {
      Serial.print("ERROR: Error setting operation mode for sensor ");
      Serial.println(i);
      blinkErrorLED();
    }
  }
}

// -------------------------
// Other Functions (getHeaterProfiles, handleSerialCommands, handleButtonPresses, collectAndOutputData, updateDutyCycleStates)
// -------------------------
void getHeaterProfiles() {
  Serial.println("Retrieving heater profiles from sensors...");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    bme68x_heatr_conf heater = sensors[i].getHeaterConfiguration();
    Serial.print("Sensor ");
    Serial.print(i + 1);
    Serial.println(": Heater Profile:");
    for (uint8_t j = 0; j < heater.profile_len; j++) {
      Serial.print("  Step ");
      Serial.print(j + 1);
      Serial.print(": Temp = ");
      Serial.print(heater.heatr_temp_prof[j]);
      Serial.print("°C, Duration = ");
      Serial.print(heater.heatr_dur_prof[j]);
      Serial.println(" ms");
    }
    Serial.print("Heater profile retrieved for sensor ");
    Serial.println(i);
  }
  Serial.println("Heater profiles retrieval complete.");
}

void handleSerialCommands() {
    while (Serial.available()) {
      String command = Serial.readStringUntil('\n');
      command.trim();
      if (command.equalsIgnoreCase(CMD_START)) {
        if (!dataCollectionStarted) {
          dataCollectionStarted = true;
          stopDataCollection = false;
          jsonClosed = false;
          lastDataSendTime = millis();
          firstDataSent = false;
        }
      }
      else if (command.equalsIgnoreCase(CMD_STOP)) {
        if (dataCollectionStarted) {
          stopDataCollection = true;
          dataCollectionStarted = false;
        }
      }
      else if (command.startsWith(CMD_SEC_PREFIX) || command.startsWith("sec_")) {
        String numStr = command.substring(strlen(CMD_SEC_PREFIX));
        numStr.trim();
        unsigned long seconds = numStr.toInt();
        if (seconds > 0) {
          dataInterval = seconds;
          Serial.println("Data interval set to " + String(dataInterval) + " ms");
        } else {
          Serial.println("ERROR: Invalid data interval received.");
        }
      }
      else if (command.equalsIgnoreCase(CMD_GETHEAT)) {
        getHeaterProfiles();
      }
      else if (command.equalsIgnoreCase("GETDUTY")) {
        getDutyCycleProfiles();
      }
      else {
        Serial.println("WARNING: Unknown command received - " + command);
        Serial.println("Available commands: START, STOP, SEC_num (e.g., SEC_5), GETHEAT, GETDUTY");
      }
    }
  }
  
void handleButtonPresses() {
  unsigned long now = millis();
  bool readingButton1 = (digitalRead(BUTTON_PIN1) == LOW);
  if (readingButton1 != lastButton1State) {
    lastDebounceTime1 = now;
  }
  if ((now - lastDebounceTime1) > DEBOUNCE_DELAY) {
    button1State = readingButton1;
  }
  lastButton1State = readingButton1;

  bool readingButton2 = (digitalRead(BUTTON_PIN2) == LOW);
  if (readingButton2 != lastButton2State) {
    lastDebounceTime2 = now;
  }
  if ((now - lastDebounceTime2) > DEBOUNCE_DELAY) {
    button2State = readingButton2;
  }
  lastButton2State = readingButton2;

  static bool prevBothPressed = false;
  bool bothPressedNow = button1State && button2State;
  if (bothPressedNow && !prevBothPressed) {
    cycleHeaterProfileAssignment();
  }
  else if (!bothPressedNow) {
    static bool prevButton1 = false;
    static bool prevButton2 = false;
    bool button1JustPressed = (button1State && !prevButton1);
    bool button2JustPressed = (button2State && !prevButton2);
    if (button1JustPressed && !button2State) {
      buttonOneValue++;
    }
    else if (button2JustPressed && !button1State) {
      buttonOneValue--;
    }
    prevButton1 = button1State;
    prevButton2 = button2State;
  }
  prevBothPressed = bothPressedNow;
}

void collectAndOutputData() {
    // Update the duty cycle state for all sensors.
    updateDutyCycleStates();
    
    uint8_t nFieldsLeft = 0;
    bool newLogdata = false;
    String line = "";
    
    if ((millis() - lastLogged) >= MEAS_DUR) {
      lastLogged = millis();
      // CSV header: TimeStamp(ms), Label_Tag, HeaterProfile_ID
      line += String(lastLogged) + "," + String(buttonOneValue) + "," + String(currentHeaterProfileIndex);
      
      for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        if (dutyCycleStates[i].isScanning) {
          // Active sensor: perform measurement.
          if (sensors[i].fetchData()) {
            nFieldsLeft = sensors[i].getData(sensorData[i]);
            if (sensorData[i].status & BME68X_NEW_DATA_MSK) {
              line += "," + String(sensorData[i].temperature, 2);
              line += "," + String(sensorData[i].pressure, 2);
              line += "," + String(sensorData[i].humidity, 2);
              line += "," + String(sensorData[i].gas_resistance, 2);
              line += "," + String(sensorData[i].res_heat, 2);
              line += "," + String(sensorData[i].gas_index);
              newLogdata = true;
            }
          }
          // Re-trigger measurement for the next active cycle.
          sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
        } else {
          // Sensor is in sleep mode—output placeholders (or skip, if desired)
          line += ",N/A,N/A,N/A,N/A,N/A,N/A";
        }
      }
      
      line += "\r\n";
      if (newLogdata) {
        Serial.print(line);
      }
    }
  }
  
  
// Call this once per measurement cycle to update each sensor's duty cycle.
void updateDutyCycleStates() {
    // For each sensor, decrement the cycle counter.
    // When it reaches zero, toggle between scanning and sleeping,
    // and reset cyclesLeft to the appropriate count from the profile.
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
      DutyCycleState &state = dutyCycleStates[i];
      DutyCycleProfile *p = state.profile;
      if (!p) continue;
      
      // Decrement the counter for every cycle.
      if (state.cyclesLeft > 0) {
        state.cyclesLeft--;
      }
      
      // When the counter reaches zero, toggle the state and reset cycles.
      if (state.cyclesLeft == 0) {
        state.isScanning = !state.isScanning;
        state.cyclesLeft = state.isScanning ? p->numberScanningCycles : p->numberSleepingCycles;
        // Optionally, update lastCycleChangeTime if you need to track time.
        state.lastCycleChangeTime = millis();
      }
    }
  }
  
  

// New function to retrieve and print duty cycle assignments.
void getDutyCycleProfiles() {
    Serial.println("Retrieving duty cycle assignments for sensors...");
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
      Serial.print("Sensor ");
      Serial.print(i);
      Serial.print(": Duty Cycle Profile: ");
      if (dutyCycleStates[i].profile != nullptr) {
        Serial.print(dutyCycleStates[i].profile->id);
        Serial.print(" (Scanning: ");
        Serial.print(dutyCycleStates[i].profile->numberScanningCycles);
        Serial.print(", Sleeping: ");
        Serial.print(dutyCycleStates[i].profile->numberSleepingCycles);
        Serial.println(")");
      } else {
        Serial.println("None assigned.");
      }
    }
    Serial.println("Duty cycle assignments retrieval complete.");
  }
  

// -------------------------
// Setup and Loop
// -------------------------
void setup(void) {
  Serial.begin(115200);
  commMuxBegin(Wire, SPI);
  pinMode(PANIC_LED, OUTPUT);
  pinMode(BUTTON_PIN1, INPUT_PULLUP);
  pinMode(BUTTON_PIN2, INPUT_PULLUP);
  delay(100);
  while (!Serial) { delay(10); }

  // Load dynamic configuration from SD card
  loadDynamicConfig();
  if (heaterConfigs[0].conf.profile_len == 0) {
    initializeHeaterConfigs();
  }
  if (numDutyCycleProfilesLoaded == 0) {
    initializeDutyCycleProfiles();
  }
  initializeSensorDutyCycles();

  // *** Initialize each sensor BEFORE assigning sensor configurations ***
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    communicationSetups[i] = commMuxSetConfig(Wire, SPI, i, communicationSetups[i]);
    sensors[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &communicationSetups[i]);
    reportBmeStatus(sensors[i], i);
    sensors[i].setTPH();
    sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
    if (sensors[i].checkStatus() == BME68X_ERROR) {
      Serial.print("ERROR: Error setting operation mode for sensor ");
      Serial.println(i);
      blinkErrorLED();
    }
  }

  // Now assign sensor configurations:
  if (numSensorConfigs > 0) {
    assignDynamicSensorConfigs();
  } else {
    assignHardcodedSensorConfigs();
  }

  Serial.println("All BME68X sensors initialized");
}
void loop(void) {
  handleSerialCommands();
  handleButtonPresses();
  unsigned long currentTime = millis();
  if ((currentTime - lastDataSendTime) >= dataInterval) {
    lastDataSendTime = currentTime;
    if (dataCollectionStarted) {
      collectAndOutputData();
    }
  }
}


