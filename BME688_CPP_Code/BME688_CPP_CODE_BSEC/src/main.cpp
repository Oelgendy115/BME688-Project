#include <bsec2.h>
#include <commMux.h>
#include <bsecUtil.h>

#define NUM_OF_SENS    8
#define PANIC_LED      LED_BUILTIN
#define ERROR_DUR      1000
#define SAMPLE_RATE    BSEC_SAMPLE_RATE_LP

void errLeds(void);
void newDataCallback(const bme68xData data, const bsecOutputs outputs, Bsec2 bsec);

Bsec2 envSensor[NUM_OF_SENS];
commMux communicationSetup[NUM_OF_SENS];
uint8_t bsecMemBlock[NUM_OF_SENS][BSEC_INSTANCE_SIZE];
uint8_t sensor = 0;

// Buttons
#define BUTTON_PIN1 32
#define BUTTON_PIN2 14
#define DEBOUNCE_DELAY 50
bool button1State = false;
bool lastButton1State = false;
bool button2State = false;
bool lastButton2State = false;
unsigned long lastDebounceTime1 = 0;
unsigned long lastDebounceTime2 = 0;
int labelTag = 1;
int heaterProfileIndex = 345;

// Commands
#define CMD_START "START"
#define CMD_STOP "STOP"
#define CMD_GETHEAT "GETHEAT"

// SD Card Definitions
#define SD_PIN_CS 33
#define CONFIG_FILE_NAME "/config.json"

bool dataCollectionStarted = false;
bool stopDataCollection = false;
bool jsonClosed = false;

void loadAndCacheConfig();
void handleSerialCommands(void);
void handleButtonPresses(void);
void newDataCallback(const bme68xData data, const bsecOutputs outputs, Bsec2 bsec);
bool assignHeaterProfileToSensor(uint8_t sensorIndex, uint8_t profileIndex);
bool assignDutyCycleProfileToSensor(uint8_t sensorIndex, uint8_t profileIndex, DutyCycleState dutyStates[]);
void printCache();
void getHeaterProfiles(void);

//-------------------------------------------------------------------------------------------------------------------------------------------------------------
// Serial Command and Button Handling Functions
//-------------------------------------------------------------------------------------------------------------------------------------------------------------

