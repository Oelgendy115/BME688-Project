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

from dataProcessor import DataProcessor

METRICS_FILE = "model_metrics.json"

WINDOW_SIZE = 10
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
        self.processed_features_file = tk.StringVar()
        self.status = tk.StringVar(value="Status: Idle")
        self.prediction_file = tk.StringVar()
        self.processed_file_predict = tk.StringVar()
        self.model_path = "data_classifier_model.joblib"
        self.model_metrics = None
        self.df_for_training = None

        self.rt_serial_port = None
        self.rt_connected = False
        self.rt_logging = False
        self.rt_stop_event = threading.Event()
        self.rt_data_buffer = []
        self.batch_length_var = tk.StringVar(value="5")
        self.time_left_var = tk.StringVar(value="0")
        self.current_prediction = tk.StringVar(value="N/A")
        
        self.window_length_var = tk.StringVar(value=str(WINDOW_SIZE))
        self.stride_length_var = tk.StringVar(value=str(STRIDE))
        self.prediction_stride_length = tk.StringVar(value=str(STRIDE))

        main_frame = tk.Frame(master)
        main_frame.grid(sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)

        ####################################################################
        # 1) TRAIN MODEL FRAME
        ####################################################################
        train_model_frame = tk.LabelFrame(main_frame, text="1. Train Model", padx=10, pady=10)
        train_model_frame.grid(row=0, column=0, sticky="ew", pady=5)
        train_model_frame.columnconfigure(0, weight=0)
        train_model_frame.columnconfigure(1, weight=1)
        train_model_frame.columnconfigure(2, weight=0)

        tk.Label(train_model_frame, text="Raw Data File:").grid(row=0, column=0, sticky="w")
        tk.Entry(train_model_frame, textvariable=self.raw_data_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(train_model_frame, text="Browse", command=self.browse_file_train).grid(row=0, column=2, padx=5)

        tk.Label(train_model_frame, text="Processed Features File:").grid(row=1, column=0, sticky="w")
        tk.Entry(train_model_frame, textvariable=self.processed_features_file).grid(row=1, column=1, padx=5, sticky="ew")
        tk.Button(train_model_frame, text="Browse", command=self.browse_file_processed_features).grid(row=1, column=2, padx=5)

        # Container frame for window and stride inputs and buttons (data interval is fixed in code)
        train_options_frame = tk.Frame(train_model_frame)
        train_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        # Left: window and stride inputs
        ws_frame = tk.Frame(train_options_frame)
        ws_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(ws_frame, text="Window Length:").grid(row=0, column=0, sticky="w")
        tk.Entry(ws_frame, textvariable=self.window_length_var, width=10).grid(row=0, column=1, padx=5, pady=2)
        tk.Label(ws_frame, text="Stride Length:").grid(row=0, column=2, sticky="w")
        tk.Entry(ws_frame, textvariable=self.stride_length_var, width=10).grid(row=0, column=3, padx=5, pady=2)
        # Right: buttons for extract features and train model
        btn_frame = tk.Frame(train_options_frame)
        btn_frame.pack(side=tk.LEFT, padx=5)
        self.extract_features_button = tk.Button(btn_frame, text="Extract Features", command=self.extract_features)
        self.extract_features_button.grid(row=0, column=0, padx=5, pady=5)
        self.train_button = tk.Button(btn_frame, text="Train Model", command=self.train_model)
        self.train_button.grid(row=0, column=1, padx=5, pady=5)

        self.train_progress_bar = ttk.Progressbar(train_model_frame, orient="horizontal", mode="determinate")
        self.train_progress_bar.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        self.train_progress_bar["maximum"] = 100
        self.train_progress_bar["value"] = 0

        ####################################################################
        # 2) MODEL PREDICTION FRAME
        ####################################################################
        predict_frame = tk.LabelFrame(main_frame, text="2. Model Prediction", padx=10, pady=10)
        predict_frame.grid(row=1, column=0, sticky="ew", pady=5)
        predict_frame.columnconfigure(0, weight=0)
        predict_frame.columnconfigure(1, weight=1)
        predict_frame.columnconfigure(2, weight=0)

        tk.Label(predict_frame, text="Prediction Input File:").grid(row=0, column=0, sticky="w")
        tk.Entry(predict_frame, textvariable=self.prediction_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(predict_frame, text="Browse", command=self.browse_file_predict).grid(row=0, column=2, padx=5)

        tk.Label(predict_frame, text="Processed Features File:").grid(row=1, column=0, sticky="w")
        tk.Entry(predict_frame, textvariable=self.processed_file_predict).grid(row=1, column=1, padx=5, sticky="ew")
        tk.Button(predict_frame, text="Browse", command=self.browse_file_processed_features_predict).grid(row=1, column=2, padx=5)

        # Container frame for prediction stride length and buttons
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

        self.predict_progress_bar = ttk.Progressbar(predict_frame, orient="horizontal", mode="determinate")
        self.predict_progress_bar.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        self.predict_progress_bar["maximum"] = 100
        self.predict_progress_bar["value"] = 0

        ####################################################################
        # 3) REAL-TIME PREDICTIONS FRAME
        ####################################################################
        rt_frame = tk.LabelFrame(main_frame, text="3. Real-time Predictions", padx=10, pady=10)
        rt_frame.grid(row=2, column=0, sticky="ew", pady=5)
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

        ####################################################################
        # 4) TERMINAL UPDATES FRAME
        ####################################################################
        status_frame = tk.LabelFrame(main_frame, text="4. Terminal Updates", padx=10, pady=10)
        status_frame.grid(row=3, column=0, sticky="ew", pady=5)
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
                if 'report' in loaded_metrics or 'cm' in loaded_metrics:
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

    def browse_file_processed_features(self):
        filename = filedialog.askopenfilename(
            title="Select Processed Features File",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.processed_features_file.set(filename)

    def browse_file_predict(self):
        filename = filedialog.askopenfilename(
            title="Select Input File for Prediction",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.prediction_file.set(filename)

    def browse_file_processed_features_predict(self):
        filename = filedialog.askopenfilename(
            title="Select Processed Features File for Prediction",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.processed_file_predict.set(filename)

    def extract_features(self):
        if not self.raw_data_file.get():
            messagebox.showerror("Error", "Please select a raw data file first.")
            return
        try:
            # Create a DataProcessor (using its default data_interval)
            processor = DataProcessor()
            df = processor.read_csv(self.raw_data_file.get())
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
                    progress_callback=None
                )
                processed_df = pd.DataFrame(processed_data)
            else:
                processed_df = df.copy()
            if processed_df.empty:
                messagebox.showwarning("No Data", "No data available after processing.")
                return
            save_path = filedialog.asksaveasfilename(
                title="Save Extracted Features",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if save_path:
                processed_df.to_csv(save_path, index=False)
                messagebox.showinfo("Success", f"Extracted features saved to {save_path}")
                self.processed_features_file.set(save_path)
            else:
                messagebox.showinfo("Cancelled", "Save operation cancelled.")
        except Exception as e:
            messagebox.showerror("Error", f"Error during feature extraction: {e}")

    def extract_features_predict(self):
        if not self.prediction_file.get():
            messagebox.showerror("Error", "Please select a prediction input file first.")
            return
        try:
            processor = DataProcessor()
            df = processor.read_csv(self.prediction_file.get())
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
                    progress_callback=None
                )
                processed_df = pd.DataFrame(processed_data)
            else:
                processed_df = df.copy()
            if processed_df.empty:
                messagebox.showwarning("No Data", "No data available after processing.")
                return
            save_path = filedialog.asksaveasfilename(
                title="Save Extracted Features",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if save_path:
                processed_df.to_csv(save_path, index=False)
                messagebox.showinfo("Success", f"Extracted features saved to {save_path}")
                self.processed_file_predict.set(save_path)
            else:
                messagebox.showinfo("Cancelled", "Save operation cancelled.")
        except Exception as e:
            messagebox.showerror("Error", f"Error during feature extraction: {e}")

    def train_model(self):
        if not self.raw_data_file.get():
            messagebox.showerror("Error", "Please select a raw data file first.")
            return
        if os.path.exists(self.model_path):
            os.remove(self.model_path)
        if os.path.exists(METRICS_FILE):
            os.remove(METRICS_FILE)
        self.model_metrics = None
        self.update_status("Reading training file...")
        self.train_progress_bar["value"] = 0
        self.master.update_idletasks()
        try:
            processor = DataProcessor()
            df_for_training = processor.read_csv(self.raw_data_file.get())
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            self.update_status("Idle")
            return
        self.update_status("Processing data...")
        thread = threading.Thread(target=self.run_training_bg, args=(df_for_training,))
        thread.daemon = True
        thread.start()

    def run_training_bg(self, df_for_training):
        try:
            processor = DataProcessor()
            selected_features = list(processor.features.keys())
            try:
                window_length = int(self.window_length_var.get())
            except ValueError:
                window_length = WINDOW_SIZE
            try:
                stride = int(self.stride_length_var.get())
            except ValueError:
                stride = STRIDE
            lower_cols = [col.lower() for col in df_for_training.columns]
            if ('timestamp_ms' in lower_cols) and ('sensor1_temperature_deg_c' in lower_cols):
                self.master.after(0, lambda: self.update_status("Raw file detected. Processing data..."))
                processed_data = processor.process_data(
                    df_for_training,
                    window_size=window_length,
                    stride=stride,
                    selected_features=selected_features,
                    progress_callback=self.train_window_progress_callback
                )
                self.master.after(0, lambda: self.train_progress_bar.configure(value=80))
                self.master.after(0, lambda: self.update_status("Data processing completed. Training model..."))
                processed_df = pd.DataFrame(processed_data)
            else:
                self.master.after(0, lambda: self.update_status("Processed file detected. Skipping window processing..."))
                processed_df = df_for_training.copy()
                self.master.after(0, lambda: self.train_progress_bar.configure(value=80))
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available to train on."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return
            os.makedirs("Processed_Data", exist_ok=True)
            processed_file_path = os.path.join("Processed_Data", "processed_data.csv")
            processed_df.to_csv(processed_file_path, index=False)
            print(f"Saved processed features to: {processed_file_path}")
            feature_cols = [c for c in processed_df.columns if c not in ['Label_Tag', 'Real_Time']]
            X = processed_df[feature_cols]
            y_raw = processed_df['Label_Tag']
            self.le = LabelEncoder()
            y = self.le.fit_transform(y_raw)
            classes = np.unique(y)
            weights = compute_class_weight(class_weight='balanced', classes=classes, y=y)
            weight_dict = dict(zip(classes, weights))
            sample_weights = np.array([weight_dict[label] for label in y])
            clf = RandomForestClassifier(random_state=42)
            clf.fit(X, y, sample_weight=sample_weights)
            dump((clf, self.le), self.model_path)
            label_info = {}
            for label_val, group_df in processed_df.groupby('Label_Tag'):
                total_windows = len(group_df)
                label_info[label_val] = {'total_windows': total_windows}
            self.model_metrics = {
                "trained_on": os.path.basename(self.raw_data_file.get()),
                "label_info": label_info
            }
            self.save_metrics_to_file(self.model_metrics)
            self.master.after(0, lambda: self.train_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status(f"Training complete. Model saved. Trained on {os.path.basename(self.raw_data_file.get())}"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Training Error", str(e)))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            time.sleep(0.5)
            self.master.after(0, lambda: self.train_progress_bar.configure(value=0))

    def train_window_progress_callback(self, current, total):
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 80
        self.master.after(0, lambda: self.train_progress_bar.configure(value=progress))

    def predict_data(self):
        if not self.prediction_file.get() and not self.processed_file_predict.get():
            messagebox.showerror("Error", "Please select an input file for prediction or a processed features file.")
            return
        self.predict_progress_bar["value"] = 0
        self.update_status("Preparing to predict...")
        self.master.update_idletasks()
        if not os.path.exists(self.model_path):
            messagebox.showerror("Error", "No trained model found. Please train a model first.")
            self.update_status("Idle")
            return
        try:
            clf, le = load(self.model_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load model: {e}")
            self.update_status("Idle")
            return
        if self.processed_file_predict.get():
            try:
                processed_df = pd.read_csv(self.processed_file_predict.get())
            except Exception as e:
                messagebox.showerror("Error", f"Error reading processed features file: {e}")
                self.update_status("Idle")
                return
            thread = threading.Thread(target=self.run_prediction_bg_processed, args=(processed_df, clf, le))
            thread.daemon = True
            thread.start()
        else:
            try:
                processor = DataProcessor()
                raw_df = processor.read_csv(self.prediction_file.get())
            except Exception as e:
                messagebox.showerror("Error", f"Error reading prediction file: {e}")
                self.update_status("Idle")
                return
            thread = threading.Thread(target=self.run_prediction_bg, args=(raw_df, clf, le))
            thread.daemon = True
            thread.start()

    def run_prediction_bg(self, raw_df, clf, le):
        try:
            self.master.after(0, lambda: self.update_status("Processing data for prediction..."))
            processor = DataProcessor()
            selected_features = list(processor.features.keys())
            try:
                window_length = int(self.window_length_var.get())
            except ValueError:
                window_length = WINDOW_SIZE
            try:
                stride = int(self.prediction_stride_length.get())
            except ValueError:
                stride = STRIDE
            processed_data = processor.process_data(
                raw_df,
                window_size=window_length,
                stride=stride,
                selected_features=selected_features,
                progress_callback=self.predict_window_progress_callback
            )
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=80))
            self.master.after(0, lambda: self.update_status("Data processed. Running predictions..."))
            processed_df = pd.DataFrame(processed_data)
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available for prediction after processing."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return
            feature_cols = [c for c in processed_df.columns if c not in ['Label_Tag', 'Predicted_Label', 'Real_Time']]
            X_pred = processed_df[feature_cols]
            y_pred_numeric = clf.predict(X_pred)
            predictions = le.inverse_transform(y_pred_numeric)
            processed_df['Predicted_Label'] = predictions
            if 'Label_Tag' in processed_df.columns:
                try:
                    y_true_text = processed_df['Label_Tag']
                    y_true_numeric = le.transform(y_true_text)
                    acc = accuracy_score(y_true_numeric, y_pred_numeric)
                    y_true_inversed = le.inverse_transform(y_true_numeric)
                    class_report = classification_report(y_true_inversed, predictions, zero_division=0)
                    cm = confusion_matrix(y_true_inversed, predictions, labels=le.classes_)
                    if not self.model_metrics:
                        self.model_metrics = {}
                    self.model_metrics['accuracy'] = acc
                    self.model_metrics['report'] = class_report
                    self.model_metrics['cm'] = cm
                    self.save_metrics_to_file(self.model_metrics)
                    self.master.after(0, lambda: self.show_metrics_button.config(state=tk.NORMAL))
                except Exception:
                    pass
            save_path = filedialog.asksaveasfilename(
                title="Save Predictions",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if save_path:
                processed_df.to_csv(save_path, index=False)
                self.master.after(0, lambda: messagebox.showinfo("Success", f"Predictions saved to {save_path}"))
            else:
                self.master.after(0, lambda: messagebox.showinfo("Cancelled", "Save operation cancelled."))
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Prediction complete!"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Prediction Error", f"Error during prediction: {e}"))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            time.sleep(0.5)
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=0))

    def run_prediction_bg_processed(self, processed_df, clf, le):
        try:
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=80))
            self.master.after(0, lambda: self.update_status("Using processed features file. Running predictions..."))
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available for prediction."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return
            feature_cols = [c for c in processed_df.columns if c not in ['Label_Tag', 'Predicted_Label', 'Real_Time']]
            X_pred = processed_df[feature_cols]
            y_pred_numeric = clf.predict(X_pred)
            predictions = le.inverse_transform(y_pred_numeric)
            processed_df['Predicted_Label'] = predictions
            if 'Label_Tag' in processed_df.columns:
                try:
                    y_true_text = processed_df['Label_Tag']
                    y_true_numeric = le.transform(y_true_text)
                    acc = accuracy_score(y_true_numeric, y_pred_numeric)
                    y_true_inversed = le.inverse_transform(y_true_numeric)
                    class_report = classification_report(y_true_inversed, predictions, zero_division=0)
                    cm = confusion_matrix(y_true_inversed, predictions, labels=le.classes_)
                    if not self.model_metrics:
                        self.model_metrics = {}
                    self.model_metrics['accuracy'] = acc
                    self.model_metrics['report'] = class_report
                    self.model_metrics['cm'] = cm
                    self.save_metrics_to_file(self.model_metrics)
                    self.master.after(0, lambda: self.show_metrics_button.config(state=tk.NORMAL))
                except Exception:
                    pass
            save_path = filedialog.asksaveasfilename(
                title="Save Predictions",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if save_path:
                processed_df.to_csv(save_path, index=False)
                self.master.after(0, lambda: messagebox.showinfo("Success", f"Predictions saved to {save_path}"))
            else:
                self.master.after(0, lambda: messagebox.showinfo("Cancelled", "Save operation cancelled."))
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Prediction complete!"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Prediction Error", f"Error during prediction: {e}"))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            time.sleep(0.5)
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=0))

    def predict_window_progress_callback(self, current, total):
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 80
        self.master.after(0, lambda: self.predict_progress_bar.configure(value=progress))

    def display_metrics(self):
        if not self.model_metrics:
            messagebox.showwarning("No Metrics", "No metrics found. Make a prediction first.")
            return
        acc = self.model_metrics.get('accuracy', None)
        class_report = self.model_metrics.get('report', None)
        cm = self.model_metrics.get('cm', None)
        if (acc is None) or (class_report is None) or (cm is None):
            trained_on = self.model_metrics.get('trained_on', "Unknown file")
            simple_message = f"Model was trained on: {trained_on}\nNo prediction metrics available."
            messagebox.showinfo("Metrics", simple_message)
            return
        self.show_results_popup(acc, class_report, cm, title="Prediction Metrics")

    def show_results_popup(self, accuracy, class_report, cm, title="Results"):
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
        # Create a DataProcessor using default settings
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
        self.status.set(message)

    def mainloop(self):
        self.master.mainloop()

def main():
    root = tk.Tk()
    app = ModelTrainerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
