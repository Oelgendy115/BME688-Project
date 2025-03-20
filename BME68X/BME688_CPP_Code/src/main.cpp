// =========================
// main.cpp
// =========================

#include "main.h"
#include <memory>  // For std::unique_ptr

// =========================
// Global Variables
// =========================

// Heater configurations (wrapper for native bme68x_heatr_conf)
HeaterConfig heaterConfigs[4];

// Duty-cycle profiles and states
DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
DutyCycleState dutyCycleStates[NUM_SENSORS];

// Sensor configurations loaded dynamically from JSON
SensorConfig sensorConfigs[NUM_SENSORS];
uint8_t numSensorConfigs = 0;

// Count of duty cycle profiles loaded from SD card
uint8_t numDutyCycleProfilesLoaded = 0;

// Sensor objects and associated data/communication setups
Bme68x sensors[NUM_SENSORS];
bme68xData sensorData[NUM_SENSORS] = {0};
commMux communicationSetups[NUM_SENSORS];

// Miscellaneous control variables
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
unsigned long dataInterval = 3000; // Default data interval (ms)

// Hardcoded mapping fallback for heater profiles (if dynamic config unavailable)
static const uint8_t hardcodedHeaterMapping[NUM_SENSORS] = {0, 0, 1, 1, 2, 2, 3, 3};

// Table for cycling dynamic heater profile assignments (if desired)
static const uint8_t heaterProfileAssignmentsTable[4][NUM_SENSORS] = {
    {0, 0, 1, 1, 2, 2, 3, 3},
    {3, 3, 0, 0, 1, 1, 2, 2},
    {2, 2, 3, 3, 0, 0, 1, 1},
    {1, 1, 2, 2, 3, 3, 0, 0}
};

// SD card object for configuration access
SdFat sd;

// Static storage for heater profiles (temperature and duration arrays)
static uint16_t heaterTemps[4][MAX_HEATER_PROFILE_LENGTH];
static uint16_t heaterDurations[4][MAX_HEATER_PROFILE_LENGTH];


// =========================
// Error Handling Functions
// =========================

// Returns a descriptive error message for a given BME68x error code.
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

// Blink the panic LED to indicate a warning.
void blinkWarningLED() {
  digitalWrite(PANIC_LED, HIGH);
  delay(200);
  digitalWrite(PANIC_LED, LOW);
  delay(2000);
}

// Blink the panic LED to indicate an error.
void blinkErrorLED() {
  for (int i = 0; i < 2; i++){
    digitalWrite(PANIC_LED, HIGH);
    delay(200);
    digitalWrite(PANIC_LED, LOW);
    delay(200);
  }
  delay(2000);
}

// Check and report sensor status; blink LED for errors/warnings.
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

// Print a complete sensor status report.
void sendSensorStatusReport() {
  Serial.println("---- Sensor Status Report ----");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    int status = sensors[i].checkStatus();
    Serial.print("Sensor ");
    Serial.print(i);
    Serial.print(": ");
    if (status < BME68X_OK) {
      Serial.print("ERROR (");
      Serial.print(status);
      Serial.print("): ");
      Serial.println(getBmeErrorMessage(status));
    } else if (status > BME68X_OK) {
      Serial.print("WARNING (");
      Serial.print(status);
      Serial.print("): ");
      Serial.println(getBmeErrorMessage(status));
    } else {
      Serial.println("OK.");
    }
  }
  Serial.println("---- End of Sensor Report ----");
}


// =========================
// Heater Profile Functions
// =========================

