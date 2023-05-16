#!/bin/bash
root=~/PhysioMonitor/
arg1=PhysioMonitor-Rabbit.json
arg2=prev_vals_Rabbit.json

# Create and activate the virtual environment
source ~/physiomonitor-venv/bin/activate

# Run the Python program with the two arguments
cd $root
python PhysioMonitor.py -c $arg1 -p $arg2

# Deactivate the virtual environment
deactivate
