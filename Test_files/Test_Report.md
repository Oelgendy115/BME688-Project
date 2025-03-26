# BME68X Project Test Report

**Date:** 25 March 2025

---

## 1. Executive Summary

This report details the test procedures, observations, and outcomes for the BME68X sensor-based odor classification project. The testing aimed to validate sensor baseline stability, dynamic odor transitions, and the overall performance of the firmware and Python-based data processing system. Through a series of controlled experiments involving air and three distinct odor samples (dry tea, regular instant coffee grounds, and Arabian coffee grounds), the project’s ability to classify odors using a RandomForest classifier was evaluated.

---

## 2. Test Setup and Environment

### Hardware and Software Configuration
- **Hardware:**
  - The BME68X sensor board was set up following the project repository instructions.
  - The board was connected to the computer via the appropriate serial port.
  - An SD card containing the configuration file for heater profiles was used to dynamically load sensor settings.

- **Odor Samples:**
  - **Odors Tested:**
    - **Tea:** Prepared using two tea bags (used dry, without water, so only the dry tea material is exposed).
    - **Regular Coffee:** Prepared using 2 teaspoons of regular instant coffee grounds, used dry.
    - **Arabian Coffee:** Prepared using 2 teaspoons of Arabian coffee grounds, used dry.
  - **Sample Isolation:**  
    Each odor sample was sealed in a clean zip lock bag to ensure that no other smells were present and to maintain sample integrity during testing.

- **Software:**
  - The data collection program was launched, and the board was connected using the correct port.
  - A configuration file with the desired heater configurations and duty profiles was sent before starting the data logging.
  - The logging session was initiated with the file name `tea_coffee_test_25_03_2025`.

- **Visual Documentation:**
  - Photographs were taken of the sensor display:
    - Initial photos for the first two sensors.
    - Final photos covering all eight sensors at the end of the initial baseline period.

---

## 3. Test Procedure

### 3.1 Baseline Recording
- **Objective:** Establish a sensor baseline in clean air.
- **Procedure:**
  - Data collection commenced by logging air-only sensor readings for 5 minutes.
  - Baseline readings were captured and visually documented to ensure sensor stability.

### 3.2 Odor Exposure and Transition
- **Odor 1: Tea**
  - The tea odor sample was introduced.
  - Data was recorded continuously until sensor readings stabilized (approximately 25 minutes).
  - After stabilization, the odor sample was removed, and the sensor was exposed to air for 5 minutes to allow readings to return toward baseline.

- **Odor 2: Regular Coffee**
  - After the air exposure period, the regular coffee odor sample was introduced.
  - Sensor data was recorded for another 25 minutes until stabilization was observed.
  - A subsequent 5-minute air exposure period was implemented to record the sensor’s return to baseline.

- **Odor 3: Arabian Coffee (Final Odor)**
  - The final odor sample was introduced, and data was recorded for 25 minutes.
  - An additional 5-minute air exposure period followed before stopping the data logging.

---

## 4. Observations and Results

### Sensor Response and Stabilization
- **Baseline Stability:**  
  The sensors provided consistent readings during the initial 5-minute air baseline period, ensuring a reliable starting point for subsequent tests.

- **Odor Stabilization:**  
  - Each odor sample required approximately 25 minutes for the sensor readings to stabilize.
  - Visual and logged data confirmed that the sensors captured the characteristic response curve for each odor.

- **Air Transition Effects:**  
  - It was observed that when transitioning from an odor to air, the sensor output did not immediately reflect an air baseline.
  - The delayed return to baseline (after odor peaks) affected the classification of “air” as an odor.
  
- **Real-Time Classification:**  
  - The real-time odor classification functionality operated as expected.
  - However, adequate time should be allowed for the sensors to transition from one odor to another to ensure accurate classification during real-time operation.

### System and GUI Performance
- **Firmware and Command Handling:**  
  - All sensor commands (e.g., `START`, `STOP`, `GETHEAT`, and configuration uploads) operated as expected.
  - Button actions effectively changed heater profiles and odor label counters, providing immediate feedback via LED indicators and serial responses.

- **Graphical User Interfaces:**  
  - The Data Logger GUI successfully connected to the board, displayed real-time sensor data, and logged the experiment data accurately.
  - The Model Trainer & Predictor GUI was effective in facilitating data loading, feature extraction, and model training for odor classification.

- **Odor Classification:**  
  - The RandomForest classifier reliably differentiated between the odor samples.
  - Although the system accurately classified odors based on stabilized sensor data, the prolonged recovery time for air signals suggests that model parameters may need adjustment for rapid transition scenarios.

---

## 5. Analysis and Conclusions

- **System Integration:**  
  The combined firmware and Python-based modules successfully managed sensor operations, real-time data logging, and subsequent odor classification. The integrated use of dynamic heater profiles and serial command handling provided a robust testing platform.

- **Sensor Response Characteristics:**  
  The experiments highlighted the sensors' inherent delay in returning to baseline after odor exposure. This phenomenon affects how quickly the system can detect a return to “air” and should be considered in future iterations of the classification model.

- **Real-Time Operation:**  
  The real-time classification worked as expected; however, it is crucial to allow sufficient time for sensor readings to transition from one odor to another, ensuring accurate prediction during rapid odor changes.

- **GUI and User Interaction:**  
  Both the Data Logger GUI and the Model Trainer & Predictor GUI were instrumental in monitoring and analyzing sensor data, confirming the system’s performance under varied odor conditions.

---
