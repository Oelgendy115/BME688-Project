# tests/test_classification.py

import pytest
import pandas as pd
import numpy as np
import os
from unittest.mock import patch, MagicMock
from dataProcessor import DataProcessor, FEATURES
from dataClassification import ModelTrainerGUI
import joblib

@pytest.fixture
def sample_dataframe():
    """Fixture to create a sample DataFrame with all required columns."""
    data = {
        'Real_Time': pd.date_range(start='2023-01-01', periods=100, freq='S'),
        'Timestamp_ms': np.arange(100) * 1000,
        'Label_Tag': ['A'] * 100,
        'HeaterProfile_ID': [1] * 100,
    }
    for sensor_num in range(1, 9):
        data[f'Sensor{sensor_num}_Temperature_deg_C'] = np.random.uniform(20, 30, 100)
        data[f'Sensor{sensor_num}_Pressure_Pa'] = np.random.uniform(1000, 1020, 100)
        data[f'Sensor{sensor_num}_Humidity_%'] = np.random.uniform(30, 50, 100)
        data[f'Sensor{sensor_num}_GasResistance_ohm'] = np.random.uniform(1e3, 1e4, 100)
        data[f'Sensor{sensor_num}_Status'] = ['OK'] * 100
        data[f'Sensor{sensor_num}_GasIndex'] = [0] * 100
    df = pd.DataFrame(data)
    return df

@pytest.fixture
def processor():
    """Fixture to create a DataProcessor instance."""
    return DataProcessor()

@pytest.fixture
def gui_instance(monkeypatch):
    """
    Fixture to create a ModelTrainerGUI instance without initializing the actual GUI.
    Mocks Tkinter's StringVar to prevent RuntimeError.
    """
    # Suppress print statements
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
    
    # Mock Tkinter's StringVar
    with patch('classification.tk.StringVar', return_value=MagicMock()):
        root = MagicMock()
        gui = ModelTrainerGUI(root)
        yield gui

def test_train_model(tmp_path, sample_dataframe, gui_instance, monkeypatch):
    """Test the model training process."""
    # Mock the file reading to return the sample dataframe
    with patch.object(gui_instance, 'read_csv', return_value=sample_dataframe):
        # Mock the save_output method to avoid file I/O
        with patch.object(gui_instance, 'save_output') as mock_save_output:
            # Mock user input dialogs to bypass label renaming
            with patch('tkinter.simpledialog.askstring', return_value=None):
                with patch('tkinter.messagebox.askyesno', return_value=False):
                    gui_instance.raw_data_file.set("dummy_path.csv")
                    gui_instance.train_model()
                    # Check if the model file was attempted to be saved
                    mock_save_output.assert_called()
                    # Ensure the model file exists
                    assert os.path.exists(gui_instance.model_path)
                    # Clean up
                    if os.path.exists(gui_instance.model_path):
                        os.remove(gui_instance.model_path)

def test_delete_model(tmp_path, gui_instance):
    """Test deleting the model."""
    # First, create a dummy model file
    with open(gui_instance.model_path, 'w') as f:
        f.write("dummy model content")
    gui_instance.model_exists = True
    # Create a dummy metrics file
    with open("model_metrics.json", 'w') as f:
        f.write("{}")
    # Delete the model
    gui_instance.delete_model()
    # Check if the model file is deleted
    assert not os.path.exists(gui_instance.model_path)
    # Check if the metrics file is deleted
    assert not os.path.exists("model_metrics.json")
    # Check the state
    assert not gui_instance.model_exists

def test_predict_data_without_model(gui_instance, sample_dataframe, tmp_path):
    """Test prediction without a trained model."""
    gui_instance.prediction_file.set("dummy_prediction.csv")
    with patch.object(gui_instance, 'read_csv', return_value=sample_dataframe):
        with patch('tkinter.messagebox.showerror') as mock_showerror:
            gui_instance.predict_data()
            mock_showerror.assert_called_with("Error", "No trained model found. Please train the model first.")

def test_predict_data_with_model(tmp_path, sample_dataframe, gui_instance, monkeypatch):
    """Test the prediction process with a trained model."""
    # First, train a dummy model
    model = MagicMock()
    le = MagicMock()
    model.predict.return_value = np.array([0] * 100)
    le.inverse_transform.return_value = ['A'] * 100
    joblib.dump((model, le), gui_instance.model_path)
    gui_instance.model_exists = True
    gui_instance.le = le
    # Mock the file reading to return the sample dataframe
    with patch.object(gui_instance, 'read_csv', return_value=sample_dataframe):
        # Mock feature processing
        with patch.object(DataProcessor, 'process_data', return_value=[{'Label_Tag': 'A', 'GasResistance_Mean_Sensor1': 5000.0}]):
            # Mock the save dialog
            with patch('tkinter.filedialog.asksaveasfilename', return_value=str(tmp_path / "predictions.csv")):
                gui_instance.prediction_file.set("dummy_prediction.csv")
                with patch.object(gui_instance, 'show_results_popup') as mock_show_results_popup:
                    gui_instance.predict_data()
                    # Check if predictions were attempted
                    mock_show_results_popup.assert_called()
                    # Ensure the predictions file exists
                    assert os.path.exists(tmp_path / "predictions.csv")
                    # Clean up
                    if os.path.exists(gui_instance.model_path):
                        os.remove(gui_instance.model_path)

def test_save_metrics_to_file(gui_instance):
    """Test saving metrics to a file."""
    metrics = {
        'accuracy': 0.95,
        'report': "classification report",
        'cm': np.array([[50, 2], [1, 47]])
    }
    gui_instance.save_metrics_to_file(metrics)
    assert os.path.exists("model_metrics.json")
    # Clean up
    os.remove("model_metrics.json")

def test_load_metrics_from_file(gui_instance, tmp_path):
    """Test loading metrics from a file."""
    metrics = {
        'accuracy': 0.95,
        'report': "classification report",
        'cm': [[50, 2], [1, 47]]
    }
    metrics_file = tmp_path / "model_metrics.json"
    with open(metrics_file, 'w') as f:
        import json
        json.dump(metrics, f)
    with patch('os.path.exists', return_value=True):
        with patch('builtins.open', return_value=open(metrics_file, 'r')):
            gui_instance.load_metrics_from_file()
            assert gui_instance.model_metrics['accuracy'] == 0.95
            assert gui_instance.model_metrics['report'] == "classification report"
            assert gui_instance.model_metrics['cm'] == [[50, 2], [1, 47]]
    # Clean up
    os.remove(metrics_file)
