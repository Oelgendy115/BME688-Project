# Import standard libraries and modules for GUI, file operations, data processing, model training, and serial communication.
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, simpledialog
import os
import pandas as pd
import json
from joblib import dump, load
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
import serial
import serial.tools.list_ports
import threading
import time
import csv
from io import StringIO
import numpy as np
from statistics import mode
from sklearn.utils.class_weight import compute_class_weight

# Import custom data processing class
from dataProcessor import DataProcessor

# Define constants for metrics file and data processing window parameters
METRICS_FILE = "model_metrics.json"
WINDOW_SIZE = 10
STRIDE = 1
MAX_WINDOW = 10

class ModelTrainerGUI:
    """
    A GUI application for training a machine learning model, performing predictions,
    and handling real-time sensor data. Built using tkinter.
    """
    def __init__(self, master):
        """
        Initialize the main GUI window and create all necessary widgets and variables.
        """
        self.master = master
        self.master.title("Data Classification GUI")
        self.master.geometry("1000x700")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        # Variables for file paths and application state
        self.raw_data_file = tk.StringVar()
        self.processed_features_file = tk.StringVar()
        self.status = tk.StringVar(value="Status: Idle")
        self.prediction_file = tk.StringVar()
        self.processed_file_predict = tk.StringVar()
        self.model_path = "data_classifier_model.joblib"
        self.model_metrics = None
        self.df_for_training = None

        # Variables for real-time serial communication and prediction control
        self.rt_serial_port = None
        self.rt_connected = False
        self.rt_logging = False
        self.rt_stop_event = threading.Event()
        self.rt_data_buffer = []
        self.batch_length_var = tk.StringVar(value="12")
        self.time_left_var = tk.StringVar(value="0")
        self.current_prediction = tk.StringVar(value="N/A")
        
        # Variables for windowing parameters used during feature extraction
        self.window_length_var = tk.StringVar(value=str(WINDOW_SIZE))
        self.stride_length_var = tk.StringVar(value=str(STRIDE))
        self.prediction_stride_length = tk.StringVar(value=str(STRIDE))

        # Create the main frame for the GUI components
        main_frame = tk.Frame(master)
        main_frame.grid(sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)

        # ----------------------------- TRAIN MODEL FRAME -----------------------------
        # Frame for training the model using raw or processed data
        train_model_frame = tk.LabelFrame(main_frame, text="1. Train Model", padx=10, pady=10)
        train_model_frame.grid(row=0, column=0, sticky="ew", pady=5)
        train_model_frame.columnconfigure(0, weight=0)
        train_model_frame.columnconfigure(1, weight=1)
        train_model_frame.columnconfigure(2, weight=0)

        # Widgets to select the raw data file for training
        tk.Label(train_model_frame, text="Raw Data File:").grid(row=0, column=0, sticky="w")
        tk.Entry(train_model_frame, textvariable=self.raw_data_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(train_model_frame, text="Browse", command=self.browse_file_train).grid(row=0, column=2, padx=5)

        # Widgets to select the processed features file (optional)
        tk.Label(train_model_frame, text="Processed Features File:").grid(row=1, column=0, sticky="w")
        tk.Entry(train_model_frame, textvariable=self.processed_features_file).grid(row=1, column=1, padx=5, sticky="ew")
        tk.Button(train_model_frame, text="Browse", command=self.browse_file_processed_features).grid(row=1, column=2, padx=5)

        # Frame containing inputs for window length and stride, and buttons for feature extraction and training
        train_options_frame = tk.Frame(train_model_frame)
        train_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        # Left sub-frame: window and stride input fields
        ws_frame = tk.Frame(train_options_frame)
        ws_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(ws_frame, text="Window Length:").grid(row=0, column=0, sticky="w")
        tk.Entry(ws_frame, textvariable=self.window_length_var, width=10).grid(row=0, column=1, padx=5, pady=2)
        tk.Label(ws_frame, text="Stride Length:").grid(row=0, column=2, sticky="w")
        tk.Entry(ws_frame, textvariable=self.stride_length_var, width=10).grid(row=0, column=3, padx=5, pady=2)
        # Right sub-frame: buttons for feature extraction and training
        btn_frame = tk.Frame(train_options_frame)
        btn_frame.pack(side=tk.LEFT, padx=5)
        self.extract_features_button = tk.Button(btn_frame, text="Extract Features", command=self.extract_features)
        self.extract_features_button.grid(row=0, column=0, padx=5, pady=5)
        self.train_button = tk.Button(btn_frame, text="Train Model", command=self.train_model)
        self.train_button.grid(row=0, column=1, padx=5, pady=5)

        # Progress bar for training progress feedback
        self.train_progress_bar = ttk.Progressbar(train_model_frame, orient="horizontal", mode="determinate")
        self.train_progress_bar.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        self.train_progress_bar["maximum"] = 100
        self.train_progress_bar["value"] = 0

        # --------------------------- MODEL PREDICTION FRAME ---------------------------
        # Frame for handling predictions using the trained model
        predict_frame = tk.LabelFrame(main_frame, text="2. Model Prediction", padx=10, pady=10)
        predict_frame.grid(row=1, column=0, sticky="ew", pady=5)
        predict_frame.columnconfigure(0, weight=0)
        predict_frame.columnconfigure(1, weight=1)
        predict_frame.columnconfigure(2, weight=0)

        # Widgets to select the input file for prediction
        tk.Label(predict_frame, text="Prediction Input File:").grid(row=0, column=0, sticky="w")
        tk.Entry(predict_frame, textvariable=self.prediction_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(predict_frame, text="Browse", command=self.browse_file_predict).grid(row=0, column=2, padx=5)

        # Widgets to select the processed features file for prediction (if already available)
        tk.Label(predict_frame, text="Processed Features File:").grid(row=1, column=0, sticky="w")
        tk.Entry(predict_frame, textvariable=self.processed_file_predict).grid(row=1, column=1, padx=5, sticky="ew")
        tk.Button(predict_frame, text="Browse", command=self.browse_file_processed_features_predict).grid(row=1, column=2, padx=5)

        # Frame containing input for prediction stride and prediction control buttons
        predict_options_frame = tk.Frame(predict_frame)
        predict_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        ws_pred_frame = tk.Frame(predict_options_frame)
        ws_pred_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(ws_pred_frame, text="Prediction Stride Length:").grid(row=0, column=0, sticky="w")
        tk.Entry(ws_pred_frame, textvariable=self.prediction_stride_length, width=10).grid(row=0, column=1, padx=5, pady=2)
        btn_pred_frame = tk.Frame(predict_options_frame)
        btn_pred_frame.pack(side=tk.LEFT, padx=5)
        self.extract_features_predict_button = tk.Button(btn_pred_frame, text="Extract Features", command=self.extract_features_predict)
        self.extract_features_predict_button.grid(row=0, column=0, padx=5, pady=5)
        self.predict_button = tk.Button(btn_pred_frame, text="Predict", command=self.predict_data)
        self.predict_button.grid(row=0, column=1, padx=5, pady=5)
        self.show_metrics_button = tk.Button(btn_pred_frame, text="Show Metrics", command=self.display_metrics)
        self.show_metrics_button.grid(row=0, column=2, padx=5, pady=5)
        self.show_metrics_button.config(state=tk.DISABLED)

        # Progress bar for prediction process feedback
        self.predict_progress_bar = ttk.Progressbar(predict_frame, orient="horizontal", mode="determinate")
        self.predict_progress_bar.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        self.predict_progress_bar["maximum"] = 100
        self.predict_progress_bar["value"] = 0

        # ----------------------- REAL-TIME PREDICTIONS FRAME -------------------------
        # Frame for connecting to a serial port and handling real-time sensor data predictions
        rt_frame = tk.LabelFrame(main_frame, text="3. Real-time Predictions", padx=10, pady=10)
        rt_frame.grid(row=2, column=0, sticky="ew", pady=5)
        rt_frame.columnconfigure(1, weight=1)
        rt_frame.columnconfigure(4, weight=1)

        # Serial port selection and refresh controls
        tk.Label(rt_frame, text="Select Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.rt_port_var = tk.StringVar()
        ports = self.get_serial_ports()
        if ports:
            self.rt_port_var.set(ports[0])
            self.rt_port_dropdown = tk.OptionMenu(rt_frame, self.rt_port_var, *ports)
        else:
            self.rt_port_var.set("")
            self.rt_port_dropdown = tk.OptionMenu(rt_frame, self.rt_port_var, "")
        self.rt_port_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(rt_frame, text="Refresh Ports", command=self.refresh_rt_ports).grid(row=0, column=2, padx=5, pady=5)
        self.rt_connect_button = tk.Button(rt_frame, text="Connect", command=self.rt_connect_serial, width=10)
        self.rt_connect_button.grid(row=0, column=3, padx=5, pady=5)
        self.rt_disconnect_button = tk.Button(rt_frame, text="Disconnect", command=self.rt_disconnect_serial, state=tk.DISABLED, width=10)
        self.rt_disconnect_button.grid(row=0, column=4, padx=5, pady=5)
        
        # Batch length input for real-time prediction and start/stop buttons
        tk.Label(rt_frame, text="Batch Length (sec):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(rt_frame, textvariable=self.batch_length_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.rt_start_button = tk.Button(rt_frame, text="Start Predictions", command=self.rt_start_predictions, state=tk.DISABLED, width=15)
        self.rt_start_button.grid(row=1, column=2, padx=5, pady=5)
        self.rt_stop_button = tk.Button(rt_frame, text="Stop Predictions", command=self.rt_stop_predictions, state=tk.DISABLED, width=15)
        self.rt_stop_button.grid(row=1, column=3, padx=5, pady=5)
        
        # Display remaining seconds in the current batch
        tk.Label(rt_frame, text="Seconds left in batch:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Label(rt_frame, textvariable=self.time_left_var, fg="blue").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # Frame to display incoming sensor data from the serial port
        rt_data_frame = tk.LabelFrame(rt_frame, text="Sensor Data Output", padx=10, pady=10)
        rt_data_frame.grid(row=3, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        rt_data_frame.columnconfigure(0, weight=1)
        self.rt_data_display = scrolledtext.ScrolledText(rt_data_frame, wrap=tk.WORD, height=5)
        self.rt_data_display.grid(row=0, column=0, sticky="nsew")
        
        # Frame to show the current prediction from real-time data
        pred_frame = tk.LabelFrame(rt_frame, text="Current Smell Prediction", padx=10, pady=10)
        pred_frame.grid(row=4, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        tk.Label(pred_frame, textvariable=self.current_prediction, fg="blue", font=("Helvetica", 12, "bold")).pack()

        # --------------------------- TERMINAL UPDATES FRAME --------------------------
        # Frame for displaying status updates and messages from the application
        status_frame = tk.LabelFrame(main_frame, text="4. Terminal Updates", padx=10, pady=10)
        status_frame.grid(row=3, column=0, sticky="ew", pady=5)
        status_frame.columnconfigure(0, weight=1)
        self.status_label = tk.Label(status_frame, textvariable=self.status, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        # Set initial status and load any saved model metrics
        self.update_status("Ready")
        self.load_metrics_from_file()

    def load_metrics_from_file(self):
        """
        Load previously saved model metrics from the METRICS_FILE.
        If the file exists, update the model metrics and enable the metrics button.
        """
        if os.path.exists(METRICS_FILE):
            try:
                with open(METRICS_FILE, "r") as f:
                    loaded_metrics = json.load(f)
                if 'cm' in loaded_metrics:
                    loaded_metrics['cm'] = np.array(loaded_metrics['cm'])
                self.model_metrics = loaded_metrics
                if 'report' in loaded_metrics or 'cm' in loaded_metrics:
                    self.show_metrics_button.config(state=tk.NORMAL)
            except Exception:
                self.model_metrics = None

    def save_metrics_to_file(self, metrics):
        """
        Save model metrics to a file named model_metrics.json in the same directory as this script.
        """
        try:
            metrics_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_metrics.json")
            serializable_metrics = {}
            for key, value in metrics.items():
                if isinstance(value, np.ndarray):
                    serializable_metrics[key] = value.tolist()
                else:
                    serializable_metrics[key] = value
            with open(metrics_file, "w") as f:
                json.dump(serializable_metrics, f, indent=4)
        except Exception as e:
            print("Error saving metrics to file:", e)


    def browse_file_train(self):
        """
        Open a file dialog to select a raw data file for training.
        If a new raw file is chosen, clear both processed file paths.
        """
        filename = filedialog.askopenfilename(
            title="Select Raw Data File for Training",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            if filename != self.raw_data_file.get():
                self.processed_features_file.set("")
                self.processed_file_predict.set("")
            self.raw_data_file.set(filename)

    def browse_file_processed_features(self):
        """
        Open a file dialog to select a processed features file for training.
        """
        filename = filedialog.askopenfilename(
            title="Select Processed Features File",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.processed_features_file.set(filename)


    def browse_file_processed_features_predict(self):
        """
        Open a file dialog to select a processed features file for prediction.
        """
        filename = filedialog.askopenfilename(
            title="Select Processed Features File for Prediction",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.processed_file_predict.set(filename)

    def browse_file_predict(self):
        """
        Open a file dialog to select a raw data file for prediction.
        If a new raw file is chosen, clear both processed file paths.
        """
        filename = filedialog.askopenfilename(
            title="Select Input File for Prediction",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            if filename != self.prediction_file.get():
                self.processed_features_file.set("")
                self.processed_file_predict.set("")
            self.prediction_file.set(filename)

    def extract_features(self):
        """
        Extract features from the selected raw data file for training.
        This now spawns a background thread so that the progress bar updates immediately.
        """
        if not self.raw_data_file.get():
            messagebox.showerror("Error", "Please select a raw data file first.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save Extracted Features",
            defaultextension=".csv",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if not save_path:
            messagebox.showinfo("Cancelled", "Save operation cancelled.")
            return
        thread = threading.Thread(target=self.run_extraction_bg, args=(self.raw_data_file.get(), save_path))
        thread.daemon = True
        thread.start()

    def extract_features_predict(self):
        """
        Extract features for prediction from the selected input file.
        This now spawns a background thread so that the progress bar updates immediately.
        """
        if not self.prediction_file.get():
            messagebox.showerror("Error", "Please select a prediction input file first.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save Extracted Features",
            defaultextension=".csv",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if not save_path:
            messagebox.showinfo("Cancelled", "Save operation cancelled.")
            return
        thread = threading.Thread(target=self.run_extraction_bg_predict, args=(self.prediction_file.get(), save_path))
        thread.daemon = True
        thread.start()

    def train_model(self):
        """
        Train the model according to the following rules:
        - If both a raw file and a processed file are set, skip processing and use the processed file.
        - If only a processed file is set, skip processing and use that file.
        - If only a raw file is set, ask the user where to save processed features, process and save them, then train.
        - If no file is set, show an error.
        """
        raw_path = self.raw_data_file.get()
        proc_path = self.processed_features_file.get()

        # 1) Neither raw nor processed
        if not raw_path and not proc_path:
            messagebox.showerror("Error", "Please select a raw data file or a processed features file first.")
            return

        # 2) Both raw and processed => skip re-processing; just train on processed
        if raw_path and proc_path:
            self.update_status("Using existing processed file. Skipping re-processing...")
            try:
                df_for_training = pd.read_csv(proc_path)
            except Exception as e:
                messagebox.showerror("Error reading processed file", str(e))
                self.update_status("Idle")
                return
            # Spawn background thread to train on the processed DataFrame
            thread = threading.Thread(target=self.run_training_bg, args=(df_for_training,))
            thread.daemon = True
            thread.start()
            return

        # 3) Only processed => train on processed
        if proc_path and not raw_path:
            self.update_status("No raw file selected. Training on existing processed file...")
            try:
                df_for_training = pd.read_csv(proc_path)
            except Exception as e:
                messagebox.showerror("Error reading processed file", str(e))
                self.update_status("Idle")
                return
            thread = threading.Thread(target=self.run_training_bg, args=(df_for_training,))
            thread.daemon = True
            thread.start()
            return

        # 4) Only raw => ask user to save processed, then process & train
        if raw_path and not proc_path:
            save_path = filedialog.asksaveasfilename(
                title="Save Processed Features for Training",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if not save_path:
                messagebox.showinfo("Cancelled", "Operation cancelled. No processed file was created.")
                return
            self.processed_features_file.set(save_path)

            # Process the raw file, save to the chosen path, then train
            try:
                processor = DataProcessor()
                df_raw = processor.read_csv(raw_path)
                selected_features = list(processor.features.keys())
                try:
                    window_length = int(self.window_length_var.get())
                except ValueError:
                    window_length = WINDOW_SIZE
                try:
                    stride = int(self.stride_length_var.get())
                except ValueError:
                    stride = STRIDE

                self.update_status("Processing raw file for training...")
                processed_data = processor.process_data(
                    df_raw,
                    window_size=window_length,
                    stride=stride,
                    selected_features=selected_features
                )
                processed_df = pd.DataFrame(processed_data)
                if processed_df.empty:
                    messagebox.showwarning("No Data", "No data available to train on after processing.")
                    self.update_status("Idle")
                    return
                processed_df.to_csv(save_path, index=False)
                self.update_status(f"Features saved to {save_path}. Starting training...")
            except Exception as e:
                messagebox.showerror("Error", f"Error processing raw file: {e}")
                self.update_status("Idle")
                return

            # Now spawn background thread to train on processed_df
            thread = threading.Thread(target=self.run_training_bg, args=(processed_df,))
            thread.daemon = True
            thread.start()
    def run_extraction_bg_predict(self, raw_file, save_path):
        """
        Background thread function for extracting features from a raw file for prediction.
        Updates the prediction progress bar using the prediction progress callback.
        """
        try:
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=0))
            self.master.after(0, lambda: self.update_status("Extracting features for prediction..."))
            processor = DataProcessor()
            df = processor.read_csv(raw_file)
            selected_features = list(processor.features.keys())
            try:
                window_length = int(self.window_length_var.get())
            except ValueError:
                window_length = WINDOW_SIZE
            try:
                stride = int(self.prediction_stride_length.get())
            except ValueError:
                stride = STRIDE
            lower_cols = [col.lower() for col in df.columns]
            if ('timestamp_ms' in lower_cols) and ('sensor1_temperature_deg_c' in lower_cols):
                processed_data = processor.process_data(
                    df,
                    window_size=window_length,
                    stride=stride,
                    selected_features=selected_features,
                    progress_callback=self.predict_window_progress_callback
                )
                processed_df = pd.DataFrame(processed_data)
            else:
                processed_df = df.copy()
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available after processing."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return
            processed_df.to_csv(save_path, index=False)
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Extracted features saved to {save_path}"))
            self.processed_file_predict.set(save_path)
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Feature extraction for prediction complete."))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Error during feature extraction for prediction: {e}"))
            self.master.after(0, lambda: self.update_status("Idle"))

    def run_extraction_bg(self, raw_file, save_path):
        """
        Background thread function for extracting features from a raw file for training.
        Updates the progress bar using the training progress callback.
        """
        try:
            self.master.after(0, lambda: self.train_progress_bar.configure(value=0))
            self.master.after(0, lambda: self.update_status("Extracting features..."))
            processor = DataProcessor()
            df = processor.read_csv(raw_file)
            selected_features = list(processor.features.keys())
            try:
                window_length = int(self.window_length_var.get())
            except ValueError:
                window_length = WINDOW_SIZE
            try:
                stride = int(self.stride_length_var.get())
            except ValueError:
                stride = STRIDE
            lower_cols = [col.lower() for col in df.columns]
            if ('timestamp_ms' in lower_cols) and ('sensor1_temperature_deg_c' in lower_cols):
                processed_data = processor.process_data(
                    df,
                    window_size=window_length,
                    stride=stride,
                    selected_features=selected_features,
                    progress_callback=self.train_window_progress_callback
                )
                processed_df = pd.DataFrame(processed_data)
            else:
                processed_df = df.copy()
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available after processing."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return
            processed_df.to_csv(save_path, index=False)
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Extracted features saved to {save_path}"))
            self.processed_features_file.set(save_path)
            self.master.after(0, lambda: self.train_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Feature extraction complete."))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Error during feature extraction: {e}"))
            self.master.after(0, lambda: self.update_status("Idle"))

    def run_training_bg(self, df_for_training):
        """
        Background thread that trains the model on a DataFrame that is already processed.
        Saves metrics and updates the UI on completion.
        """
        try:
            self.master.after(0, lambda: self.train_progress_bar.configure(value=0))
            self.master.after(0, lambda: self.update_status("Training model..."))

            feature_cols = [c for c in df_for_training.columns if c not in ['Label_Tag', 'Real_Time']]
            if not feature_cols or 'Label_Tag' not in df_for_training.columns:
                raise ValueError("Processed DataFrame must contain 'Label_Tag' and some feature columns.")

            X = df_for_training[feature_cols]
            # Strip whitespace from labels for consistency.
            y_raw = df_for_training['Label_Tag'].astype(str).str.strip()
            self.le = LabelEncoder()
            y = self.le.fit_transform(y_raw)
            clf = RandomForestClassifier(random_state=42)
            clf.fit(X, y)

            # Save model.
            dump((clf, self.le), self.model_path)

            # Save simple metrics (e.g., number of windows per label).
            label_info = {}
            for label_val, group_df in df_for_training.groupby('Label_Tag'):
                total_windows = len(group_df)
                label_info[label_val] = {'total_windows': total_windows}

            self.model_metrics = {
                "trained_on": os.path.basename(self.processed_features_file.get()),
                "label_info": label_info
            }
            self.save_metrics_to_file(self.model_metrics)

            self.master.after(0, lambda: self.train_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Training complete. Model saved."))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Training Error", str(e)))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            time.sleep(0.5)
            self.master.after(0, lambda: self.train_progress_bar.configure(value=0))


    def train_window_progress_callback(self, current, total):
        """
        Callback function to update the training progress bar based on window processing progress.
        """
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 80
        self.master.after(0, lambda: self.train_progress_bar.configure(value=progress))

    def predict_data(self):
        """
        Make predictions according to the following rules:
        - If both a raw file (prediction) and a processed file are set, skip re-processing and use the processed file.
        - If only a processed file is set, skip processing and use that file.
        - If only a raw file is set, ask where to save processed features, process and save them, then predict.
        - If no file is set, show an error.
        """
        raw_pred_path = self.prediction_file.get()
        proc_pred_path = self.processed_file_predict.get()

        # 1) Neither raw nor processed
        if not raw_pred_path and not proc_pred_path:
            messagebox.showerror("Error", "Please select an input file for prediction or a processed features file.")
            return

        # 2) Both raw and processed => skip re-processing
        if raw_pred_path and proc_pred_path:
            self.update_status("Using existing processed file for prediction. Skipping re-processing...")
            try:
                processed_df = pd.read_csv(proc_pred_path)
            except Exception as e:
                messagebox.showerror("Error", f"Error reading processed features file: {e}")
                self.update_status("Idle")
                return
            thread = threading.Thread(target=self.run_prediction_bg_processed, args=(processed_df,))
            thread.daemon = True
            thread.start()
            return

        # 3) Only processed => predict using it
        if proc_pred_path and not raw_pred_path:
            self.update_status("No raw file selected. Predicting on existing processed file...")
            try:
                processed_df = pd.read_csv(proc_pred_path)
            except Exception as e:
                messagebox.showerror("Error", f"Error reading processed features file: {e}")
                self.update_status("Idle")
                return
            thread = threading.Thread(target=self.run_prediction_bg_processed, args=(processed_df,))
            thread.daemon = True
            thread.start()
            return

        # 4) Only raw => ask user to save processed, then process & predict
        if raw_pred_path and not proc_pred_path:
            save_path = filedialog.asksaveasfilename(
                title="Save Processed Features for Prediction",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if not save_path:
                messagebox.showinfo("Cancelled", "Operation cancelled. No processed file was created.")
                return
            self.processed_file_predict.set(save_path)

            # Process the raw file, save to the chosen path, then predict
            try:
                processor = DataProcessor()
                df_raw = processor.read_csv(raw_pred_path)
                selected_features = list(processor.features.keys())
                try:
                    window_length = int(self.window_length_var.get())
                except ValueError:
                    window_length = WINDOW_SIZE
                try:
                    stride = int(self.prediction_stride_length.get())
                except ValueError:
                    stride = STRIDE

                self.update_status("Processing raw file for prediction...")
                processed_data = processor.process_data(
                    df_raw,
                    window_size=window_length,
                    stride=stride,
                    selected_features=selected_features,
                    progress_callback=self.predict_window_progress_callback
                )
                self.master.after(0, lambda: self.predict_progress_bar.configure(value=80))

                processed_df = pd.DataFrame(processed_data)
                if processed_df.empty:
                    messagebox.showwarning("No Data", "No data available for prediction after processing.")
                    self.update_status("Idle")
                    return

                processed_df.to_csv(save_path, index=False)
                self.update_status(f"Features saved to {save_path}. Starting prediction...")
            except Exception as e:
                messagebox.showerror("Error", f"Error processing raw prediction file: {e}")
                self.update_status("Idle")
                return

            # Now spawn background thread to run prediction on processed_df
            thread = threading.Thread(target=self.run_prediction_bg_processed, args=(processed_df,))
            thread.daemon = True
            thread.start()

    def run_prediction_bg(self, processed_df):
        """
        (Optional) If you decide you no longer want a separate path for raw in run_prediction_bg,
        you can remove references to re-processing here.
        This function is not strictly needed if you always call run_prediction_bg_processed 
        with a processed DataFrame. 
        """
        pass  # You can delete or leave a no-op if you prefer.

    def run_prediction_bg_processed(self, processed_df):
        """
        Background thread for running predictions on an already-processed DataFrame.
        The predictions are automatically saved back to the processed file without prompting the user.
        Also computes and saves prediction metrics into model_metrics.json.
        If ground truth is not available or an error occurs during metrics computation,
        a default metrics dictionary is stored.
        """
        try:
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=80))
            self.master.after(0, lambda: self.update_status("Using processed features file. Running predictions..."))

            if not os.path.exists(self.model_path):
                raise FileNotFoundError("No trained model found. Please train a model first.")

            clf, le = load(self.model_path)
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available for prediction."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return

            # Identify feature columns (excluding ground truth and prediction columns).
            feature_cols = [c for c in processed_df.columns if c not in ['Label_Tag', 'Predicted_Data', 'Real_Time']]
            if not feature_cols:
                raise ValueError("No feature columns found in the processed DataFrame.")

            X_pred = processed_df[feature_cols]
            y_pred_numeric = clf.predict(X_pred)
            predictions = le.inverse_transform(y_pred_numeric)
            # Create a new column 'Predicted_Data' with the predictions.
            processed_df['Predicted_Data'] = predictions

            # Compute metrics using the ground truth labels if available.
            if 'Label_Tag' in processed_df.columns and processed_df['Label_Tag'].notna().all():
                try:
                    if processed_df['Label_Tag'].nunique() > 0:
                        # Strip extra whitespace for consistency.
                        y_true_text = processed_df['Label_Tag'].astype(str).str.strip()
                        y_true_numeric = le.transform(y_true_text)
                        acc = accuracy_score(y_true_numeric, y_pred_numeric)
                        y_true_inversed = le.inverse_transform(y_true_numeric)
                        class_report = classification_report(y_true_inversed, predictions, zero_division=0)
                        cm = confusion_matrix(y_true_inversed, predictions, labels=le.classes_)

                        self.model_metrics = {
                            "accuracy": acc,
                            "report": class_report,
                            "cm": cm,
                            "trained_on": os.path.basename(self.processed_file_predict.get())
                        }
                        self.save_metrics_to_file(self.model_metrics)
                    else:
                        raise ValueError("No ground truth labels available for metric computation.")
                except Exception as e:
                    print("Metrics computation error:", e)
                    self.model_metrics = {
                        "accuracy": None,
                        "report": "No ground truth labels provided or error computing metrics.",
                        "cm": None,
                        "trained_on": os.path.basename(self.processed_file_predict.get())
                    }
                    self.save_metrics_to_file(self.model_metrics)
            else:
                self.model_metrics = {
                    "accuracy": None,
                    "report": "No ground truth labels provided for metric computation.",
                    "cm": None,
                    "trained_on": os.path.basename(self.processed_file_predict.get())
                }
                self.save_metrics_to_file(self.model_metrics)

            self.master.after(0, lambda: self.show_metrics_button.config(state=tk.NORMAL))

            # Automatically save predictions to the processed file path.
            save_path = self.processed_file_predict.get()
            if not save_path:
                raise ValueError("No processed file path available to save predictions.")
            processed_df.to_csv(save_path, index=False)
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Predictions automatically saved to {save_path}"))

            self.master.after(0, lambda: self.predict_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Prediction complete!"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Prediction Error", f"Error during prediction: {e}"))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            time.sleep(0.5)
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=0))

    def predict_window_progress_callback(self, current, total):
        """
        Callback to update prediction progress based on window processing progress.
        """
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 80
        self.master.after(0, lambda: self.predict_progress_bar.configure(value=progress))

    def display_metrics(self):
        """
        Display saved model metrics (accuracy, classification report, confusion matrix)
        in a popup window and also save them into model_metrics.json in the same directory as this script.
        """
        if not self.model_metrics:
            messagebox.showwarning("No Metrics", "No metrics found. Make a prediction first.")
            return

        metrics_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_metrics.json")
        try:
            with open(metrics_file, "w") as f:
                serializable_metrics = {}
                for key, value in self.model_metrics.items():
                    if isinstance(value, np.ndarray):
                        serializable_metrics[key] = value.tolist()
                    else:
                        serializable_metrics[key] = value
                json.dump(serializable_metrics, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save metrics to file: {e}")
            return

        acc = self.model_metrics.get('accuracy', None)
        class_report = self.model_metrics.get('report', None)
        cm = self.model_metrics.get('cm', None)
        trained_on = self.model_metrics.get('trained_on', "Unknown file")
        if acc is None and (class_report is None or cm is None):
            simple_message = f"Model was trained on: {trained_on}\nNo prediction metrics available."
            messagebox.showinfo("Metrics", simple_message)
            return

        popup = tk.Toplevel(self.master)
        popup.title("Prediction Metrics")
        popup.geometry("800x600")
        txt = scrolledtext.ScrolledText(popup, width=100, height=30)
        txt.pack(padx=10, pady=10, fill="both", expand=True)
        txt.insert(tk.END, f"Model trained on: {trained_on}\n\n")
        if acc is not None:
            txt.insert(tk.END, f"Accuracy: {acc:.4f}\n\n")
        else:
            txt.insert(tk.END, "Accuracy: N/A\n\n")
        txt.insert(tk.END, "Classification Report:\n")
        txt.insert(tk.END, str(class_report) + "\n")
        txt.insert(tk.END, "Confusion Matrix:\n")
        txt.insert(tk.END, str(cm) + "\n")
        txt.config(state="disabled")

    def show_results_popup(self, accuracy, class_report, cm, title="Results"):
        """
        Create and display a popup window containing the model's prediction metrics.
        """
        popup = tk.Toplevel(self.master)
        popup.title(title)
        popup.geometry("800x600")
        txt = scrolledtext.ScrolledText(popup, width=100, height=30)
        txt.pack(padx=10, pady=10, fill="both", expand=True)
        trained_on_file = self.model_metrics.get('trained_on', "Unknown")
        txt.insert(tk.END, f"Model trained on: {trained_on_file}\n\n")
        txt.insert(tk.END, f"Accuracy: {accuracy:.4f}\n\n")
        txt.insert(tk.END, "Classification Report:\n")
        txt.insert(tk.END, class_report + "\n")
        txt.insert(tk.END, "Confusion Matrix:\n")
        txt.insert(tk.END, str(cm) + "\n")
        txt.config(state="disabled")

    def get_serial_ports(self):
        """
        Retrieve a list of available serial ports on the system.
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_rt_ports(self):
        """
        Refresh the list of available serial ports and update the dropdown menu.
        """
        ports = self.get_serial_ports()
        menu = self.rt_port_dropdown["menu"]
        menu.delete(0, "end")
        for p in ports:
            menu.add_command(label=p, command=lambda val=p: self.rt_port_var.set(val))
        if ports:
            self.rt_port_var.set(ports[0])
        else:
            self.rt_port_var.set("")
        self.update_status(f"Ports refreshed. Available ports: {', '.join(ports) if ports else 'None'}")

    def rt_connect_serial(self):
        """
        Connect to the selected serial port for real-time predictions.
        Updates UI elements based on connection status.
        """
        if not self.rt_port_var.get():
            self.update_status("No serial port selected for real-time predictions.")
            messagebox.showwarning("Warning", "No serial port selected for real-time predictions.")
            return
        try:
            self.rt_serial_port = serial.Serial(self.rt_port_var.get(), 115200, timeout=1)
            time.sleep(2)
            self.rt_connected = True
            self.update_status(f"Connected to {self.rt_port_var.get()} for real-time predictions.")
            self.rt_connect_button.config(state=tk.DISABLED)
            self.rt_disconnect_button.config(state=tk.NORMAL)
            self.rt_start_button.config(state=tk.NORMAL)
        except serial.SerialException as e:
            self.update_status(f"RT Connection Error: {str(e)}")
            messagebox.showerror("Connection Error", f"Failed to connect to {self.rt_port_var.get()}.\nError: {str(e)}")

    def rt_disconnect_serial(self):
        """
        Disconnect from the serial port. Stops real-time predictions if running and resets UI elements.
        """
        if self.rt_serial_port and self.rt_serial_port.is_open:
            if self.rt_logging:
                self.rt_stop_predictions()
            self.rt_stop_event.set()
            self.rt_serial_port.close()
            self.rt_connected = False
            self.update_status("RT serial port disconnected.")
            self.rt_connect_button.config(state=tk.NORMAL)
            self.rt_disconnect_button.config(state=tk.DISABLED)
            self.rt_start_button.config(state=tk.DISABLED)
            self.rt_stop_button.config(state=tk.DISABLED)

    def rt_start_predictions(self):
        """
        Start real-time predictions by sending the start command to the serial device,
        clearing previous data, and launching a background thread to read serial data.
        """
        if not self.rt_connected:
            messagebox.showwarning("Warning", "Not connected to any port.")
            return
        if not os.path.exists(self.model_path):
            messagebox.showwarning("Warning", "No trained model available. Train a model first.")
            return
        self.rt_send_command("START")
        self.rt_logging = True
        self.rt_stop_event.clear()
        self.rt_stop_button.config(state=tk.NORMAL)
        self.rt_start_button.config(state=tk.DISABLED)
        self.update_status("Real-time predictions started.")
        self.rt_data_buffer.clear()
        self.rt_data_display.config(state='normal')
        self.rt_data_display.delete('1.0', tk.END)
        self.rt_data_display.config(state='disabled')
        self.rt_read_thread = threading.Thread(target=self.rt_read_serial_data, daemon=True)
        self.rt_read_thread.start()

    def rt_stop_predictions(self):
        """
        Stop real-time predictions by sending the stop command to the serial device and updating the UI.
        """
        self.rt_logging = False
        self.rt_stop_event.set()
        self.rt_stop_button.config(state=tk.DISABLED)
        self.rt_start_button.config(state=tk.NORMAL)
        self.update_status("Real-time predictions stopped.")
        self.rt_send_command("STOP")

    def rt_send_command(self, command):
        """
        Send a command (e.g., START or STOP) to the serial device.
        """
        if self.rt_serial_port and self.rt_serial_port.is_open:
            try:
                self.rt_serial_port.write(f"{command}\n".encode())
                self.update_status(f"Sent command: {command}")
            except serial.SerialException as e:
                self.update_status(f"Serial Communication Error: {str(e)}")
                messagebox.showerror("Communication Error", f"Failed to send command.\nError: {str(e)}")

    def rt_read_serial_data(self):
        """
        Continuously read serial data from the connected device.
        Buffer and process data in batches, perform predictions on the data,
        and update the UI with sensor output and current prediction.
        """
        buffer = ""
        start_time = None
        try:
            batch_length = float(self.batch_length_var.get())
        except ValueError:
            batch_length = 5
        processor = DataProcessor()
        selected_features = list(processor.features.keys())
        columns = [
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
        expected_col_count = len(columns)
        non_numeric_cols = ["Real_Time", "Label_Tag", "HeaterProfile_ID"]
        for sn in range(1, 9):
            non_numeric_cols.append(f"Sensor{sn}_Status")
        numeric_cols = [c for c in columns if c not in non_numeric_cols]
        try:
            clf, le = load(self.model_path)
        except:
            self.update_status("No model file found for real-time predictions.")
            return
        while not self.rt_stop_event.is_set():
            if self.rt_serial_port and self.rt_serial_port.in_waiting > 0:
                try:
                    byte_data = self.rt_serial_port.read(self.rt_serial_port.in_waiting)
                    buffer += byte_data.decode(errors='ignore')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue
                        self.rt_data_display.config(state='normal')
                        self.rt_data_display.insert(tk.END, line + "\n")
                        self.rt_data_display.yview(tk.END)
                        self.rt_data_display.config(state='disabled')
                        csv_reader = csv.reader(StringIO(line))
                        parsed = next(csv_reader, None)
                        if not parsed:
                            continue
                        if len(parsed) == expected_col_count - 1:
                            real_time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                            parsed = [real_time_str] + parsed
                        elif len(parsed) != expected_col_count:
                            continue
                        try:
                            row_df = pd.DataFrame([parsed], columns=columns)
                            for col in numeric_cols:
                                row_df[col] = pd.to_numeric(row_df[col], errors='coerce')
                        except:
                            continue
                        self.rt_data_buffer.append(row_df)
                        if start_time is None:
                            start_time = time.time()
                        elapsed = time.time() - start_time
                        remain = max(0, round(batch_length - elapsed))
                        self.time_left_var.set(str(remain))
                        if elapsed >= batch_length:
                            batch_df = pd.concat(self.rt_data_buffer, ignore_index=True)
                            self.rt_data_buffer.clear()
                            start_time = time.time()
                            self.time_left_var.set(str(int(batch_length)))
                            try:
                                try:
                                    window_length = int(self.window_length_var.get())
                                except ValueError:
                                    window_length = WINDOW_SIZE
                                try:
                                    stride = int(self.stride_length_var.get())
                                except ValueError:
                                    stride = STRIDE
                                features_df = processor.process_batch(
                                    batch_df,
                                    window_size=window_length,
                                    stride=stride,
                                    selected_features=selected_features
                                )
                                if not features_df.empty:
                                    feature_cols_batch = [c for c in features_df.columns if c not in ['Label_Tag', 'Real_Time']]
                                    preds_numeric = clf.predict(features_df[feature_cols_batch])
                                    final_pred_list = le.inverse_transform(preds_numeric)
                                    try:
                                        final_pred = mode(final_pred_list)
                                    except:
                                        values, counts = np.unique(final_pred_list, return_counts=True)
                                        final_pred = values[np.argmax(counts)]
                                    self.current_prediction.set(str(final_pred))
                                else:
                                    self.current_prediction.set("No features extracted")
                            except Exception as ex:
                                import traceback
                                traceback.print_exc()
                                self.update_status(f"Batch processing error: {ex}")
                except serial.SerialException:
                    self.update_status("Serial Communication Error: Connection lost.")
                    messagebox.showerror("Communication Error", "Serial Communication Error: Connection lost.")
                    break

    def update_status(self, message):
        """
        Update the status message displayed in the terminal updates frame.
        """
        self.status.set(message)

    def mainloop(self):
        """
        Start the main tkinter event loop.
        """
        self.master.mainloop()

def main():
    """
    Entry point of the application. Creates the main window and starts the GUI.
    """
    root = tk.Tk()
    app = ModelTrainerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
