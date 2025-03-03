#include "main.h"

// -------------------------
// Global Variables
// -------------------------

HeaterProfile heaterProfiles[4];
DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
DutyCycleState dutyCycleStates[NUM_SENSORS];

SensorConfig sensorConfigs[NUM_SENSORS];
uint8_t numSensorConfigs = 0;
uint8_t numDutyCycleProfilesLoaded = 0;

Bsec2 bsecSensors[NUM_SENSORS];
commMux communicationSetups[NUM_SENSORS];
uint8_t bsecMemBlock[NUM_SENSORS][BSEC_INSTANCE_SIZE];

int buttonOneValue = 1;
uint8_t currentHeaterProfileIndex = 0;
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
unsigned long dataInterval = 1000;  // default 1 second
float heaterTimeBase = 1.0;  // Default value (multiplier from config)

// Hardcoded mapping table for cycling heater profile assignments
const uint8_t heaterProfileAssignmentsTable[4][NUM_SENSORS] = {
  {0,0,1,1,2,2,3,3},
  {3,3,0,0,1,1,2,2},
  {2,2,3,3,0,0,1,1},
  {1,1,2,2,3,3,0,0}
};

// SD card object
SdFat sd;

// Global sensor cache for CSV-formatted readings.
String sensorCache[NUM_SENSORS];

// New per-sensor timing array (in ms).
unsigned long lastSensorUpdate[NUM_SENSORS] = {0};


// -------------------------
// Application Functions
// -------------------------
bool setHeaterProfile(uint8_t profileIndex, Bsec2 &sensor) {
  if (profileIndex >= 4) {
    Serial.println("ERROR: Invalid heater profile index " + String(profileIndex));
    return false;
  }
  HeaterProfile &prof = heaterProfiles[profileIndex];
  sensor.sensor.setHeaterProf(prof.temps, prof.durations, prof.length);
  if (sensor.sensor.checkStatus() == BME68X_ERROR) {
    Serial.println("ERROR: setHeaterProf() failed for profile " + prof.id);
    return false;
  }
  return true;
}

void getHeaterProfiles(void) {
  Serial.println("[INFO] Retrieving heater profiles from sensors via BSEC2...");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    bme68x_heatr_conf heaterConf = bsecSensors[i].sensor.getHeaterConfiguration();
    Serial.print("Sensor ");
    Serial.print(i);
    Serial.println(" => Heater Profile:");
    for (uint8_t j = 0; j < heaterConf.profile_len; j++) {
      Serial.print("  Step ");
      Serial.print(j + 1);
      Serial.print(": Temp = ");
      Serial.print(heaterConf.heatr_temp_prof[j]);
      Serial.print(" °C, Dur = ");
      Serial.print(heaterConf.heatr_dur_prof[j]);
      Serial.println(" ms");
    }
  }
  Serial.println("[INFO] Heater profiles retrieval complete.\n");
}

void initializeHeaterProfiles(void) {
  heaterProfiles[0] = {
    "heater_354",
    {320, 100, 100, 100, 200, 200, 200, 320, 320, 320},
    {  5,   2,  10,  30,   5,   5,   5,   5,   5,   5},
    10
  };
  heaterProfiles[1] = {
    "heater_301",
    {100, 100, 200, 200, 200, 200, 320, 320, 320, 320},
    {  2,  41,   2,  14,  14,  14,   2,  14,  14,  14},
    10
  };
  heaterProfiles[2] = {
    "heater_411",
    {100, 320, 170, 320, 240, 240, 240, 320, 320, 320},
    { 43,   2,  43,   2,   2,  20,  21,   2,  20,  21},
    10
  };
  heaterProfiles[3] = {
    "heater_501",
    {210, 265, 265, 320, 320, 265, 210, 155, 100, 155},
    { 24,   2,  22,   2,  22,  24,  24,  24,  24,  24},
    10
  };
  Serial.println("[INFO] Hardcoded heater profiles initialized.");
}

void initializeDutyCycleProfiles(void) {
  dutyCycleProfiles[0].id = "duty_1";
  dutyCycleProfiles[0].numberScanningCycles = 1;
  dutyCycleProfiles[0].numberSleepingCycles = 0;
  Serial.println("[INFO] Duty-cycle profiles initialized.");
}

