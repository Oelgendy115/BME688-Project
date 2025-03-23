# BME688 Project Setup Guide

Welcome to the BME688 Project! This guide will walk you through cloning the repository from GitHub, understanding the directory structure, and running the installer to set up your environment.

## 1. Clone the Repository

First, clone the repository to your local machine. Open your Terminal (or Git Bash on Windows) and run:

```bash
git clone https://github.com/Oelgendy115/BME688-Project.git
```

This will create a folder named `BME688-Project` containing all the project files.

## 2. Directory Structure

After cloning, your project directory should look like this:

```
BME688-Project/
│
├── BME68X/
│   ├── BME688_CPP_Code/
│   │   └── platformio.ini          <-- Firmware configuration file (generated during installation)
│   ├── BME688_Data_Handler/
│   │   ├── DataCollection/
│   │   │   └── dataCollection.py   <-- Entry point for data collection
│   │   ├── DataClassification/
│   │   │   └── dataClassification.py  <-- Entry point for data classification
│   │   └── Label_Encoder.csv       <-- Maps raw labels to class names
│   └── requirements.txt            <-- List of Python dependencies (optional)
│
├── install.py                      <-- Installer script to set up dependencies, firmware, and launchers
└── README.md                       <-- This setup guide
```

## 3. Running the Installer

The installer script (`install.py`) will:

1. **Install Dependencies:**  
   It checks for `BME68X/requirements.txt` (if available) and installs the required Python packages. If not found, it will install a default set of dependencies.

2. **Configure Firmware:**  
   It writes a hard-coded `platformio.ini` file into the `BME68X/BME688_CPP_Code` directory. The configuration is automatically selected based on your operating system. If you choose to build and upload the firmware, the installer will list available serial ports, let you select one, and update the configuration accordingly.

3. **Build and Upload Firmware (Optional):**  
   You’ll be prompted to build and upload the firmware using PlatformIO. If you confirm, the installer will update the serial port settings based on your selection and run the necessary PlatformIO commands.

4. **Create Launcher Scripts:**  
   It creates desktop launcher scripts for the two entry-point programs (data collection and data classification) and saves them in a folder called `launchers` in the project root.

### How to Run

- **On Windows:**  
  Open Command Prompt or PowerShell, navigate to the project root (`BME688-Project`), and run:
  
  ```
  python install.py
  ```

- **On macOS/Linux:**  
  Open Terminal, navigate to the project root, and run:
  
  ```
  python3 install.py
  ```

The installer will guide you through each step. Follow the on-screen prompts to complete the setup.

## 4. Running the Application

After installation:

- You can run the project by executing the entry-point scripts directly:
  - Data Collection: `python3 BME68X/BME688_Data_Handler/DataCollection/dataCollection.py`
  - Data Classification: `python3 BME68X/BME688_Data_Handler/DataClassification/dataClassification.py`
  
- Alternatively, use the launcher files created in the `launchers` folder:
  - On Windows: `launch_data_collection.bat` and `launch_classification.bat`
  - On macOS/Linux: `launch_data_collection.command` and `launch_classification.command`

## 5. Additional Notes

- Ensure that Python (and pip) are installed on your system.
- If you need to update dependencies later, simply re-run the installer.
- The installer sets the working directory to the project root automatically, so the relative paths will work correctly on both Windows and macOS.
- For any issues or questions, please open an issue on the GitHub repository.

Enjoy using the BME688 Project!
