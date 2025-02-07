#include "main.h"

// ------------------------------------------------------------
// Global variables
// ------------------------------------------------------------

// -- Heater Profiles --
HeaterProfile heaterProfiles[4];

// -- Duty Cycle Profiles (we have 1 in this example) --
DutyCycleProfile dutyCycleProfiles[NUM_DUTY_CYCLE_PROFILES];
DutyCycleState   dutyCycleStates[NUM_SENSORS];

// -- BSEC2 sensor objects --
Bsec2            bsecSensors[NUM_SENSORS];
commMux          communicationSetups[NUM_SENSORS];

// -- Misc button/label usage --
int              buttonOneValue         = 1; 
bool             button1State           = false;
bool             lastButton1State       = false;
bool             button2State           = false;
bool             lastButton2State       = false;
unsigned long    lastDebounceTime1      = 0;
unsigned long    lastDebounceTime2      = 0;

// -- Start/Stop Logic --
bool             stopDataCollection     = false;
bool             jsonClosed             = false;
bool             dataCollectionStarted  = false;
unsigned long    dataInterval           = 1000;  // default 1 second
unsigned long    lastDataSendTime       = 0;
bool             firstDataSent          = false;

// -- Heater cycling --
bool             customHeaterActive     = false;  // <--- NEW: Tracks if user has activated custom profiles
uint8_t          currentHeaterProfileIndex = 0;
uint32_t         lastLogged             = 0;


// Helper table for cycling entire sensor assignments when both buttons are pressed
// The layout is [profile used for sensor0, sensor1, ..., sensor7]
static const uint8_t heaterProfileAssignmentsTable[4][NUM_SENSORS] = {
    {0,0,1,1,2,2,3,3},  
    {3,3,0,0,1,1,2,2},
    {2,2,3,3,0,0,1,1},
    {1,1,2,2,3,3,0,0}
};

// -----------------------------------------------------------------
// setup()
// -----------------------------------------------------------------
void setup(void)
{
    Serial.begin(115200);

    // Start multiplexer (Wire/SPI)
    commMuxBegin(Wire, SPI);

    pinMode(PANIC_LED, OUTPUT);
    pinMode(BUTTON_PIN1, INPUT_PULLUP);
    pinMode(BUTTON_PIN2, INPUT_PULLUP);

    delay(100);
    while (!Serial) {
        delay(10);
    }

    // 1. Initialize local structures
    initializeHeaterProfiles();
    initializeDutyCycleProfiles();
    initializeSensorDutyCycles();

    // 2. Initialize BSEC2 objects, but DO NOT assign custom heater profiles yet
    //    => This means each sensor uses its default built-in heater config.
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        // Initialize commMux config for sensor i
        communicationSetups[i] = commMuxSetConfig(Wire, SPI, i, communicationSetups[i]);
        
        // Begin BSEC2 with MUX read/write/delay
        if (!bsecSensors[i].begin(BME68X_SPI_INTF,
                                  commMuxRead, commMuxWrite,
                                  commMuxDelay, &communicationSetups[i])) {
            Serial.println("ERROR: BSEC2 begin() failed on sensor index " + String(i));
            errLeds();
        }

        // Subscribe to the BSEC outputs you want
        bsecSensor sensorList[] = {
            BSEC_OUTPUT_RAW_TEMPERATURE,
            BSEC_OUTPUT_RAW_HUMIDITY,
            BSEC_OUTPUT_RAW_PRESSURE,
            BSEC_OUTPUT_RAW_GAS,
            BSEC_OUTPUT_IAQ,
            BSEC_OUTPUT_CO2_EQUIVALENT,
            BSEC_OUTPUT_BREATH_VOC_EQUIVALENT
        };
        if (!bsecSensors[i].updateSubscription(sensorList,
                                               sizeof(sensorList)/sizeof(sensorList[0]),
                                               BSEC_SAMPLE_RATE_LP)) {
            Serial.println("ERROR: BSEC2 updateSubscription() failed on sensor index " + String(i));
            errLeds();
        }

        // Simply put the sensor in sequential mode with its default heater config
        bsecSensors[i].sensor.setOpMode(BME68X_SEQUENTIAL_MODE);
        if (bsecSensors[i].sensor.checkStatus() == BME68X_ERROR) {
            Serial.println("ERROR: OpMode set error on sensor index " + String(i));
            errLeds();
        }
    }

    Serial.println("All BME68X sensors (via BSEC2) initialized with default heater settings.\n");
}

