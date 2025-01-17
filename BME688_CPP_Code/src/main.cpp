#include "main.h"

// ------------------------------------------------------------
// Global variables
// ------------------------------------------------------------

// We have 4 heater profiles
HeaterProfile heaterProfiles[4];

// We have 1 duty-cycle profile and a DutyCycleState for each sensor
DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
DutyCycleState dutyCycleStates[NUM_SENSORS];

Bme68x sensors[NUM_SENSORS];
bme68xData sensorData[NUM_SENSORS] = {0};
commMux communicationSetups[NUM_SENSORS];

uint8_t currentHeaterProfileIndex = 0;
uint8_t buttonOneValue = 1;
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

// ------------------------------------------------------------
// setup()
// ------------------------------------------------------------
void setup(void)
{
    Serial.begin(115200);

    commMuxBegin(Wire, SPI);

    pinMode(PANIC_LED, OUTPUT);
    pinMode(BUTTON_PIN1, INPUT_PULLUP);
    pinMode(BUTTON_PIN2, INPUT_PULLUP);

    delay(100);
    while (!Serial) {
        delay(10);
    }

    // Initialize heater profiles 
    initializeHeaterProfiles();

    // Initialize the single duty-cycle profile
    initializeDutyCycleProfiles();

    // Optionally initialize sensors' duty-cycle states
    // (If you actually need scanning vs. sleeping logic)
    initializeSensorDutyCycles();

    // 0->heater_354, 1->heater_354,
    // 2->heater_301, 3->heater_301,
    // 4->heater_411, 5->heater_411,
    // 6->heater_501, 7->heater_501
    uint8_t heaterProfileAssignment[NUM_SENSORS] = {0, 0, 1, 1, 2, 2, 3, 3};

    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        communicationSetups[i] = commMuxSetConfig(Wire, SPI, i, communicationSetups[i]);
        sensors[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &communicationSetups[i]);
        
        if (sensors[i].checkStatus() != BME68X_OK) {
            Serial.println("ERROR: Failed to initialize BME68X sensor " + String(i));
            errLeds();
        }

        // Typical TPH settings if needed
        sensors[i].setTPH();

        // Assign heater profile
        if (!setHeaterProfile(heaterProfileAssignment[i], sensors[i])) {
            Serial.println("ERROR: Failed to assign heater profile for sensor " + String(i));
            errLeds();
        }

        // Put sensor in sequential mode
        sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
        if (sensors[i].checkStatus() == BME68X_ERROR) {
            Serial.println("ERROR: Error setting operation mode for sensor " + String(i));
            errLeds();
        }
    }

    Serial.println("All BME68X sensors initialized");
}

// ------------------------------------------------------------
// loop()
// ------------------------------------------------------------
void loop(void)
{
    handleSerialCommands();
    handleButtonPresses();

    // If you want to implement scanning/sleeping logic, call:
    // updateDutyCycleStates();

    unsigned long currentTime = millis();
    if ((currentTime - lastDataSendTime) >= dataInterval) {
        lastDataSendTime = millis();
        if (dataCollectionStarted) {
            collectAndOutputData();
        }
    }
}

// ------------------------------------------------------------
// handleSerialCommands()
// ------------------------------------------------------------
void handleSerialCommands()
{
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
                // If you want to print CSV header, uncomment:
                /*
                String header = "TimeStamp(ms),Label_Tag,HeaterProfile_ID";
                for (uint8_t i = 0; i < NUM_SENSORS; i++) {
                    header += ",Sensor" + String(i + 1) + "_Temperature(deg C)";
                    header += ",Sensor" + String(i + 1) + "_Pressure(Pa)";
                    header += ",Sensor" + String(i + 1) + "_Humidity(%)";
                    header += ",Sensor" + String(i + 1) + "_GasResistance(ohm)";
                    header += ",Sensor" + String(i + 1) + "_Status";
                    header += ",Sensor" + String(i + 1) + "_GasIndex";
                }
                header += "\r\n";
                Serial.print(header);
                */
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
        else {
            Serial.println("WARNING: Unknown command received - " + command);
            Serial.println("Unknown command. Available commands: START, STOP, SEC_num (e.g., SEC_5), GETHEAT");
        }
    }
}

