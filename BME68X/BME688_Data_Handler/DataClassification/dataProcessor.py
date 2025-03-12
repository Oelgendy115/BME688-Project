import numpy as np
import pandas as pd
import os
import tkinter as tk
from tkinter import simpledialog
from scipy.fft import fft, fftfreq
from scipy.stats import entropy

###############################################################################
# GLOBAL VARIABLE FOR LABEL ENCODER CSV PATH
###############################################################################
LABEL_ENCODER_PATH = r"/Users/omarelgendy/Documents/BME688-Project/BME68X/BME688_Data_Handler/Label_Encoder.csv"

def make_feature_func(column, func):
    """
    Returns a feature function that computes a statistic on a given column.
    """
    def feature_func(batch):
        try:
            result = func(batch[column])
            # If the result is a float, round it to 2 decimals
            if isinstance(result, (float, np.floating)):
                return round(result, 2)
            return result
        except Exception:
            return np.nan
    return feature_func

def get_feature_functions(data_interval=3, sensor_count=8):
    """
    Dynamically creates feature functions for each sensor and measurement type.
    This mapping makes it simple to add or remove features.
    
    Parameters:
      data_interval: Expected interval between data points (in seconds). [Not used in
                     computation here but can be used for further customizations.]
      sensor_count: Number of sensors to process.
      
    Returns:
      A dictionary where keys are feature names and values are functions that take a 
      DataFrame window and return the computed value.
    """
    features = {}
    # Map measurement type to its column suffix and the functions to compute
    measurement_map = {
        "GasResistance": ("GasResistance_ohm", np.mean, np.std, np.min, np.max),
        "Temperature":   ("Temperature_deg_C", np.mean, np.std, np.min, np.max),
        "Pressure":      ("Pressure_Pa", np.mean, np.std, np.min, np.max),
        "Humidity":      ("Humidity_%", np.mean, np.std, np.min, np.max)
    }
    stat_names = ["Mean", "StdDev", "Min", "Max"]
    
    for sensor_num in range(1, sensor_count + 1):
        for measurement, (col_suffix, mean_func, std_func, min_func, max_func) in measurement_map.items():
            funcs = {"Mean": mean_func, "StdDev": std_func, "Min": min_func, "Max": max_func}
            for stat, func in funcs.items():
                col_name = f"Sensor{sensor_num}_{col_suffix}"
                feature_name = f"{measurement}_{stat}_Sensor{sensor_num}"
                features[feature_name] = make_feature_func(col_name, func)
    return features