// Wraps the native setHeaterProf() call for a sensor.
// Returns true if the heater profile was set successfully.
bool setHeaterProfile(uint8_t profileIndex, Bme68x &sensor) {
  if (profileIndex >= 4) {
    Serial.println("ERROR: Invalid heater profile index " + String(profileIndex));
    return false;
  }
  HeaterConfig &hc = heaterConfigs[profileIndex];
  sensor.setHeaterProf(hc.conf.heatr_temp_prof, hc.conf.heatr_dur_prof, hc.conf.profile_len);
  
  delay(100);  // Allow the settings to take effect.
  
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


// =========================
// Configuration Loader
// =========================

// Loads configuration from the SD card and parses JSON.
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

  Serial.println("---- SD Card Config File Contents ----");
  serializeJsonPretty(doc, Serial);
  Serial.println("\n---- End of Config File ----");

  JsonObject configBody = doc["configBody"];
  if (configBody.isNull()) {
    Serial.println("configBody not found in JSON. Using hardcoded configuration.");
    return;
  }

  // Load heater configurations
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
      heaterConfigs[index].conf.heatr_dur = MEAS_DUR;
      Serial.print("Loaded heater config: ");
      Serial.println(heaterConfigs[index].id);
      index++;
    }
  } else {
    Serial.println("No heaterProfiles found in config. Using hardcoded heater configuration.");
  }

  // Load duty cycle profiles
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

  // Load sensor configurations
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


// =========================
// Hardcoded Initialization Functions
// =========================

// Initializes hardcoded heater configurations.
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
  heaterConfigs[0].conf.heatr_dur = MEAS_DUR;

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
  heaterConfigs[1].conf.heatr_dur = MEAS_DUR;

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
  heaterConfigs[2].conf.heatr_dur = MEAS_DUR;

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
  heaterConfigs[3].conf.heatr_dur = MEAS_DUR;

  Serial.println("Hardcoded heater configurations initialized.");
}

// Initializes hardcoded duty cycle profiles.
void initializeDutyCycleProfiles() {
  dutyCycleProfiles[0].id = "duty_1";
  dutyCycleProfiles[0].numberScanningCycles = 1;
  dutyCycleProfiles[0].numberSleepingCycles = 0;
  Serial.println("Hardcoded duty cycle profiles initialized.");
}

// Initializes sensor duty cycles.
void initializeSensorDutyCycles() {
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    dutyCycleStates[i].profile = &dutyCycleProfiles[0];
    dutyCycleStates[i].isScanning = true;
    dutyCycleStates[i].cyclesLeft = dutyCycleProfiles[0].numberScanningCycles;
    dutyCycleStates[i].lastCycleChangeTime = millis();
  }
  Serial.println("Sensor duty cycles initialized (all use 'duty_1').");
}


// =========================
// Sensor Assignment Functions
// =========================

// Dynamically assigns sensor configurations from the loaded JSON.
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

// Assigns sensor configurations using hardcoded mapping.
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


// =========================
// Configuration Upload Functions
// =========================

// Reads JSON configuration from the serial monitor and writes it to the SD card.
void uploadConfigFromSerial() {
  Serial.println("Enter JSON config data. End with a single line 'END_CONFIG_UPLOAD'.");
  String jsonConfig = "";
  
  while (true) {
    while (!Serial.available()) { delay(10); }  // Wait for input
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.equalsIgnoreCase("END_CONFIG_UPLOAD")) {
      break;
    }
    jsonConfig += line;
  }
  
  if (jsonConfig.length() == 0) {
    Serial.println("No config data received.");
    return;
  }
  
  if (writeConfigToSD(jsonConfig)) {
    Serial.println("Config file updated successfully.");
    loadDynamicConfig();  // Reload configuration
  } else {
    Serial.println("Failed to update config file.");
  }
}

// Writes configuration data to the SD card.
bool writeConfigToSD(const String &configData) {
  if (!sd.begin(SD_PIN_CS, SPI_EIGHTH_SPEED)) {
    Serial.println("SD card not found.");
    return false;
  }
  
  FsFile configFile = sd.open(CONFIG_FILE_NAME, O_WRITE | O_CREAT | O_TRUNC);
  if (!configFile) {
    Serial.println("Failed to open config file for writing.");
    return false;
  }
  
  size_t bytesWritten = configFile.print(configData);
  configFile.close();
  
  if (bytesWritten != configData.length()) {
    Serial.println("Error writing complete config data.");
    return false;
  }
  return true;
}