void initializeSensorDutyCycles(void) {
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    dutyCycleStates[i].profile = &dutyCycleProfiles[0];
    dutyCycleStates[i].isScanning = true;
    dutyCycleStates[i].cyclesLeft = dutyCycleProfiles[0].numberScanningCycles;
    dutyCycleStates[i].lastCycleChangeTime = millis();
  }
  Serial.println("[INFO] Sensor duty cycles initialized (all 'duty_1').");
}

void loadDynamicConfig(void) {
  Serial.println("[INFO] Loading dynamic configuration from SD card...");
  if (!sd.begin(SD_PIN_CS, SPI_EIGHTH_SPEED)) {
    Serial.println("[WARN] SD card not found. Using hardcoded configuration.");
    return;
  }
  FsFile configFile = sd.open(CONFIG_FILE_NAME, O_RDONLY);
  if (!configFile) {
    Serial.println("[WARN] Failed to open " CONFIG_FILE_NAME ". Using hardcoded configuration.");
    return;
  }
  size_t size = configFile.size();
  if (size == 0) {
    Serial.println("[WARN] Config file empty. Using hardcoded configuration.");
    configFile.close();
    return;
  }
  std::unique_ptr<char[]> buf(new char[size]);
  configFile.readBytes(buf.get(), size);
  configFile.close();

  DynamicJsonDocument doc(4096);
  DeserializationError error = deserializeJson(doc, buf.get());
  if (error) {
    Serial.print("[ERROR] Failed to parse config file: ");
    Serial.println(error.f_str());
    return;
  }
  Serial.println("---- SD Card Config File Contents ----");
  serializeJsonPretty(doc, Serial);
  Serial.println("\n---- End of Config File ----");

  JsonObject configBody = doc["configBody"];
  if (configBody.isNull()) {
    Serial.println("[WARN] configBody not found in JSON. Using hardcoded configuration.");
    return;
  }

  // Load Heater Profiles
  JsonArray hpArray = configBody["heaterProfiles"].as<JsonArray>();
  if (!hpArray.isNull()) {
    uint8_t index = 0;
    for (JsonObject hp : hpArray) {
      if (index >= 4) break;
      heaterProfiles[index].id = hp["id"].as<String>();
      uint8_t step = 0;
      JsonArray tvArray = hp["temperatureTimeVectors"].as<JsonArray>();
      for (JsonArray vec : tvArray) {
        if (step >= MAX_HEATER_PROFILE_LENGTH) break;
        heaterProfiles[index].temps[step] = vec[0].as<uint16_t>();
        heaterProfiles[index].durations[step] = vec[1].as<uint16_t>();
        step++;
      }
      heaterProfiles[index].length = step;
      index++;
    }
    Serial.println("[INFO] Heater profiles loaded from SD card.");
  } else {
    Serial.println("[WARN] No heaterProfiles found in config.");
  }

  // Load Duty Cycle Profiles
  JsonArray dcpArray = configBody["dutyCycleProfiles"].as<JsonArray>();
  numDutyCycleProfilesLoaded = 0;
  if (!dcpArray.isNull()) {
    uint8_t index = 0;
    for (JsonObject dcp : dcpArray) {
      if (index >= NUM_DUTY_CYCLE_PROFILES) break;
      dutyCycleProfiles[index].id = dcp["id"].as<String>();
      dutyCycleProfiles[index].numberScanningCycles = dcp["numberScanningCycles"].as<uint8_t>();
      dutyCycleProfiles[index].numberSleepingCycles = dcp["numberSleepingCycles"].as<uint8_t>();
      Serial.print("[INFO] Loaded duty cycle profile: ");
      Serial.println(dutyCycleProfiles[index].id);
      index++;
      numDutyCycleProfilesLoaded++;
    }
  } else {
    Serial.println("[WARN] No dutyCycleProfiles found in config.");
  }

  // Load Sensor Configurations
  JsonArray sensorCfgArray = configBody["sensorConfigurations"].as<JsonArray>();
  if (!sensorCfgArray.isNull()) {
    numSensorConfigs = 0;
    for (JsonObject sc : sensorCfgArray) {
      if (numSensorConfigs >= NUM_SENSORS) break;
      sensorConfigs[numSensorConfigs].sensorIndex = sc["sensorIndex"].as<uint8_t>();
      sensorConfigs[numSensorConfigs].heaterProfile = sc["heaterProfile"].as<String>();
      sensorConfigs[numSensorConfigs].dutyCycleProfile = sc["dutyCycleProfile"].as<String>();
      Serial.print("[INFO] Sensor config loaded: Sensor ");
      Serial.print(sensorConfigs[numSensorConfigs].sensorIndex);
      Serial.print(", Heater Profile: ");
      Serial.print(sensorConfigs[numSensorConfigs].heaterProfile);
      Serial.print(", Duty Cycle: ");
      Serial.println(sensorConfigs[numSensorConfigs].dutyCycleProfile);
      numSensorConfigs++;
    }
  } else {
    Serial.println("[WARN] No sensorConfigurations found in config. Dynamic assignment not available.");
  }
  Serial.println("[INFO] Dynamic configuration loaded from SD card.");
}

