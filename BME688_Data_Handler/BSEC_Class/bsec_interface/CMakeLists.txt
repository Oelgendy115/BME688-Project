cmake_minimum_required(VERSION 3.4)
project(bsec_interface_module)

# Find pybind11 package (if installed via pip or as a submodule)
find_package(pybind11 REQUIRED)

# Create the Python module
pybind11_add_module(bsec_interface C:\BME688 Project\BME688_Data_Handler\BSEC_Class\bsec_interface\src\bsec_interface.cpp)

#Link against the BSEC library if needed (replace 'bsec' with your actual library name/path)
target_link_libraries(bsec_interface PRIVATE C:\BME688 Project\BME688_Data_Handler\BSEC_Class\bsec_interface\src\bsec_interface.cpp)