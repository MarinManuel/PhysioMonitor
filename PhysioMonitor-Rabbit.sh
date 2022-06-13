#!/bin/bash
cd /home/electrophy/PhysioMonitor/
/home/electrophy/physiomonitor-venv/bin/python ./PhysioMonitor.py -c ./PhysioMonitor-Rabbit.json --prev-values-file=./prev_vals_Rabbit.json