void assignDynamicSensorConfigs(void) {
  Serial.println("[INFO] Assigning sensor configurations dynamically...");
  for (uint8_t i = 0; i < numSensorConfigs; i++) {
    uint8_t sensorIdx = sensorConfigs[i].sensorIndex;
    int heaterIdx = -1;
    for (int j = 0; j < 4; j++) {
      if (heaterProfiles[j].id == sensorConfigs[i].heaterProfile) {
        heaterIdx = j;
        break;
      }
    }
    if (heaterIdx < 0) {
      Serial.print("[WARN] Heater profile ");
      Serial.print(sensorConfigs[i].heaterProfile);
      Serial.print(" not found for sensor ");
      Serial.println(sensorIdx);
    } else {
      if (!setHeaterProfile(heaterIdx, bsecSensors[sensorIdx])) {
        Serial.print("[ERROR] Failed to assign heater profile for sensor ");
        Serial.println(sensorIdx);
      } else {
        Serial.print("[INFO] Sensor ");
        Serial.print(sensorIdx);
        Serial.print(" assigned heater profile ");
        Serial.println(heaterProfiles[heaterIdx].id);
      }
    }
    // Duty-cycle assignment
    int dutyIdx = -1;
    for (int j = 0; j < numDutyCycleProfilesLoaded; j++) {
      if (dutyCycleProfiles[j].id == sensorConfigs[i].dutyCycleProfile) {
        dutyIdx = j;
        break;
      }
    }
    if (dutyIdx < 0) {
      Serial.print("[WARN] Duty cycle profile ");
      Serial.print(sensorConfigs[i].dutyCycleProfile);
      Serial.print(" not found for sensor ");
      Serial.println(sensorIdx);
    } else {
      dutyCycleStates[sensorIdx].profile = &dutyCycleProfiles[dutyIdx];
      Serial.print("[INFO] Sensor ");
      Serial.print(sensorIdx);
      Serial.print(" assigned duty cycle profile ");
      Serial.println(dutyCycleProfiles[dutyIdx].id);
    }
  }
}

void assignHardcodedSensorConfigs(void) {
  Serial.println("[INFO] Assigning sensor configurations using hardcoded mapping...");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    uint8_t profileIdx = heaterProfileAssignmentsTable[0][i]; // fallback row
    if (!setHeaterProfile(profileIdx, bsecSensors[i])) {
      Serial.print("[ERROR] Failed to assign heater profile for sensor ");
      Serial.println(i);
      errLeds();
    } else {
      Serial.print("[INFO] Sensor ");
      Serial.print(i);
      Serial.print(" assigned hardcoded heater profile index ");
      Serial.println(profileIdx);
    }
    dutyCycleStates[i].profile = &dutyCycleProfiles[0];
  }
}

// New function to control each sensor’s operating mode based on its duty cycle.
void controlSensorOpModes(void) {
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    if (dutyCycleStates[i].isScanning) {
      bsecSensors[i].sensor.setOpMode(BME68X_SEQUENTIAL_MODE);
    } else {
      bsecSensors[i].sensor.setOpMode(BME68X_SLEEP_MODE);
    }
  }
}

