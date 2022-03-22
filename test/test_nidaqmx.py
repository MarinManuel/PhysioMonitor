import pprint
import nidaqmx
import nidaqmx.constants

pp = pprint.PrettyPrinter(indent=4)


with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan("Dev1/ai0:7",
                                         terminal_config=nidaqmx.constants.TerminalConfiguration.BAL_DIFF)
    data = task.read(number_of_samples_per_channel=1)
    print(data)
