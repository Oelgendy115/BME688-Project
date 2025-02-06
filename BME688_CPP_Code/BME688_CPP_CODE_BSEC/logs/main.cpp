// main.cpp
#include "main.h"

// Define Heater Profiles
HeaterProfile heaterProfiles[4];

// Sensor and Communication Setup
Bme68x sensors[NUM_SENSORS];
commMux communicationSetups[NUM_SENSORS];

// Heater Profile and Button Management
uint8_t currentHeaterProfileIndex = 0; // Ranges from 0 to 3
uint8_t buttonOneValue = 1;            // Ranges from 1 to 4

// Button States and Debouncing
bool button1State = false;
bool lastButton1State = false;
bool button2State = false;
bool lastButton2State = false;
unsigned long lastDebounceTime1 = 0;
unsigned long lastDebounceTime2 = 0;

// Data Collection Flags
bool stopDataCollection = false;
bool jsonClosed = false;
bool dataCollectionStarted = false;

// Timing Variables
unsigned long lastDataSendTime = 0;
bool firstDataSent = false;
unsigned long dataInterval = 1000; // Default data interval in ms

void getHeaterProfiles();

/**
 * @brief Initializes the heater profiles using predefined configurations
 */
void initializeHeaterProfiles()
{
    heaterProfiles[0] = {
        "heater_354",
        {320, 100, 100, 100, 200, 200, 200, 320, 320, 320},  // Temperatures
        {5, 2, 10, 30, 5, 5, 5, 5, 5, 5},                   // Durations in ms
        10                                                  // Number of steps
    };
    heaterProfiles[1] = {
        "heater_301",
        {100, 100, 200, 200, 200, 200, 320, 320, 320, 320}, // Temperatures
        {2, 41, 2, 14, 14, 14, 2, 14, 14, 14},              // Durations in ms
        10                                                  // Number of steps
    };
    heaterProfiles[2] = {
        "heater_411",
        {100, 320, 170, 320, 240, 240, 240, 320, 320, 320}, // Temperatures
        {43, 2, 43, 2, 2, 20, 21, 2, 20, 21},               // Durations in ms
        10                                                  // Number of steps
    };
    heaterProfiles[3] = {
        "heater_501",
        {210, 265, 265, 320, 320, 265, 210, 155, 100, 155}, // Temperatures
        {24, 2, 22, 2, 22, 24, 24, 24, 24, 24},             // Durations in ms
        10                                                  // Number of steps
    };
}

/**
 * @brief Sets the heater profile for a given sensor
 * @param profileIndex Index of the heater profile (0-3)
 * @param sensor Reference to the sensor
 * @return True if successful, False otherwise
 */
bool setHeaterProfile(uint8_t profileIndex, Bme68x& sensor)
{
    if (profileIndex >= sizeof(heaterProfiles) / sizeof(heaterProfiles[0]))
    {
        Serial.println("Invalid heater profile index");
        return false;
    }

    HeaterProfile& profile = heaterProfiles[profileIndex];
    sensor.setHeaterProf(profile.temps, profile.durations, profile.length);
    if (sensor.checkStatus() == BME68X_ERROR)
    {
        Serial.println("Error setting heater profile.");
        return false;
    }

    return true;
}

/**
 * @brief Initializes the sensor and hardware settings
 */
void setup(void)
{
    Serial.begin(115200);
    commMuxBegin(Wire, SPI);
    pinMode(PANIC_LED, OUTPUT);
    pinMode(BUTTON_PIN1, INPUT_PULLUP);
    pinMode(BUTTON_PIN2, INPUT_PULLUP);
    delay(100);
    while(!Serial) delay(10);

    // Initialize heater profiles
    initializeHeaterProfiles();

    // Initialize sensors
    for (uint8_t i = 0; i < NUM_SENSORS; i++)
    {
        communicationSetups[i] = commMuxSetConfig(Wire, SPI, i, communicationSetups[i]);
        sensors[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &communicationSetups[i]);
        if (sensors[i].checkStatus() != BME68X_OK)
        {
            Serial.println("Failed to initialize BME68X sensor " + String(i));
            errLeds();
        }
        sensors[i].setTPH();
        sensors[i].setSeqSleep(BME68X_ODR_250_MS);
        if (!setHeaterProfile(0, sensors[i]))
        {
            Serial.println("Failed to set heater profile for sensor " + String(i));
            errLeds();
        }
        sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
        if (sensors[i].checkStatus() == BME68X_ERROR)
        {
            Serial.println("Error setting operation mode for sensor " + String(i));
            errLeds();
        }

    }

    Serial.println("All BME68X sensors initialized");
}

/**
 * @brief Handles serial commands (START, STOP, SEC_num, GETHEAT)
 */
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
                String header = "TimeStamp(ms)";
                header += ",Label_Tag,HeaterProfile_ID";
                for (uint8_t i = 0; i < NUM_SENSORS; i++) {
                    header += ",Sensor" + String(i+1) + "_Temperature(deg C)";
                    header += ",Sensor" + String(i+1) + "_Pressure(Pa)";
                    header += ",Sensor" + String(i+1) + "_Humidity(%)";
                    header += ",Sensor" + String(i+1) + "_GasResistance(ohm)";
                    header += ",Sensor" + String(i+1) + "_Status";
                    header += ",Sensor" + String(i+1) + "_GasIndex";
                }
                Serial.println(header);
            }
        }
        else if (command.equalsIgnoreCase(CMD_STOP)) {
            if (dataCollectionStarted) {
                stopDataCollection = true;
                dataCollectionStarted = false;
                // Implement any additional stop procedures here
            }
        }
        else if (command.startsWith(CMD_SEC_PREFIX) || command.startsWith("sec_")) {
            String numStr = command.substring(4);
            numStr.trim();
            unsigned long newInterval = numStr.toInt();
            if (newInterval > 0) {
                dataInterval = newInterval;
                Serial.println("Data interval set to " + String(dataInterval) + " ms");
            }
            else {
                Serial.println("Invalid data interval.");
            }
        }
        else if (command.equalsIgnoreCase(CMD_GETHEAT)) {
            // Handle GETHEAT command
            getHeaterProfiles();
        }
        else {
            Serial.println("Unknown command. Available commands: START, STOP, SEC_num (e.g., SEC_5000), GETHEAT");
        }
    }
}