void cycleHeaterProfileAssignment(void) {
  currentHeaterProfileIndex = (currentHeaterProfileIndex + 1) % 4;
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    uint8_t newProfile = heaterProfileAssignmentsTable[currentHeaterProfileIndex][i];
    if (!setHeaterProfile(newProfile, bsecSensors[i])) {
      Serial.print("[ERROR] Failed to set heater profile for sensor ");
      Serial.println(i);
      errLeds();
    }
    bsecSensors[i].sensor.setOpMode(BME68X_SEQUENTIAL_MODE);
    if (bsecSensors[i].sensor.checkStatus() == BME68X_ERROR) {
      Serial.print("[ERROR] Error setting op mode for sensor ");
      Serial.println(i);
      errLeds();
    }
  }
  Serial.println("[INFO] Now using custom heater layout row " + String(currentHeaterProfileIndex));
}

void handleSerialCommands(void) {
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
        Serial.println("[INFO] Data collection STARTED.");
      }
    }
    else if (command.equalsIgnoreCase(CMD_STOP)) {
      if (dataCollectionStarted) {
        stopDataCollection = true;
        dataCollectionStarted = false;
        Serial.println("[INFO] STOP command received.");
      }
    }
    else if (command.startsWith(CMD_SEC_PREFIX) || command.startsWith("sec_")) {
      String numStr = command.substring(strlen(CMD_SEC_PREFIX));
      numStr.trim();
      unsigned long interval = numStr.toInt();
      if (interval > 0) {
        dataInterval = interval;
        Serial.println("[INFO] Data interval set to " + String(dataInterval) + " ms");
      } else {
        Serial.println("[ERROR] Invalid data interval: " + command);
      }
    }
    else if (command.equalsIgnoreCase(CMD_GETHEAT)) {
      getHeaterProfiles();
    }
    else if (command.equalsIgnoreCase(CMD_GETDUTY)) {
      getDutyCycleProfiles();
    }
    else if (command.equalsIgnoreCase("REPORT")) {  // New command
      reportSensorsStatus();
    }
    else {
      Serial.println("[WARN] Unknown command: " + command);
      Serial.println("Available commands: START, STOP, SEC_[ms], GETHEAT, GETDUTY, REPORT");
    }
  }
}

void handleButtonPresses(void) {
  unsigned long now = millis();
  bool readingB1 = (digitalRead(BUTTON_PIN1) == LOW);
  if (readingB1 != lastButton1State) { lastDebounceTime1 = now; }
  if ((now - lastDebounceTime1) > DEBOUNCE_DELAY) { button1State = readingB1; }
  lastButton1State = readingB1;

  bool readingB2 = (digitalRead(BUTTON_PIN2) == LOW);
  if (readingB2 != lastButton2State) { lastDebounceTime2 = now; }
  if ((now - lastDebounceTime2) > DEBOUNCE_DELAY) { button2State = readingB2; }
  lastButton2State = readingB2;

  static bool prevBothPressed = false;
  bool bothNow = (button1State && button2State);
  if (bothNow && !prevBothPressed) {
    cycleHeaterProfileAssignment();
  }
  else if (!bothNow) {
    static bool prevB1 = false, prevB2 = false;
    bool b1JustPressed = (button1State && !prevB1);
    bool b2JustPressed = (button2State && !prevB2);
    if (b1JustPressed && !button2State) { buttonOneValue++; }
    else if (b2JustPressed && !button1State) { buttonOneValue--; }
    prevB1 = button1State; prevB2 = button2State;
  }
  prevBothPressed = bothNow;
}