// -----------------------------------------------------------------
// loop()
// -----------------------------------------------------------------
void loop(void)
{
    // 1. Handle user serial commands (START, STOP, SEC_ etc.)
    handleSerialCommands();

    // 2. Handle pushbuttons
    handleButtonPresses();

    // 3. Optional: handle scanning vs. sleeping
    //    updateDutyCycleStates();

    // 4. Periodically gather data and output
    unsigned long now = millis();
    if ((now - lastDataSendTime) >= dataInterval) {
        lastDataSendTime = now;
        if (dataCollectionStarted && !stopDataCollection) {
            collectAndOutputData();
        }
    }

    // 5. If requested to stop, finalize JSON or cleanup
    if (stopDataCollection && !jsonClosed) {
        Serial.println("\n[INFO] Data collection stopped. Closing JSON or data stream...");
        jsonClosed             = true;
        dataCollectionStarted  = false;
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
                stopDataCollection    = false;
                jsonClosed            = false;
                lastDataSendTime      = millis();
                firstDataSent         = false;
                Serial.println("[INFO] Data collection STARTED.");
            }
        }
        else if (command.equalsIgnoreCase(CMD_STOP)) {
            if (dataCollectionStarted) {
                stopDataCollection    = true;
                dataCollectionStarted = false;
                Serial.println("[INFO] STOP command received.");
            }
        }
        else if (command.startsWith(CMD_SEC_PREFIX) || command.startsWith("sec_")) {
            String numStr;
            if (command.startsWith(CMD_SEC_PREFIX)) {
                numStr = command.substring(strlen(CMD_SEC_PREFIX));
            } else {
                // if "sec_" prefix used
                numStr = command.substring(4);
            }
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
        else {
            Serial.println("[WARN] Unknown command: " + command);
            Serial.println("Available commands: START, STOP, SEC_[milliseconds], GETHEAT");
        }
    }
}

// ------------------------------------------------------------
// handleButtonPresses()
//    - Debounce
//    - Single-press increments/decrements buttonOneValue
//    - Both pressed => If not yet customHeaterActive, start with
//                     profile 0; otherwise cycle to next row
// ------------------------------------------------------------
void handleButtonPresses()
{
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

    // Both pressed => cycle entire heater layout
    if (bothNow && !prevBothPressed) {
        // If not yet using custom profiles, we'll jump to the first row (profile 0)
        if (!customHeaterActive) {
            customHeaterActive        = true;
            currentHeaterProfileIndex = 0;
        } 
        else {
            // Move to next row in table
            currentHeaterProfileIndex = (currentHeaterProfileIndex + 1) % 4;
        }

        cycleHeaterProfileAssignment();
    }
    else if (!bothNow) {
        // Single-press logic
        static bool prevB1 = false;
        static bool prevB2 = false;
        bool b1JustPressed = (button1State && !prevB1);
        bool b2JustPressed = (button2State && !prevB2);

        if (b1JustPressed && !button2State) {
            buttonOneValue++;
        }
        else if (b2JustPressed && !button1State) {
            buttonOneValue--;
        }

        prevB1 = button1State;
        prevB2 = button2State;
    }

    prevBothPressed = bothNow;
}

// ------------------------------------------------------------
// cycleHeaterProfileAssignment()
//   - Apply the row from heaterProfileAssignmentsTable to each
//     sensor, using setHeaterProfile()
// ------------------------------------------------------------
void cycleHeaterProfileAssignment()
{
    // If for some reason customHeaterActive is false, we do nothing
    if (!customHeaterActive) {
        Serial.println("[INFO] Default heater is still active. No custom assignment done.");
        return;
    }

    // Apply the new row to each sensor
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        uint8_t newProfileIndex = heaterProfileAssignmentsTable[currentHeaterProfileIndex][i];

        if (!setHeaterProfile(newProfileIndex, bsecSensors[i])) {
            Serial.println("ERROR: setHeaterProfile failed for sensor " + String(i));
            errLeds();
        }
        bsecSensors[i].sensor.setOpMode(BME68X_SEQUENTIAL_MODE);
        if (bsecSensors[i].sensor.checkStatus() == BME68X_ERROR) {
            Serial.println("ERROR: setOpMode failed for sensor " + String(i));
            errLeds();
        }
    }

    Serial.println("[INFO] Now using custom heater layout row " + String(currentHeaterProfileIndex));
}

// ------------------------------------------------------------
// collectAndOutputData()
//   - Called periodically; fetch new data from BSEC2
//   - Print in CSV or any desired format
// ------------------------------------------------------------
void collectAndOutputData()
{
    unsigned long now = millis();
    if ((now - lastLogged) < MEAS_DUR) {
        return; // only collect every MEAS_DUR ms
    }
    lastLogged = now;

    // We'll build a CSV row:
    //   timestamp, buttonValue, heaterProfileIdx, <sensor0 data> ... <sensor7 data>
    String row;
    row += String(now);                   // 1) TimeStamp in ms
    row += "," + String(buttonOneValue);  // 2) Label/Tag

    // If we're not using custom profiles yet, let's just note "-1" or something
    int profileVal = (customHeaterActive) ? currentHeaterProfileIndex : -1;
    row += "," + String(profileVal);

    bool anyData = false;

    // For each sensor, run() BSEC2 to get new data
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        if (bsecSensors[i].run()) {
            const bsecOutputs *outputs = bsecSensors[i].getOutputs();
            if (outputs != nullptr) {
                float rawTemp  = NAN;
                float rawHum   = NAN;
                float rawPress = NAN;
                float gasRes   = NAN;
                float iaq      = NAN;

                for (uint8_t j = 0; j < outputs->nOutputs; j++) {
                    switch (outputs->output[j].sensor_id) {
                        case BSEC_OUTPUT_RAW_TEMPERATURE:
                            rawTemp = outputs->output[j].signal;
                            break;
                        case BSEC_OUTPUT_RAW_HUMIDITY:
                            rawHum = outputs->output[j].signal;
                            break;
                        case BSEC_OUTPUT_RAW_PRESSURE:
                            rawPress = outputs->output[j].signal;
                            break;
                        case BSEC_OUTPUT_RAW_GAS:
                            gasRes = outputs->output[j].signal;
                            break;
                        case BSEC_OUTPUT_IAQ:
                            iaq    = outputs->output[j].signal;
                            break;
                        default:
                            break;
                    }
                }

                row += "," + String(rawTemp, 2);
                row += "," + String(rawPress, 2);
                row += "," + String(rawHum, 2);
                row += "," + String(gasRes, 2);
                row += "," + String(iaq, 2);

                anyData = true;
            } else {
                // Possibly check bsecSensors[i].status for errors or warnings
                // If no new data, you might want placeholders:
                row += ",,,,,";
            }
        } else {
            // If run() not producing new data, placeholders or skip
            row += ",,,,,";
        }
    }

    if (anyData) {
        Serial.println(row);
    }
}

