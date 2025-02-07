#include "main.h"

// ------------------------------------------------------------
// Global Variables
// ------------------------------------------------------------

// BSEC2 sensor objects – one per sensor
Bsec2 bsecSensors[NUM_SENSORS];
// Communication setups for each sensor (via your multiplexer)
commMux communicationSetups[NUM_SENSORS];

// -------------------------------------------------------------------------
// Define two example subscription configurations.
// (You can modify these to include any outputs you need.)
//
// In this example one “full” configuration returns raw values plus processed
// outputs (IAQ, CO₂ equivalent, breath VOC) while the “minimal” configuration
// returns only a subset.
// We then duplicate them to give 4 profiles so that the profile-cycling button
// can cycle through several choices.
// -------------------------------------------------------------------------
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

// ------------------------------------------------------------
// Other Global Variables
// ------------------------------------------------------------
int buttonOneValue = 1;
uint8_t currentBsecProfileIndex = 0;
unsigned long lastLogged = 0;
bool dataCollectionStarted = false;
bool stopDataCollection = false;
unsigned long lastDataSendTime = 0;
unsigned long dataInterval = 1000;  // Default data interval in ms

bool button1State = false, lastButton1State = false;
bool button2State = false, lastButton2State = false;
unsigned long lastDebounceTime1 = 0, lastDebounceTime2 = 0;

// ------------------------------------------------------------
// setup()
// ------------------------------------------------------------
void setup(void) {
    Serial.begin(115200);
    Wire.begin();
    commMuxBegin(Wire, SPI);

    pinMode(PANIC_LED, OUTPUT);
    pinMode(BUTTON_PIN1, INPUT_PULLUP);
    pinMode(BUTTON_PIN2, INPUT_PULLUP);

    delay(100);
    while (!Serial) { delay(10); }

    setupSensors();
    Serial.println("All BSEC sensors initialized");
}

// ------------------------------------------------------------
// loop()
// ------------------------------------------------------------
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

// ------------------------------------------------------------
// setupSensors()
// ------------------------------------------------------------
void setupSensors(void) {
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        // Set up the communication configuration for sensor i (using your commMux)
        communicationSetups[i] = commMuxSetConfig(Wire, SPI, i, communicationSetups[i]);

        // Initialize the BSEC2 sensor using the SPI interface.
        int8_t status = bsecSensors[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &communicationSetups[i]);
        if (status != BSEC_OK) {
            Serial.println("ERROR: Failed to initialize BSEC sensor " + String(i));
            errLeds();
        }

        // (Optional) Set temperature offset if needed:
        if (bsecProfiles[currentBsecProfileIndex].sampleRate == BSEC_SAMPLE_RATE_ULP)
            bsecSensors[i].setTemperatureOffset(TEMP_OFFSET_ULP);
        else if (bsecProfiles[currentBsecProfileIndex].sampleRate == BSEC_SAMPLE_RATE_LP)
            bsecSensors[i].setTemperatureOffset(TEMP_OFFSET_LP);

        // Subscribe to outputs using the current profile
        status = bsecSensors[i].updateSubscription(sensorList,8,BSEC_SAMPLE_RATE_CONT);
        if (status != BSEC_OK) {
            Serial.println("ERROR: Failed to update subscription for sensor " + String(i));
            errLeds();
        }
    }
}

