# PhysioMonitor
Python application to track physiological parameters during surgery

# Configuration
The software needs a configuration file in JSON format to run. The global structure of the file is:
```json
{
  "log-filename": str;
    This is the name of the file in which the surgical log 
    is saved (without path)
  "acquisition-modules": list; 
    This is a list of modules used for data acquisition.
    See list of supported modules and configuration options below
  "channels": list;
    List of channels and their configuration. See below for details
  "pump-serials": list; 
    List of serial ports to be used for controlling syringe pumps
  "pumps": list;
    List of syringe pumps and their configuration. See list of supported
    modules and their configuration below.
  
}
```
## Data acquisition modules
Each element of the list must contain the following items:
```json
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
This module is intented for testing and debugging. It is a dummy modules that does not require external hardware.
It reads a CSV file (or any file that can be parsed by [`numpy.loadtxt`](https://numpy.org/doc/1.20/reference/generated/numpy.loadtxt.html#numpy.loadtxt)),
and outputs the content at the given sampling rate.

The arguments to supply in `"module-args"` are:

- `filename` - the path to the file to read (default `./media/file_streamer_data.txt`)
- `loadtxt_kws` - obtional arguments passed to `numpy.loadtxt`. See [the documentation]((https://numpy.org/doc/1.20/reference/generated/numpy.loadtxt.html#numpy.loadtxt)) for a list of possible arguments.

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

# Installation
 - TODO
