import os
import serial
import threading
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from tkinter import ttk
import serial.tools.list_ports
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from queue import Queue, Empty
import csv
from io import StringIO
import datetime  # Import datetime for Real_Time
import matplotlib.dates as mdates  # Import for date formatting

class DataLoggerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Data Logger GUI")
        self.master.geometry("1400x700")  
        self.master.minsize(800, 600)  
        self.serial_port = None
        self.logging = False
        self.log_file = None
        self.plotting = False
        self.stop_event = threading.Event()

        # Flags and Buffers
        self.get_heat_response_pending = False
        self.heater_profiles_buffer = []  # Buffer to collect heater profiles

        # Updated Columns based on the current CSV data format with Real_Time added
        self.predefined_columns = [
            "Real_Time",  # New column for real-time recording
            "Timestamp_ms",
            "Label_Tag",
            "HeaterProfile_ID",
            # Sensor1 Data
            "Sensor1_Temperature_deg_C",
            "Sensor1_Pressure_Pa",
            "Sensor1_Humidity_%",
            "Sensor1_GasResistance_ohm",
            "Sensor1_Status",
            "Sensor1_GasIndex",
            # Sensor2 Data
            "Sensor2_Temperature_deg_C",
            "Sensor2_Pressure_Pa",
            "Sensor2_Humidity_%",
            "Sensor2_GasResistance_ohm",
            "Sensor2_Status",
            "Sensor2_GasIndex",
            # Sensor3 Data
            "Sensor3_Temperature_deg_C",
            "Sensor3_Pressure_Pa",
            "Sensor3_Humidity_%",
            "Sensor3_GasResistance_ohm",
            "Sensor3_Status",
            "Sensor3_GasIndex",
            # Sensor4 Data
            "Sensor4_Temperature_deg_C",
            "Sensor4_Pressure_Pa",
            "Sensor4_Humidity_%",
            "Sensor4_GasResistance_ohm",
            "Sensor4_Status",
            "Sensor4_GasIndex",
            # Sensor5 Data
            "Sensor5_Temperature_deg_C",
            "Sensor5_Pressure_Pa",
            "Sensor5_Humidity_%",
            "Sensor5_GasResistance_ohm",
            "Sensor5_Status",
            "Sensor5_GasIndex",
            # Sensor6 Data
            "Sensor6_Temperature_deg_C",
            "Sensor6_Pressure_Pa",
            "Sensor6_Humidity_%",
            "Sensor6_GasResistance_ohm",
            "Sensor6_Status",
            "Sensor6_GasIndex",
            # Sensor7 Data
            "Sensor7_Temperature_deg_C",
            "Sensor7_Pressure_Pa",
            "Sensor7_Humidity_%",
            "Sensor7_GasResistance_ohm",
            "Sensor7_Status",
            "Sensor7_GasIndex",
            # Sensor8 Data
            "Sensor8_Temperature_deg_C",
            "Sensor8_Pressure_Pa",
            "Sensor8_Humidity_%",
            "Sensor8_GasResistance_ohm",
            "Sensor8_Status",
            "Sensor8_GasIndex"
        ]

        # Initialize DataFrame with CSV columns
        self.data_lock = threading.Lock()
        self.df = pd.DataFrame(columns=self.predefined_columns.copy())

        # Parameter-to-column mapping for plotting
        # Removed "Status" and added "Label_Tag"
        self.parameters = [
            "Temperature_deg_C",
            "Pressure_Pa",
            "Humidity_%",
            "GasResistance_ohm",
            "GasIndex",
            "Label_Tag"  # New parameter added
        ]

        # Initialize selected parameter (dropdown)
        self.selected_parameter = tk.StringVar()
        self.selected_parameter.set("Temperature_deg_C")  # Default selection

        # Initialize selected sensors (checkboxes)
        self.selected_sensors = {f"Sensor{i}": tk.BooleanVar(value=False) for i in range(1, 9)}

        # Initialize Queue for thread-safe communication
        self.data_queue = Queue()

        # Initialize time_window (in seconds)
        self.time_window = 60  # default to 1 minute

        # Initialize StringVars for Label Tag and Heater Profile
        self.label_tag_var = tk.StringVar(value="N/A")
        self.heaterpfl_var = tk.StringVar(value="N/A")

        # Initialize Status Bar
        self.status_var = tk.StringVar(value="Ready")

        # Initialize list to store Checkbutton widgets
        self.checkbox_buttons = []

        self.create_widgets()
        self.create_plot()
        self.master.after(100, self.process_queue)  # Schedule queue processing

    def create_widgets(self):
        # Configure grid layout for responsiveness
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=0)  # Serial Connection
        self.master.rowconfigure(1, weight=0)  # Controller
        self.master.rowconfigure(2, weight=1)  # Plotting
        self.master.rowconfigure(3, weight=0)  # Data Transferred
        self.master.rowconfigure(4, weight=0)  # Status Bar

        # Serial Connection Box
        connection_frame = tk.LabelFrame(self.master, text="Serial Connection", padx=10, pady=10)
        connection_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        connection_frame.columnconfigure(1, weight=1)
        connection_frame.columnconfigure(2, weight=0)
        connection_frame.columnconfigure(3, weight=0)
        connection_frame.columnconfigure(4, weight=0)

        # Label for Serial Port
        tk.Label(connection_frame, text="Select Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")

        # Dropdown for Serial Ports
        self.port_var = tk.StringVar()
        self.port_dropdown = ttk.Combobox(connection_frame, textvariable=self.port_var, state="readonly", width=15)
        self.port_dropdown['values'] = self.get_serial_ports()
        if self.port_dropdown['values']:
            self.port_dropdown.current(0)
        self.port_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Connect Button
        self.connect_button = tk.Button(connection_frame, text="Connect", command=self.connect_serial, width=10)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)

        # Disconnect Button
        self.disconnect_button = tk.Button(connection_frame, text="Disconnect", command=self.disconnect_serial, state=tk.DISABLED, width=10)
        self.disconnect_button.grid(row=0, column=3, padx=5, pady=5)

        # Refresh Ports Button
        self.refresh_button = tk.Button(connection_frame, text="Refresh Ports", command=self.refresh_ports, width=12)
        self.refresh_button.grid(row=0, column=4, padx=5, pady=5)

        # Controller Box
        controller_frame = tk.LabelFrame(self.master, text="Controller", padx=10, pady=10)
        controller_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        controller_frame.columnconfigure(5, weight=1)  # Adjusted to accommodate moved button

        # Start Logging Button
        self.start_button = tk.Button(controller_frame, text="Start Logging", command=self.start_logging, state=tk.DISABLED, width=15)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        # Stop Logging Button
        self.stop_button = tk.Button(controller_frame, text="Stop Logging", command=self.stop_logging, state=tk.DISABLED, width=15)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Get Heater Profiles Button - Moved next to Stop Logging Button
        self.get_heater_profiles_button = tk.Button(controller_frame, text="Get Heater Profiles", command=self.get_heater_profiles, width=20, state=tk.DISABLED)
        self.get_heater_profiles_button.grid(row=0, column=2, padx=5, pady=5)

        # Sampling Period Control (Removed LabelFrame)
        # Place label and entry directly in controller_frame
        tk.Label(controller_frame, text="Sampling Period (sec):").grid(row=0, column=3, padx=5, pady=5, sticky="e")
        self.sampling_rate_var = tk.StringVar(value="1")
        self.sampling_entry = tk.Entry(controller_frame, textvariable=self.sampling_rate_var, width=10)
        self.sampling_entry.grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.sampling_entry.bind("<Return>", self.set_sampling_rate)

        # Plotting Box
        self.plotting_frame = tk.LabelFrame(self.master, text="Plotting", padx=10, pady=10)
        self.plotting_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        self.plotting_frame.columnconfigure(1, weight=1)
        self.plotting_frame.rowconfigure(0, weight=1)

        # Sensors Checkboxes Frame (Left Side)
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

        # Plot Frame (Right Side)
        self.plot_frame = tk.Frame(self.plotting_frame)
        self.plot_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.plot_frame.columnconfigure(0, weight=1)
        self.plot_frame.rowconfigure(1, weight=1)  # Allow space for plot and controls

        # Create `plot_canvas` below the controls
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.ax.set_title("Sensor Data")
        self.ax.set_xlabel("Time (HH:MM:SS)")  # Updated label to reflect real-time
        self.ax.set_ylabel("Value")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))  # Format x-axis labels
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto-locate major ticks

        self.fig.autofmt_xdate()  # Auto-format date labels

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Log File Display inside Plotting Box
        log_in_plot_frame = tk.Frame(self.plotting_frame)
        log_in_plot_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        log_in_plot_frame.columnconfigure(1, weight=1)

        tk.Label(log_in_plot_frame, text="Log File:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.log_file_var = tk.StringVar(value="No file selected.")
        self.log_file_label = tk.Label(log_in_plot_frame, textvariable=self.log_file_var, fg="green")
        self.log_file_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Time Window and Select Parameter (Switched Positions)
        # Previously: Time Window first, Select Parameter second
        # Now: Select Parameter first, Time Window second
        controls_frame = tk.Frame(self.plotting_frame)
        controls_frame.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(3, weight=1)

        # Select Parameter (Moved to be first)
        tk.Label(controls_frame, text="Select Parameter:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.parameter_dropdown = ttk.Combobox(controls_frame, textvariable=self.selected_parameter, state="disabled", width=25)
        self.parameter_dropdown['values'] = [param.replace('_', ' ') for param in self.parameters]
        if self.parameter_dropdown['values']:
            self.parameter_dropdown.current(0)
        self.parameter_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.parameter_dropdown.bind("<<ComboboxSelected>>", lambda event: self.update_plot(immediate=True))

        # Time Window (Moved to be second)
        tk.Label(controls_frame, text="Time Window:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.time_window_var = tk.StringVar(value="1 Minute")
        self.time_window_dropdown = ttk.Combobox(controls_frame, textvariable=self.time_window_var, state="readonly", width=10)
        self.time_window_dropdown['values'] = ("1 Minute", "5 Minutes", "10 Minutes","30 Minutes","60 Minutes","120 Minutes")
        self.time_window_dropdown.current(0)
        self.time_window_dropdown.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.time_window_dropdown.bind("<<ComboboxSelected>>", lambda event: self.update_time_window())

        # Data Transferred Box - Shrink to half size
        data_display_frame = tk.LabelFrame(self.master, text="Data Transferred", padx=10, pady=10)
        data_display_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        data_display_frame.columnconfigure(0, weight=1)
        data_display_frame.rowconfigure(1, weight=1)

        # Align Label Tag and Heater Profile side by side
        label_frame = tk.Frame(data_display_frame)
        label_frame.grid(row=0, column=0, columnspan=4, sticky="w")

        tk.Label(label_frame, text="Label Tag:").grid(row=0, column=0, sticky='w')
        tk.Label(label_frame, textvariable=self.label_tag_var, fg="blue").grid(row=0, column=1, sticky='w', padx=(5, 20))

        tk.Label(label_frame, text="Heater Profile:").grid(row=0, column=2, sticky='w')
        tk.Label(label_frame, textvariable=self.heaterpfl_var, fg="blue").grid(row=0, column=3, sticky='w', padx=(5, 0))

        # Add a scrollable text widget with further reduced height
        self.data_display = scrolledtext.ScrolledText(data_display_frame, wrap=tk.WORD, state='disabled', height=5)  # Reduced height
        self.data_display.grid(row=1, column=0, columnspan=4, pady=(10, 0), sticky="nsew")

        # Status Bar
        status_frame = tk.Frame(self.master, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

        self.status_label = tk.Label(status_frame, textvariable=self.status_var, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        # Disable Controller Widgets
        self.disable_controller_widgets()

    def disable_controller_widgets(self):
        """
        Disables all widgets within the Controller Frame except for Connect and Refresh buttons.
        """
        # Start and Stop Logging Buttons
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        # Sampling Period Entry
        self.sampling_entry.config(state=tk.DISABLED)
        # Get Heater Profiles Button
        self.get_heater_profiles_button.config(state=tk.DISABLED)
        # Disable Plotting Controls
        self.parameter_dropdown.config(state="disabled")
        for chk in self.checkbox_buttons:
            chk.config(state=tk.DISABLED)

    def enable_controller_widgets(self):
        """
        Enables all widgets within the Controller Frame.
        """
        # Start and Stop Logging Buttons
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        # Sampling Period Entry
        self.sampling_entry.config(state=tk.NORMAL)
        # Get Heater Profiles Button
        self.get_heater_profiles_button.config(state=tk.NORMAL)
        # Enable Plotting Controls
        self.parameter_dropdown.config(state="readonly")
        for chk in self.checkbox_buttons:
            chk.config(state=tk.NORMAL)

    def create_plot(self):
        # Plot creation moved to create_widgets to align with new layout
        pass  # Plot is created directly in create_widgets()

    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_ports(self):
        ports = self.get_serial_ports()
        self.port_dropdown['values'] = ports
        if ports:
            self.port_dropdown.current(0)
        else:
            self.port_var.set("")
        self.update_status(f"Ports refreshed. Available ports: {', '.join(ports) if ports else 'None'}")

    def connect_serial(self):
        selected_port = self.port_var.get()
        if not selected_port:
            self.update_status("No serial port selected.")
            messagebox.showwarning("Warning", "No serial port selected.")
            return

        try:
            self.serial_port = serial.Serial(selected_port, 115200, timeout=1)
            time.sleep(2)  # Wait for the connection to establish
            self.update_status(f"Connected to {selected_port}.")

            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.refresh_button.config(state=tk.DISABLED)

            # Enable Controller Frame widgets
            self.enable_controller_widgets()

            # Start the serial reading thread
            self.stop_event.clear()
            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()
        except serial.SerialException as e:
            self.update_status(f"Serial Connection Error: {str(e)}")
            messagebox.showerror("Connection Error", f"Failed to connect to {selected_port}.\nError: {str(e)}")

    def disconnect_serial(self):
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

                # Disable Controller Frame widgets
                self.disable_controller_widgets()

                self.log_file_var.set("No file selected.")
            except serial.SerialException as e:
                self.update_status(f"Disconnection Error: {str(e)}")
                messagebox.showerror("Disconnection Error", f"Failed to disconnect.\nError: {str(e)}")

    def send_command(self, command):
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
        if not self.serial_port or not self.serial_port.is_open:
            self.update_status("Serial port is not connected.")
            messagebox.showwarning("Warning", "Serial port is not connected.")
            return

        file_path = filedialog.asksaveasfilename(
            initialdir="log_files",
            title="Select file",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),  # Changed to CSV
            defaultextension=".csv"  # Changed default extension to .csv
        )
        if not file_path:
            self.update_status("Logging canceled. No file selected.")
            return

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            self.log_file = open(file_path, 'w', newline='')  # Open with newline=''
            self.csv_writer = csv.writer(self.log_file)
            self.csv_writer.writerow(self.predefined_columns)  # Write CSV header

            self.logging = True
            self.plotting = True  # Start plotting simultaneously
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

            self.send_command("START")

            # Initialize plot
            self.ax.cla()
            self.ax.set_title(f"Sensor Data Over Time")
            self.ax.set_xlabel("Time (HH:MM:SS)")  # Updated label
            self.ax.set_ylabel("Value")
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))  # Format x-axis labels
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto-locate major ticks
            self.fig.autofmt_xdate()  # Auto-format date labels
            self.canvas.draw()

            self.log_file_var.set(file_path)
            self.update_status(f"Logging started. Saving to {file_path}.")

            # Disable Sampling Period entry while logging is active
            self.sampling_entry.config(state="disabled")
        except IOError as e:
            self.update_status(f"File Error: {str(e)}")
            messagebox.showerror("File Error", f"Failed to open file.\nError: {str(e)}")

    def stop_logging(self):
        if not self.logging:
            self.update_status("Logging is not active.")
            messagebox.showwarning("Warning", "Logging is not active.")
            return

        self.send_command("STOP")
        self.logging = False
        self.plotting = False  # Stop plotting

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

        # Enable Sampling Period entry after logging has stopped
        self.sampling_entry.config(state="normal")

    def get_heater_profiles(self):
        """
        Sends a GETHEAT command to the serial port and waits for the response.
        The response is displayed in a custom pop-up window.
        """
        if not self.serial_port or not self.serial_port.is_open:
            self.update_status("Serial port is not connected.")
            messagebox.showerror("Error", "Serial port is not connected.")
            return
        try:
            self.get_heat_response_pending = True
            self.heater_profiles_buffer = []  # Reset buffer
            self.send_command("GETHEAT")
            self.update_status("Sent GETHEAT command.")
        except Exception as e:
            self.update_status(f"Error sending GETHEAT: {str(e)}")
            messagebox.showerror("Error", f"Failed to send GETHEAT command.\nError: {str(e)}")
            self.get_heat_response_pending = False

    def read_serial_data(self):
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
                            if "Heater profiles retrieval complete." in line:
                                self.get_heat_response_pending = False
                                # Display the collected heater profiles in a custom popup
                                heater_profiles_str = "\n".join(self.heater_profiles_buffer)
                                self.show_heater_profiles(heater_profiles_str)
                                self.update_status("Received Heater Profiles.")
                        else:
                            if self.logging:
                                csv_reader = csv.reader(StringIO(line))
                                parsed = next(csv_reader, None)
                                if parsed and len(parsed) >= 51:
                                    # Prepend Real_Time with seconds included
                                    real_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    new_row = [real_time] + parsed
                                    if self.log_file:
                                        self.csv_writer.writerow(new_row)  # Write using csv.writer
                                        self.log_file.flush()
                                    # Reconstruct the line with Real_Time for data_queue
                                    reconstructed_line = ",".join(new_row)
                                    # Enqueue only the reconstructed line
                                    self.data_queue.put(reconstructed_line)
                            else:
                                # Enqueue lines only if not part of GETHEAT response
                                self.data_queue.put(line)
            except serial.SerialException:
                self.update_status("Serial Communication Error: Connection lost.")
                messagebox.showerror("Communication Error", "Serial Communication Error: Connection lost.")
                break
            except UnicodeDecodeError:
                continue
            
    def parse_and_store_data(self, line):
        try:
            # Handle GETHEAT response (already handled in read_serial_data)
            # So, proceed only if it's not a GETHEAT response
            if self.get_heat_response_pending:
                # The GETHEAT response is handled in read_serial_data
                return

            # Skip header line if present
            if line.startswith("Real_Time"):
                return  # Skip header line

            # Use StringIO to read the CSV line
            csv_reader = csv.reader(StringIO(line))
            row = next(csv_reader)

            expected_fields = 1 + 3 + 8 * 6  # Real_Time + 3 + 8 sensors * 6 fields each = 52
            if len(row) < expected_fields:
                self.update_status(f"Incomplete data received. Expected at least {expected_fields} fields, got {len(row)}.")
                return

            # Extract Real_Time, timestamp, label tag, heaterprofile id
            real_time_str = row[0]
            try:
                real_time = datetime.datetime.strptime(real_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.update_status(f"Invalid Real_Time format: {real_time_str}")
                return

            timestamp_ms = row[1]
            label_tag = row[2]
            heater_profile_id = row[3]

            # Extract sensor data
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

            # Create a dictionary mapping columns to values
            data_dict = {
                "Real_Time": real_time,  # Store as datetime object
                "Timestamp_ms": timestamp_ms,
                "Label_Tag": label_tag,
                "HeaterProfile_ID": heater_profile_id,
                "local_timestamp": time.time()
            }

            # Add sensor data to data_dict
            for sensor, params in sensors_data.items():
                for param, value in params.items():
                    column_name = f"{sensor}_{param}"
                    data_dict[column_name] = value

            # Append the new data to the DataFrame
            with self.data_lock:
                new_row = pd.DataFrame([data_dict])
                self.df = pd.concat([self.df, new_row], ignore_index=True)

                # Update Label Tag and Heater Profile in GUI with the latest data
                if not self.df.empty:
                    latest_row = self.df.iloc[-1]
                    heater_profile_id = latest_row.get("HeaterProfile_ID", "N/A")
                    label_tag = latest_row.get("Label_Tag", "N/A")
                    self.heaterpfl_var.set(str(heater_profile_id))
                    self.label_tag_var.set(str(label_tag))

                # Keep only data within the time window
                current_time = time.time()
                self.df = self.df[self.df["local_timestamp"] >= current_time - self.time_window]

        except Exception as e:
            self.update_status(f"Data Parsing Error: {str(e)}")
            messagebox.showerror("Parsing Error", f"An error occurred while parsing data.\nError: {str(e)}")

    def process_queue(self):
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
        self.data_display.config(state='normal')
        self.data_display.insert(tk.END, data + "\n")
        self.data_display.yview(tk.END)
        self.data_display.config(state='disabled')

    def set_sampling_rate(self, event):
        freq = self.sampling_rate_var.get().strip()
        if not freq:
            self.update_status("Please enter a Sampling Period number in seconds.")
            messagebox.showwarning("Input Error", "Please enter a Sampling Period number in seconds.")
            return
        try:
            freq_sec = float(freq)
            if freq_sec <= 0:
                self.update_status("Sampling Period must be greater than zero seconds.")
                messagebox.showwarning("Input Error", "Sampling Period must be greater than zero seconds.")
                return
            freq_msec = int(freq_sec * 1000)

            if self.logging:
                # If logging is active, prompt to stop logging to set Sampling Period
                if not self.confirm_action("Logging is active. Do you want to stop logging to set the Sampling Period?"):
                    return
                self.stop_logging()
                self.master.after(500, lambda: self.send_sampling_command(freq_msec))
            else:
                if not self.serial_port or not self.serial_port.is_open:
                    self.update_status("Serial port is not connected.")
                    messagebox.showwarning("Warning", "Serial port is not connected.")
                    return
                self.send_sampling_command(freq_msec)
        except ValueError:
            self.update_status("Please enter a valid number for Sampling Period.")
            messagebox.showerror("Input Error", "Please enter a valid number for Sampling Period.")

    def send_sampling_command(self, msec):
        command = f"SEC_{msec}"
        self.send_command(command)
        self.update_status(f"Sampling Period set to {msec / 1000} seconds.")

    def update_plot(self, immediate=False):
        if not self.plotting:
            return

        selected_parameter = self.selected_parameter.get().replace(' ', '_')  # Match column naming
        column = selected_parameter  # e.g., "Temperature_deg_C"

        if column not in self.parameters:
            self.update_status(f"Invalid parameter selected: {selected_parameter}")
            messagebox.showerror("Parameter Error", f"Invalid parameter selected: {selected_parameter}")
            return

        selected_sensors = [sensor for sensor, var in self.selected_sensors.items() if var.get()]
        if not selected_sensors:
            # Clear the plot if no sensors are selected
            self.ax.cla()
            self.ax.set_title("Sensor Data")
            self.ax.set_xlabel("Time (HH:MM:SS)")
            self.ax.set_ylabel("Value")
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))  # Format x-axis labels
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto-locate major ticks
            self.fig.autofmt_xdate()  # Auto-format date labels
            self.canvas.draw()
            return

        # Clear the plot
        self.ax.cla()
        self.ax.set_title(f"{selected_parameter.replace('_', ' ')} Over Time")
        self.ax.set_xlabel("Time (HH:MM:SS)")
        self.ax.set_ylabel(selected_parameter.replace('_', ' '))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))  # Format x-axis labels
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto-locate major ticks

        has_data = False

        with self.data_lock:
            if not self.df.empty:
                # Filter data within the time window
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

        # If the selected parameter is 'Label_Tag', plot it as integer
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
            self.ax.legend(loc='upper left')  # Ensure legend is at top-left

        # Set the x-axis limits based on the time window
        current_time = datetime.datetime.now()
        time_window_start = current_time - datetime.timedelta(seconds=self.time_window)
        self.ax.set_xlim(time_window_start, current_time)

        self.fig.autofmt_xdate()  # Auto-format date labels
        self.canvas.draw()

        if not immediate:
            self.master.after(1000, self.update_plot)

    def on_closing(self):
        if self.logging:
            if self.confirm_action("Logging is in progress. Do you want to quit?"):
                self.stop_logging()
                self.stop_event.set()
                self.master.destroy()
        else:
            self.stop_event.set()
            self.master.destroy()

    def update_time_window(self):
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
        self.status_var.set(message)

    def confirm_action(self, message):
        """
        Implement a confirmation dialog using tkinter.messagebox.
        """
        return messagebox.askyesno("Confirmation", message)

    def show_heater_profiles(self, heater_profiles_str):
        """
        Creates a custom pop-up window to display heater profiles in a readable format.
        """
        popup = tk.Toplevel(self.master)
        popup.title("Heater Profiles")
        popup.geometry("800x600")  # Adjust the size as needed
        popup.transient(self.master)  # Make the popup stay on top of the main window
        popup.grab_set()  # Make the popup modal

        # Add a label
        tk.Label(popup, text="Heater Profiles", font=("Helvetica", 16, "bold")).pack(pady=10)

        # Create a scrolled text widget
        text_area = scrolledtext.ScrolledText(popup, wrap=tk.WORD, width=100, height=30, font=("Courier", 10))
        text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Insert the heater profiles
        formatted_text = self.format_heater_profiles(heater_profiles_str)
        text_area.insert(tk.END, formatted_text)
        text_area.config(state='disabled')  # Make it read-only

        # Add a close button
        close_button = tk.Button(popup, text="Close", command=popup.destroy, width=10)
        close_button.pack(pady=10)

    def format_heater_profiles(self, heater_profiles_str):
        """
        Formats the raw heater profiles string into a more readable layout.
        """
        lines = heater_profiles_str.split('\n')
        formatted_lines = []
        for line in lines:
            if line.startswith("Sensor"):
                # Add sensor header with underlines
                formatted_lines.append(f"\n{line}\n" + "-"*len(line))
            elif line.startswith("  Step"):
                # Indent the step details
                formatted_lines.append(f"    {line}")
            elif line.startswith("Heater profile retrieved for sensor"):
                # Add a separator line
                formatted_lines.append(f"{line}\n")
            else:
                formatted_lines.append(line)
        return "\n".join(formatted_lines)

def main():
    root = tk.Tk()
    app = DataLoggerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()