/**
 * @brief Handles button presses for Button1 and Button2 with debouncing
 */
void handleButtonPresses() {
    unsigned long currentTime = millis();

    // Handle Button1 (Cycle buttonOneValue 1-4)
    bool readingButton1 = digitalRead(BUTTON_PIN1) == LOW; // Active LOW
    if (readingButton1 != lastButton1State) {
        lastDebounceTime1 = currentTime;
    }

    if ((currentTime - lastDebounceTime1) > DEBOUNCE_DELAY) {
        if (readingButton1 && !button1State) {
            // Button1 pressed
            buttonOneValue++;
            if (buttonOneValue > 4) {
                buttonOneValue = 1;
            }
        }
        button1State = readingButton1;
    }
    lastButton1State = readingButton1;

    // Handle Button2 (Cycle heaterProfileIndex 0-3)
    bool readingButton2 = digitalRead(BUTTON_PIN2) == LOW; // Active LOW
    if (readingButton2 != lastButton2State) {
        lastDebounceTime2 = currentTime;
    }

    if ((currentTime - lastDebounceTime2) > DEBOUNCE_DELAY) {
        if (readingButton2 && !button2State) {
            // Button2 pressed
            currentHeaterProfileIndex++;
            if (currentHeaterProfileIndex > 3) {
                currentHeaterProfileIndex = 0;
            }
            for (uint8_t i = 0; i < NUM_SENSORS; i++) {
                if (!setHeaterProfile(currentHeaterProfileIndex, sensors[i])) {
                    Serial.println("Failed to set heater profile for sensor " + String(i));
                    errLeds();
                }
                sensors[i].setOpMode(BME68X_SEQUENTIAL_MODE);
                if (sensors[i].checkStatus() == BME68X_ERROR)
                {
                    Serial.println("Error setting operation mode for sensor " + String(i));
                    errLeds();
                } 
                else if (sensors[i].checkStatus() == BME68X_WARNING)
                {
                    Serial.println("Warning setting operation mode for sensor " + String(i));
                    errLeds();           
                }
            }
        }
        button2State = readingButton2;
    }
    lastButton2State = readingButton2;
}

/**
 * @brief Collects data from all sensors and outputs it in a single line
 */
void collectAndOutputData()
{
    String line = String(millis());
    line += "," + String(buttonOneValue) + "," + String(currentHeaterProfileIndex + 1);
    // Iterate through each sensor
    for (uint8_t i = 0; i < NUM_SENSORS; i++)
    {
        bme68xData data;
        if (sensors[i].fetchData())
        {
            // Attempt to get one data point
            if (sensors[i].getData(data) > 0)
            {
                // Append sensor data to the line
                line += ",";
                line += String(data.temperature, 2);        // Temperature with 2 decimal places
                line += ",";
                line += String(data.pressure, 2);           // Pressure with 2 decimal places
                line += ",";
                line += String(data.humidity, 2);           // Humidity with 2 decimal places
                line += ",";
                line += String(data.gas_resistance, 2);     // Gas resistance with 2 decimal places
                line += ",";
                line += String(data.status, HEX);           // Status in HEX
                line += ",";
                line += String(data.gas_index);
            }
            else
            {
                // If no data, append empty fields
                line += ",,,,,,";
            }
        }
        else
        {
            // If fetchData() failed, append empty fields
            line += ",,,,,,";
        }
    }

    // Print the complete line
    Serial.println(line);
}

/**
 * @brief Main loop function
 */
void loop(void)
{
    // Handle incoming serial commands
    handleSerialCommands();

    // Handle button presses
    handleButtonPresses();

    // If data collection is started, check if it's time to send data
    if (dataCollectionStarted) {
        unsigned long currentTime = millis();
        if (!firstDataSent || (currentTime - lastDataSendTime) >= dataInterval) {
            collectAndOutputData();
            lastDataSendTime = currentTime;
            firstDataSent = true;
        }
    }
}

/**
 * @brief Retrieves and prints the current heater profiles from all sensors
 */
void getHeaterProfiles() {
    Serial.println("Retrieving heater profiles from sensors...");

    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        bme68x_heatr_conf heater = sensors[i].getHeaterConfiguration();
        
        Serial.print("Sensor ");
        Serial.print(i + 1);
        Serial.println(": Heater Profile:");

        for (uint8_t j = 0; j < heater.profile_len; j++) { // Correct loop condition and increment
            Serial.print("  Step ");
            Serial.print(j + 1);
            Serial.print(": Temp = ");
            Serial.print(heater.heatr_temp_prof[j]);
            Serial.print("°C, Duration = ");
            Serial.print(heater.heatr_dur_prof[j]);
            Serial.println(" ms");
        }
    }

    Serial.println("Heater profiles retrieval complete.");
}

/**
 * @brief Handles error LEDs (e.g., panic LED)
 */
void errLeds(void)
{
    while(1)
    {
        digitalWrite(PANIC_LED, HIGH);
        delay(ERROR_DUR);
        digitalWrite(PANIC_LED, LOW);
        delay(ERROR_DUR);
    }
}