// =========================
// Sensor Profile Cycling
// =========================

// Cycles the heater profile assignment for all sensors.
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


// =========================
// Data Collection and Reporting
// =========================

// Retrieves and prints heater and duty cycle profiles for each sensor.
void getHeaterProfiles() {
  Serial.println("Retrieving heater and duty cycle profiles for sensors...");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    // Print heater profile for sensor i.
    bme68x_heatr_conf heater = sensors[i].getHeaterConfiguration();
    Serial.print("Sensor ");
    Serial.print(i);
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
    
    // Print duty cycle profile for sensor i.
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
    
    Serial.println(""); // Blank line between sensors
  }
  Serial.println("Heater and duty cycle profiles retrieval complete.");
}


// Processes serial commands from the serial monitor.
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
    else if (command.startsWith(CMD_MS_PREFIX) || command.startsWith("ms_")) {
      String numStr = command.substring(strlen(CMD_MS_PREFIX));
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
    else if (command.equalsIgnoreCase("START_CONFIG_UPLOAD")) {
      uploadConfigFromSerial();
    }
    else if (command.equalsIgnoreCase("STATUS_REPORT")) {
      sendSensorStatusReport();
    }
    else {
      Serial.println("WARNING: Unknown command received - " + command);
      Serial.println("Available commands: START, STOP, MS_num (e.g., MS_5000), GETHEAT, GETDUTY, START_CONFIG_UPLOAD, STATUS_REPORT");
    }
  }
}

// Processes button inputs for manual control and cycling.
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

// Collects sensor data and outputs it in CSV format.
void collectAndOutputData() {
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
        sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
      } else {
        line += ",N/A,N/A,N/A,N/A,N/A,N/A";
      }
    }
    
    line += "\r\n";
    if (newLogdata) {
      Serial.print(line);
    }
  }
}

// Updates duty cycle states for all sensors.
// If a profile has 0 sleeping cycles, the sensor remains in scanning mode.
void updateDutyCycleStates() {
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    DutyCycleState &state = dutyCycleStates[i];
    DutyCycleProfile *p = state.profile;
    if (!p) continue;
    
    // Remain in scanning mode if no sleeping cycles are defined.
    if (p->numberSleepingCycles == 0) {
      state.isScanning = true;
      state.cyclesLeft = p->numberScanningCycles;
      continue;
    }
    
    if (state.cyclesLeft > 0) {
      state.cyclesLeft--;
    }
    
    if (state.cyclesLeft == 0) {
      state.isScanning = !state.isScanning;
      state.cyclesLeft = state.isScanning ? p->numberScanningCycles : p->numberSleepingCycles;
      state.lastCycleChangeTime = millis();
    }
  }
}

// Retrieves and prints duty cycle assignments for each sensor.
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


// =========================
// Setup and Main Loop
// =========================

void setup(void) {
  Serial.begin(115200);
  commMuxBegin(Wire, SPI);
  pinMode(PANIC_LED, OUTPUT);
  pinMode(BUTTON_PIN1, INPUT_PULLUP);
  pinMode(BUTTON_PIN2, INPUT_PULLUP);
  delay(100);
  while (!Serial) { delay(10); }

  // Load configuration from SD card, or use hardcoded values if unavailable.
  loadDynamicConfig();
  if (heaterConfigs[0].conf.profile_len == 0) {
    initializeHeaterConfigs();
  }
  if (numDutyCycleProfilesLoaded == 0) {
    initializeDutyCycleProfiles();
  }
  initializeSensorDutyCycles();

  // Initialize each sensor.
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

  // Assign sensor configurations.
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


// =========================
// End of main.cpp
// =========================

