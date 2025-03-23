#ifndef MAIN_H
#define MAIN_H

#include <string>
#include <vector>

// Include the BSEC2 library header (adjust the include path if needed)
#include "bsec2.h"  // Example: This header should provide the necessary BSEC2 functions

// Structure representing a single sensor's reading.
struct SensorReading {
    float temperature;
    float pressure;
    float humidity;
    float gasResistance;
    int status;
    int gasIndex;
};

// Structure representing one row (one timestamp) of CSV data.
struct SensorData {
    std::string realTime;
    unsigned long timestamp_ms;
    std::string labelTag;
    int heaterProfileID;
    // Expect 8 sensor readings per row.
    std::vector<SensorReading> sensors;  // Should have exactly 8 elements.
};

// Structure for storing computed outputs from the BSEC2 library.
struct BsecOutput {
    float iaq;
    float co2Equivalent;
    // Add additional computed outputs as needed.
};

class SensorProcessor {
public:
    // Process the CSV file and compute BSEC outputs for each row.
    void processCSVFile(const std::string& filename);
    
private:
    // Parses a CSV line into a SensorData structure.
    bool parseCSVLine(const std::string& line, SensorData& data);
    
    // Calls the BSEC2 library to compute outputs (e.g., IAQ, CO2 equivalent) from sensor data.
    BsecOutput computeBsecOutput(const SensorData& data);
};

#endif // SENSORPROCESSOR_H
