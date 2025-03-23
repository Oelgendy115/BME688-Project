#!/usr/bin/env python3
"""
Installer Script for the BME688 Project
========================================
This script performs the following tasks:
1. Installs project dependencies using requirements.txt (or a default list if not found).
2. Writes a hard-coded PlatformIO configuration file (platformio.ini) into:
       BME68X/BME688_CPP_Code/platformio.ini
   The configuration is selected based on the detected operating system.
3. Optionally builds and uploads the firmware using PlatformIO.
4. Creates desktop launcher scripts for two entry-point programs:
   • Data Collection:   BME68X/BME688_Data_Handler/DataCollection/dataCollection.py
   • Data Classification: BME68X/BME688_Data_Handler/DataClassification/dataClassification.py

Usage:
    Run this script in Terminal from the project root (BME688-Project):
        python3 install.py
"""

import os
import sys
import subprocess
import platform

def run_command(command, cwd=None):
    """Run a shell command and exit if it fails."""
    print("Running:", " ".join(command) if isinstance(command, list) else command)
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        print(f"Error: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

def install_dependencies():
    """Install project dependencies from BME68X/requirements.txt or from a default package list."""
    interpreter = sys.executable
    req_file = os.path.join("BME68X", "requirements.txt")
    if os.path.exists(req_file):
        print("Installing dependencies from requirements.txt...")
        run_command([interpreter, "-m", "pip", "install", "-r", req_file])
    else:
        print("requirements.txt not found. Installing default dependencies...")
        default_packages = ["matplotlib", "pandas", "numpy", "sciki-learn", "joblib", "pyserial"]
        run_command([interpreter, "-m", "pip", "install"] + default_packages)
    print("Dependencies installed.\n")

def write_platformio_ini():
    """
    Write the PlatformIO configuration file into:
        BME68X/BME688_CPP_Code/platformio.ini
    The configuration is chosen based on the operating system.
    """
    target_dir = os.path.join("BME68X", "BME688_CPP_Code")
    os.makedirs(target_dir, exist_ok=True)
    target_file = os.path.join(target_dir, "platformio.ini")
    
    os_type = platform.system()
    if os_type == "Windows":
        content = r""";
; PlatformIO Configuration for Windows
[env:featheresp32]
platform = espressif32
board = featheresp32
framework = arduino
upload_port = COM5
monitor_port = COM5
monitor_speed = 115200
monitor_filters = log2file
monitor_logfile = serial_output.txt
lib_deps =
    bblanchon/ArduinoJson@^7.3.1
    greiman/SdFat@^2.3.0
    boschsensortec/BME68x Sensor library@^1.2.40408

[platformio]
description = WINDOWS MAIN CODE
"""
    elif os_type == "Darwin":
        content = r""";
; PlatformIO Configuration for macOS
[env:featheresp32]
platform = espressif32
board = featheresp32
framework = arduino
upload_port = /dev/cu.usbserial-0231B908
monitor_port = /dev/cu.usbserial-0231B908
monitor_speed = 115200
monitor_filters = log2file
monitor_logfile = serial_output.txt
lib_deps =
    bblanchon/ArduinoJson@^7.3.1
    greiman/SdFat@^2.3.0
    boschsensortec/BME68x Sensor library@^1.2.40408

[platformio]
description = MAC MAIN CODE
"""
    else:
        content = r""";
; PlatformIO Configuration for Linux/Other
[env:featheresp32]
platform = espressif32
board = featheresp32
framework = arduino
upload_port = /dev/ttyUSB0
monitor_port = /dev/ttyUSB0
monitor_speed = 115200
monitor_filters = log2file
monitor_logfile = serial_output.txt
lib_deps =
    bblanchon/ArduinoJson@^7.3.1
    greiman/SdFat@^2.3.0
    boschsensortec/BME68x Sensor library@^1.2.40408

[platformio]
description = LINUX MAIN CODE
"""
    with open(target_file, "w") as f:
        f.write(content)
    print(f"platformio.ini written to {target_file}\n")

def build_and_upload_firmware():
    """
    Optionally build and upload the firmware using PlatformIO.
    Prompts the user for confirmation.
    """
    answer = input("Do you want to build and upload the firmware? (y/n): ").strip().lower()
    if answer == "y":
        firmware_dir = os.path.join("BME68X", "BME688_CPP_Code")
        if os.path.exists(firmware_dir):
            print("Building and uploading firmware...")
            run_command([sys.executable, "-m", "platformio", "run", "--target", "upload"], cwd=firmware_dir)
        else:
            print("Firmware directory not found. Please check the project structure.\n")
    else:
        print("Skipping firmware build/upload.\n")

def create_launcher_scripts():
    """
    Create launcher scripts for data collection and classification.
    The launcher scripts will use absolute paths relative to the project root.
    """
    project_root = os.path.abspath(os.path.dirname(__file__))
    launch_dir = os.path.join(project_root, "launchers")
    os.makedirs(launch_dir, exist_ok=True)
    
    # Construct absolute paths for the entry-point scripts
    data_script = os.path.join(project_root, "BME68X", "BME688_Data_Handler", "DataCollection", "dataCollection.py")
    class_script = os.path.join(project_root, "BME68X", "BME688_Data_Handler", "DataClassification", "dataClassification.py")
    interpreter = "python" if platform.system() == "Windows" else "python3"
    
    if platform.system() == "Windows":
        data_launcher = os.path.join(launch_dir, "launch_data_collection.bat")
        with open(data_launcher, "w") as f:
            f.write(f"@echo off\n{interpreter} \"{data_script}\"\npause\n")
        class_launcher = os.path.join(launch_dir, "launch_classification.bat")
        with open(class_launcher, "w") as f:
            f.write(f"@echo off\n{interpreter} \"{class_script}\"\npause\n")
        print("Launcher batch files created in", launch_dir)
    else:
        data_launcher = os.path.join(launch_dir, "launch_data_collection.command")
        with open(data_launcher, "w") as f:
            f.write(f"#!/bin/bash\n{interpreter} \"{data_script}\"\n")
        os.chmod(data_launcher, 0o755)
        
        class_launcher = os.path.join(launch_dir, "launch_classification.command")
        with open(class_launcher, "w") as f:
            f.write(f"#!/bin/bash\n{interpreter} \"{class_script}\"\n")
        os.chmod(class_launcher, 0o755)
        print("Launcher command files created in", launch_dir)
    print("Launcher scripts creation complete.\n")

def main():
    # Set the working directory to the project root (where this script is located)
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    
    install_dependencies()
    write_platformio_ini()
    build_and_upload_firmware()
    create_launcher_scripts()
    
    print("Installation complete!")
    print("You can run the project by executing the entry-point scripts directly")
    print("or by using the launcher files in the 'launchers' folder.")
    if platform.system() == "Windows":
        print("  (launch_data_collection.bat and launch_classification.bat)")
    else:
        print("  (launch_data_collection.command and launch_classification.command)")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