// New function: updateSensors() is called for each sensor individually,
// but only if the sensor is scanning and the required sample interval (MEAS_DUR) has elapsed.
// Adjusted updateSensors() function
void updateSensors(void) {
  unsigned long now = millis();
  static const uint8_t featuresToPrint[] = {
    BSEC_OUTPUT_RAW_TEMPERATURE,
    BSEC_OUTPUT_RAW_PRESSURE,
    BSEC_OUTPUT_RAW_HUMIDITY,
    BSEC_OUTPUT_RAW_GAS,
    BSEC_OUTPUT_IAQ
  };
  const size_t numFeatures = sizeof(featuresToPrint) / sizeof(featuresToPrint[0]);
  
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    if (dutyCycleStates[i].isScanning) {
      if ((now - lastSensorUpdate[i]) >= MEAS_DUR) {
        lastSensorUpdate[i] = now;
        // Do not force setOpMode here.
        if (bsecSensors[i].run()) {
          const bsecOutputs *outputs = bsecSensors[i].getOutputs();
          if (outputs != nullptr) {
            String sensorData = "";
            for (size_t f = 0; f < numFeatures; f++) {
              bool found = false;
              for (uint8_t j = 0; j < outputs->nOutputs; j++) {
                if (outputs->output[j].sensor_id == featuresToPrint[f]) {
                  sensorData += String(outputs->output[j].signal, 2);
                  found = true;
                  break;
                }
              }
              if (!found) {
                sensorData = "";
                break;
              }
              if (f < numFeatures - 1) {
                sensorData += ",";
              }
            }
            sensorCache[i] = sensorData;
          }
        }
      }
    }
  }
}

// Adjusted collectAndOutputData() uses the cached data.
// It prints a CSV row only when all sensors are scanning and have valid cached readings.
// Adjusted collectAndOutputData() function
void collectAndOutputData(void) {
  if (!dataCollectionStarted) return;
  
  unsigned long now = millis();
  if ((now - lastLogged) < dataInterval) {
    return;
  }
  lastLogged = now;
  
  // Build CSV row regardless of sensor duty state,
  // substituting "NA" for sensors that are sleeping or have no data.
  String row = String(now) + "," + String(buttonOneValue) + "," + String(currentHeaterProfileIndex);
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    row += ",";
    if (dutyCycleStates[i].isScanning && sensorCache[i].length() > 0) {
      row += sensorCache[i];
    } else {
      row += "NA";
    }
  }
  Serial.println(row);
}


// New function to report status of each sensor
void reportSensorsStatus(void) {
  Serial.println("[INFO] Sensor Status Report:");
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    Serial.print("Sensor ");
    Serial.print(i);
    Serial.println(":");
    
    // Report BSEC status
    Serial.print("  BSEC Status: ");
    if (bsecSensors[i].status < BSEC_OK) {
      Serial.println(getBsecErrorMessage(bsecSensors[i].status));
    }
    else if (bsecSensors[i].status > BSEC_OK) {
      Serial.println(getBsecErrorMessage(bsecSensors[i].status));
    }
    else {
      Serial.println("OK");
    }
    
    // Report BME68x sensor status
    Serial.print("  BME68x Status: ");
    if (bsecSensors[i].sensor.status < BME68X_OK) {
      Serial.println(getBmeErrorMessage(bsecSensors[i].sensor.status));
    }
    else if (bsecSensors[i].sensor.status > BME68X_OK) {
      Serial.println(getBmeErrorMessage(bsecSensors[i].sensor.status));
    }
    else {
      Serial.println("OK");
    }
  }
  Serial.println("[INFO] Sensor Status Report Complete.");
}

// Adjusted updateDutyCycleStates() function:
void updateDutyCycleStates(void) {
  unsigned long now = millis();
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    DutyCycleState &state = dutyCycleStates[i];
    DutyCycleProfile *p = state.profile;
    if (!p) continue;
    if (now - state.lastCycleChangeTime >= MEAS_DUR) {
      if (state.cyclesLeft > 0) {
        state.cyclesLeft--;
      }
      if (state.cyclesLeft == 0) {
        state.isScanning = !state.isScanning;
        state.cyclesLeft = state.isScanning ? p->numberScanningCycles : p->numberSleepingCycles;
        state.lastCycleChangeTime = now;
      }
    }
  }
}


void getDutyCycleProfiles(void) {
  Serial.println("[INFO] Retrieving duty cycle assignments...");
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
  Serial.println("[INFO] Duty cycle assignments retrieval complete.");
}

