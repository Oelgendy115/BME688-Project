#include "main.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <stdexcept>
#include <cstdlib>  // for std::strtoul, std::atoi

// Note: Include and initialize the BSEC2 library as required by its documentation.
// For example, you might need to initialize the library or set up its state before processing data.

// Process the CSV file by reading each line, parsing it, and computing BSEC outputs.
void SensorProcessor::processCSVFile(const std::string& filename) {
    std::ifstream infile(filename);
    if (!infile.is_open()) {
        std::cerr << "Error: Cannot open file " << filename << std::endl;
        return;
    }
    
    std::string line;
    
    // Read the header line and discard it.
    if (!std::getline(infile, line)) {
        std::cerr << "Error: File is empty or unable to read header" << std::endl;
        return;
    }
    
    // Process each subsequent line in the CSV file.
    while (std::getline(infile, line)) {
        SensorData data;
        if (parseCSVLine(line, data)) {
            BsecOutput output = computeBsecOutput(data);
            // For demonstration purposes, output the computed values.
            std::cout << "Timestamp: " << data.timestamp_ms 
                      << " | IAQ: " << output.iaq 
                      << " | CO2 Equivalent: " << output.co2Equivalent 
                      << std::endl;
        } else {
            std::cerr << "Warning: Failed to parse line: " << line << std::endl;
        }
    }
}

// Parses a CSV line into a SensorData structure.
// This example assumes that the CSV is comma-delimited and that the columns match the provided header.
bool SensorProcessor::parseCSVLine(const std::string& line, SensorData& data) {
    std::istringstream ss(line);
    std::string token;
    std::vector<std::string> tokens;
    
    // Split the line into tokens using comma as the delimiter.
    while (std::getline(ss, token, ',')) {
        tokens.push_back(token);
    }
    
    // Expecting 52 columns: 4 general fields + 8 sensors × 6 fields each = 52.
    if (tokens.size() != 52) {
        std::cerr << "Error: Expected 52 columns but got " << tokens.size() << std::endl;
        return false;
    }
    
    try {
        // Parse the header information.
        data.realTime = tokens[0];
        data.timestamp_ms = std::strtoul(tokens[1].c_str(), nullptr, 10);
        data.labelTag = tokens[2];
        data.heaterProfileID = std::atoi(tokens[3].c_str());
        
        // Reserve space for 8 sensor readings.
        data.sensors.reserve(8);
        int index = 4;  // Starting index for sensor data.
        for (int sensor = 0; sensor < 8; ++sensor) {
            SensorReading reading;
            reading.temperature   = std::stof(tokens[index++]);
            reading.pressure      = std::stof(tokens[index++]);
            reading.humidity      = std::stof(tokens[index++]);
            reading.gasResistance = std::stof(tokens[index++]);
            reading.status        = std::atoi(tokens[index++].c_str());
            reading.gasIndex      = std::atoi(tokens[index++].c_str());
            data.sensors.push_back(reading);
        }
    } catch (const std::exception& ex) {
        std::cerr << "Parsing error: " << ex.what() << std::endl;
        return false;
    }
    
    return true;
}

// Stub function that demonstrates how one might call into the BSEC2 library.
// Replace the contents of this function with the actual calls to your BSEC2 API.
BsecOutput SensorProcessor::computeBsecOutput(const SensorData& data) {
    BsecOutput output;
    
    // In a realistic implementation, you would:
    // 1. Prepare the sensor data in the format expected by the BSEC2 library.
    // 2. Call the appropriate BSEC2 functions (e.g., bsec2_update) to process the input.
    // 3. Retrieve the computed values, such as IAQ and CO2 equivalent.
    
    // For demonstration purposes, here are dummy computations:
    float totalTemperature = 0.0f;
    for (const auto& sensor : data.sensors) {
        totalTemperature += sensor.temperature;
    }
    // A simple average might be used as a placeholder for IAQ.
    output.iaq = totalTemperature / data.sensors.size();
    
    // A dummy CO2 equivalent computation.
    output.co2Equivalent = output.iaq * 10.0f;  // Replace with actual processing logic.
    
    return output;
}