// ------------------------------------------------------------
// setHeaterProfile()
//   - Replaces the Bme68x call with bsecSensors[i].sensor.setHeaterProf()
// ------------------------------------------------------------
bool setHeaterProfile(uint8_t profileIndex, Bsec2 &sensor)
{
    if (profileIndex >= (sizeof(heaterProfiles)/sizeof(heaterProfiles[0]))) {
        Serial.println("ERROR: Invalid heater profile index " + String(profileIndex));
        return false;
    }

    HeaterProfile &prof = heaterProfiles[profileIndex];

    // Call Bsec2's underlying Bme68x dev to set the heater profile
    sensor.sensor.setHeaterProf(prof.temps, prof.durProf, prof.length);
    if (sensor.sensor.checkStatus() == BME68X_ERROR) {
        Serial.println("ERROR: setHeaterProf() failed for profile " + prof.id);
        return false;
    }
    return true;
}

// ------------------------------------------------------------
// getHeaterProfiles()
//   - Show the "applied" heater profile from each sensor
// ------------------------------------------------------------
void getHeaterProfiles()
{
    Serial.println("[INFO] Retrieving heater profiles from each sensor via Bsec2->Bme68x...");
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

// ------------------------------------------------------------
// initializeHeaterProfiles()
//   - Example data
// ------------------------------------------------------------
void initializeHeaterProfiles()
{
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
}

// ------------------------------------------------------------
// initializeDutyCycleProfiles()
//   - Single profile "duty_1"
// ------------------------------------------------------------
void initializeDutyCycleProfiles()
{
    dutyCycleProfiles[0].id                   = "duty_1";
    dutyCycleProfiles[0].numberScanningCycles = 1;
    dutyCycleProfiles[0].numberSleepingCycles = 0;

    Serial.println("[INFO] Duty-cycle profiles initialized.");
}

// ------------------------------------------------------------
// initializeSensorDutyCycles()
//   - All sensors share the single duty-cycle profile
// ------------------------------------------------------------
void initializeSensorDutyCycles()
{
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        dutyCycleStates[i].profile             = &dutyCycleProfiles[0];
        dutyCycleStates[i].isScanning          = true;
        dutyCycleStates[i].cyclesLeft          = dutyCycleProfiles[0].numberScanningCycles;
        dutyCycleStates[i].lastCycleChangeTime = millis();
    }
    Serial.println("[INFO] Sensor duty cycles initialized (all 'duty_1').");
}

// ------------------------------------------------------------
// updateDutyCycleStates()
//   - Placeholder if you want to let each sensor do scanning vs. sleeping
// ------------------------------------------------------------
void updateDutyCycleStates()
{
    unsigned long now = millis();
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        DutyCycleState &state = dutyCycleStates[i];
        DutyCycleProfile *p    = state.profile;
        if (!p) continue;

        // If scanning and used up cycles => switch to sleeping
        if (state.isScanning && (state.cyclesLeft == 0)) {
            state.isScanning  = false;
            state.cyclesLeft  = p->numberSleepingCycles;
            state.lastCycleChangeTime = now;
            // Possibly reduce measurement frequency, etc.
        }
        // If sleeping and used up cycles => switch to scanning
        else if (!state.isScanning && (state.cyclesLeft == 0)) {
            state.isScanning  = true;
            state.cyclesLeft  = p->numberScanningCycles;
            state.lastCycleChangeTime = now;
        }
        // else still in the same mode
    }
}

// ------------------------------------------------------------
// errLeds()
//   - Panic LED blink
// ------------------------------------------------------------
void errLeds(void)
{
    while (true) {
        digitalWrite(PANIC_LED, HIGH);
        delay(ERROR_DUR);
        digitalWrite(PANIC_LED, LOW);
        delay(ERROR_DUR);
    }
}