// ------------------------------------------------------------
// handleSerialCommands()
// ------------------------------------------------------------
void handleSerialCommands(void) {
    while (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();

        if (command.equalsIgnoreCase(CMD_START)) {
            if (!dataCollectionStarted) {
                dataCollectionStarted = true;
                stopDataCollection = false;
                lastDataSendTime = millis();

                // Print CSV header
                String header = "TimeStamp(ms),Label_Tag,BsecProfile_ID";
                for (uint8_t i = 0; i < NUM_SENSORS; i++) {
                    header += ",Sensor" + String(i + 1) + "_Temperature(deg C)";
                    header += ",Sensor" + String(i + 1) + "_Pressure(Pa)";
                    header += ",Sensor" + String(i + 1) + "_Humidity(%)";
                    header += ",Sensor" + String(i + 1) + "_GasResistance(ohm)";
                    header += ",Sensor" + String(i + 1) + "_IAQ";
                    header += ",Sensor" + String(i + 1) + "_CO2eq";
                    header += ",Sensor" + String(i + 1) + "_BreathVOC";
                }
                header += "\r\n";
                Serial.print(header);
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
            unsigned long sec = numStr.toInt();
            if (sec > 0) {
                dataInterval = sec;
                Serial.println("Data interval set to " + String(dataInterval) + " ms");
            } else {
                Serial.println("ERROR: Invalid data interval received.");
            }
        }
        else if (command.equalsIgnoreCase(CMD_GETHEAT)) {
            // With BSEC the heater management is internal.
            Serial.println("Current BSEC Profile: " + bsecProfiles[currentBsecProfileIndex].id);
        }
        else {
            Serial.println("WARNING: Unknown command received - " + command);
            Serial.println("Available commands: START, STOP, SEC_x (e.g., SEC_5), GETHEAT");
        }
    }
}

// ------------------------------------------------------------
// handleButtonPresses()
// ------------------------------------------------------------
void handleButtonPresses(void) {
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

    // If both buttons become pressed simultaneously, cycle the BSEC profile.
    if (bothPressedNow && !prevBothPressed) {
        cycleBsecProfileAssignment();
    }
    else if (!bothPressedNow) {
        // Single-button press logic (adjust label value)
        static bool prevButton1 = false, prevButton2 = false;
        bool button1JustPressed = (button1State && !prevButton1);
        bool button2JustPressed = (button2State && !prevButton2);

        if (button1JustPressed && !button2State)
            buttonOneValue++;
        else if (button2JustPressed && !button1State)
            buttonOneValue--;

        prevButton1 = button1State;
        prevButton2 = button2State;
    }
    prevBothPressed = bothPressedNow;
}


// ------------------------------------------------------------
// collectAndOutputData()
// ------------------------------------------------------------
void collectAndOutputData(void) {
    String line = "";
    bool newDataAvailable = false;
    unsigned long currentTime = millis();

    // Ensure we only log at least every MEAS_DUR milliseconds.
    if ((currentTime - lastLogged) < MEAS_DUR)
        return;
    lastLogged = currentTime;

    // Build the CSV line: timestamp, label (buttonOneValue), current profile ID.
    line += String(currentTime) + "," + String(buttonOneValue) + "," + bsecProfiles[currentBsecProfileIndex].id;

    // For each sensor, run the BSEC algorithm to update its outputs.
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        bsecData output = bsecSensors[i].getData();
        if (!bsecSensors[i].run()) {
            checkBsecStatus(bsecSensors[i]);
        }
            line += "," + String(o, 2);
            line += "," + String(bsecSensors[i].pressure, 2);
            line += "," + String(bsecSensors[i].humidity, 2);
            line += "," + String(bsecSensors[i].gasResistance, 2);
            line += "," + String(bsecSensors[i].iaq, 2);
            line += "," + String(bsecSensors[i].co2Equivalent, 2);
            line += "," + String(bsecSensors[i].breathVoc, 2);
            newDataAvailable = true;
        else {
            line += ",,,,,,,";
        }
    }
    line += "\r\n";

    if (newDataAvailable)
        Serial.print(line);
}

// ------------------------------------------------------------
// errLeds()
// ------------------------------------------------------------
void errLeds(void) {
    while (1) {
        digitalWrite(PANIC_LED, HIGH);
        delay(ERROR_DUR);
        digitalWrite(PANIC_LED, LOW);
        delay(ERROR_DUR);
    }
}

// ------------------------------------------------------------
// checkBsecStatus()
// ------------------------------------------------------------
void checkBsecStatus(Bsec2 sensor) {
    if (sensor.status < BSEC_OK) {
        Serial.println("BSEC error code: " + String(sensor.status));
        errLeds();
    } else if (sensor.status > BSEC_OK) {
        Serial.println("BSEC warning code: " + String(sensor.status));
    }
    
    if (sensor.sensor.status < BME68X_OK) {
        Serial.println("BME68X error code: " + String(sensor.sensor.status));
        errLeds();
    } else if (sensor.sensor.status > BME68X_OK) {
        Serial.println("BME68X warning code: " + String(sensor.sensor.status));
    }
}
