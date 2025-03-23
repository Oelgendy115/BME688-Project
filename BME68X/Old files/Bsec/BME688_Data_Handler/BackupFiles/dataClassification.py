# classification.py

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import os
import pandas as pd
import json
from joblib import dump, load
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
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

from dataProcessor import DataProcessor, FEATURES

METRICS_FILE = "model_metrics.json"

WINDOW_SIZE = 5
STRIDE = 1
MAX_WINDOW = 10

class ModelTrainerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Data Classification GUI")
        self.master.geometry("1000x700")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        self.raw_data_file = tk.StringVar()
        self.status = tk.StringVar(value="Status: Idle")
        self.prediction_file = tk.StringVar()
        self.model_path = "data_classifier_model.joblib"
        self.model_exists = os.path.exists(self.model_path)
        self.rt_serial_port = None
        self.rt_connected = False
        self.rt_logging = False
        self.rt_stop_event = threading.Event()
        self.rt_data_buffer = []
        self.batch_length_var = tk.StringVar(value="5")
        self.time_left_var = tk.StringVar(value="0")
        self.current_prediction = tk.StringVar(value="N/A")
        self.model_metrics = None
        self.df_for_training = None

        main_frame = tk.Frame(master)
        main_frame.grid(sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)

        file_frame = tk.LabelFrame(main_frame, text="1. Select Raw Data File for Training", padx=10, pady=10)
        file_frame.grid(row=0, column=0, sticky="ew", pady=5)
        file_frame.columnconfigure(1, weight=1)

        tk.Label(file_frame, text="Raw Data File:").grid(row=0, column=0, sticky="w")
        tk.Entry(file_frame, textvariable=self.raw_data_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(file_frame, text="Browse", command=self.browse_file_train).grid(row=0, column=2, padx=5)

        train_frame = tk.LabelFrame(main_frame, text="2. Train Model", padx=10, pady=10)
        train_frame.grid(row=1, column=0, sticky="ew", pady=5)
        train_frame.columnconfigure(1, weight=1)

        tk.Button(train_frame, text="Train Model", command=self.train_model).grid(row=0, column=0, padx=5, pady=5)
        self.progress_bar = ttk.Progressbar(train_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=0, column=1, padx=10, sticky="ew")
        self.progress_bar["maximum"] = 100
        self.progress_bar.grid_remove()
        self.delete_model_button = tk.Button(train_frame, text="Delete Model", command=self.delete_model)
        self.delete_model_button.grid(row=0, column=2, padx=5, pady=5)
        if self.model_exists:
            self.delete_model_button.config(state=tk.NORMAL)
        else:
            self.delete_model_button.config(state=tk.DISABLED)
        self.show_metrics_button = tk.Button(train_frame, text="Show Metrics", command=self.display_metrics)
        self.show_metrics_button.grid(row=0, column=3, padx=5, pady=5)
        self.show_metrics_button.config(state=tk.NORMAL)
        self.windows_processed_str = tk.StringVar(value="Processed 0 / 0 windows")
        tk.Label(train_frame, textvariable=self.windows_processed_str).grid(row=0, column=4, padx=10, pady=5, sticky="w")

        predict_frame = tk.LabelFrame(main_frame, text="3. Prediction", padx=10, pady=10)
        predict_frame.grid(row=2, column=0, sticky="ew", pady=5)
        predict_frame.columnconfigure(1, weight=1)

        tk.Label(predict_frame, text="Prediction Input File:").grid(row=0, column=0, sticky="w")
        tk.Entry(predict_frame, textvariable=self.prediction_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(predict_frame, text="Browse", command=self.browse_file_predict).grid(row=0, column=2, padx=5)
        tk.Button(predict_frame, text="Predict", command=self.predict_data).grid(row=0, column=3, padx=5)

        rt_frame = tk.LabelFrame(main_frame, text="4. Real-time Predictions", padx=10, pady=10)
        rt_frame.grid(row=3, column=0, sticky="ew", pady=5)
        rt_frame.columnconfigure(1, weight=1)
        rt_frame.columnconfigure(4, weight=1)

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
        tk.Label(rt_frame, text="Batch Length (sec):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(rt_frame, textvariable=self.batch_length_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.rt_start_button = tk.Button(rt_frame, text="Start Predictions", command=self.rt_start_predictions, state=tk.DISABLED, width=15)
        self.rt_start_button.grid(row=1, column=2, padx=5, pady=5)
        self.rt_stop_button = tk.Button(rt_frame, text="Stop Predictions", command=self.rt_stop_predictions, state=tk.DISABLED, width=15)
        self.rt_stop_button.grid(row=1, column=3, padx=5, pady=5)
        tk.Label(rt_frame, text="Seconds left in batch:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Label(rt_frame, textvariable=self.time_left_var, fg="blue").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        rt_data_frame = tk.LabelFrame(rt_frame, text="Sensor Data Output", padx=10, pady=10)
        rt_data_frame.grid(row=3, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        rt_data_frame.columnconfigure(0, weight=1)
        self.rt_data_display = scrolledtext.ScrolledText(rt_data_frame, wrap=tk.WORD, height=5)
        self.rt_data_display.grid(row=0, column=0, sticky="nsew")
        pred_frame = tk.LabelFrame(rt_frame, text="Current Smell Prediction", padx=10, pady=10)
        pred_frame.grid(row=4, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        tk.Label(pred_frame, textvariable=self.current_prediction, fg="blue", font=("Helvetica", 12, "bold")).pack()

        status_frame = tk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=4, column=0, sticky="ew", pady=5)
        status_frame.columnconfigure(0, weight=1)
        self.status_label = tk.Label(status_frame, textvariable=self.status, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.update_status("Ready")
        self.load_metrics_from_file()

    def load_metrics_from_file(self):
        if os.path.exists(METRICS_FILE):
            try:
                with open(METRICS_FILE, "r") as f:
                    loaded_metrics = json.load(f)
                if 'cm' in loaded_metrics:
                    loaded_metrics['cm'] = np.array(loaded_metrics['cm'])
                self.model_metrics = loaded_metrics
                self.show_metrics_button.config(state=tk.NORMAL)
            except Exception:
                self.model_metrics = None

    def save_metrics_to_file(self, metrics):
        try:
            serializable_metrics = {}
            for key, value in metrics.items():
                if isinstance(value, np.ndarray):
                    serializable_metrics[key] = value.tolist()
                else:
                    serializable_metrics[key] = value
            with open(METRICS_FILE, "w") as f:
                json.dump(serializable_metrics, f, indent=4)
        except Exception:
            pass

    def browse_file_train(self):
        filename = filedialog.askopenfilename(
            title="Select Raw Data File for Training",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.raw_data_file.set(filename)

    def browse_file_predict(self):
        filename = filedialog.askopenfilename(
            title="Select Input File for Prediction",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.prediction_file.set(filename)

    def train_model(self):
        if not self.raw_data_file.get():
            messagebox.showerror("Error", "Please select a raw data file first.")
            return
        try:
            processor = DataProcessor()
            self.df_for_training = processor.read_csv(self.raw_data_file.get())
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            return
        try:
            if 'Label_Tag' not in self.df_for_training.columns:
                messagebox.showerror("Error", "No 'Label_Tag' column found.")
                return
            self.df_for_training['Label_Tag'] = self.df_for_training['Label_Tag'].astype(str)
            unique_labels = self.df_for_training['Label_Tag'].unique()
            for label in unique_labels:
                try:
                    float(label)
                    rename = messagebox.askyesno("Numeric Label Detected", f"Label '{label}' is numeric. Rename?")
                    if rename:
                        new_label = simpledialog.askstring("Rename Label", f"Enter new name for label '{label}':")
                        if new_label:
                            self.df_for_training.loc[self.df_for_training['Label_Tag'] == label, 'Label_Tag'] = new_label
                    else:
                        self.df_for_training.loc[self.df_for_training['Label_Tag'] == label, 'Label_Tag'] = str(label)
                except ValueError:
                    pass
        except Exception as e:
            messagebox.showerror("Rename Error", str(e))
            return
        self.update_status("Starting training...")
        self.progress_bar.grid()
        self.progress_bar["value"] = 0
        thread = threading.Thread(target=self.run_training_bg)
        thread.daemon = True
        thread.start()

    def window_progress_callback(self, current, total):
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 40
        self.master.after(0, lambda: self.progress_bar.configure(value=progress))
        self.master.after(0, lambda: self.windows_processed_str.set(f"Processed {current} / {total} windows"))

    def run_training_bg(self):
        try:
            self.master.after(0, lambda: self.update_status("Processing data..."))
            processor = DataProcessor()
            selected_features = list(FEATURES.keys())
            processed_output_path = "processed_features.csv"
            processed_data = processor.process_data(
                self.df_for_training, window_size=WINDOW_SIZE, stride=STRIDE, selected_features=selected_features,
                progress_callback=self.window_progress_callback
            )
            processor.save_output(processed_data, processed_output_path)
            self.master.after(0, lambda: self.update_status("Preparing training data..."))
            
            # Update progress to 45%
            self.master.after(0, lambda: self.progress_bar.configure(value=45))

            processed_df = pd.read_csv(processed_output_path)
            feature_cols = [c for c in processed_df.columns if c != 'Label_Tag']
            X = processed_df[feature_cols]
            y_raw = processed_df['Label_Tag']
            self.le = LabelEncoder()
            y = self.le.fit_transform(y_raw)
            
            # Update progress to 50%
            self.master.after(0, lambda: self.progress_bar.configure(value=50))
            self.master.after(0, lambda: self.update_status("Splitting data..."))
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.3, random_state=42, stratify=y
            )
            
            # Update progress to 60%
            self.master.after(0, lambda: self.progress_bar.configure(value=60))
            self.master.after(0, lambda: self.update_status("Training model..."))
            clf = RandomForestClassifier(random_state=42, class_weight='balanced')
            clf.fit(X_train, y_train)
            
            # Update progress to 80%
            self.master.after(0, lambda: self.progress_bar.configure(value=80))
            self.master.after(0, lambda: self.update_status("Evaluating model..."))
            y_pred = clf.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            y_test_text = self.le.inverse_transform(y_test)
            y_pred_text = self.le.inverse_transform(y_pred)
            class_report = classification_report(y_test_text, y_pred_text, zero_division=0)
            unique_y_test = np.unique(y_test)
            unique_y_pred = np.unique(y_pred)
            if len(unique_y_test) == 1 and len(unique_y_pred) ==1 and unique_y_test[0] == unique_y_pred[0]:
                cm = np.array([[len(y_test)]])
            else:
                cm = confusion_matrix(y_test_text, y_pred_text, labels=self.le.classes_)
            dump((clf, self.le), self.model_path)
            self.model_exists = True
            self.master.after(0, lambda: self.delete_model_button.config(state=tk.NORMAL))
            self.model_metrics = {'accuracy': acc, 'report': class_report, 'cm': cm}
            self.save_metrics_to_file(self.model_metrics)
            self.master.after(0, lambda: self.show_metrics_button.config(state=tk.NORMAL))
            self.master.after(0, lambda: self.update_status("Training Completed!"))
            
            # Finalize progress bar to 100%
            self.master.after(0, lambda: self.progress_bar.configure(value=100))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Training Error", str(e)))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            self.master.after(0, lambda: self.progress_bar.grid_remove())
            self.master.after(0, lambda: self.windows_processed_str.set(f"Processed 0 / 0 windows"))

    def display_metrics(self):
        if not self.model_metrics:
            messagebox.showwarning("No Metrics", "No metrics found. Train a model or load existing metrics.")
            return
        acc = self.model_metrics['accuracy']
        class_report = self.model_metrics['report']
        cm = self.model_metrics['cm']
        self.show_results_popup(acc, class_report, cm, title="Model Metrics")

    def show_results_popup(self, accuracy, class_report, cm, title="Results"):
        popup = tk.Toplevel(self.master)
        popup.title(title)
        popup.geometry("800x600")
        txt = scrolledtext.ScrolledText(popup, width=100, height=30)
        txt.pack(padx=10, pady=10, fill="both", expand=True)
        txt.insert(tk.END, f"Accuracy: {accuracy:.4f}\n\n")
        txt.insert(tk.END, "Classification Report:\n")
        txt.insert(tk.END, class_report + "\n")
        txt.insert(tk.END, "Confusion Matrix:\n")
        txt.insert(tk.END, str(cm) + "\n")
        txt.config(state="disabled")

    def predict_data(self):
        if not self.prediction_file.get():
            messagebox.showerror("Error", "Please select an input file for prediction.")
            return
        self.update_status("Predicting data...")
        self.master.update_idletasks()
        if not os.path.exists(self.model_path):
            messagebox.showerror("Error", "No trained model found. Please train the model first.")
            self.update_status("Idle")
            return
        try:
            clf, le = load(self.model_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load model: {e}")
            self.update_status("Idle")
            return
        try:
            processor = DataProcessor()
            raw_df = processor.read_csv(self.prediction_file.get())
        except Exception as e:
            messagebox.showerror("Error", f"Error reading prediction file: {e}")
            self.update_status("Idle")
            return

        try:
            if 'Label_Tag' in raw_df.columns:
                raw_df['Label_Tag'] = raw_df['Label_Tag'].astype(str)
                unique_labels = raw_df['Label_Tag'].unique()
                for label in unique_labels:
                    try:
                        float(label)
                        rename = messagebox.askyesno("Numeric Label Detected", f"Label '{label}' is numeric. Rename?")
                        if rename:
                            new_label = simpledialog.askstring("Rename Label", f"Enter new name for label '{label}':")
                            if new_label:
                                raw_df.loc[raw_df['Label_Tag'] == label, 'Label_Tag'] = new_label
                        else:
                            raw_df.loc[raw_df['Label_Tag'] == label, 'Label_Tag'] = str(label)
                    except ValueError:
                        pass
        except Exception as e:
            messagebox.showerror("Rename Error", f"Error during renaming: {e}")
            return

        try:
            selected_features = list(FEATURES.keys())
            processed_data = processor.process_data(raw_df, window_size=WINDOW_SIZE, stride=STRIDE, selected_features=selected_features)
            processed_df = pd.DataFrame(processed_data)
            if processed_df.empty:
                messagebox.showwarning("No Data", "No data available for prediction after processing.")
                self.update_status("Idle")
                return
            if 'Predicted_Label' in processed_df.columns:
                processed_df.drop(columns=['Predicted_Label'], inplace=True)
            feature_cols = [c for c in processed_df.columns if c != 'Predicted_Label' and c != 'Label_Tag']
            X_pred = processed_df[feature_cols]
            y_pred_numeric = clf.predict(X_pred)
            predictions = le.inverse_transform(y_pred_numeric)
            processed_df['Predicted_Label'] = predictions
            if 'Label_Tag' in processed_df.columns:
                try:
                    y_true_numeric = le.transform(processed_df['Label_Tag'])
                    acc = accuracy_score(y_true_numeric, y_pred_numeric)
                    y_true_text = le.inverse_transform(y_true_numeric)
                    class_report = classification_report(y_true_text, predictions, zero_division=0)
                    cm = confusion_matrix(y_true_text, predictions, labels=le.classes_)
                    self.show_results_popup(acc, class_report, cm, title="Prediction Results")
                except ValueError:
                    messagebox.showinfo("Info", "Could not compute accuracy. Possibly unseen labels in prediction data.")
            else:
                messagebox.showinfo("Info", "No 'Label_Tag' found. Accuracy cannot be computed.")
            save_path = filedialog.asksaveasfilename(
                title="Save Predictions",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if save_path:
                processed_df.to_csv(save_path, index=False)
                messagebox.showinfo("Success", f"Predictions saved to {save_path}")
            else:
                messagebox.showinfo("Cancelled", "Save operation cancelled.")
            self.update_status("Predictions Complete!")
        except Exception as e:
            messagebox.showerror("Prediction Error", f"Error during prediction: {e}")
            self.update_status("Idle")

    def delete_model(self):
        if self.model_exists and os.path.exists(self.model_path):
            os.remove(self.model_path)
            self.model_exists = False
            self.delete_model_button.config(state=tk.DISABLED)
            self.model_metrics = None
            if os.path.exists(METRICS_FILE):
                os.remove(METRICS_FILE)
            self.update_status("Model and metrics deleted.")
        else:
            messagebox.showwarning("No Model", "No model file found to delete.")

    def update_status(self, message):
        self.status.set(message)

    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_rt_ports(self):
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
        if not self.rt_connected:
            messagebox.showwarning("Warning", "Not connected to any port.")
            return
        if not self.model_exists:
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
        self.rt_logging = False
        self.rt_stop_event.set()
        self.rt_stop_button.config(state=tk.DISABLED)
        self.rt_start_button.config(state=tk.NORMAL)
        self.update_status("Real-time predictions stopped.")
        self.rt_send_command("STOP")

    def rt_send_command(self, command):
        if self.rt_serial_port and self.rt_serial_port.is_open:
            try:
                self.rt_serial_port.write(f"{command}\n".encode())
                self.update_status(f"Sent command: {command}")
            except serial.SerialException as e:
                self.update_status(f"Serial Communication Error: {str(e)}")
                messagebox.showerror("Communication Error", f"Failed to send command.\nError: {str(e)}")

    def rt_read_serial_data(self):
        buffer = ""
        start_time = None
        try:
            batch_length = float(self.batch_length_var.get())
        except ValueError:
            batch_length = 5
        processor = DataProcessor()
        selected_features = list(FEATURES.keys())
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
                                if batch_length >= MAX_WINDOW:
                                    features_df = processor.process_batch(
                                        batch_df, window_size=WINDOW_SIZE, stride=STRIDE, selected_features=selected_features
                                    )
                                else:
                                    single_features = processor.calculate_features(batch_df, selected_features)
                                    features_df = pd.DataFrame([single_features])
                                if not features_df.empty:
                                    feature_cols_batch = [c for c in features_df.columns if c != 'Label_Tag']
                                    preds_numeric = clf.predict(features_df[feature_cols_batch])
                                    try:
                                        final_pred_list = le.inverse_transform(preds_numeric)
                                        final_pred = mode(final_pred_list)
                                    except:
                                        values, counts = np.unique(final_pred_list, return_counts=True)
                                        final_pred = values[np.argmax(counts)]
                                    self.current_prediction.set(str(final_pred))
                                else:
                                    self.current_prediction.set("No features extracted")
                            except Exception:
                                self.update_status("Batch processing error.")
                except serial.SerialException:
                    self.update_status("Serial Communication Error: Connection lost.")
                    messagebox.showerror("Communication Error", "Serial Communication Error: Connection lost.")
                    break

    def mainloop(self):
        self.master.mainloop()

def main():
    root = tk.Tk()
    app = ModelTrainerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
