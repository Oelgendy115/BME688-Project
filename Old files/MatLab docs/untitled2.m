% Specify the JSON file name (update the file name if needed)
filename = '2023_04_25_13_33_Board_4022D8F42680_PowerOnOff_1_w3s5tyuw68xbh6m4_File_11.json';

% Read the JSON file as text and decode it
jsonText = fileread(filename);
data = jsondecode(jsonText);

% Extract the data block from the JSON structure
dataBlock = data.rawDataBody.dataBlock;

% Check if dataBlock is a cell array; if so, convert it to a numeric matrix
if iscell(dataBlock)
    dataMat = cell2mat(dataBlock);
else
    dataMat = dataBlock;
end

% According to the JSON structure:
% - Temperature is in column 5 ("Temperature")
% - Resistance Gassensor is in column 8 ("Resistance Gassensor")
temperature = dataMat(:, 5);
resistance = dataMat(:, 8);

% Create a figure to plot both datasets with two y-axes
figure;

% Plot temperature on the left y-axis
yyaxis left
plot(temperature, 'b-', 'LineWidth', 2);
ylabel('Temperature (°C)');
xlabel('Data Point Index');
title('Temperature and Gas Sensor Resistance');
grid on;

% Plot resistance on the right y-axis
yyaxis right
plot(resistance, 'r--', 'LineWidth', 2);
ylabel('Resistance (Ohms)');

% Add a legend
legend('Temperature', 'Resistance', 'Location', 'best');