void handleSerialCommands(void) {
  while (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command.equalsIgnoreCase(CMD_START)) {
      dataCollectionStarted = true;
      Serial.println("[INFO] Data collection STARTED.");
    }
    else if (command.equalsIgnoreCase(CMD_STOP)) {
      dataCollectionStarted = false;
      Serial.println("[INFO] STOP command received.");
    }
    else if (command.equalsIgnoreCase(CMD_GETHEAT)) {
      getHeaterProfiles();
    }
    else if (command.equalsIgnoreCase("REPORT")) {  // New command
      reportAllSensorsStatus(envSensor, NUM_OF_SENS);
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
  if (readingB1 != lastButton1State) {
    lastDebounceTime1 = now;
  }
  if ((now - lastDebounceTime1) > DEBOUNCE_DELAY) {
    button1State = readingB1;
  }
  lastButton1State = readingB1;

  bool readingB2 = (digitalRead(BUTTON_PIN2) == LOW);
  if (readingB2 != lastButton2State) {
    lastDebounceTime2 = now;
  }
  if ((now - lastDebounceTime2) > DEBOUNCE_DELAY) {
    button2State = readingB2;
  }
  lastButton2State = readingB2;

  static bool prevBothPressed = false;
  bool bothNow = (button1State && button2State);
  if (bothNow && !prevBothPressed) {
    Serial.println("Both buttons pressed - cycleHeaterProfileAssignment to be implemented");
  }
  else if (!bothNow) {
    static bool prevB1 = false, prevB2 = false;
    bool b1JustPressed = (button1State && !prevB1);
    bool b2JustPressed = (button2State && !prevB2);
    if (b1JustPressed && !button2State) {
      labelTag++;
    }
    else if (b2JustPressed && !button1State) {
      labelTag--;
    }
    prevB1 = button1State;
    prevB2 = button2State;
  }
  prevBothPressed = bothNow;
}

void newDataCallback(const bme68xData data, const bsecOutputs outputs, Bsec2 bsec) {
  if (!outputs.nOutputs) {
    return;
  }
  
  if (!dataCollectionStarted) {
    return;
  }
  
  // For the first sensor (sensor==0), print the labelTag and heaterProfileIndex along with the header.
  if (sensor == 0) {
    Serial.print(String(labelTag) + ",");          // Print the label tag
    Serial.print(String(heaterProfileIndex) + ",");    // Print the heater profile index
  }
  
  // Print sensor index and timestamp.
  Serial.print(String(sensor) + ",");
  Serial.print(String((int)(outputs.output[0].time_stamp / INT64_C(1000000))) + ",");
  
  // Loop through the sensor outputs and print each value.
  for (uint8_t i = 0; i < outputs.nOutputs; i++) {
    const bsecData output = outputs.output[i];
    switch (output.sensor_id) {
      case BSEC_OUTPUT_IAQ:
        Serial.print(String(output.signal) + ",");
        Serial.print(String((int)output.accuracy) + ",");
        break;
      case BSEC_OUTPUT_RAW_TEMPERATURE:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_RAW_PRESSURE:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_RAW_HUMIDITY:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_RAW_GAS:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_STABILIZATION_STATUS:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_RUN_IN_STATUS:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_STATIC_IAQ:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_CO2_EQUIVALENT:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_BREATH_VOC_EQUIVALENT:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_GAS_PERCENTAGE:
        Serial.print(String(output.signal) + ",");
        break;
      case BSEC_OUTPUT_COMPENSATED_GAS:
        Serial.print(String(output.signal) + ",");
        break;
      default:
        break;
    }
  }
  
  if (sensor == 7) {
    Serial.println();
  }
}

//-------------------------------------------------------------------------------------------------------------------------------------------------------------
// Configuration Management Functions
//-------------------------------------------------------------------------------------------------------------------------------------------------------------

// Loads the configuration from the SD card and caches heater and duty cycle profiles.
void loadAndCacheConfig() {
  if (loadConfigFromSD()) {
    Serial.println("[INFO] Configuration loaded and cached successfully.");
  } else {
    Serial.println("[WARN] Failed to load configuration from SD card. Using defaults.");
  }
}

// Applies a cached heater profile (by profileIndex) to the sensor at sensorIndex.
bool assignHeaterProfileToSensor(uint8_t sensorIndex, uint8_t profileIndex) {
  if (sensorIndex >= NUM_OF_SENS) {
    Serial.println("[ERROR] Invalid sensor index for heater profile assignment.");
    return false;
  }
  return applyCachedHeaterProfile(envSensor[sensorIndex], profileIndex);
}

// Applies a cached duty cycle profile (by profileIndex) to a sensor's duty cycle state.
bool assignDutyCycleProfileToSensor(uint8_t sensorIndex, uint8_t profileIndex, DutyCycleState dutyStates[]) {
  if (sensorIndex >= NUM_OF_SENS) {
    Serial.println("[ERROR] Invalid sensor index for duty cycle assignment.");
    return false;
  }
  applyCachedDutyCycleProfile(dutyStates[sensorIndex], profileIndex);
  return true;
}

// Prints all cached heater and duty cycle profiles.
void printCache() {
  Serial.println("---- Cached Heater Profiles ----");
  for (uint8_t i = 0; i < NUM_HEATER_PROFILES; i++) {
    Serial.print("Heater Profile "); Serial.println(i);
    if (cachedHeaterProfiles[i].id.length() == 0) {
      Serial.println("  [Empty]");
    } else {
      Serial.print("  ID: "); Serial.println(cachedHeaterProfiles[i].id);
      Serial.print("  Length: "); Serial.println(cachedHeaterProfiles[i].length);
      for (uint8_t j = 0; j < cachedHeaterProfiles[i].length; j++) {
        Serial.print("    Step "); Serial.print(j);
        Serial.print(": Temp = "); Serial.print(cachedHeaterProfiles[i].temps[j]);
        Serial.print(", Dur = "); Serial.println(cachedHeaterProfiles[i].durations[j]);
      }
    }
  }
  
  Serial.println("---- Cached Duty Cycle Profiles ----");
  for (uint8_t i = 0; i < NUM_DUTY_CYCLE_PROFILES; i++) {
    Serial.print("Duty Cycle Profile "); Serial.println(i);
    if (cachedDutyCycleProfiles[i].id.length() == 0) {
      Serial.println("  [Empty]");
    } else {
      Serial.print("  ID: "); Serial.println(cachedDutyCycleProfiles[i].id);
      Serial.print("  Number Scanning Cycles: "); Serial.println(cachedDutyCycleProfiles[i].numberScanningCycles);
      Serial.print("  Number Sleeping Cycles: "); Serial.println(cachedDutyCycleProfiles[i].numberSleepingCycles);
    }
  }
}

void getHeaterProfiles(void) {
  Serial.println("[INFO] Retrieving heater profiles from sensors via BSEC2...");
  // Use NUM_OF_SENS (instead of NUM_SENSORS) to match your sensor array size.
  for (uint8_t i = 0; i < NUM_OF_SENS; i++) {
    bme68x_heatr_conf heaterConf = envSensor[i].sensor.getHeaterConfiguration();
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

//-------------------------------------------------------------------------------------------------------------------------------------------------------------
void setup(void)
{
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

  Serial.begin(115200);
  commMuxBegin(Wire, SPI);
  pinMode(PANIC_LED, OUTPUT);

  // *** NEW: Set button pins as input with pullups ***
  pinMode(BUTTON_PIN1, INPUT_PULLUP);
  pinMode(BUTTON_PIN2, INPUT_PULLUP);
  
  delay(100);
  while (!Serial) delay(10);

  for (uint8_t i = 0; i < NUM_OF_SENS; i++)
  {
    communicationSetup[i] = commMuxSetConfig(Wire, SPI, i, communicationSetup[i]);
    envSensor[i].allocateMemory(bsecMemBlock[i]);
    if (!envSensor[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &communicationSetup[i]))
    {
      reportBsecStatus(envSensor[i]);
    }
	
    if (SAMPLE_RATE == BSEC_SAMPLE_RATE_ULP)
    {
      envSensor[i].setTemperatureOffset(TEMP_OFFSET_ULP);
    }
    else if (SAMPLE_RATE == BSEC_SAMPLE_RATE_LP)
    {
      envSensor[i].setTemperatureOffset(TEMP_OFFSET_LP);
    }
	
    if (!envSensor[i].updateSubscription(sensorList, ARRAY_LEN(sensorList), SAMPLE_RATE))
    {
      reportBsecStatus (envSensor[i]);
    }

    envSensor[i].attachCallback(newDataCallback);
  }
  loadAndCacheConfig();
  printCache();
  Serial.println("BSEC library version " + 
                 String(envSensor[0].version.major) + "." +
                 String(envSensor[0].version.minor) + "." +
                 String(envSensor[0].version.major_bugfix) + "." +
                 String(envSensor[0].version.minor_bugfix));
}

void loop(void)
{
  handleSerialCommands();
  handleButtonPresses();
  for (sensor = 0; sensor < NUM_OF_SENS; sensor++)
  {
    if (!envSensor[sensor].run())
    {
      reportBsecStatus(envSensor[sensor]);
    }
  }
}


/*
Label,HeaterProfileIndex,Sensor,Timestamp,IAQ,IAQ_accuracy,Raw_Temperature,Raw_Pressure,Raw_Humidity,Raw_Gas,Stabilization_Status,Run_In_Status,Heat_Comp_Temperature,Heat_Comp_Humidity,Static_IAQ,CO2_Equivalent,Breath_VOC_Equivalent,Gas_Percentage,Compensated_Gas
*/