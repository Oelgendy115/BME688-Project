# Standard library imports
import os
import threading
import time
import csv
import datetime
from queue import Queue, Empty
from io import StringIO

# Tkinter for GUI components
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk

# PySerial for serial communication
import serial
import serial.tools.list_ports

# Matplotlib for plotting; use TkAgg backend for Tkinter integration
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# Pandas for data handling
import pandas as pd


class DataLoggerGUI:
    """
    Graphical user interface for a serial data logger application.
    
    This class manages serial communication, logging data to CSV files,
    real-time plotting of sensor data, and additional device commands.
    """
    def __init__(self, master):
        """
        Initialize the GUI, set up variables, and start periodic tasks.
        
        Args:
            master (tk.Tk): The root Tkinter window.
        """
        self.master = master
        self.master.title("Data Logger GUI")
        self.master.geometry("1400x700")
        self.master.minsize(800, 600)
        
        # Serial communication and logging state variables
        self.serial_port = None
        self.logging = False
        self.log_file = None
        self.plotting = False
        self.stop_event = threading.Event()

        # Flag and buffer for heater profiles response from the device
        self.get_heat_response_pending = False
        self.heater_profiles_buffer = []

        # CSV columns for data logging (includes a new 'Real_Time' column)
        self.predefined_columns = [
            "Real_Time",
            "Timestamp_ms",
            "Label_Tag",
            "HeaterProfile_ID",
            "Sensor1_Temperature_deg_C",
            "Sensor1_Pressure_Pa",
            "Sensor1_Humidity_%",
            "Sensor1_GasResistance_ohm",
            "Sensor1_Status",
            "Sensor1_GasIndex",
            "Sensor2_Temperature_deg_C",
            "Sensor2_Pressure_Pa",
            "Sensor2_Humidity_%",
            "Sensor2_GasResistance_ohm",
            "Sensor2_Status",
            "Sensor2_GasIndex",
            "Sensor3_Temperature_deg_C",
            "Sensor3_Pressure_Pa",
            "Sensor3_Humidity_%",
            "Sensor3_GasResistance_ohm",
            "Sensor3_Status",
            "Sensor3_GasIndex",
            "Sensor4_Temperature_deg_C",
            "Sensor4_Pressure_Pa",
            "Sensor4_Humidity_%",
            "Sensor4_GasResistance_ohm",
            "Sensor4_Status",
            "Sensor4_GasIndex",
            "Sensor5_Temperature_deg_C",
            "Sensor5_Pressure_Pa",
            "Sensor5_Humidity_%",
            "Sensor5_GasResistance_ohm",
            "Sensor5_Status",
            "Sensor5_GasIndex",
            "Sensor6_Temperature_deg_C",
            "Sensor6_Pressure_Pa",
            "Sensor6_Humidity_%",
            "Sensor6_GasResistance_ohm",
            "Sensor6_Status",
            "Sensor6_GasIndex",
            "Sensor7_Temperature_deg_C",
            "Sensor7_Pressure_Pa",
            "Sensor7_Humidity_%",
            "Sensor7_GasResistance_ohm",
            "Sensor7_Status",
            "Sensor7_GasIndex",
            "Sensor8_Temperature_deg_C",
            "Sensor8_Pressure_Pa",
            "Sensor8_Humidity_%",
            "Sensor8_GasResistance_ohm",
            "Sensor8_Status",
            "Sensor8_GasIndex"
        ]

        # DataFrame for storing logged data; protected by a thread lock
        self.data_lock = threading.Lock()
        self.df = pd.DataFrame(columns=self.predefined_columns.copy())

        # Parameters available for plotting sensor data
        self.parameters = [
            "Temperature_deg_C",
            "Pressure_Pa",
            "Humidity_%",
            "GasResistance_ohm",
            "GasIndex",
            "Label_Tag"
        ]

        # Variable for selected parameter from the dropdown (default is Temperature)
        self.selected_parameter = tk.StringVar()
        self.selected_parameter.set("Temperature_deg_C")

        # BooleanVars for sensor checkboxes (for sensors 1 to 8)
        self.selected_sensors = {f"Sensor{i}": tk.BooleanVar(value=False) for i in range(1, 9)}

        # Queue for thread-safe communication between the serial thread and the GUI
        self.data_queue = Queue()

        # Time window (in seconds) for displaying recent data in the plot
        self.time_window = 60

        # GUI variables for displaying Label Tag and Heater Profile information
        self.label_tag_var = tk.StringVar(value="N/A")
        self.heaterpfl_var = tk.StringVar(value="N/A")

        # Status bar variable to show current application status
        self.status_var = tk.StringVar(value="Ready")

        # List to keep track of sensor checkbox widgets
        self.checkbox_buttons = []

        # Build the GUI and initialize the plot
        self.create_widgets()
        self.create_plot()
        # Schedule regular processing of incoming serial data
        self.master.after(100, self.process_queue)

    def create_widgets(self):
        """
        Build and arrange the GUI components including connection controls,
        logging and configuration commands, plotting area, data display, and status bar.
        """
        # Configure main window grid layout
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=0)  # Serial Connection row
        self.master.rowconfigure(1, weight=0)  # Controller row
        self.master.rowconfigure(2, weight=1)  # Plotting row
        self.master.rowconfigure(3, weight=0)  # Data display row
        self.master.rowconfigure(4, weight=0)  # Status bar row

        # ----- Serial Connection Controls -----
        connection_frame = tk.LabelFrame(self.master, text="Serial Connection", padx=10, pady=10)
        connection_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        connection_frame.columnconfigure(1, weight=1)
        connection_frame.columnconfigure(2, weight=0)
        connection_frame.columnconfigure(3, weight=0)
        connection_frame.columnconfigure(4, weight=0)

        tk.Label(connection_frame, text="Select Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.port_var = tk.StringVar()
        self.port_dropdown = ttk.Combobox(connection_frame, textvariable=self.port_var, state="readonly", width=15)
        self.port_dropdown['values'] = self.get_serial_ports()
        if self.port_dropdown['values']:
            self.port_dropdown.current(0)
        self.port_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.connect_button = tk.Button(connection_frame, text="Connect", command=self.connect_serial, width=10)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)

        self.disconnect_button = tk.Button(connection_frame, text="Disconnect", command=self.disconnect_serial, state=tk.DISABLED, width=10)
        self.disconnect_button.grid(row=0, column=3, padx=5, pady=5)

        self.refresh_button = tk.Button(connection_frame, text="Refresh Ports", command=self.refresh_ports, width=12)
        self.refresh_button.grid(row=0, column=4, padx=5, pady=5)

        # ----- Controller Panel -----
        controller_frame = tk.LabelFrame(self.master, text="Controller", padx=10, pady=10)
        controller_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.start_button = tk.Button(controller_frame, text="Start Logging", command=self.start_logging, state=tk.DISABLED, width=15)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.stop_button = tk.Button(controller_frame, text="Stop Logging", command=self.stop_logging, state=tk.DISABLED, width=15)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)
        
        self.get_heater_profiles_button = tk.Button(controller_frame, text="Get Heater Profiles", command=self.get_heater_profiles, width=20, state=tk.DISABLED)
        self.get_heater_profiles_button.grid(row=0, column=2, padx=5, pady=5)
        
        self.send_new_config_button = tk.Button(controller_frame, text="Send New Config", command=self.send_new_config, width=20, state=tk.DISABLED)
        self.send_new_config_button.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(controller_frame, text="Sampling Period (ms):").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.sampling_rate_var = tk.StringVar(value="3000")
        self.sampling_entry = tk.Entry(controller_frame, textvariable=self.sampling_rate_var, width=10)
        self.sampling_entry.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        self.sampling_entry.bind("<Return>", self.set_sampling_rate)

        # ----- Plotting Area -----
        self.plotting_frame = tk.LabelFrame(self.master, text="Plotting", padx=10, pady=10)
        self.plotting_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        self.plotting_frame.columnconfigure(1, weight=1)
        self.plotting_frame.rowconfigure(0, weight=1)

        # Sensor selection checkboxes (left side)
        sensors_side_frame = tk.LabelFrame(self.plotting_frame, text="Sensors", padx=10, pady=10)
        sensors_side_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ns")
        sensors_side_frame.columnconfigure(0, weight=1)
        self.checkbox_buttons = []
        for i in range(1, 9):
            var = self.selected_sensors[f"Sensor{i}"]
            chk = tk.Checkbutton(sensors_side_frame, text=str(i), variable=var, command=lambda: self.update_plot(immediate=True))
            chk.config(state=tk.DISABLED)
            chk.pack(anchor='w', pady=2)
            self.checkbox_buttons.append(chk)

        # Plot display frame (right side)
        self.plot_frame = tk.Frame(self.plotting_frame)
        self.plot_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.plot_frame.columnconfigure(0, weight=1)
        self.plot_frame.rowconfigure(1, weight=1)

        # Create a matplotlib figure and configure the axis
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.ax.set_title("Sensor Data")
        self.ax.set_xlabel("Time (HH:MM:SS)")
        self.ax.set_ylabel("Value")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.fig.autofmt_xdate()

        # Embed the matplotlib canvas into the Tkinter GUI
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Log file display within the plotting area
        log_in_plot_frame = tk.Frame(self.plotting_frame)
        log_in_plot_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        log_in_plot_frame.columnconfigure(1, weight=1)
        tk.Label(log_in_plot_frame, text="Log File:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.log_file_var = tk.StringVar(value="No file selected.")
        self.log_file_label = tk.Label(log_in_plot_frame, textvariable=self.log_file_var, fg="green")
        self.log_file_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Controls for selecting parameter and time window
        controls_frame = tk.Frame(self.plotting_frame)
        controls_frame.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(3, weight=1)
        tk.Label(controls_frame, text="Select Parameter:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.parameter_dropdown = ttk.Combobox(controls_frame, textvariable=self.selected_parameter, state="disabled", width=25)
        self.parameter_dropdown['values'] = [param.replace('_', ' ') for param in self.parameters]
        if self.parameter_dropdown['values']:
            self.parameter_dropdown.current(0)
        self.parameter_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.parameter_dropdown.bind("<<ComboboxSelected>>", lambda event: self.update_plot(immediate=True))
        tk.Label(controls_frame, text="Time Window:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.time_window_var = tk.StringVar(value="1 Minute")
        self.time_window_dropdown = ttk.Combobox(controls_frame, textvariable=self.time_window_var, state="readonly", width=10)
        self.time_window_dropdown['values'] = ("1 Minute", "5 Minutes", "10 Minutes", "30 Minutes", "60 Minutes", "120 Minutes")
        self.time_window_dropdown.current(0)
        self.time_window_dropdown.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.time_window_dropdown.bind("<<ComboboxSelected>>", lambda event: self.update_time_window())

        # ----- Data Transferred Display -----
        data_display_frame = tk.LabelFrame(self.master, text="Data Transferred", padx=10, pady=10)
        data_display_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        data_display_frame.columnconfigure(0, weight=1)
        data_display_frame.rowconfigure(1, weight=1)
        label_frame = tk.Frame(data_display_frame)
        label_frame.grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(label_frame, text="Label Tag:").grid(row=0, column=0, sticky='w')
        tk.Label(label_frame, textvariable=self.label_tag_var, fg="blue").grid(row=0, column=1, sticky='w', padx=(5, 20))
        tk.Label(label_frame, text="Heater Profile:").grid(row=0, column=2, sticky='w')
        tk.Label(label_frame, textvariable=self.heaterpfl_var, fg="blue").grid(row=0, column=3, sticky='w', padx=(5, 0))
        self.data_display = scrolledtext.ScrolledText(data_display_frame, wrap=tk.WORD, state='disabled', height=5)
        self.data_display.grid(row=1, column=0, columnspan=4, pady=(10, 0), sticky="nsew")

        # ----- Status Bar -----
        status_frame = tk.Frame(self.master, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        self.status_label = tk.Label(status_frame, textvariable=self.status_var, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        # Initially disable controller widgets until connected
        self.disable_controller_widgets()

    def send_new_config(self):
        """
        Prompts the user to select a configuration JSON file and sends its content
        over the serial connection using a defined start-content-end command sequence.
        """
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Warning", "Serial port is not connected.")
            return

        file_path = filedialog.askopenfilename(
            title="Select Configuration JSON File",
            filetypes=(("JSON Files", "*.json"), ("All Files", "*.*"))
        )
        if not file_path:
            messagebox.showinfo("Info", "No file selected.")
            return

        try:
            with open(file_path, 'r') as f:
                json_content = f.read()
        except Exception as e:
            messagebox.showerror("File Error", f"Error reading file: {str(e)}")
            return

        self.send_command("START_CONFIG_UPLOAD")
        for line in json_content.splitlines():
            self.send_command(line)
            time.sleep(0.05)
        self.send_command("END_CONFIG_UPLOAD")
        messagebox.showinfo("Info", "Configuration uploaded successfully.")

    def disable_controller_widgets(self):
        """
        Disables interactive widgets in the controller panel and plotting controls.
        """
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.get_heater_profiles_button.config(state=tk.DISABLED)
        self.send_new_config_button.config(state=tk.DISABLED)
        self.sampling_entry.config(state=tk.DISABLED)
        self.parameter_dropdown.config(state="disabled")
        for chk in self.checkbox_buttons:
            chk.config(state=tk.DISABLED)

    def enable_controller_widgets(self):
        """
        Enables interactive widgets in the controller panel and plotting controls.
        """
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.get_heater_profiles_button.config(state=tk.NORMAL)
        self.send_new_config_button.config(state=tk.NORMAL)
        self.sampling_entry.config(state=tk.NORMAL)
        self.get_heater_profiles_button.config(state=tk.NORMAL)
        self.parameter_dropdown.config(state="readonly")
        for chk in self.checkbox_buttons:
            chk.config(state=tk.NORMAL)

    def create_plot(self):
        """
        Placeholder for plot creation.
        The plot is already initialized in the create_widgets method.
        """
        pass

    def get_serial_ports(self):
        """
        Retrieves and returns a list of available serial port device names.
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_ports(self):
        """
        Refreshes the serial port dropdown with the current available ports.
        """
        ports = self.get_serial_ports()
        self.port_dropdown['values'] = ports
        if ports:
            self.port_dropdown.current(0)
        else:
            self.port_var.set("")
        self.update_status(f"Ports refreshed. Available ports: {', '.join(ports) if ports else 'None'}")

    def connect_serial(self):
        """
        Opens the selected serial port, initializes communication, and starts
        the background thread to read incoming serial data.
        """
        selected_port = self.port_var.get()
        if not selected_port:
            self.update_status("No serial port selected.")
            messagebox.showwarning("Warning", "No serial port selected.")
            return

        try:
            self.serial_port = serial.Serial(selected_port, 115200, timeout=1)
            time.sleep(2)
            self.update_status(f"Connected to {selected_port}.")
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.refresh_button.config(state=tk.DISABLED)
            self.enable_controller_widgets()
            self.stop_event.clear()
            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()
        except serial.SerialException as e:
            self.update_status(f"Serial Connection Error: {str(e)}")
            messagebox.showerror("Connection Error", f"Failed to connect to {selected_port}.\nError: {str(e)}")

    def disconnect_serial(self):
        """
        Closes the serial connection and stops the serial reading thread.
        """
        if self.serial_port and self.serial_port.is_open:
            try:
                if self.logging:
                    self.stop_logging()
                self.stop_event.set()
                self.read_thread.join(timeout=2)
                self.serial_port.close()
                self.update_status("Serial port disconnected.")
                self.connect_button.config(state=tk.NORMAL)
                self.disconnect_button.config(state=tk.DISABLED)
                self.refresh_button.config(state=tk.NORMAL)
                self.disable_controller_widgets()
                self.log_file_var.set("No file selected.")
            except serial.SerialException as e:
                self.update_status(f"Disconnection Error: {str(e)}")
                messagebox.showerror("Disconnection Error", f"Failed to disconnect.\nError: {str(e)}")

    def send_command(self, command):
        """
        Sends a command string over the open serial connection.
        
        Args:
            command (str): The command to send.
        """
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(f"{command}\n".encode())
                self.update_status(f"Sent command: {command}")
            except serial.SerialException as e:
                self.update_status(f"Serial Communication Error: {str(e)}")
                messagebox.showerror("Communication Error", f"Failed to send command.\nError: {str(e)}")
        else:
            self.update_status("Serial port is not connected.")
            messagebox.showwarning("Warning", "Serial port is not connected.")

    def start_logging(self):
        """
        Prompts the user for a file path, starts logging data from the serial port,
        initializes the CSV file with headers, and resets the plot.
        """
        if not self.serial_port or not self.serial_port.is_open:
            self.update_status("Serial port is not connected.")
            messagebox.showwarning("Warning", "Serial port is not connected.")
            return

        file_path = filedialog.asksaveasfilename(
            initialdir="log_files",
            title="Select file",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            defaultextension=".csv"
        )
        if not file_path:
            self.update_status("Logging canceled. No file selected.")
            return

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            self.log_file = open(file_path, 'w', newline='')
            self.csv_writer = csv.writer(self.log_file)
            self.csv_writer.writerow(self.predefined_columns)
            self.logging = True
            self.plotting = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.send_command("START")

            # Reset and configure the plot for new logging session
            self.ax.cla()
            self.ax.set_title(f"Sensor Data Over Time")
            self.ax.set_xlabel("Time (HH:MM:SS)")
            self.ax.set_ylabel("Value")
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.fig.autofmt_xdate()
            self.canvas.draw()

            self.log_file_var.set(file_path)
            self.update_status(f"Logging started. Saving to {file_path}.")
            self.sampling_entry.config(state="disabled")
        except IOError as e:
            self.update_status(f"File Error: {str(e)}")
            messagebox.showerror("File Error", f"Failed to open file.\nError: {str(e)}")

    def stop_logging(self):
        """
        Stops the logging process, sends a stop command, and closes the log file.
        """
        if not self.logging:
            self.update_status("Logging is not active.")
            messagebox.showwarning("Warning", "Logging is not active.")
            return

        self.send_command("STOP")
        self.logging = False
        self.plotting = False
        self.stop_button.config(state=tk.DISABLED)

        if self.log_file:
            try:
                self.log_file.close()
            except IOError as e:
                self.update_status(f"File Error: {str(e)}")
                messagebox.showerror("File Error", f"Failed to close file.\nError: {str(e)}")

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log_file_var.set("No file selected.")
        self.update_status("Logging stopped.")
        self.sampling_entry.config(state="normal")

    def get_heater_profiles(self):
        """
        Sends a command to request heater profiles from the device and sets a flag
        to process the incoming heater profile data.
        """
        if not self.serial_port or not self.serial_port.is_open:
            self.update_status("Serial port is not connected.")
            messagebox.showerror("Error", "Serial port is not connected.")
            return
        try:
            self.get_heat_response_pending = True
            self.heater_profiles_buffer = []
            self.send_command("GETHEAT")
            self.update_status("Sent GETHEAT command.")
        except Exception as e:
            self.update_status(f"Error sending GETHEAT: {str(e)}")
            messagebox.showerror("Error", f"Failed to send GETHEAT command.\nError: {str(e)}")
            self.get_heat_response_pending = False

    def read_serial_data(self):
        """
        Continuously reads from the serial port.
        
        This method handles heater profile responses as well as CSV data lines.
        Valid CSV lines are enqueued for further parsing.
        """
        buffer = ""
        while not self.stop_event.is_set():
            try:
                if self.serial_port.in_waiting:
                    byte_data = self.serial_port.read(self.serial_port.in_waiting)
                    buffer += byte_data.decode(errors='ignore')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue

                        if self.get_heat_response_pending:
                            self.heater_profiles_buffer.append(line)
                            # Adjusted check: look for "retrieval complete" in the line.
                            if "retrieval complete" in line.lower():
                                self.get_heat_response_pending = False
                                heater_profiles_str = "\n".join(self.heater_profiles_buffer)
                                # Schedule the GUI update on the main thread
                                self.master.after(0, lambda: self.show_heater_profiles(heater_profiles_str))
                                self.master.after(0, lambda: self.update_status("Received Heater Profiles."))
                        else:
                            if self.logging:
                                csv_reader = csv.reader(StringIO(line))
                                parsed = next(csv_reader, None)
                                if parsed and len(parsed) >= 51:
                                    real_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    new_row = [real_time] + parsed
                                    if self.log_file:
                                        self.csv_writer.writerow(new_row)
                                        self.log_file.flush()
                                    reconstructed_line = ",".join(new_row)
                                    self.data_queue.put(reconstructed_line)
                            else:
                                self.data_queue.put(line)
            except serial.SerialException:
                self.master.after(0, lambda: self.update_status("Serial Communication Error: Connection lost."))
                self.master.after(0, lambda: messagebox.showerror("Communication Error", "Serial Communication Error: Connection lost."))
                break
            except UnicodeDecodeError:
                continue

    def parse_and_store_data(self, line):
        """
        Parses a CSV-formatted string from the serial input and stores the data
        in a pandas DataFrame. Also updates the Label Tag and Heater Profile display.
        
        Args:
            line (str): A CSV-formatted string containing sensor data.
        """
        try:
            if self.get_heat_response_pending:
                return

            if line.startswith("Real_Time"):
                return

            csv_reader = csv.reader(StringIO(line))
            row = next(csv_reader)
            expected_fields = 1 + 3 + 8 * 6
            if len(row) < expected_fields:
                self.update_status(f"Incomplete data received. Expected at least {expected_fields} fields, got {len(row)}.")
                return

            real_time_str = row[0]
            try:
                real_time = datetime.datetime.strptime(real_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.update_status(f"Invalid Real_Time format: {real_time_str}")
                return

            timestamp_ms = row[1]
            label_tag = row[2]
            heater_profile_id = row[3]

            sensors_data = {}
            for sensor_num in range(1, 9):
                base_idx = 4 + (sensor_num - 1) * 6
                sensors_data[f"Sensor{sensor_num}"] = {
                    "Temperature_deg_C": row[base_idx],
                    "Pressure_Pa": row[base_idx + 1],
                    "Humidity_%": row[base_idx + 2],
                    "GasResistance_ohm": row[base_idx + 3],
                    "Status": row[base_idx + 4],
                    "GasIndex": row[base_idx + 5]
                }

            data_dict = {
                "Real_Time": real_time,
                "Timestamp_ms": timestamp_ms,
                "Label_Tag": label_tag,
                "HeaterProfile_ID": heater_profile_id,
                "local_timestamp": time.time()
            }

            for sensor, params in sensors_data.items():
                for param, value in params.items():
                    column_name = f"{sensor}_{param}"
                    data_dict[column_name] = value

            with self.data_lock:
                new_row = pd.DataFrame([data_dict])
                self.df = pd.concat([self.df, new_row], ignore_index=True)

                if not self.df.empty:
                    latest_row = self.df.iloc[-1]
                    heater_profile_id = latest_row.get("HeaterProfile_ID", "N/A")
                    label_tag = latest_row.get("Label_Tag", "N/A")
                    self.heaterpfl_var.set(str(heater_profile_id))
                    self.label_tag_var.set(str(label_tag))

                current_time = time.time()
                self.df = self.df[self.df["local_timestamp"] >= current_time - self.time_window]

        except Exception as e:
            self.update_status(f"Data Parsing Error: {str(e)}")
            messagebox.showerror("Parsing Error", f"An error occurred while parsing data.\nError: {str(e)}")

    def process_queue(self):
        """
        Processes lines from the data queue by parsing, storing, updating the data display,
        and refreshing the plot.
        """
        try:
            while True:
                line = self.data_queue.get_nowait()
                self.parse_and_store_data(line)
                self.update_data_display(line)
                self.update_plot(immediate=True)
                self.data_queue.task_done()
        except Empty:
            pass
        self.master.after(100, self.process_queue)

    def update_data_display(self, data):
        """
        Appends a new line of data to the scrollable text widget.
        
        Args:
            data (str): The data string to display.
        """
        self.data_display.config(state='normal')
        self.data_display.insert(tk.END, data + "\n")
        self.data_display.yview(tk.END)
        self.data_display.config(state='disabled')

    def set_sampling_rate(self, event):
        """
        Validates and sets the sampling rate (in ms) based on user input.
        """
        freq = self.sampling_rate_var.get().strip()
        if not freq:
            self.update_status("Please enter a Sampling Period in milliseconds.")
            messagebox.showwarning("Input Error", "Please enter a Sampling Period in milliseconds.")
            return
        try:
            freq_ms = int(float(freq))
            if freq_ms <= 0:
                self.update_status("Sampling Period must be greater than zero.")
                messagebox.showwarning("Input Error", "Sampling Period must be greater than zero.")
                return

            if self.logging:
                if not self.confirm_action("Logging is active. Do you want to stop logging to set the Sampling Period?"):
                    return
                self.stop_logging()
                self.master.after(500, lambda: self.send_sampling_command(freq_ms))
            else:
                if not self.serial_port or not self.serial_port.is_open:
                    self.update_status("Serial port is not connected.")
                    messagebox.showwarning("Warning", "Serial port is not connected.")
                    return
                self.send_sampling_command(freq_ms)
        except ValueError:
            self.update_status("Please enter a valid number for Sampling Period.")
            messagebox.showerror("Input Error", "Please enter a valid number for Sampling Period.")

    def send_sampling_command(self, msec):
        """
        Sends a command to set the sampling rate on the device.
        
        Args:
            msec (int): Sampling period in milliseconds.
        """
        command = f"MS_{msec}"
        self.send_command(command)
        self.update_status(f"Sampling Period set to {msec} ms.")

    def update_plot(self, immediate=False):
        """
        Updates the real-time plot based on selected sensor data and parameter.
        
        Args:
            immediate (bool): If True, update the plot immediately.
        """
        if not self.plotting:
            return

        selected_parameter = self.selected_parameter.get().replace(' ', '_')
        column = selected_parameter

        if column not in self.parameters:
            self.update_status(f"Invalid parameter selected: {selected_parameter}")
            messagebox.showerror("Parameter Error", f"Invalid parameter selected: {selected_parameter}")
            return

        selected_sensors = [sensor for sensor, var in self.selected_sensors.items() if var.get()]
        if not selected_sensors:
            self.ax.cla()
            self.ax.set_title("Sensor Data")
            self.ax.set_xlabel("Time (HH:MM:SS)")
            self.ax.set_ylabel("Value")
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.fig.autofmt_xdate()
            self.canvas.draw()
            return

        self.ax.cla()
        self.ax.set_title(f"{selected_parameter.replace('_', ' ')} Over Time")
        self.ax.set_xlabel("Time (HH:MM:SS)")
        self.ax.set_ylabel(selected_parameter.replace('_', ' '))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())

        has_data = False

        with self.data_lock:
            if not self.df.empty:
                df_filtered = self.df[self.df["local_timestamp"] >= time.time() - self.time_window]
                if not df_filtered.empty:
                    sensor_times = df_filtered['Real_Time']
                    for sensor in selected_sensors:
                        sensor_column = f"{sensor}_{selected_parameter}"
                        if sensor_column in self.df.columns:
                            try:
                                sensor_data = pd.to_numeric(df_filtered[sensor_column], errors='coerce')
                                self.ax.plot(sensor_times, sensor_data, label=sensor)
                                has_data = True
                            except Exception as e:
                                self.update_status(f"Plotting Error for {sensor}: {str(e)}")
                                messagebox.showerror("Plotting Error", f"An error occurred while plotting {sensor} data.\nError: {str(e)}")
            else:
                self.update_status("No data available.")

        if selected_parameter == "Label_Tag":
            with self.data_lock:
                if not self.df.empty:
                    df_filtered = self.df[self.df["local_timestamp"] >= time.time() - self.time_window]
                    if not df_filtered.empty:
                        sensor_times = df_filtered['Real_Time']
                        label_tags = pd.to_numeric(df_filtered["Label_Tag"], errors='coerce')
                        self.ax.plot(sensor_times, label_tags, label="Label Tag", color='red')
                        has_data = True

        if has_data:
            self.ax.legend(loc='upper left')

        current_time = datetime.datetime.now()
        time_window_start = current_time - datetime.timedelta(seconds=self.time_window)
        self.ax.set_xlim(time_window_start, current_time)
        self.fig.autofmt_xdate()
        self.canvas.draw()

        if not immediate:
            self.master.after(1000, self.update_plot)

    def on_closing(self):
        """
        Handles the closing event of the main window.
        Stops logging and ensures a clean exit.
        """
        if self.logging:
            if self.confirm_action("Logging is in progress. Do you want to quit?"):
                self.stop_logging()
                self.stop_event.set()
                self.master.destroy()
                os._exit(0)
            else:
                return
        else:
            self.stop_event.set()
            self.master.destroy()
            os._exit(0)

    def update_time_window(self):
        """
        Updates the time window for displaying data on the plot based on user selection.
        """
        selected_time = self.time_window_var.get()
        if selected_time == "1 Minute":
            self.time_window = 60
        elif selected_time == "5 Minutes":
            self.time_window = 300
        elif selected_time == "10 Minutes":
            self.time_window = 600
        elif selected_time == "30 Minutes":
            self.time_window = 1800
        elif selected_time == "60 Minutes":
            self.time_window = 3600
        elif selected_time == "120 Minutes":
            self.time_window = 7200
        else:
            self.time_window = 60
        self.update_plot()

    def update_status(self, message):
        """
        Updates the status bar with the provided message.
        
        Args:
            message (str): Status message to display.
        """
        self.status_var.set(message)

    def confirm_action(self, message):
        """
        Displays a confirmation dialog with the given message.
        
        Args:
            message (str): The confirmation message.
        
        Returns:
            bool: True if the user confirms, False otherwise.
        """
        return messagebox.askyesno("Confirmation", message)

    def show_heater_profiles(self, heater_profiles_str):
        """
        Displays heater profiles in a pop-up window with formatted text.
        
        Args:
            heater_profiles_str (str): Raw heater profile data.
        """
        popup = tk.Toplevel(self.master)
        popup.title("Heater Profiles")
        popup.geometry("800x600")
        popup.transient(self.master)
        popup.grab_set()

        tk.Label(popup, text="Heater Profiles", font=("Helvetica", 16, "bold")).pack(pady=10)

        text_area = scrolledtext.ScrolledText(popup, wrap=tk.WORD, width=100, height=30, font=("Courier", 10))
        text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        formatted_text = self.format_heater_profiles(heater_profiles_str)
        text_area.insert(tk.END, formatted_text)
        text_area.config(state='disabled')

        close_button = tk.Button(popup, text="Close", command=popup.destroy, width=10)
        close_button.pack(pady=10)

    def format_heater_profiles(self, heater_profiles_str):
        """
        Formats the raw heater profiles string into a more readable layout.
        
        Args:
            heater_profiles_str (str): The unformatted heater profile data.
        
        Returns:
            str: The formatted heater profile data.
        """
        lines = heater_profiles_str.split('\n')
        formatted_lines = []
        for line in lines:
            if line.startswith("Sensor"):
                formatted_lines.append(f"\n{line}\n" + "-" * len(line))
            elif line.startswith("  Step"):
                formatted_lines.append(f"    {line}")
            elif line.startswith("Heater profile retrieved for sensor"):
                formatted_lines.append(f"{line}\n")
            else:
                formatted_lines.append(line)
        return "\n".join(formatted_lines)


def main():
    """
    Entry point for the application.
    Creates the main Tkinter window and starts the GUI event loop.
    """
    root = tk.Tk()
    app = DataLoggerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
