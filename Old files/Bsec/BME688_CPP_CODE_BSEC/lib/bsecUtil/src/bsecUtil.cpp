#include "bsecUtil.h"

// -------------------------
// Global Variable Definitions
// -------------------------
HeaterProfile cachedHeaterProfiles[NUM_HEATER_PROFILES];
DutyCycleProfile cachedDutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
SdFat sd;  // Static instance used for all SD functions
bool configLoaded = false;

// -------------------------
// Configuration Management Function Definitions
// -------------------------
bool loadConfigFromSD() {
  Serial.println("[INFO] Loading config file from SD card...");

  if (!sd.begin(SD_PIN_CS, SPI_FULL_SPEED)) {
    Serial.println("[ERROR] SD card initialization failed.");
    return false;
  }

  FsFile configFile = sd.open(CONFIG_FILE_NAME, O_RDONLY);
  if (!configFile) {
    Serial.print("[ERROR] Could not open config file: ");
    Serial.println(CONFIG_FILE_NAME);
    return false;
  }

  size_t size = configFile.size();
  if (size == 0) {
    Serial.println("[ERROR] Config file is empty.");
    configFile.close();
    return false;
  }

  std::unique_ptr<char[]> buf(new char[size]);
  configFile.readBytes(buf.get(), size);
  configFile.close();

  DynamicJsonDocument doc(4096);
  DeserializationError error = deserializeJson(doc, buf.get());
  if (error) {
    Serial.print("[ERROR] Failed to parse config file: ");
    Serial.println(error.f_str());
    return false;
  }

  JsonObject configBody = doc["configBody"];
  if (configBody.isNull()) {
    Serial.println("[ERROR] configBody not found in JSON.");
    return false;
  }

  // --- Load Heater Profiles ---
  JsonArray hpArray = configBody["heaterProfiles"].as<JsonArray>();
  if (!hpArray.isNull()) {
    uint8_t index = 0;
    for (JsonObject hp : hpArray) {
      if (index >= NUM_HEATER_PROFILES) break;
      cachedHeaterProfiles[index].id = hp["id"].as<String>();
      uint8_t step = 0;
      JsonArray tvArray = hp["temperatureTimeVectors"].as<JsonArray>();
      for (JsonArray vec : tvArray) {
        if (step >= MAX_HEATER_PROFILE_LENGTH) break;
        cachedHeaterProfiles[index].temps[step] = vec[0].as<uint16_t>();
        cachedHeaterProfiles[index].durations[step] = vec[1].as<uint16_t>();
        step++;
      }
      cachedHeaterProfiles[index].length = step;
      Serial.print("[INFO] Loaded Heater Profile: ");
      Serial.println(cachedHeaterProfiles[index].id);
      index++;
    }
  } else {
    Serial.println("[WARN] No heaterProfiles found in config.");
  }

  // --- Load Duty Cycle Profiles ---
  JsonArray dcpArray = configBody["dutyCycleProfiles"].as<JsonArray>();
  if (!dcpArray.isNull()) {
    uint8_t index = 0;
    for (JsonObject dcp : dcpArray) {
      if (index >= NUM_DUTY_CYCLE_PROFILES) break;
      cachedDutyCycleProfiles[index].id = dcp["id"].as<String>();
      cachedDutyCycleProfiles[index].numberScanningCycles = dcp["numberScanningCycles"].as<uint8_t>();
      cachedDutyCycleProfiles[index].numberSleepingCycles = dcp["numberSleepingCycles"].as<uint8_t>();
      Serial.print("[INFO] Loaded Duty Cycle Profile: ");
      Serial.println(cachedDutyCycleProfiles[index].id);
      index++;
    }
  } else {
    Serial.println("[WARN] No dutyCycleProfiles found in config.");
  }

  configLoaded = true;
  Serial.println("[INFO] Config file loaded successfully.");
  return true;
}

bool applyCachedHeaterProfile(Bsec2 &sensor, uint8_t profileIndex) {
  if (profileIndex >= NUM_HEATER_PROFILES) {
    Serial.print("[ERROR] Invalid heater profile index: ");
    Serial.println(profileIndex);
    return false;
  }
  HeaterProfile &prof = cachedHeaterProfiles[profileIndex];
  sensor.sensor.setHeaterProf(prof.temps, prof.durations, prof.length);
  if (sensor.sensor.checkStatus() == BME68X_ERROR) {
    Serial.print("[ERROR] setHeaterProf() failed for profile: ");
    Serial.println(prof.id);
    return false;
  }
  Serial.print("[INFO] Applied Heater Profile ");
  Serial.println(prof.id);
  return true;
}