// ------------------------------------------------------------
// handleButtonPresses()
// ------------------------------------------------------------
void handleButtonPresses()
{
    unsigned long currentTime = millis();
    
    // Handle Button 1
    bool readingButton1 = (digitalRead(BUTTON_PIN1) == LOW);
    if (readingButton1 != lastButton1State) {
        lastDebounceTime1 = currentTime;
    }
    if ((currentTime - lastDebounceTime1) > DEBOUNCE_DELAY) {
        if (readingButton1 && !button1State) {
            // Increments "buttonOneValue" from 1..4, then cycles
            buttonOneValue++;
            if (buttonOneValue > 4) {
                buttonOneValue = 1;
            }
        }
        button1State = readingButton1;
    }
    lastButton1State = readingButton1;

    // Handle Button 2
    bool readingButton2 = (digitalRead(BUTTON_PIN2) == LOW);
    if (readingButton2 != lastButton2State) {
        lastDebounceTime2 = currentTime;
    }
    if ((currentTime - lastDebounceTime2) > DEBOUNCE_DELAY) {
        if (readingButton2 && !button2State) {
            // Example: cycle between the 4 profiles in code
            currentHeaterProfileIndex++;
            if (currentHeaterProfileIndex > 3) {
                currentHeaterProfileIndex = 0;
            }
            for (uint8_t i = 0; i < NUM_SENSORS; i++) {
                if (!setHeaterProfile(currentHeaterProfileIndex, sensors[i])) {
                    Serial.println("ERROR: Failed to set heater profile for sensor " + String(i));
                    errLeds();
                }
                sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
                if (sensors[i].checkStatus() == BME68X_ERROR) {
                    Serial.println("ERROR: Error setting operation mode for sensor " + String(i));
                    errLeds();
                }
            }
        }
        button2State = readingButton2;
    }
    lastButton2State = readingButton2;
}

// ------------------------------------------------------------
// collectAndOutputData()
// ------------------------------------------------------------
void collectAndOutputData()
{
    uint8_t nFieldsLeft = 0;
    bool newLogdata = false;
    String line = "";

    if ((millis() - lastLogged) >= MEAS_DUR) {
        lastLogged = millis();

        // TimeStamp(ms), Label_Tag, HeaterProfile_ID
        line += String(lastLogged) + "," + String(buttonOneValue) + "," + String(currentHeaterProfileIndex);

        for (uint8_t i = 0; i < NUM_SENSORS; i++) {
            if (sensors[i].fetchData()) {
                nFieldsLeft = sensors[i].getData(sensorData[i]);
                if (sensorData[i].status & BME68X_NEW_DATA_MSK) {
                    // Append sensor data to line
                    line += "," +
                        String(sensorData[i].temperature, 2) + "," +
                        String(sensorData[i].pressure, 2) + "," +
                        String(sensorData[i].humidity, 2) + "," +
                        String(sensorData[i].gas_resistance, 2) + "," +
                        String(sensorData[i].status) + "," +
                        String(sensorData[i].gas_index);
                    newLogdata = true;
                }
            }
        }
        line += "\r\n";
        if (newLogdata) {
            Serial.print(line);
        }
    }
}

// ------------------------------------------------------------
// initializeHeaterProfiles()
// ------------------------------------------------------------
void initializeHeaterProfiles()
{
    heaterProfiles[0] = {
        "heater_354",
        // temps array
        {320, 100, 100, 100, 200, 200, 200, 320, 320, 320},
        // durations array
        { 5, 2, 10, 30, 5, 5, 5, 5, 5, 5 },
        10
    };

    heaterProfiles[1] = {
        "heater_301",
        {100, 100, 200, 200, 200, 200, 320, 320, 320, 320},
        { 2, 41, 2, 14, 14, 14, 2, 14, 14, 14 },
        10
    };

    heaterProfiles[2] = {
        "heater_411",
        {100, 320, 170, 320, 240, 240, 240, 320, 320, 320},
        {43,  2,  43,  2,  2,  20,  21,  2,  20,  21},
        10
    };

    heaterProfiles[3] = {
        "heater_501",
        {210, 265, 265, 320, 320, 265, 210, 155, 100, 155},
        {24,  2,   22,  2,   22,  24,  24,  24,  24,  24},
        10
    };

    Serial.println("Heater profiles defined (from JSON).");
}

