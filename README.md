# PhysioMonitor
Python application to track physiological parameters during surgery

# Configuration
The software needs a configuration file in JSON format to run. The global structure of the file is:
```
{
  "base-folder": str,
    The folder in which the logs are going to be saved
  "create-sub-folder": true|false,
    Whether to create a separate sub-folder for every day of experiment. If `true`, a new folder with the name 
    'YYYY-MM-DD/' will be created in base-folder
  "log-filename": str,
    This is the name of the file in which the surgical log 
    is saved (without path)
  "measurements-output-period-min": float,
    The period (in minutes) with which the trend measurements are written to the log file
  "acquisition-modules": list,
    This is a list of modules used for data acquisition.
    See list of supported modules and configuration options below
  "channels": list,
    List of channels and their configuration. See below for details
  "syringe-pump": 
    "serial-ports": list,
      This is a list of serial ports to open in order to communicate with the syringe pump(s).
      Contains a list of parameters to pass to serial.Serial(). See https://pythonhosted.org/pyserial/pyserial_api.html#native-ports
      for a complete list.
    "pumps": list
      List of syringe pumps and their configuration. See list of supported
      modules and their configuration below.
}
```
## Data acquisition modules
Each element of the list must contain the following items:
```
{
  "module-name": str;
    Name of the module to use. See the list below
  "sampling-rate": float;
    Sampling rate for the acquisition (in Hz)
  "module-args": section;
    Section containing the parameters needed to create the modules. See below for each module's options.
}
```
Available data acquisition modules are:
### "demo"
This module is intended for testing and debugging. It is a dummy modules that does not require external hardware.
It reads a CSV file (or any file that can be parsed by [`numpy.loadtxt`](https://numpy.org/doc/1.20/reference/generated/numpy.loadtxt.html#numpy.loadtxt)),
and outputs the content at the given sampling rate.

The arguments to supply in `"module-args"` are:

- `filename` - the path to the file to read (default `./media/file_streamer_data.txt`)
- `genfromtxt_kws` - optional arguments passed to `numpy.genfromtxt`. See [the documentation]((https://numpy.org/doc/stable/reference/generated/numpy.genfromtxt.html#numpy-genfromtxt)) for a list of possible arguments.

### "nidaqmx"
This module allows the use of NI cards supported by [the nidaqmx python library](https://nidaqmx-python.readthedocs.io/en/latest/). 
Currently, only tested on Windows.

The arguments to supply in `"module-args"` are:

- `device` - the name of the physical device to use (e.g. `"Dev1"`)
- `channels`- a list of physical channels to sample from (e.g. `["ai0","ai7","ai2"]`)
- `input_modes` - a list (same length as `channels`) of terminal configurations (e.g. `["RSE", "MRSE", "DEFAULT"]`). 
Valid configurations are `DEFAULT`, `RSE`, `NRSE`, `DIFFERENTIAL` and `PSEUDODIFFERENTIAL`.
- `buffer_size` - size of the buffer used to store the data in between each read (default 1000).

### "mcc"
This module allows the use of Measurement Computing devices supported by [the MCC Universal Library (uldaq)](https://github.com/mccdaq/uldaq).

The arguments to supply in `"module-args"` are:

- `device` - the device number (e.g. `0`). This corresponds to the index of the device as returned by 
`uldaq.get_daq_device_inventory(InterfaceType.ANY)`.
See the documentation  on [device discovery](https://www.mccdaq.com/PDFs/Manuals/UL-Linux/python/api.html#device-discovery) 
for more information.
- `channels` - a list of channel numbers to sample from (e.g. `[0, 7, 3]`).
- `input_modes` - a list (same length as `channels`) of input modes (e.g. `['SINGLE_ENDED','SINGLE_ENDED','DIFFERENTIAL']`).
Valid input modes are `DIFFERENTIAL`,`SINGLE_ENDED`, and `PSEUDO_DIFFERENTIAL`.
- `input_ranges` - a list (same length as `channels`) of input range (e.g. `['BIP5VOLTS', 'BIP10VOLTS', 'UNI10VOLTS']`).
See [the documentation](https://www.mccdaq.com/PDFs/Manuals/UL-Linux/python/api.html?highlight=uni10volts#uldaq.Range) for
a list of valid input ranges.
- `buffer_size` - size of the buffer used to store the data in between each read (default 1000).

### "comedi"
No longer supported under Python 3

## Channel configuration
Each channel is configured by the following intructions:
- `acquisition-module-index` - <span style="color:DarkGreen">int</span> - Index of the acquisition module to use for this channel 
  (as defined by its position in the list of acquisition modules declared in the section "Data acquisition modules")
- `channel-index` - <span style="color:DarkGreen">int</span> - Index corresponding to this channel's data in the relevant stream.
  WARNING: this is not the physical channel number as entered in channel list in the acquisition configuration, but the index of the channel
  in the list of channels.
- `window-size` - <span style="color:DarkGreen">float</span> - Width of the window of data to display (in seconds).
- `label` - <span style="color:DarkGreen">string</span> - Channel title.
- `units` - <span style="color:DarkGreen">string</span> - Real world unit for the channel.
- `scale` - <span style="color:DarkGreen">float</span> - used to convert the value in volts to the value in real worl units: `Units = scale x volts + offset`.
- `offset` - <span style="color:DarkGreen">float</span> - used to convert the value in volts to the value in real worl units: `Units = scale x volts + offset`.
- `autoscale` - <span style="color:DarkGreen">true/false</span> - Whether to automatically adjust the y-axis limit to fit with the data limits.
- `ymin` - <span style="color:DarkGreen">float</span> - Lower y-axis limit. Only usefull if autoscale is off.
- `ymax` - <span style="color:DarkGreen">float</span> - Upper y-axis linit. Only usefull if autoscale is off.
- `line-color` - <span style="color:DarkGreen">variable</span> - color of the data line. Accepts any argument that can be passed to [`pyqtgraph.mkColor()`](https://pyqtgraph.readthedocs.io/en/latest/functions.html#pyqtgraph.mkColor) 
- `line-width` - <span style="color:DarkGreen">float</span> - line thickness.
- `persistence` - <span style="color:DarkGreen">int</span> - Number of past traces to keep. Older traces fade towards the background color.
- `trigger-mode` - <span style="color:DarkGreen">string</span> - Sets whether new data is shown immediately upon reaching the right-hand side of the screen
  (`'AUTO'`), or whether the waveform must first cross a threshold value (see below) in the upward (`'RISING'`) or 
  downward direction (`'FALLING'`).
- `trigger-level` - <span style="color:DarkGreen">float</span> - Threshold value (in channel units).
- `auto-trigger-level` - <span style="color:DarkGreen">true/false</span> - Whether the trigger threshold is automatically calculated based on the historical 
  data. The value is calculated as 75% of the range of the data if the threshold mode is `RISING`, and 25% of the range
  if it is `FALLING`.
- `trend-window-size` - <span style="color:DarkGreen">float</span> - Width of the window of trend data (in seconds). 
- `trend-period` - Period over which to calculate the trend value (in seconds).
- `trend-function` - <span style="color:DarkGreen">string</span> - Function used to calculate the trend value. Valid values are:
    - `'HR'` calculates heart rate based on QRS detection 
    - `'max'` returns the maximum of the data,
    - `'min'` returns the minimum of the data,
    - `'lastPeak'` returns the value of the latest detected peak in the data,
    - `'avgPeak'` returns the average of the peak values detected in the data,
    - `'average'` returns the average of the data
- `trend-function-args` - arguments passed to `trend-function`. See the code for the `trend_*` functions in the GUI.scope module.
- `trend-units` - <span style="color:DarkGreen">string</span> - Units of the trend data 
- `trend-autoscale` - <span style="color:DarkGreen">true/false</span> - Whether to automatically adjust the y-axis limit of the trend window to fit with 
  the data limits.
- `trend-ymin` - <span style="color:DarkGreen">float</span> - Lower y-axis limit of the trend window. Only usefull if autoscale is off.
- `trend-ymax` - <span style="color:DarkGreen">float</span> - Lower y-axis limit of the trend window. Only usefull if autoscale is off.
- `alarm-enabled` - <span style="color:DarkGreen">true/false</span> - Whether an alarm should sound when the trend data is outside the lower and higher limits.
- `alarm-low` - <span style="color:DarkGreen">float</span> - The lower threshold for the alarm.
- `alarm-high` - <span style="color:DarkGreen">float</span> - the upper threshold for the alarm.
- `alarm-sound-file` - <span style="color:DarkGreen">string</span> - path to an OGG or a WAV sound file that is being played when the alarm is triggered.
- `alarmBGColor` - <span style="color:DarkGreen">var</span> - Color of the window when the alarm is triggered.

## Syringe Pumps
PhysioMonitor can control serial pumps through serial communication. Currently, the following models are supported: 
- fake pump, for testing purposes
- [Aladdin pump](https://www.wpiinc.com/var-2300-aladdin-single-syringe-pump)
- [Harvard Apparatus Model 11 plus (old model)](https://www.harvardapparatus.com/media/harvard/pdf/Pump11_2002.pdf)

Parameters:
### `serial-ports`
list of serial ports to open. Each of the element contains parameters that can be passed to 
[serial.Serial()](https://pythonhosted.org/pyserial/pyserial_api.html#native-ports).

### `pumps`
Each element of the list must contain the following items:
```
{
  "module-name": str,
    Name of the module to use. One of "demo", "aladdin" or "model11plus".
  "serial-port": int,
    index of the serial port to use to control that syringe pump.
  "module-args": section,
    Section containing the parameters needed to create the modules. See below for each module's options.
}
```
Available modules are:
#### "dummy"
Fake pump, for testing purposes. "module-args" is empty

#### "aladdin"
Module for [Aladdin syringe pumps](https://www.wpiinc.com/var-2300-aladdin-single-syringe-pump).

The arguments to supply in `"module-args"` are:
- `adress`: unique network address to identify the pump to the computer. 
  Network addresses are from 00 to 99. If the network consists of only 1 pump, set the pump’s address to 0.
  
#### "modell11plus"
Module for [Harvard Apparatus Model 11 plus (old model)](https://www.harvardapparatus.com/media/harvard/pdf/Pump11_2002.pdf).
"module-args" is empty.

# Installation
 - TODO