void applyCachedDutyCycleProfile(DutyCycleState &state, uint8_t profileIndex) {
  if (profileIndex >= NUM_DUTY_CYCLE_PROFILES) {
    Serial.print("[ERROR] Invalid duty cycle profile index: ");
    Serial.println(profileIndex);
    return;
  }
  state.profile = &cachedDutyCycleProfiles[profileIndex];
  state.isScanning = true;
  state.cyclesLeft = cachedDutyCycleProfiles[profileIndex].numberScanningCycles;
  state.lastCycleChangeTime = millis();
  Serial.print("[INFO] Applied Duty Cycle Profile ");
  Serial.println(cachedDutyCycleProfiles[profileIndex].id);
}

void applyCachedDutyCycleProfileToAll(DutyCycleState dutyStates[], uint8_t numSensors, uint8_t profileIndex) {
  for (uint8_t i = 0; i < numSensors; i++) {
    applyCachedDutyCycleProfile(dutyStates[i], profileIndex);
  }
}

// -------------------------
// Error Reporting & Utility Function Definitions
// -------------------------
String getBsecErrorMessage(int code) {
  switch (code) {
    case BSEC_OK:
      return "BSEC: No error.";
    case BSEC_E_DOSTEPS_INVALIDINPUT:
      return "BSEC: Invalid input.";
    case BSEC_E_DOSTEPS_VALUELIMITS:
      return "BSEC: Input value exceeds limits.";
    case BSEC_W_DOSTEPS_TSINTRADIFFOUTOFRANGE:
      return "BSEC: Timestamp difference out of range.";
    case BSEC_E_DOSTEPS_DUPLICATEINPUT:
      return "BSEC: Duplicate input sensor IDs.";
    case BSEC_I_DOSTEPS_NOOUTPUTSRETURNABLE:
      return "BSEC: No outputs returnable.";
    case BSEC_W_DOSTEPS_EXCESSOUTPUTS:
      return "BSEC: Not enough memory allocated for outputs.";
    case BSEC_W_DOSTEPS_GASINDEXMISS:
      return "BSEC: Gas index missing.";
    case BSEC_E_SU_WRONGDATARATE:
      return "BSEC: Wrong data rate.";
    case BSEC_E_SU_SAMPLERATELIMITS:
      return "BSEC: Sample rate exceeds limits.";
    case BSEC_E_SU_DUPLICATEGATE:
      return "BSEC: Duplicate output sensor requested.";
    case BSEC_E_SU_INVALIDSAMPLERATE:
      return "BSEC: Invalid sample rate.";
    case BSEC_E_SU_GATECOUNTEXCEEDSARRAY:
      return "BSEC: Gate count exceeds array size.";
    case BSEC_E_SU_SAMPLINTVLINTEGERMULT:
      return "BSEC: Sample interval is not an integer multiple.";
    case BSEC_E_SU_MULTGASSAMPLINTVL:
      return "BSEC: Multiple gas sample intervals.";
    case BSEC_E_SU_HIGHHEATERONDURATION:
      return "BSEC: Heater duration exceeds allowed time.";
    case BSEC_W_SU_UNKNOWNOUTPUTGATE:
      return "BSEC: Unknown output gate.";
    case BSEC_W_SU_MODINNOULP:
      return "BSEC: ULP mode not allowed.";
    case BSEC_I_SU_SUBSCRIBEDOUTPUTGATES:
      return "BSEC: No subscribed outputs.";
    case BSEC_I_SU_GASESTIMATEPRECEDENCE:
      return "BSEC: Gas estimate precedence error.";
    case BSEC_W_SU_SAMPLERATEMISMATCH:
      return "BSEC: Sample rate mismatch.";
    case BSEC_E_PARSE_SECTIONEXCEEDSWORKBUFFER:
      return "BSEC: Work buffer size insufficient for parse section.";
    case BSEC_E_CONFIG_FAIL:
      return "BSEC: Configuration failed.";
    case BSEC_E_CONFIG_VERSIONMISMATCH:
      return "BSEC: Configuration version mismatch.";
    case BSEC_E_CONFIG_FEATUREMISMATCH:
      return "BSEC: Configuration feature mismatch.";
    case BSEC_E_CONFIG_CRCMISMATCH:
      return "BSEC: Configuration CRC mismatch.";
    case BSEC_E_CONFIG_EMPTY:
      return "BSEC: Configuration empty.";
    case BSEC_E_CONFIG_INSUFFICIENTWORKBUFFER:
      return "BSEC: Insufficient work buffer for configuration.";
    case BSEC_E_CONFIG_INVALIDSTRINGSIZE:
      return "BSEC: Invalid configuration string size.";
    case BSEC_E_CONFIG_INSUFFICIENTBUFFER:
      return "BSEC: Insufficient buffer for configuration.";
    case BSEC_E_SET_INVALIDCHANNELIDENTIFIER:
      return "BSEC: Invalid channel identifier.";
    case BSEC_E_SET_INVALIDLENGTH:
      return "BSEC: Invalid length.";
    case BSEC_W_SC_CALL_TIMING_VIOLATION:
      return "BSEC: Sensor control call timing violation.";
    case BSEC_W_SC_MODEXCEEDULPTIMELIMIT:
      return "BSEC: ULP timing limit exceeded.";
    case BSEC_W_SC_MODINSUFFICIENTWAITTIME:
      return "BSEC: Insufficient wait time for ULP mode.";
    default:
      return (code < 0) ? ("BSEC: Unknown error (" + String(code) + ").")
                        : ("BSEC: Warning (" + String(code) + ").");
  }
}

