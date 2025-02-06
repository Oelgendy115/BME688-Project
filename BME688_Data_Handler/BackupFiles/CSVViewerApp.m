classdef CSVViewerApp < matlab.apps.AppBase

    % Properties that correspond to app components
    properties (Access = public)
        UIFigure               matlab.ui.Figure
        LoadRawButton          matlab.ui.control.Button
        LoadProcessedButton    matlab.ui.control.Button
        SensorListBoxLabel     matlab.ui.control.Label
        SensorListBox          matlab.ui.control.ListBox
        LabelListBoxLabel      matlab.ui.control.Label
        LabelListBox           matlab.ui.control.ListBox
        DataTypePanel          matlab.ui.container.Panel
        TemperatureCheckBox    matlab.ui.control.CheckBox
        PressureCheckBox       matlab.ui.control.CheckBox
        HumidityCheckBox       matlab.ui.control.CheckBox
        GasResistanceCheckBox  matlab.ui.control.CheckBox
        DisplayButton          matlab.ui.control.Button
        UITable                matlab.ui.control.Table
        UIAxes                 matlab.ui.control.UIAxes
    end

    
    properties (Access = private)
        RawData % Table for raw data
        ProcessedData % Table for processed data
        AvailableLabels % Unique labels from the data
    end
    
    methods (Access = private)
        
        % Button pushed function: LoadRawButton
        function LoadRawButtonPushed(app, event)
            [file, path] = uigetfile('*.csv', 'Select Raw CSV File');
            if isequal(file,0)
                return;
            else
                fullPath = fullfile(path, file);
                app.RawData = readtable(fullPath);
                % Populate Labels ListBox
                app.AvailableLabels = unique(app.RawData.Label_Tag);
                app.LabelListBox.Items = app.AvailableLabels;
                msgbox('Raw data loaded successfully!', 'Success');
            end
        end

        % Button pushed function: LoadProcessedButton
        function LoadProcessedButtonPushed(app, event)
            [file, path] = uigetfile('*.csv', 'Select Processed CSV File');
            if isequal(file,0)
                return;
            else
                fullPath = fullfile(path, file);
                app.ProcessedData = readtable(fullPath);
                % Populate Labels ListBox
                app.AvailableLabels = unique(app.ProcessedData.Label_Tag);
                app.LabelListBox.Items = app.AvailableLabels;
                msgbox('Processed data loaded successfully!', 'Success');
            end
        end

        % Button pushed function: DisplayButton
        function DisplayButtonPushed(app, event)
            if isempty(app.RawData) && isempty(app.ProcessedData)
                errordlg('Please load at least one CSV file (Raw or Processed).', 'Data Not Loaded');
                return;
            end
            
            selectedSensors = app.SensorListBox.Value;
            selectedLabels = app.LabelListBox.Value;
            selectedDataTypes = {};
            if app.TemperatureCheckBox.Value
                selectedDataTypes{end+1} = 'Temperature';
            end
            if app.PressureCheckBox.Value
                selectedDataTypes{end+1} = 'Pressure';
            end
            if app.HumidityCheckBox.Value
                selectedDataTypes{end+1} = 'Humidity';
            end
            if app.GasResistanceCheckBox.Value
                selectedDataTypes{end+1} = 'GasResistance';
            end
            
            if isempty(selectedSensors) || isempty(selectedDataTypes)
                errordlg('Please select at least one sensor and one data type.', 'Selection Missing');
                return;
            end
            
            % Determine which data to display
            if ~isempty(app.RawData)
                data = app.RawData;
                dataTypePrefix = ''; % Raw data has specific columns
            elseif ~isempty(app.ProcessedData)
                data = app.ProcessedData;
                dataTypePrefix = ''; % Processed data has different columns
            end
            
            % Filter by labels
            if ~isempty(selectedLabels)
                data = data(ismember(data.Label_Tag, selectedLabels), :);
            end
            
            % Select relevant columns
            selectedColumns = {'Timestamp_ms', 'Label_Tag'};
            for i = 1:length(selectedSensors)
                sensor = selectedSensors{i};
                for j = 1:length(selectedDataTypes)
                    type = selectedDataTypes{j};
                    if ~isempty(app.RawData)
                        colName = sprintf('Sensor%d_%s_deg_C', str2double(sensor(7)), type);
                        % Adjust column naming based on actual raw data
                        switch type
                            case 'Temperature'
                                colName = sprintf('Sensor%d_Temperature_deg_C', str2double(sensor(7)));
                            case 'Pressure'
                                colName = sprintf('Sensor%d_Pressure_Pa', str2double(sensor(7)));
                            case 'Humidity'
                                colName = sprintf('Sensor%d_Humidity_%%', str2double(sensor(7)));
                            case 'GasResistance'
                                colName = sprintf('Sensor%d_GasResistance_ohm', str2double(sensor(7)));
                        end
                    else
                        % Processed data columns
                        switch type
                            case 'Temperature'
                                colName = sprintf('Temperature_Mean_Sensor%d', str2double(sensor(7)));
                            case 'Pressure'
                                colName = sprintf('Pressure_Mean_Sensor%d', str2double(sensor(7)));
                            case 'Humidity'
                                colName = sprintf('Humidity_Mean_Sensor%d', str2double(sensor(7)));
                            case 'GasResistance'
                                colName = sprintf('GasResistance_Mean_Sensor%d', str2double(sensor(7)));
                        end
                    end
                    if ismember(colName, data.Properties.VariableNames)
                        selectedColumns{end+1} = colName; %#ok<AGROW>
                    end
                end
            end
            
            data = data(:, selectedColumns);
            app.UITable.Data = data;
            
            % Plotting (example: plot first selected data type)
            if ~isempty(selectedColumns) > 2
                x = data.Timestamp_ms;
                y = data{:, 3}; % First selected data column
                plot(app.UIAxes, x, y);
                xlabel(app.UIAxes, 'Timestamp (ms)');
                ylabel(app.UIAxes, selectedColumns{3});
                title(app.UIAxes, sprintf('%s vs Time', selectedColumns{3}));
            end
        end
    end

    
    % Component initialization
    methods (Access = private)

        % Create UIFigure and components
        function createComponents(app)

            % Create UIFigure
            app.UIFigure = uifigure;
            app.UIFigure.Position = [100 100 1000 600];
            app.UIFigure.Name = 'CSV Viewer';

            % Create LoadRawButton
            app.LoadRawButton = uibutton(app.UIFigure, 'push');
            app.LoadRawButton.ButtonPushedFcn = createCallbackFcn(app, @LoadRawButtonPushed, true);
            app.LoadRawButton.Position = [20 550 100 30];
            app.LoadRawButton.Text = 'Load Raw CSV';

            % Create LoadProcessedButton
            app.LoadProcessedButton = uibutton(app.UIFigure, 'push');
            app.LoadProcessedButton.ButtonPushedFcn = createCallbackFcn(app, @LoadProcessedButtonPushed, true);
            app.LoadProcessedButton.Position = [140 550 120 30];
            app.LoadProcessedButton.Text = 'Load Processed CSV';

            % Create SensorListBoxLabel
            app.SensorListBoxLabel = uilabel(app.UIFigure);
            app.SensorListBoxLabel.HorizontalAlignment = 'right';
            app.SensorListBoxLabel.Position = [20 500 100 22];
            app.SensorListBoxLabel.Text = 'Select Sensors';

            % Create SensorListBox
            app.SensorListBox = uilistbox(app.UIFigure, 'MultiSelect', 'on');
            app.SensorListBox.Items = {'Sensor1', 'Sensor2', 'Sensor3', 'Sensor4', 'Sensor5', 'Sensor6', 'Sensor7', 'Sensor8'};
            app.SensorListBox.Position = [130 450 100 80];

            % Create LabelListBoxLabel
            app.LabelListBoxLabel = uilabel(app.UIFigure);
            app.LabelListBoxLabel.HorizontalAlignment = 'right';
            app.LabelListBoxLabel.Position = [250 500 100 22];
            app.LabelListBoxLabel.Text = 'Select Labels';

            % Create LabelListBox
            app.LabelListBox = uilistbox(app.UIFigure, 'MultiSelect', 'on');
            app.LabelListBox.Position = [360 450 150 80];

            % Create DataTypePanel
            app.DataTypePanel = uipanel(app.UIFigure);
            app.DataTypePanel.Title = 'Select Data Types';
            app.DataTypePanel.Position = [550 450 200 130];

            % Create TemperatureCheckBox
            app.TemperatureCheckBox = uicheckbox(app.DataTypePanel);
            app.TemperatureCheckBox.Text = 'Temperature';
            app.TemperatureCheckBox.Position = [10 80 100 22];

            % Create PressureCheckBox
            app.PressureCheckBox = uicheckbox(app.DataTypePanel);
            app.PressureCheckBox.Text = 'Pressure';
            app.PressureCheckBox.Position = [10 60 100 22];

            % Create HumidityCheckBox
            app.HumidityCheckBox = uicheckbox(app.DataTypePanel);
            app.HumidityCheckBox.Text = 'Humidity';
            app.HumidityCheckBox.Position = [10 40 100 22];

            % Create GasResistanceCheckBox
            app.GasResistanceCheckBox = uicheckbox(app.DataTypePanel);
            app.GasResistanceCheckBox.Text = 'Gas Resistance';
            app.GasResistanceCheckBox.Position = [10 20 120 22];

            % Create DisplayButton
            app.DisplayButton = uibutton(app.UIFigure, 'push');
            app.DisplayButton.ButtonPushedFcn = createCallbackFcn(app, @DisplayButtonPushed, true);
            app.DisplayButton.Position = [800 550 100 30];
            app.DisplayButton.Text = 'Display';

            % Create UITable
            app.UITable = uitable(app.UIFigure);
            app.UITable.Position = [20 50 600 380];

            % Create UIAxes
            app.UIAxes = uiaxes(app.UIFigure);
            app.UIAxes.Position = [650 50 330 380];
        end
    end

    
    % App initialization and construction
    methods (Access = public)

        % Construct app
        function app = CSVViewerApp

            % Create and configure components
            createComponents(app)

            % Register the app with App Designer
            registerApp(app, app.UIFigure)

            if nargout == 0
                clear app
            end
        end

        % Code that executes before app deletion
        function delete(app)

            % Delete UIFigure when app is deleted
            delete(app.UIFigure)
        end
    end
end
