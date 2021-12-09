AVAIL_ACQ_MODULES = {}

try:
    from .comedistreamer import ComediStreamer

    AVAIL_ACQ_MODULES['comedi'] = ComediStreamer
except ModuleNotFoundError:
    pass

try:
    from .demostreamer import DemoStreamer

    AVAIL_ACQ_MODULES['demo'] = DemoStreamer
except ModuleNotFoundError:
    pass

try:
    from .mccstreamer import MCCStreamer

    AVAIL_ACQ_MODULES['mcc'] = MCCStreamer
except ModuleNotFoundError:
    pass

try:
    from .nistreamer import NIStreamer

    AVAIL_ACQ_MODULES['nidaqmx'] = NIStreamer
except ModuleNotFoundError:
    pass

try:
    from .serialstreamer import SerialStreamer

    AVAIL_ACQ_MODULES['serial'] = SerialStreamer
except ModuleNotFoundError:
    pass