String getBmeErrorMessage(int code) {
  switch (code) {
    case BME68X_OK:
      return "BME68X: No error.";
    case BME68X_E_NULL_PTR:
      return "BME68X: Null pointer error.";
    case BME68X_E_COM_FAIL:
      return "BME68X: Communication failure.";
    case BME68X_E_DEV_NOT_FOUND:
      return "BME68X: Device not found.";
    case BME68X_E_INVALID_LENGTH:
      return "BME68X: Invalid length parameter.";
    case BME68X_E_SELF_TEST:
      return "BME68X: Self test failure.";
    case BME68X_W_NO_NEW_DATA:
      return "BME68X: No new data available.";
    case BME68X_W_DEFINE_SHD_HEATR_DUR:
      return "BME68X: Shared heater duration not defined.";
    case BME68X_W_DEFINE_OP_MODE:
      return "BME68X: Define valid operation mode / Parameter correction info.";
    default:
      return (code < 0) ? ("BME68X: Unknown error (" + String(code) + ").")
                        : ("BME68X: Warning (" + String(code) + ").");
  }
}

void blinkWarningLED(void) {
  digitalWrite(PANIC_LED, HIGH);
  delay(200);
  digitalWrite(PANIC_LED, LOW);
  delay(2000);
}

void blinkErrorLED(void) {
  for (int i = 0; i < 2; i++) {
    digitalWrite(PANIC_LED, HIGH);
    delay(200);
    digitalWrite(PANIC_LED, LOW);
    delay(200);
  }
  delay(2000);
}

void reportBsecStatus(Bsec2 bsec) {
  if (bsec.status < BSEC_OK) {
    Serial.println(getBsecErrorMessage(bsec.status));
    blinkErrorLED();
  } else if (bsec.status > BSEC_OK) {
    Serial.println(getBsecErrorMessage(bsec.status));
    blinkWarningLED();
  } else {
    Serial.println("BSEC: OK.");
  }
  if (bsec.sensor.status < BME68X_OK) {
    Serial.println(getBmeErrorMessage(bsec.sensor.status));
    blinkErrorLED();
  } else if (bsec.sensor.status > BME68X_OK) {
    Serial.println(getBmeErrorMessage(bsec.sensor.status));
    blinkWarningLED();
  } else {
    Serial.println("BME68X: OK.");
  }
}

void reportAllSensorsStatus(Bsec2 sensors[], uint8_t sensorCount) {
  Serial.println("[INFO] Sensor Status Report:");
  for (uint8_t i = 0; i < sensorCount; i++) {
    Serial.print("Sensor ");
    Serial.print(i);
    Serial.println(":");
    
    Serial.print("  BSEC Status: ");
    if (sensors[i].status < BSEC_OK) {
      Serial.println(getBsecErrorMessage(sensors[i].status));
    } else if (sensors[i].status > BSEC_OK) {
      Serial.println(getBsecErrorMessage(sensors[i].status));
    } else {
      Serial.println("OK");
    }
    
    Serial.print("  BME68x Status: ");
    if (sensors[i].sensor.status < BME68X_OK) {
      Serial.println(getBmeErrorMessage(sensors[i].sensor.status));
    } else if (sensors[i].sensor.status > BME68X_OK) {
      Serial.println(getBmeErrorMessage(sensors[i].sensor.status));
    } else {
      Serial.println("OK");
    }
  }
  Serial.println("[INFO] Sensor Status Report Complete.");
}