class DataProcessor:
    def __init__(self, label_encoder_path=LABEL_ENCODER_PATH, features=None, sensor_count=8, data_interval=3):
        """
        Initializes the DataProcessor with a label encoder and feature functions.
        
        Parameters:
          label_encoder_path: Path to the label encoder CSV.
          features: A dictionary of feature functions. If None, uses the default ones.
          sensor_count: Number of sensors.
          data_interval: Expected data interval in seconds (default is 3 sec).
        """
        self.output_data = []
        self.label_encoder_path = label_encoder_path
        self.label_mapping = self.load_label_encoder(self.label_encoder_path)
        self.sensor_count = sensor_count
        self.data_interval = data_interval
        # Use provided feature functions or build default ones dynamically.
        self.features = features if features is not None else get_feature_functions(data_interval, sensor_count)
    
    def load_label_encoder(self, path):
        """
        Loads the label encoder CSV (with columns: Label_Tag, Class_name) into a dictionary.
        """
        label_dict = {}
        if not os.path.isfile(path):
            print(f"Label encoder file not found: {path} -- will create one on new label.")
            return label_dict

        try:
            df_encoder = pd.read_csv(path)
            for _, row in df_encoder.iterrows():
                raw_tag = row['Label_Tag']
                class_name = row['Class_name']
                try:
                    raw_tag = int(float(raw_tag))
                except ValueError:
                    pass
                label_dict[raw_tag] = str(class_name)
        except Exception as e:
            print(f"Could not load label encoder from {path}: {e}")
        return label_dict

    def update_label_encoder(self, raw_label, new_class_name):
        """
        Appends a new label mapping to the encoder CSV and updates the in-memory mapping.
        """
        self.label_mapping[raw_label] = new_class_name
        file_exists = os.path.isfile(self.label_encoder_path)
        mode = 'a' if file_exists else 'w'
        with open(self.label_encoder_path, mode, newline='') as f:
            if not file_exists:
                f.write("Label_Tag,Class_name\n")
            f.write(f"{raw_label},{new_class_name}\n")

    def ask_for_new_label_name(self, raw_label):
        """
        Prompts the user to provide a new label name for an unknown Label_Tag.
        """
        parent = tk._default_root if tk._default_root else None
        prompt_text = (
            f"A new label '{raw_label}' was encountered.\n"
            "Please enter a class name for this label, or click Cancel to keep the numeric/string value."
        )
        user_input = simpledialog.askstring("New Label Encountered", prompt_text, parent=parent)
        if not user_input:
            user_input = str(raw_label)
        self.update_label_encoder(raw_label, user_input)
        return user_input

    def read_csv(self, input_file):
        """
        Reads data from a CSV file.
        Expects columns:
         'Real_Time','Timestamp_ms','Label_Tag','HeaterProfile_ID', plus sensor columns.
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"Input CSV not found: {input_file}")
        try:
            df = pd.read_csv(input_file)
            print(f"Read {len(df)} rows from {input_file}")
            return df
        except Exception as e:
            raise Exception(f"Error reading CSV file: {e}")

    def check_required_columns(self, df):
        """
        Ensures the CSV has the minimal required columns.
        """
        required_columns = [
            'Real_Time', 'Timestamp_ms', 'Label_Tag', 'HeaterProfile_ID',
        ]
        for sensor_num in range(1, self.sensor_count + 1):
            required_columns.extend([
                f'Sensor{sensor_num}_Temperature_deg_C',
                f'Sensor{sensor_num}_Pressure_Pa',
                f'Sensor{sensor_num}_Humidity_%',
                f'Sensor{sensor_num}_GasResistance_ohm',
                f'Sensor{sensor_num}_Status',
                f'Sensor{sensor_num}_GasIndex',
            ])
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise Exception(f"Missing columns in CSV: {missing_columns}")

    def process_data(self, df, window_size, stride, selected_features, data_interval=None, gap_threshold=None, progress_callback=None):
        """
        Splits data into sliding time windows (of window_size seconds) with a stride of stride seconds.
        Uses timestamps (Real_Time) so it is independent of how many rows are present.
        
        Parameters:
          df: Input DataFrame.
          window_size: Window size in seconds.
          stride: Stride length in seconds.
          selected_features: List of feature names to compute.
          data_interval: Expected data interval in seconds (overrides default if provided).
          gap_threshold: Maximum allowed gap to continue a block (in seconds). If not provided, set as data_interval * 3.
          progress_callback: Optional callback for progress tracking.
        """
        self.check_required_columns(df)
        df['Real_Time'] = pd.to_datetime(df['Real_Time'], errors='coerce')
        df = df.sort_values('Real_Time').reset_index(drop=True)
        if df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")

        # Use provided data_interval or default value
        current_data_interval = data_interval if data_interval is not None else self.data_interval
        # Define gap threshold dynamically if not provided (e.g., 3 times the expected interval)
        if gap_threshold is None:
            gap_threshold = pd.Timedelta(seconds=current_data_interval * 3)
        else:
            gap_threshold = pd.Timedelta(seconds=gap_threshold)

        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)

        # Identify blocks where time difference exceeds gap_threshold
        df['Time_Diff'] = df['Real_Time'].diff()
        df['Block_ID'] = (df['Time_Diff'] > gap_threshold).cumsum()

        # Count total windows for optional progress reporting
        total_windows = 0
        for _, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                total_windows += 1
                window_start += stride_td

        output_data = []
        windows_processed = 0

        for _, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start

            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df[(block_df['Real_Time'] >= window_start) &
                                     (block_df['Real_Time'] < window_end)]
                # If the window is empty, skip
                if window_df.empty:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Ensure the window has a consistent label
                if window_df['Label_Tag'].nunique() != 1:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Optionally, check if the window covers a near-complete duration (e.g., at least 80% of the window)
                actual_duration = (window_df['Real_Time'].iloc[-1] - window_df['Real_Time'].iloc[0]).total_seconds()
                if actual_duration < window_size * 0.8:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Process the label (convert to int if possible)
                raw_label_str = str(window_df['Label_Tag'].iloc[-1]).strip()
                try:
                    raw_label = int(float(raw_label_str))
                except ValueError:
                    raw_label = raw_label_str

                if raw_label not in self.label_mapping:
                    class_name = self.ask_for_new_label_name(raw_label)
                else:
                    class_name = self.label_mapping[raw_label]

                features = self.calculate_features(window_df, selected_features)
                features['Real_Time'] = window_df['Real_Time'].iloc[0]
                features['Label_Tag'] = class_name
                output_data.append(features)

                window_start += stride_td
                windows_processed += 1
                if progress_callback:
                    progress_callback(windows_processed, total_windows)

        self.output_data = output_data
        return output_data

    def process_batch(self, batch_df, window_size, stride, selected_features, data_interval=None, gap_threshold=None):
        """
        Similar to process_data but without a progress callback.
        """
        self.check_required_columns(batch_df)
        batch_df['Real_Time'] = pd.to_datetime(batch_df['Real_Time'], errors='coerce')
        batch_df = batch_df.sort_values('Real_Time').reset_index(drop=True)
        if batch_df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")

        current_data_interval = data_interval if data_interval is not None else self.data_interval
        if gap_threshold is None:
            gap_threshold = pd.Timedelta(seconds=current_data_interval * 3)
        else:
            gap_threshold = pd.Timedelta(seconds=gap_threshold)

        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)

        batch_df['Time_Diff'] = batch_df['Real_Time'].diff()
        batch_df['Block_ID'] = (batch_df['Time_Diff'] > gap_threshold).cumsum()

        output_data = []
        for _, block_df in batch_df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start

            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df[(block_df['Real_Time'] >= window_start) &
                                     (block_df['Real_Time'] < window_end)]
                if window_df.empty:
                    window_start += stride_td
                    continue

                if window_df['Label_Tag'].nunique() != 1:
                    window_start += stride_td
                    continue

                actual_duration = (window_df['Real_Time'].iloc[-1] - window_df['Real_Time'].iloc[0]).total_seconds()
                if actual_duration < window_size * 0.8:
                    window_start += stride_td
                    continue

                raw_label_str = str(window_df['Label_Tag'].iloc[-1]).strip()
                try:
                    raw_label = int(float(raw_label_str))
                except ValueError:
                    raw_label = raw_label_str

                if raw_label not in self.label_mapping:
                    class_name = self.ask_for_new_label_name(raw_label)
                else:
                    class_name = self.label_mapping[raw_label]

                features = self.calculate_features(window_df, selected_features)
                features['Real_Time'] = window_df['Real_Time'].iloc[0]
                features['Label_Tag'] = class_name
                output_data.append(features)
                window_start += stride_td

        if output_data:
            df_out = pd.DataFrame(output_data).round(2)
            if 'Real_Time' in df_out.columns:
                cols = df_out.columns.tolist()
                cols.remove('Real_Time')
                df_out = df_out[['Real_Time'] + cols]
            return df_out
        else:
            return pd.DataFrame()

    def calculate_features(self, window_df, selected_features):
        """
        Computes each feature listed in selected_features on the given window of data.
        """
        features = {}
        for feature_name in selected_features:
            feature_func = self.features.get(feature_name)
            if feature_func:
                try:
                    value = feature_func(window_df)
                    features[feature_name] = value
                except Exception:
                    features[feature_name] = np.nan
        return features

    def save_output(self, output_data, output_path):
        """
        Saves the processed output data (with replaced Label_Tag) to a CSV file.
        """
        try:
            output_df = pd.DataFrame(output_data).round(2)
            if 'Real_Time' in output_df.columns:
                cols = output_df.columns.tolist()
                cols.remove('Real_Time')
                output_df = output_df[['Real_Time'] + cols]
            output_df.to_csv(output_path, index=False, float_format='%.2f')
            print(f"Output saved to {output_path}")
        except Exception as e:
            print(f"Error saving output CSV: {e}")
