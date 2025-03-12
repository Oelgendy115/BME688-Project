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
LABEL_ENCODER_PATH = "C:\BME688 Project\BME688_Data_Handler\Label_Encoder.csv"

def calculate_gasresistance_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].mean()

def calculate_gasresistance_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].std()

def calculate_gasresistance_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].min()

def calculate_gasresistance_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].max()

def calculate_temperature_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].mean()

def calculate_temperature_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].std()

def calculate_temperature_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].min()

def calculate_temperature_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].max()

def calculate_pressure_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].mean()

def calculate_pressure_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].std()

def calculate_pressure_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].min()

def calculate_pressure_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].max()

def calculate_humidity_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].mean()

def calculate_humidity_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].std()

def calculate_humidity_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].min()

def calculate_humidity_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].max()

def get_feature_functions(sampling_rate=10.0):
    features = {}
    for sensor_num in range(1, 9):
        features[f'GasResistance_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_mean(batch, sn)
        features[f'GasResistance_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_std(batch, sn)
        features[f'GasResistance_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_min(batch, sn)
        features[f'GasResistance_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_max(batch, sn)

    for sensor_num in range(1, 9):
        features[f'Temperature_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_mean(batch, sn)
        features[f'Temperature_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_std(batch, sn)
        features[f'Temperature_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_min(batch, sn)
        features[f'Temperature_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_max(batch, sn)

    for sensor_num in range(1, 9):
        features[f'Pressure_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_mean(batch, sn)
        features[f'Pressure_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_std(batch, sn)
        features[f'Pressure_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_min(batch, sn)
        features[f'Pressure_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_max(batch, sn)

    for sensor_num in range(1, 9):
        features[f'Humidity_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_mean(batch, sn)
        features[f'Humidity_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_std(batch, sn)
        features[f'Humidity_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_min(batch, sn)
        features[f'Humidity_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_max(batch, sn)

    return features

FEATURES = get_feature_functions(sampling_rate=10.0)


class DataProcessor:
    def __init__(self, label_encoder_path=LABEL_ENCODER_PATH):
        """
        Creates a DataProcessor that will look up numeric Label_Tag values in
        a label encoder CSV. If a new label is encountered, it prompts the user
        for a class name and appends it to the encoder.
        """
        self.output_data = []
        self.label_encoder_path = label_encoder_path
        # Load label encoder
        self.label_mapping = self.load_label_encoder(self.label_encoder_path)

    def load_label_encoder(self, path):
        """
        Loads a CSV file with columns [Label_Tag, Class_name] into a dictionary.
        Keys = Label_Tag (int or str).
        Values = Class_name (str).
        If file is missing or invalid, returns an empty dict.
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
                # Convert to int if possible
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
        Appends a new label -> class_name row to the label encoder CSV file,
        and updates self.label_mapping as well.
        """
        self.label_mapping[raw_label] = new_class_name

        # If the file doesn't exist yet, we create it with a header
        file_exists = os.path.isfile(self.label_encoder_path)
        mode = 'a' if file_exists else 'w'

        with open(self.label_encoder_path, mode, newline='') as f:
            if not file_exists:
                # Write header
                f.write("Label_Tag,Class_name\n")
            # We'll store numeric labels as is, or string if truly not convertible
            f.write(f"{raw_label},{new_class_name}\n")

    def ask_for_new_label_name(self, raw_label):
        """
        If a new numeric or string label is encountered, ask the user for a name via pop-up.
        We rely on the main classification.py to already be running a Tk application.
        """
        parent = tk._default_root if tk._default_root else None

        prompt_text = (
            f"A new label '{raw_label}' was encountered.\n"
            "Please enter a class name for this label, or click Cancel to keep the numeric/string value."
        )
        user_input = simpledialog.askstring("New Label Encountered", prompt_text, parent=parent)
        if not user_input:  # user cancels or no input
            user_input = str(raw_label)

        # Update the label encoder mapping
        self.update_label_encoder(raw_label, user_input)
        return user_input

    def read_csv(self, input_file):
        """
        Reads data from a CSV file. Expects the columns:
          'Real_Time','Timestamp_ms','Label_Tag','HeaterProfile_ID', 
          plus sensor columns like 'Sensor1_Temperature_deg_C' etc.
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
        Raises Exception if missing.
        """
        required_columns = [
            'Real_Time', 'Timestamp_ms', 'Label_Tag', 'HeaterProfile_ID',
        ]
        for sensor_num in range(1, 9):
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

    def process_data(self, df, window_size, stride, selected_features, progress_callback=None):
        """
        Splits data into windows (of 'window_size' seconds) with a stride of 'stride' seconds,
        ensuring each window has only one unique label. If a new label is found, prompts user.
        """
        self.check_required_columns(df)

        df['Real_Time'] = pd.to_datetime(df['Real_Time'], errors='coerce')
        df = df.sort_values('Real_Time').reset_index(drop=True)
        if df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")

        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)

        # Identify blocks separated by > 10s
        df['Time_Diff'] = df['Real_Time'].diff()
        threshold = pd.Timedelta(seconds=10)
        df['Block_ID'] = (df['Time_Diff'] > threshold).cumsum()

        # Count total windows
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

        # Process each block
        for block_id, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start

            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df[(block_df['Real_Time'] >= window_start) &
                                     (block_df['Real_Time'] < window_end)]
                if window_df.empty:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Must have exactly one label in this window
                if window_df['Label_Tag'].nunique() != 1:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Ensure enough rows
                if len(window_df) < window_size:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Convert raw_label to int if possible
                raw_label_str = str(window_df['Label_Tag'].iloc[-1]).strip()
                try:
                    raw_label = int(float(raw_label_str))
                except ValueError:
                    raw_label = raw_label_str  # keep as string if we can't parse

                # Check if in encoder
                if raw_label not in self.label_mapping:
                    # Ask user for a name
                    class_name = self.ask_for_new_label_name(raw_label)
                else:
                    class_name = self.label_mapping[raw_label]

                # Calculate features
                features = self.calculate_features(window_df, selected_features)
                # Store Real_Time of first data point in the window
                features['Real_Time'] = window_df['Real_Time'].iloc[0]
                # Replace numeric label with class name
                features['Label_Tag'] = class_name

                output_data.append(features)

                # Move window
                window_start += stride_td
                windows_processed += 1
                if progress_callback:
                    progress_callback(windows_processed, total_windows)

        self.output_data = output_data
        return output_data

    def process_batch(self, batch_df, window_size, stride, selected_features):
        """
        Similar to process_data, but does not require a progress callback.
        """
        if not isinstance(batch_df, pd.DataFrame):
            raise ValueError("Input batch must be a pandas DataFrame.")

        self.check_required_columns(batch_df)

        batch_df['Real_Time'] = pd.to_datetime(batch_df['Real_Time'], errors='coerce')
        batch_df = batch_df.sort_values('Real_Time').reset_index(drop=True)
        if batch_df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")

        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)

        batch_df['Time_Diff'] = batch_df['Real_Time'].diff()
        threshold = pd.Timedelta(seconds=10)
        batch_df['Block_ID'] = (batch_df['Time_Diff'] > threshold).cumsum()

        total_windows = 0
        for _, block_df2 in batch_df.groupby('Block_ID'):
            block_start = block_df2['Real_Time'].iloc[0]
            block_end = block_df2['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                total_windows += 1
                window_start += stride_td

        output_data = []
        windows_processed = 0

        for block_id, block_df2 in batch_df.groupby('Block_ID'):
            block_start = block_df2['Real_Time'].iloc[0]
            block_end = block_df2['Real_Time'].iloc[-1]
            window_start = block_start

            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df2[(block_df2['Real_Time'] >= window_start) &
                                      (block_df2['Real_Time'] < window_end)]
                if window_df.empty:
                    window_start += stride_td
                    windows_processed += 1
                    continue

                if window_df['Label_Tag'].nunique() != 1:
                    window_start += stride_td
                    windows_processed += 1
                    continue

                if len(window_df) < window_size:
                    window_start += stride_td
                    windows_processed += 1
                    continue

                # Convert label
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

                windows_processed += 1
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
        Runs each feature function in 'selected_features' over the window_df.
        """
        features = {}
        for feature_name in selected_features:
            feature_func = FEATURES.get(feature_name)
            if feature_func:
                try:
                    value = feature_func(window_df)
                    if isinstance(value, float):
                        value = round(value, 2)
                    features[feature_name] = value
                except Exception:
                    features[feature_name] = np.nan
        return features

    def save_output(self, output_data, output_path):
        """
        Saves the final processed data (including replaced Label_Tag) to CSV.
        """
        try:
            output_df = pd.DataFrame(output_data)
            output_df = output_df.round(2)

            if 'Real_Time' in output_df.columns:
                cols = output_df.columns.tolist()
                cols.remove('Real_Time')
                output_df = output_df[['Real_Time'] + cols]

            output_df.to_csv(output_path, index=False, float_format='%.2f')
            print(f"Output saved to {output_path}")
        except Exception as e:
            print(f"Error saving output CSV: {e}")