// -------------------------
// setup() and loop()
// -------------------------
void setup(void) {
  Serial.begin(115200);
  commMuxBegin(Wire, SPI);
  pinMode(PANIC_LED, OUTPUT);
  pinMode(BUTTON_PIN1, INPUT_PULLUP);
  pinMode(BUTTON_PIN2, INPUT_PULLUP);
  delay(100);
  while (!Serial) { delay(10); }

  loadDynamicConfig();
  if (heaterProfiles[0].length == 0) {
    initializeHeaterProfiles();
  }
  if (numDutyCycleProfilesLoaded == 0) {
    initializeDutyCycleProfiles();
  }
  initializeSensorDutyCycles();
  
  // Initialize lastSensorUpdate for all sensors.
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    lastSensorUpdate[i] = millis();
  }

  // Define sensor outputs for subscription.
  bsecSensor sensorList[] = {
    BSEC_OUTPUT_IAQ,
    BSEC_OUTPUT_RAW_TEMPERATURE,
    BSEC_OUTPUT_RAW_PRESSURE,
    BSEC_OUTPUT_RAW_HUMIDITY,
    BSEC_OUTPUT_RAW_GAS,
    BSEC_OUTPUT_STABILIZATION_STATUS,
    BSEC_OUTPUT_RUN_IN_STATUS,
    BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE,
    BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY,
    BSEC_OUTPUT_STATIC_IAQ,
    BSEC_OUTPUT_CO2_EQUIVALENT,
    BSEC_OUTPUT_BREATH_VOC_EQUIVALENT,
    BSEC_OUTPUT_GAS_PERCENTAGE,
    BSEC_OUTPUT_COMPENSATED_GAS
  };

  // Initialize each BSEC2 sensor.
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    communicationSetups[i] = commMuxSetConfig(Wire, SPI, i, communicationSetups[i]);
    bsecSensors[i].allocateMemory(bsecMemBlock[i]);
    if (!bsecSensors[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &communicationSetups[i])) {
      Serial.println("Initialization failure for sensor " + String(i) + ":");
      reportBsecStatus(bsecSensors[i]);
    }
    if (!bsecSensors[i].setConfig(bsec_config_selectivity)) {
      Serial.println("Failed to set LP configuration for sensor " + String(i));
    }
    else {
      Serial.println("LP configuration set successfully for sensor " + String(i));
    }
    if (SAMPLE_RATE == BSEC_SAMPLE_RATE_ULP) {
      bsecSensors[i].setTemperatureOffset(TEMP_OFFSET_ULP);
    }
    else if (SAMPLE_RATE == BSEC_SAMPLE_RATE_LP) {
      bsecSensors[i].setTemperatureOffset(TEMP_OFFSET_LP);
    }
    if (!bsecSensors[i].updateSubscription(sensorList, sizeof(sensorList) / sizeof(sensorList[0]), SAMPLE_RATE)) {
      Serial.println("Subscription failure for sensor " + String(i) + ":");
      reportBsecStatus(bsecSensors[i]);
    }
  }
  
  // Assign sensor configurations.
  if (numSensorConfigs > 0) {
    assignDynamicSensorConfigs();
  }
  else {
    assignHardcodedSensorConfigs();
  }
  
  Serial.println("[INFO] All BSEC2 sensors initialized with heater profiles.");
}

// In loop(), after updating duty cycles and controlling sensor modes,
// updateSensors() is called to refresh each sensor’s cached readings at a fixed interval.
// Then, if data collection is active, collectAndOutputData() prints the CSV row.
void loop(void) {
  handleSerialCommands();
  handleButtonPresses();
  updateDutyCycleStates();
  controlSensorOpModes();
  
  // Update sensor readings at a fixed rate.
  updateSensors();
  
  unsigned long currentTime = millis();
  if ((currentTime - lastDataSendTime) >= dataInterval) {
    lastDataSendTime = currentTime;
    if (dataCollectionStarted && !stopDataCollection) {
      collectAndOutputData();
    }
  }
  if (stopDataCollection && !jsonClosed) {
    Serial.println("\n[INFO] Data collection stopped. Closing JSON/data stream...");
    jsonClosed = true;
    dataCollectionStarted = false;
  }
}
