#!/usr/bin/env python3
"""
Installer Script for the BME688 Project

This script performs the following tasks:
1. Creates a Python virtual environment (if not already present) in the current "BME68X" folder.
2. Upgrades pip and installs project dependencies using requirements.txt 
   (or a default package list if requirements.txt is not found).
3. Writes a hard-coded PlatformIO configuration file (platformio.ini)
   into the firmware directory:
       BME68X/BME688_CPP_Code/platformio.ini
   The configuration is based on the detected operating system.
4. Optionally builds and uploads the firmware using PlatformIO.
5. Creates desktop launcher scripts for two entry-point programs:
   • Data Collection: 
       BME68X/BME688_Data_Handler/DataCollection/dataCollection.py
   • Data Classification:
       BME68X/BME688_Data_Handler/DataClassification/dataClassification.py

After running this installer, users can either activate the virtual environment manually
or double-click one of the launcher files (located in the "launchers" folder) to run the programs.

Usage:
    • For macOS/Linux:
          Open Terminal, navigate to the BME68X folder, and run:
              python3 install.py
          Or, if file associations are configured, simply double-click install.py.
    • For Windows:
          Open Command Prompt (or PowerShell), navigate to the BME68X folder, and run:
              python install.py

Packaging as an Executable:
    To package this installer as a standalone executable (so non-technical users can simply double-click it),
    you can use PyInstaller. For example:
        pip install pyinstaller
        pyinstaller --onefile install.py
    The resulting executable (found in the "dist" folder) can then be provided along with your repository.
    
NOTE:
    • Ensure that your repository structure matches the paths used in this script:
         - Firmware directory: BME68X/BME688_CPP_Code
         - Data handler entry-points:
             BME68X/BME688_Data_Handler/DataCollection/dataCollection.py
             BME68X/BME688_Data_Handler/DataClassification/dataClassification.py
    • Review and update PlatformIO settings (e.g. upload_port) in the script if necessary.
"""

import os
import sys
import subprocess
import platform
import shutil

def run_command(cmd, shell=False, cwd=None):
    """
    Executes a shell command. If the command fails (non-zero exit code),
    the script prints an error message and exits.
    """
    print("Running command:", " ".join(cmd) if isinstance(cmd, list) else cmd)
    result = subprocess.run(cmd, shell=shell, cwd=cwd)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

def create_virtualenv(venv_dir):
    """
    Creates a Python virtual environment in venv_dir if it does not already exist.
    """
    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        run_command([sys.executable, "-m", "venv", venv_dir])
    else:
        print("Virtual environment already exists.")

def write_platformio_ini():
    """
    Writes a hard-coded PlatformIO configuration file (platformio.ini)
    into the firmware directory based on the detected operating system.
    
    The firmware directory is assumed to be:
       BME68X/BME688_CPP_Code
    Adjust the settings (e.g. upload_port) as necessary.
    """
    target_dir = os.path.join("BME68X", "BME688_CPP_Code")
    target_file = os.path.join(target_dir, "platformio.ini")
    
    if platform.system() == "Windows":
        content = r""";
; PlatformIO Project Configuration File for Windows
; https://docs.platformio.org/page/projectconf.html

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
    elif platform.system() == "Darwin":
        content = r""";
; PlatformIO Project Configuration File for macOS
; https://docs.platformio.org/page/projectconf.html

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
; PlatformIO Project Configuration File for Linux/Other
; https://docs.platformio.org/page/projectconf.html

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
    os.makedirs(target_dir, exist_ok=True)
    with open(target_file, "w") as f:
        f.write(content)
    print(f"platformio.ini updated for {platform.system()} at {target_file}")