// ------------------------------------------------------------
// setHeaterProfile()
// ------------------------------------------------------------
bool setHeaterProfile(uint8_t profileIndex, Bme68x& sensor)
{
    if (profileIndex >= (sizeof(heaterProfiles) / sizeof(heaterProfiles[0]))) {
        Serial.println("ERROR: Invalid heater profile index " + String(profileIndex));
        return false;
    }

    HeaterProfile &profile = heaterProfiles[profileIndex];
    sensor.setHeaterProf(profile.temps, profile.durProf, profile.length);
    if (sensor.checkStatus() == BME68X_ERROR) {
        Serial.println("ERROR: Setting heater profile failed for sensor.");
        return false;
    }
    Serial.println("Heater profile " + profile.id + " set successfully (index " + String(profileIndex) + ").");
    return true;
}

// ------------------------------------------------------------
// getHeaterProfiles()
// ------------------------------------------------------------
void getHeaterProfiles()
{
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
        Serial.println("Heater profile retrieved for sensor " + String(i));
    }
    Serial.println("Heater profiles retrieval complete.");
}

// ------------------------------------------------------------
// initializeDutyCycleProfiles()
// ------------------------------------------------------------
void initializeDutyCycleProfiles()
{
    // From JSON: "id": "duty_1", scanning=1, sleeping=0
    dutyCycleProfiles[0].id = "duty_1";
    dutyCycleProfiles[0].numberScanningCycles = 1;
    dutyCycleProfiles[0].numberSleepingCycles = 0;

    Serial.println("Duty-cycle profiles defined (from JSON).");
}

// ------------------------------------------------------------
// initializeSensorDutyCycles()
// ------------------------------------------------------------
void initializeSensorDutyCycles()
{
    // Example: All sensors use the single "duty_1" profile.
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        dutyCycleStates[i].profile = &dutyCycleProfiles[0];
        dutyCycleStates[i].isScanning = true;
        dutyCycleStates[i].cyclesLeft = dutyCycleProfiles[0].numberScanningCycles;
        dutyCycleStates[i].lastCycleChangeTime = millis();
    }
    Serial.println("Sensor duty cycles initialized (all use 'duty_1').");
}

// ------------------------------------------------------------
// updateDutyCycleStates()
// (Optional if you want to actually alternate scanning & sleeping)
// ------------------------------------------------------------
void updateDutyCycleStates()
{
    unsigned long now = millis();
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        DutyCycleState &state = dutyCycleStates[i];
        DutyCycleProfile *p = state.profile;
        if (!p) continue;

        // Example pseudo-logic: if scanning & cyclesLeft=0, switch to sleep
        // if sleeping & cyclesLeft=0, switch to scan, etc.
        // (You can decide how you decrement cyclesLeft, e.g., each data read)
        if (state.isScanning && (state.cyclesLeft == 0)) {
            state.isScanning = false;
            state.cyclesLeft = p->numberSleepingCycles;
            state.lastCycleChangeTime = now;
            // If you had a "sleep" mode:
            // sensors[i].setOpMode(BME68X_SLEEP_MODE);
        }
        else if (!state.isScanning && (state.cyclesLeft == 0)) {
            state.isScanning = true;
            state.cyclesLeft = p->numberScanningCycles;
            state.lastCycleChangeTime = now;
            // sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
        }
    }
}

// ------------------------------------------------------------
// errLeds()
// ------------------------------------------------------------
void errLeds(void)
{
    while (1) {
        digitalWrite(PANIC_LED, HIGH);
        delay(ERROR_DUR);
        digitalWrite(PANIC_LED, LOW);
        delay(ERROR_DUR);
    }
}