def create_launcher_scripts(venv_dir, python_path):
    """
    Creates desktop launcher scripts that activate the virtual environment and run
    the entry-point programs for data collection and classification.
    
    The entry-point scripts are assumed to be located at:
      - BME68X/BME688_Data_Handler/DataCollection/dataCollection.py
      - BME68X/BME688_Data_Handler/DataClassification/dataClassification.py
    """
    launch_dir = os.path.join(os.getcwd(), "launchers")
    os.makedirs(launch_dir, exist_ok=True)

    # Define full paths for the entry-point scripts
    data_collection = os.path.join(os.getcwd(), "BME68X", "BME688_Data_Handler", "DataCollection", "dataCollection.py")
    classification = os.path.join(os.getcwd(), "BME68X", "BME688_Data_Handler", "DataClassification", "dataClassification.py")
    
    if platform.system() == "Windows":
        # Create Windows batch files.
        data_launcher = os.path.join(launch_dir, "launch_data_collection.bat")
        with open(data_launcher, "w") as f:
            f.write(f"""@echo off
REM Activate virtual environment and run data collection
call "{venv_dir}\\Scripts\\activate"
python "{data_collection}"
pause
""")
        class_launcher = os.path.join(launch_dir, "launch_classification.bat")
        with open(class_launcher, "w") as f:
            f.write(f"""@echo off
REM Activate virtual environment and run classification
call "{venv_dir}\\Scripts\\activate"
python "{classification}"
pause
""")
        print("Launcher batch files created in the 'launchers' directory.")
    else:
        # For macOS/Linux, create .command files (which are double-clickable on macOS).
        data_launcher = os.path.join(launch_dir, "launch_data_collection.command")
        with open(data_launcher, "w") as f:
            f.write(f"""#!/bin/bash
# Activate virtual environment and run data collection
source "{venv_dir}/bin/activate"
python "{data_collection}"
""")
        os.chmod(data_launcher, 0o755)
        
        class_launcher = os.path.join(launch_dir, "launch_classification.command")
        with open(class_launcher, "w") as f:
            f.write(f"""#!/bin/bash
# Activate virtual environment and run classification
source "{venv_dir}/bin/activate"
python "{classification}"
""")
        os.chmod(class_launcher, 0o755)
        print("Launcher .command files created in the 'launchers' directory.")

def main():
    """
    Main installation process:
      1. Create the virtual environment.
      2. Upgrade pip and install dependencies.
      3. Write the PlatformIO configuration.
      4. Optionally build and upload firmware.
      5. Create desktop launcher scripts.
    """
    # The installer assumes it is inside the "BME68X" folder.
    # Define the virtual environment directory.
    venv_dir = os.path.join(os.getcwd(), "venv")

    # Create the virtual environment.
    create_virtualenv(venv_dir)

    # Determine pip and python paths in the virtual environment.
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")

    # Upgrade pip.
    print("Upgrading pip...")
    run_command([pip_path, "install", "--upgrade", "pip"])

    # Install dependencies from requirements.txt if available; otherwise, install defaults.
    if os.path.exists("requirements.txt"):
        print("Installing dependencies from requirements.txt...")
        run_command([pip_path, "install", "-r", "requirements.txt"])
    else:
        print("No requirements.txt found. Installing default dependencies...")
        run_command([pip_path, "install", "pandas", "scikit-learn", "matplotlib", "pyserial", "platformio"])

    # Check for PlatformIO installation.
    try:
        subprocess.run([python_path, "-m", "platformio", "--version"], check=True, stdout=subprocess.PIPE)
        print("PlatformIO is available.")
    except subprocess.CalledProcessError:
        print("PlatformIO not found. Installing PlatformIO...")
        run_command([pip_path, "install", "platformio"])

    # Write the hard-coded PlatformIO configuration based on the OS.
    write_platformio_ini()

    # Optionally, build and upload firmware using PlatformIO.
    build_firmware = input("Do you want to build and upload the firmware? (y/n): ").strip().lower()
    if build_firmware == "y":
        firmware_dir = os.path.join("BME68X", "BME688_CPP_Code")
        if os.path.exists(firmware_dir):
            print("Building and uploading firmware...")
            run_command([python_path, "-m", "platformio", "run", "--target", "upload"], cwd=firmware_dir)
        else:
            print("Firmware directory not found. Please check the project structure.")
    else:
        print("Skipping firmware build/upload.")

    # Create desktop launcher scripts to run data collection and classification.
    create_launcher_scripts(venv_dir, python_path)

    print("Installation complete!")
    print("To run the project, you can either activate the virtual environment manually or double-click one of the launcher files in the 'launchers' folder.")
    if platform.system() == "Windows":
        print("Launcher files: launch_data_collection.bat and launch_classification.bat")
    else:
        print("Launcher files: launch_data_collection.command and launch_classification.command")
    print("Enjoy!")

if __name__ == "__main__":
    main()
