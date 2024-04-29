import logging
import re
import time
from enum import IntEnum

from PyQt5.QtCore import QTimer

logger = logging.getLogger(__name__)

# default values for bolus injections
DEFAULT_BOLUS_RATE = 1.0
DEFAULT_BOLUS_RATE_UNITS: int = 1


class SyringePump(object):
    """
    This is an abstract class that declares the functions available
    to control a syringe pump of any brand
    """

    UNITS = ["mL/hr", "mL/min", "uL/hr", "uL/min"]

    class STATE(IntEnum):
        STOPPED = 0
        INFUSING = 1
        WITHDRAWING = 2

    min_val = 0.001
    max_val = 9999
    _display_name = ""
    _bolus_rate = DEFAULT_BOLUS_RATE
    _bolus_rate_units = DEFAULT_BOLUS_RATE_UNITS

    def __init__(self):
        """
        constructor
        """
        pass

    def __del__(self):
        """
        Destructor to cleanly close the serial object if needed
        """
        pass

    def start(self):
        """
        starts the pump with the parameters defined beforehand
        """
        pass

    def stop(self):
        """
        stops the pump
        """
        pass

    def reverse(self):
        """
        reverse the flow of the pump (if available)
        """
        pass

    def is_running(self):
        """
        returns True if the pump is running (infusion or withdrawing)
        and False if it is stopped
        """
        pass

    def clear_accumulated_volume(self):
        """
        resets to 0 the volume of liquid pumped
        """
        pass

    def clear_target_volume(self):
        """
        clears the target volume for the pump. This should put the pump in
        continuous injection mode
        """
        pass

    def set_direction(self, value: int):
        """
        defines the direction that the pump will run.
        inValue is an int representation of the directions that the pump is capable of running in
        """
        pass

    def set_syringe_diameter_mm(self, value: float):
        """
        defines the diameter of the syringe in mm
        """
        pass

    def set_rate(self, value: float, units: int):
        """
        sets the rate of the pump
        optionally, one can also change the units (see set units)
        """
        pass

    def set_target_volume_uL(self, value: float):
        """
        puts the pump in fixed amount mode and defines the volume
        after which it will stop pumping
        """
        pass

    def get_diameter_mm(self) -> float:
        """
        returns the current diameter (in mm) of the syringe
        """
        pass

    def get_rate(self) -> float:
        """
        returns the current rate of pumping as a float
        """
        pass

    def get_units(self) -> int:
        """
        return the current units as an int
        """
        pass

    def get_accumulated_volume_uL(self) -> float:
        """
        returns the amount of liquid pumped so far (in μL)
        """
        pass

    def get_target_volume_uL(self) -> float:
        """
        returns the target volume for the pump (in μL)
        """
        pass

    def get_direction(self) -> STATE:
        """
        returns the current direction of the pump as an int
        """
        pass

    def get_possible_units(self) -> list:
        """
        returns an array of the possible units accepted by this pump
        """
        pass

    @property
    def display_name(self) -> str:
        return self._display_name

    @display_name.setter
    def display_name(self, value: str):
        self._display_name = value

    @property
    def bolus_rate(self) -> float:
        return self._bolus_rate

    @bolus_rate.setter
    def bolus_rate(self, value: float):
        self._bolus_rate = value

    @property
    def bolus_rate_units(self) -> int:
        return self._bolus_rate_units

    @bolus_rate_units.setter
    def bolus_rate_units(self, value: int):
        self._bolus_rate_units = value


class SyringePumpException(Exception):
    pass


class SyringePumpValueOORException(SyringePumpException):
    pass


class SyringePumpUnknownCommandException(SyringePumpException):
    pass


class SyringePumpNotRunningException(SyringePumpException):
    pass


class SyringePumpNotStoppedException(SyringePumpException):
    pass


class SyringePumpInvalidAnswerException(SyringePumpException):
    pass


class SyringePumpAlarmException(SyringePumpException):
    pass


class SyringePumpInvalidCommandException(SyringePumpException):
    pass


class SyringePumpUnforeseenException(SyringePumpException):
    pass


class DummyPump(SyringePump):
    # noinspection PyMissingConstructor
    def __init__(
            self, serial_port, diameter=10, rate=20, units=0, target_vol=0, display_name=""
    ):
        self.serial = serial_port
        self.currDir = self.STATE.INFUSING
        self.currState = self.STATE.STOPPED
        self.currDiameter = diameter
        self.currRate = rate
        self.currUnits = units
        self.targetVolume = target_vol
        self.display_name = display_name

    def __del__(self):
        pass

    def start(self):
        if self.currState == self.STATE.STOPPED:
            self.currState = self.currDir
            if self.targetVolume > 0:
                # simulate the fact that the pump stops automatically when a target volume is set
                QTimer(None).singleShot(1000, lambda: self.stop())

    def stop(self):
        self.currState = self.STATE.STOPPED

    def reverse(self):
        if self.currDir == self.STATE.INFUSING:
            self.currDir = self.STATE.WITHDRAWING
        elif self.currDir == self.STATE.WITHDRAWING:
            self.currDir = self.STATE.INFUSING

    def is_running(self):
        return not self.currState == self.STATE.STOPPED

    def clear_accumulated_volume(self):
        pass

    def clear_target_volume(self):
        self.targetVolume = 0

    def set_direction(self, value: SyringePump.STATE):
        self.currDir = value

    def set_syringe_diameter_mm(self, value: int):
        if value <= 0:
            raise SyringePumpValueOORException("Diameter must be a positive value")
        else:
            self.currDiameter = value

    def set_rate(self, rate: int, units: int):
        if rate <= 0:
            raise SyringePumpValueOORException("Rate must be a positive value")
        if units < 0 or units > (len(self.UNITS) - 1):
            raise SyringePumpValueOORException(
                "Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1)
            )
        self.currRate = rate
        self.currUnits = units

    def set_target_volume_uL(self, value):
        self.targetVolume = value

    def get_diameter_mm(self):
        return self.currDiameter

    def get_rate(self):
        return self.currRate

    def get_units(self):
        return self.currUnits

    def get_accumulated_volume_uL(self):
        return 0

    def get_target_volume_uL(self):
        return 0

    def get_direction(self):
        return self.currDir

    def get_possible_units(self):
        return self.UNITS


class Model11plusPump(SyringePump):
    __PROMPT_STP = "\r\n:"
    __PROMPT_FWD = "\r\n>"
    __PROMPT_REV = "\r\n<"
    __ANS_OOR = "\r\nOOR"
    __ANS_UNKNOWN = "\r\n?"
    __CMD_RUN = "RUN\r"
    __CMD_STOP = "STP\r"
    __CMD_CLEAR_VOLUME = "CLV\r"
    __CMD_CLEAR_TARGET = "CLT\r"
    __CMD_REV = "REV\r"
    __CMD_SET_DIAMETER = "MMD %5.4f\r"
    __CMD_SET_FLOW_UL_H = "ULH %5.4f\r"
    __CMD_SET_FLOW_UL_MIN = "ULM %5.4f\r"
    __CMD_SET_FLOW_ML_H = "MLH %5.4f\r"
    __CMD_SET_FLOW_ML_MIN = "MLM %5.4f\r"
    __CMD_SET_RATE = [
        __CMD_SET_FLOW_ML_H,
        __CMD_SET_FLOW_ML_MIN,
        __CMD_SET_FLOW_UL_H,
        __CMD_SET_FLOW_UL_MIN,
    ]
    __CMD_SET_TARGET = "MLT %5.4f\r"
    __CMD_GET_DIAMETER = "DIA\r"
    __CMD_GET_RATE = "RAT\r"
    __CMD_GET_UNITS = "RNG\r"
    __CMD_GET_VOLUME = "VOL\r"
    __CMD_GET_VERSION = "VER\r"
    __CMD_GET_TARGET = "TAR\r"
    __CMD_QUIT_REMOTE = "KEY\r"

    # noinspection PyMissingConstructor
    def __init__(self, serial_port, display_name=""):
        self.serial = serial_port
        self.currUnits = 0
        self.display_name = display_name

        self.serial.open()
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()

    def __del__(self):
        self.send_command(self.__CMD_QUIT_REMOTE)
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()

    def get_info(self):
        return self.get_status()

    def send_command(self, command):
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        logger.debug('sending command "%s"...' % command)
        self.serial.write(command)
        time.sleep(0.3)
        nb_char = self.serial.inWaiting()
        ans = str(self.serial.read(nb_char))
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        # print "reading %d bytes in response: \"%s\""%(nbChar,repr(ans)) #DEBUG
        if ans.startswith(self.__ANS_OOR):
            # print "OOR Error encountered!" #DEBUG
            raise SyringePumpValueOORException()
        elif ans.startswith(self.__ANS_UNKNOWN):
            # print "Unknown command Error encountered!" #DEBUG
            raise SyringePumpUnknownCommandException()
        else:
            return ans

    def strip_prompt(self, prompt: str) -> str:
        prompt = prompt.replace(self.__PROMPT_STP, "")
        prompt = prompt.replace(self.__PROMPT_FWD, "")
        prompt = prompt.replace(self.__PROMPT_REV, "")
        prompt = prompt.strip()
        return prompt

    def run(self):
        self.send_command(self.__CMD_RUN)
        ans = self.get_direction()
        if ans == "FWD" or ans == "REV":
            pass
        else:
            raise SyringePumpNotRunningException()

    def start(self):
        self.run()

    def stop(self):
        self.send_command(self.__CMD_STOP)
        ans = self.get_direction()
        if ans == "STOPPED":
            pass
        else:
            raise SyringePumpNotStoppedException()

    def clear_accumulated_volume(self):
        self.send_command(self.__CMD_CLEAR_VOLUME)

    def clear_target_volume(self):
        self.send_command(self.__CMD_CLEAR_TARGET)

    def reverse(self):
        self.send_command(self.__CMD_REV)

    def set_syringe_diameter_mm(self, diameter: float):
        self.send_command(self.__CMD_SET_DIAMETER % diameter)

    def set_rate(self, value: float, units: int):
        if value <= 0:
            raise SyringePumpValueOORException("Rate must be a positive value")
        if units < 0 or (units > len(self.UNITS) - 1):
            raise SyringePumpValueOORException(
                "Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1)
            )
        self.send_command(
            (self.__CMD_SET_RATE[units]) % value
        )

    def set_target_volume_uL(self, value: float):
        self.send_command(self.__CMD_SET_TARGET % value)

    def get_diameter_mm(self) -> float:
        diameter = self.send_command(self.__CMD_GET_DIAMETER)
        diameter = self.strip_prompt(diameter)
        return float(diameter)

    def get_rate(self) -> float:
        rate = self.send_command(self.__CMD_GET_RATE)
        rate = self.strip_prompt(rate)
        return float(rate)

    # noinspection DuplicatedCode
    def get_accumulated_volume_uL(self) -> float:
        volume = self.send_command(self.__CMD_GET_VOLUME)
        volume = self.strip_prompt(volume)
        volume = float(volume)
        units = self.get_units()
        if self.UNITS[units].upper().startswith('ML'):
            volume *= 1e3  # if range is in mL, convert volume to μL
        return volume

    def get_version(self) -> str:
        version = self.send_command(self.__CMD_GET_VERSION)
        version = self.strip_prompt(version)
        return version

    # noinspection DuplicatedCode
    def get_target_volume_uL(self) -> float:
        target = self.send_command(self.__CMD_GET_TARGET)
        target = self.strip_prompt(target)
        target = float(target)
        units = self.get_units()
        if self.UNITS[units].upper().startswith('ML'):
            target *= 1e3  # if range is in mL, convert volume to μL
        return target

    def get_units(self) -> int:
        units = self.send_command(self.__CMD_GET_UNITS)
        units = self.strip_prompt(units)
        upper_units = [u.upper() for u in self.UNITS]
        if units.upper() in upper_units:
            return upper_units.index(units.upper())
        else:
            raise SyringePumpInvalidAnswerException(f'Could not understand units returned by getUnits(): got "{units}"')

    def get_direction(self) -> SyringePump.STATE:
        _ = self.send_command("\r")
        _ = self.send_command("\r")
        ans = self.send_command("\r")
        if ans == self.__PROMPT_FWD:
            return self.STATE.INFUSING
        elif ans == self.__PROMPT_REV:
            return self.STATE.WITHDRAWING
        elif ans == self.__PROMPT_STP:
            return self.STATE.STOPPED

    def get_status(self) -> str:
        port = self.serial.portstr
        version = self.get_version()
        diameter = self.get_diameter_mm()
        rate = self.get_rate()
        units = self.get_units()
        target = self.get_target_volume_uL()
        volume = self.get_accumulated_volume_uL()
        direction = self.get_direction()
        return (
                "Syringe Pump v.%s (%s) {direction: %s, diameter: %.4f mm, rate: %.4f %s, accumulated volume: %.4f, "
                "target volume: %.4f}"
                % (version, port, direction, diameter, rate, units, volume, target)
        )

    def set_direction(self, value):
        pass

    def is_running(self):
        return not self.get_status() == self.STATE.STOPPED

    def get_possible_units(self):
        return self.UNITS


# noinspection SpellCheckingInspection
class AladdinPump(SyringePump):
    TIMEOUT = 1.0  # second
    # ******* PUMP ANSWERS ******
    __ANS_TRUE = "1"
    __ANS_FALSE = "0"
    # direction
    __ANS_DIR_INF = "INF"
    __ANS_DIR_WDR = "WDR"
    __ANS_DIR_REV = "REV"
    # units
    __ANS_UNITS_ML = "ML"
    __ANS_UNITS_UL = "UL"
    __ANS_UNITS_ULMIN = "UM"
    __ANS_UNITS_ULHR = "UH"
    __ANS_UNITS_MLMIN = "MM"
    __ANS_UNITS_MLHR = "MH"
    __ANS_UNITS = [
        __ANS_UNITS_MLHR,
        __ANS_UNITS_MLMIN,
        __ANS_UNITS_ULHR,
        __ANS_UNITS_ULMIN,
    ]
    # status message
    __ANS_STATUS_INFUSING = "I"
    __ANS_STATUS_WITHDRAWING = "W"
    __ANS_STATUS_STOPPED = "S"
    __ANS_STATUS_PAUSED = "P"
    __ANS_STATUS_PAUSEPHASE = "T"
    __ANS_STATUS_TRIGGERWAIT = "U"
    # alarm message
    __ANS_ALARM_RESET = "R"
    __ANS_ALARM_STALLED = "S"
    __ANS_ALARM_TIMEOUT = "T"
    __ANS_ALARM_PROGERROR = "E"
    __ANS_ALARM_PHASEOOR = "O"
    # regexp to extract status and message in response packet
    __ANS_PATTERN = (
            r"""^\x02([0-9]{2})(["""
            + __ANS_STATUS_INFUSING
            + __ANS_STATUS_WITHDRAWING
            + __ANS_STATUS_STOPPED
            + __ANS_STATUS_PAUSED
            + __ANS_STATUS_PAUSEPHASE
            + __ANS_STATUS_TRIGGERWAIT
            + """]|A\?["""
            + __ANS_ALARM_RESET
            + __ANS_ALARM_STALLED
            + __ANS_ALARM_TIMEOUT
            + __ANS_ALARM_PROGERROR
            + __ANS_ALARM_PHASEOOR
            + """])(.*)\x03$"""
    )
    # regexp to extract model and version numbers
    __ANS_VER_PATTERN = r"^NE([0-9]+)V([0-9]+).([0-9]+)$"
    # regexp to extract dispensed volume
    __ANS_DISVOL_PATTERN = r"^I([0-9\.]+)W([0-9\.]+)([UML]{2})$"
    # error codes
    __ANS_ERROR_UNRECOGNIZED = "?"
    __ANS_ERROR_NOTAPPLICABLE = "?NA"
    __ANS_ERROR_OOR = "?OOR"
    __ANS_ERROR_COMERR = "?COM"
    __ANS_ERROR_IGNORED = "?IGN"
    # trigger modes
    __ANS_TRIG_FOOT = "FT"
    __ANS_TRIG_TTL = "LE"
    __ANS_TRIG_START = "ST"

    # ******* Commands *******
    # GET commands
    __CMD_GET_DIAMETER = "DIA\r"  # get the syringe diameter
    __CMD_GET_PHASE = "PHN\r"  # get the phase number
    __CMD_GET_PHASEFUNCTION = "FUN\r"  # get the program's phase function
    __CMD_GET_RATE = "RAT\r"  # get the rate of inf/withdraw, including unit
    __CMD_GET_TARVOL = "VOL\r"  # get target volume, incl units
    __CMD_GET_DIR = "DIR\r"  # get the direction of the pump
    __CMD_GET_DISVOL = (
        "DIS\r"  # get the volume dispensed in infusion as well as in withdrawal
    )
    __CMD_GET_ALARM = "AL\r"  # get current alarm mode
    __CMD_GET_POWERFAIL = "PF\r"  # get current power failure mode
    __CMD_GET_TRIGMODE = "TRG\r"  # get current trigger mode
    __CMD_GET_TTLDIR = "DIN\r"  # get TTL directional control mode
    __CMD_GET_TTLOUT = "ROM\r"  # get TTL output mode
    __CMD_GET_KEYLOCK = "LOC\r"  # get state of keypad lock
    __CMD_GET_KEYBEEP = "BP\r"  # get keypad beep mode
    __CMD_GET_TTLIO = "IN\r"  # get ttl level of TTL I/O connector
    __CMD_GET_BUZZ = "BUZ\r"  # gets whether buzzer is buzzing
    __CMD_GET_VERSION = "VER\r"  # gets the model number and the firmware version
    # SET commands
    __CMD_SET_DIAMETER = "DIA%.2f\r"  # set the syringe diameter
    __CMD_SET_PHASE = "PHN%d\r"  # set the phase number
    __CMD_SET_PHASEFUNCTION = "FUN%d\r"  # set the program's phase function
    # ... a bunch of other instructions could be here. cf p50 of the manual
    __CMD_SET_RATE = "RAT%s%s\r"  # set the rate of inf/withdraw, including unit
    __CMD_SET_TARVOL = "VOL%s\r"  # set target volume, always in UL
    __CMD_SET_DIR = "DIR%s\r"  # set the direction of the pump
    __CMD_SET_RUNPHASE = "RUN%d\r"  # start the pumping program
    __CMD_SET_STOP = "STP\r"  # stops the pump
    __CMD_CLEAR_DISVOL = "CLD%s\r"  # clears dispensed volume in INF or WITHDR
    __CMD_SET_ADDRESS = "ADR%02d\r"  # sets the network address
    __CMD_SET_SAFEMODE = "SAF%03d\r"  # enables safe mode communication
    __CMD_SET_ALARM = "AL%d\r"  # set the alarm mode
    __CMD_SET_POWERFAIL = "PF%d\r"  # set current power failure mode
    __CMD_SET_TRIGMODE = "TRG%s\r"  # set current trigger mode
    __CMD_SET_TTLDIR = "DIN%d\r"  # set TTL directional control mode
    __CMD_SET_TTLOUT = "ROM%d\r"  # set TTL output mode
    __CMD_SET_KEYLOCK = "LOC%d\r"  # set state of keypad lock
    __CMD_SET_KEYBEEP = "BP%d\r"  # set keypad beep mode
    __CMD_SET_TTLIO = "OUT5%s\r"  # set ttl level of TTL I/O connector pin 5
    __CMD_SET_BUZZ = "BUZ%d%d\r"  # sets whether buzzer is buzzing

    @staticmethod
    def format_float(val):
        return "{:05.3f}".format(val)[:5]

    # noinspection PyMissingConstructor
    def __init__(self, serial_port, address=0, display_name=""):
        self.address = address
        self.ansParser = re.compile(self.__ANS_PATTERN)
        self.serial = serial_port
        self.display_name = display_name
        self.serial.open()
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        self.serial.timeout = self.TIMEOUT
        self.do_beep()

    def __del__(self):
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()

    def get_info(self) -> str:
        port = self.serial.name
        version = self.get_version()
        diameter = self.get_diameter_mm()
        rate = self.get_rate()
        units = self.UNITS[self.get_units()]
        target = self.get_target_volume_uL()
        volume = self.get_accumulated_volume_uL()
        direction = self.get_direction().name
        return (
                "Syringe Pump %s (%s) {direction: %s, diameter: %04f mm, rate: %04f %s, accumulated volume: %04f, "
                "target volume: %04f}"
                % (version, port, direction, diameter, rate, units, volume, target)
        )

    def send_command(self, command, return_all=False):
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        command = f"{self.address:02d}{command}"
        logger.debug('>>sending command "%s"...' % (command.replace("\r", "\\r")))
        self.serial.write(command.encode())
        ans = self.serial.read_until(b"\x03").decode()
        nb_bytes = len(ans)
        # while ans[-1:] != "\x03":
        #     nb_char = self.serial.inWaiting()
        #     nb_bytes += nb_char
        #     ans += self.serial.read(nb_char).decode()
        #     if (time.time() - send_time) > self._readTimeout:
        #         raise ReadTimeoutException("Timeout while waiting for an answer")
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        logger.debug('<<reading %d bytes in response: "%s"' % (nb_bytes, repr(ans)))
        address, status, message = self.parse(ans)
        if "A?" in status:
            raise AlarmException(status)
        if "?" in message:
            if "?OOR" in message:
                raise SyringePumpValueOORException(message)
            elif "?NA" in message:
                raise SyringePumpInvalidCommandException(message)
            else:
                raise SyringePumpUnforeseenException(message)
        if return_all:
            return address, status, message
        else:
            return message

    def parse(self, value) -> tuple:
        m = self.ansParser.match(value)
        if m is None:
            raise SyringePumpInvalidAnswerException
        # noinspection PyStringFormat
        logger.debug(
            "<<received valid answer from pump [%02s]. Status is '%s' and answer is '%s'"
            % m.groups()
        )
        return m.groups()

    def convert_volume_units_to_uL(self, volume: float):
        """
        The units of the accumulated infusion and withdrawal volumes and the “Volume to be Dispensed” are set according to the diameter setting:
         - From 0.1 to 14.0 mm Syringes smaller than 10 mL: Volume units are "µL"
         - From 14.01 to 50.0 mm Syringes greater than or equal to 10 mL: V olume units are "mL"
        """
        diameter = self.get_diameter_mm()
        if diameter <= 14.0:
            return volume
        else:
            return volume*1e3

    def start(self):
        _, status, _ = self.send_command(self.__CMD_SET_RUNPHASE % 1, True)
        if "A?" in status:
            raise SyringePumpAlarmException(status)
        if not ("I" in status or "W" in status):
            raise SyringePumpUnforeseenException("Pump did not start!")

    def stop(self):
        _, status, _ = self.send_command(self.__CMD_SET_STOP, True)
        if "A?" in status:
            raise AladdinAlarmException(status)
        if "?" in status:
            raise AladdinErrorException(status)
        if "P" not in status:
            raise SyringePumpUnforeseenException("Pump did not stop")

    def reverse(self):
        self.send_command(self.__CMD_SET_DIR % self.__ANS_DIR_REV)

    def is_running(self) -> bool:
        _, status, _ = self.send_command("\r", True)
        return (
                status == self.__ANS_STATUS_INFUSING
                or status == self.__ANS_STATUS_WITHDRAWING
        )

    def clear_accumulated_volume(self):
        self.send_command(self.__CMD_CLEAR_DISVOL % self.__ANS_DIR_INF)
        self.send_command(self.__CMD_CLEAR_DISVOL % self.__ANS_DIR_WDR)

    def clear_target_volume(self):
        self.send_command(self.__CMD_SET_TARVOL % 0.0)

    def set_direction(self, value: SyringePump.STATE):
        if value == self.STATE.INFUSING:
            self.send_command(self.__CMD_SET_DIR % self.__ANS_DIR_INF)
        elif value == self.STATE.WITHDRAWING:
            self.send_command(self.__CMD_SET_DIR % self.__ANS_DIR_WDR)
        else:
            raise SyringePumpInvalidCommandException()

    def set_syringe_diameter_mm(self, value: float):
        if value <= 0:
            raise SyringePumpValueOORException("Diameter must be a positive float value")
        else:
            self.send_command(self.__CMD_SET_DIAMETER % (self.format_float(value)))

    def set_rate(self, value: float, units: int):
        if value <= 0:
            raise SyringePumpValueOORException("Rate must be a positive value")
        if units < 0 or units > len(self.UNITS) - 1:
            raise SyringePumpValueOORException(
                "Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1)
            )
        ans = self.send_command(
            self.__CMD_SET_RATE
            % (self.format_float(value), self.__ANS_UNITS[units])
        )
        if "?" in ans:
            raise SyringePumpInvalidCommandException(ans)

    def set_target_volume_uL(self, value: float):
        """ sets the target volume in μL """
        if value < 0:
            raise SyringePumpValueOORException("Target volume must be a positive float value")
        else:
            diameter = self.get_diameter_mm()
            if diameter>14.0:
                # volume must be sent in mL
                value *= 1e-3
            self.send_command(self.__CMD_SET_TARVOL % (self.format_float(value)))

    def get_diameter_mm(self) -> float:
        ans = self.send_command(self.__CMD_GET_DIAMETER)
        return float(ans)

    def get_rate(self) -> float:
        ans = self.send_command(self.__CMD_GET_RATE)
        return float(ans[:-3])  # strips units

    def get_units(self) -> int:
        ans = self.send_command(self.__CMD_GET_RATE)
        # [-2:] keeps only the last two char, corresponding to the units
        units = ans[-2:]
        if units not in self.__ANS_UNITS:
            raise SyringePumpInvalidAnswerException(f'Cannot parse unit returned by getUnits(): "{units}"')
        return self.__ANS_UNITS.index(units)

    def get_accumulated_infusion_volume_uL(self) -> float:
        ans = self.send_command(self.__CMD_GET_DISVOL)
        m = re.match(self.__ANS_DISVOL_PATTERN, ans)
        if m:
            vol = float(m.group(1))
            units = m.group(3)
            if units.upper().startswith('M'):
                vol *= 1e3
            return vol
        else:
            raise SyringePumpUnforeseenException("Error while parsing accumulated volume")

    def get_accumulated_withdrawal_volume_uL(self) -> float:
        ans = self.send_command(self.__CMD_GET_DISVOL)
        m = re.match(self.__ANS_DISVOL_PATTERN, ans)
        if m:
            vol = float(m.group(2))
            units = m.group(3)
            if units.upper().startswith('M'):
                vol *= 1e3
            return vol
        else:
            raise SyringePumpUnforeseenException("Error while parsing accumulated volume")

    def get_accumulated_volume_uL(self) -> float:
        return self.get_accumulated_infusion_volume_uL()

    def get_target_volume_uL(self) -> float:
        ans = self.send_command(self.__CMD_GET_TARVOL)
        volume = float(ans[:-2])
        units = ans[-2:]
        if units.upper().startswith('M'):
            volume *= 1e3
        return volume

    def get_direction(self) -> SyringePump.STATE:
        if self.is_running():
            ans = self.send_command(self.__CMD_GET_DIR)
            if ans == self.__ANS_DIR_INF:
                return self.STATE.INFUSING
            elif ans == self.__ANS_DIR_WDR:
                return self.STATE.WITHDRAWING
            else:
                raise SyringePumpInvalidAnswerException("Error while parsing direction")
        else:
            return self.STATE.STOPPED

    def get_possible_units(self) -> list:
        return self.UNITS

    def get_version(self) -> str:
        ans = self.send_command(self.__CMD_GET_VERSION)
        m = re.match(self.__ANS_VER_PATTERN, ans)
        if not m:
            raise SyringePumpUnforeseenException("Error while parsing version number")
        else:
            # noinspection PyStringFormat
            return "Model #%s, firmware v%s.%s" % m.groups()

    def do_beep(self, nb_beeps=1):
        self.send_command(self.__CMD_SET_BUZZ % (1, nb_beeps))


class AladdinErrorException(SyringePumpException):
    def __init__(self, status):
        if status == "?COM":
            Exception.__init__(self, "Invalid communications packet received")
        elif status == "?IGN":
            Exception.__init__(
                self, "Command ignored due to a simultaneous new phase start"
            )
        elif status == "?NA":
            Exception.__init__(self, "Command is not currently applicable")
        elif status == "?OOR":
            Exception.__init__(self, "Command data is out of range")
        elif status == "?":
            Exception.__init__(self, "Command is not recognized")
        else:
            Exception.__init__(self, status)


class AlarmException(SyringePumpException):
    pass


class ReadTimeoutException(SyringePumpException):
    pass


class AladdinAlarmException(SyringePumpException):
    def __init__(self, status):
        if status == "A?R":
            Exception.__init__(self, "Pump was reset")
        elif status == "A?S":
            Exception.__init__(self, "Pump motor stalled")
        elif status == "A?T":
            Exception.__init__(self, "Safe mode communications time out")
        elif status == "A?E":
            Exception.__init__(self, "Pumping program error")
        elif status == "A?O":
            Exception.__init__(self, "Pumping program phase is out of range")
        else:
            Exception.__init__(self, status)


def _convert_volume_to_uL(volume: float, units: str):
    volume = float(volume)
    match units[0].upper():
        case 'M':
            volume *= 1e3
        case 'U':
            pass
        case 'N':
            volume *= 1e-3
        case 'P':
            volume *= 1e-6
    return volume


class Harvard11ElitePump(SyringePump):
    __CMD_RUN = 'run'
    __CMD_STOP = 'stop'
    __CMD_STATUS = 'status'
    # noinspection SpellCheckingInspection
    __CMD_CLEAR_ACCUMULATED_VOLUME = 'cvolume'
    # noinspection SpellCheckingInspection
    __CMD_CLEAR_TARGET_VOLUME = 'ctvolume'
    __CMD_VERSION = 'ver'
    __CMD_SET_POLL = 'poll {status}'
    # noinspection SpellCheckingInspection
    __CMD_GET_TARGET_VOL = 'tvolume'
    # noinspection SpellCheckingInspection
    __CMD_SET_TARGET_VOL = 'tvolume {volume} {units}'
    # noinspection SpellCheckingInspection
    __CMD_GET_ACCUMULATED_VOLUME = 'ivolume'
    __CMD_GET_RATE = 'irate'
    __CMD_SET_RATE = 'irate {rate} {units}'
    __CMD_GET_DIAMETER = 'diameter'
    __CMD_SET_DIAMETER = 'diameter {diameter} mm'

    __ANS_TARGET_VOL_NOT_SET = 'Target volume not set.'

    __WAIT_TIME = 0.1  # this is used as a timeout before we enable poll mode
    __TERM_CHAR = b'\x11'

    # noinspection PyMissingConstructor
    def __init__(self, serial_port, address=0, display_name=""):
        logger.setLevel(logging.DEBUG)
        self.serial = serial_port
        self.address = address
        self.display_name = display_name

        self._rate_fL_per_sec = 0
        self._infuse_time_ms = 0
        self._infuse_vol_fL = 0
        self._state = self.STATE.STOPPED
        self._stalled = False
        self._target_reached = False

        self.__PROMPT_PREFIX = f'{self.address:02d}:'
        self.__PROMPT_STP = f'{self.address:02d}:'
        self.__PROMPT_FWD = f'{self.address:02d}>'
        self.__PROMPT_REV = f'{self.address:02d}<'
        self.__PROMPT_STALLED = f'{self.address:02d}:*'
        self.__PROMPT_TARGET_REACHED = f'{self.address:02d}:T*'
        self.__POSSIBLE_PROMPTS = [self.__PROMPT_FWD, self.__PROMPT_REV, self.__PROMPT_STALLED,
                                   self.__PROMPT_TARGET_REACHED, self.__PROMPT_STP]

        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()

        if not self.check_connected():
            raise SyringePumpException(f'Could not communicate with Harvard 11 Elite on port {serial_port.name}')

        self._enable_poll_mode()
        self._get_status()
        self.clear_accumulated_volume()
        self.clear_target_volume()

    def _enable_poll_mode(self, enabled=True):
        cmd = self.__CMD_SET_POLL.format(status='ON' if enabled else 'OFF')
        cmd += '\r'
        self.serial.write(cmd.encode())
        time.sleep(0.1)
        self.serial.read(self.serial.inWaiting())

    def check_connected(self):
        cmd = self.__CMD_VERSION + '\r'
        self.serial.write(cmd.encode())
        time.sleep(0.1)
        ans = self.serial.read(self.serial.inWaiting()).decode()
        return 'ELITE' in ans

    def __del__(self):
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        super().__del__()

    def _send_command(self, command):
        # noinspection DuplicatedCode
        command = f"{self.address:02d}{command}\r\n"
        logger.debug('>>sending command "%s"...' % (command.replace("\r", "\\r")))
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        self.serial.write(command.encode())
        ans = self._get_answer()
        nb_bytes = len(ans)
        logger.debug('<<reading %d bytes in response: "%s"' % (nb_bytes, repr(ans)))
        stripped_ans = self._strip_prompt(ans)
        return stripped_ans

    def _get_answer(self):
        ans = self.serial.read_until(expected=self.__TERM_CHAR).decode()
        if not ans.startswith(self.__PROMPT_PREFIX) and not any(ans.endswith(s+self.__TERM_CHAR.decode()) for s in self.__POSSIBLE_PROMPTS):
            raise SyringePumpInvalidAnswerException(f'answer "{ans}" is not a valid answer')
        return ans

    def _strip_prompt(self, prompt):
        prompt = prompt.replace(self.__TERM_CHAR.decode(), '')
        for p in self.__POSSIBLE_PROMPTS:
            prompt = prompt.replace(p.format(address=self.address), "")
        prompt = prompt.replace(self.__PROMPT_PREFIX, '')
        prompt = prompt.strip()
        return prompt

    def _get_status(self):
        status_str = self._send_command(self.__CMD_STATUS)
        status = status_str.split()
        self._rate_fL_per_sec = int(status[0])
        self._infuse_time_ms = int(status[1])
        self._infuse_vol_fL = int(status[2])
        flags = status[3]
        if flags[0].islower():
            self._state = self.STATE.STOPPED
        else:
            if flags[0] == 'I':
                self._state = self.STATE.INFUSING
            else:
                self._state = self.STATE.WITHDRAWING
        self._stalled = flags[2].upper() == 'S'
        self._target_reached = flags[5].upper() == 'T'

    def start(self):
        self._send_command(self.__CMD_RUN)

    def stop(self):
        self._send_command(self.__CMD_STOP)

    def reverse(self):
        pass  # pump is not capable of reversing

    def is_running(self) -> bool:
        self._get_status()
        return not self._state == self.STATE.STOPPED

    def clear_accumulated_volume(self):
        self._send_command(self.__CMD_CLEAR_ACCUMULATED_VOLUME)

    def clear_target_volume(self):
        self._send_command(self.__CMD_CLEAR_TARGET_VOLUME)

    def set_direction(self, value: SyringePump.STATE):
        pass  # not implemented

    def set_syringe_diameter_mm(self, value: float):
        self._send_command(self.__CMD_SET_DIAMETER.format(diameter=value))

    def set_rate(self, value: float, units: int):
        self._send_command(self.__CMD_SET_RATE.format(rate=value, units=self.UNITS[units]))

    def set_target_volume_uL(self, value):
        self._send_command(self.__CMD_SET_TARGET_VOL.format(volume=value, units='uL'))

    def get_diameter_mm(self):
        ans = self._send_command(self.__CMD_GET_DIAMETER)
        dia, units = ans.split()
        return float(dia)

    def get_rate(self):
        ans = self._send_command(self.__CMD_GET_RATE)
        value, units = ans.split()
        return float(value)  # FIXME: need to uniform units

    def get_units(self):
        ans = self._send_command(self.__CMD_GET_RATE)
        value, units = ans.split()
        try:
            ix = [u.upper() for u in self.UNITS].index(units.upper())
        except ValueError:
            raise SyringePumpInvalidAnswerException(f'Could not understand units {units}')
        return ix

    def get_accumulated_volume_uL(self) -> float:
        ans = self._send_command(self.__CMD_GET_ACCUMULATED_VOLUME)
        volume, units = ans.split()
        volume = _convert_volume_to_uL(volume, units)
        return volume

    def get_target_volume_uL(self) -> float:
        ans = self._send_command(self.__CMD_GET_TARGET_VOL)
        if ans == self.__ANS_TARGET_VOL_NOT_SET:
            return 0.0
        else:
            volume, units = ans.split()
            volume = _convert_volume_to_uL(volume, units)
            return volume

    def get_direction(self) -> SyringePump.STATE:
        return self.STATE.INFUSING

    def get_possible_units(self) -> list[str]:
        return self.UNITS


AVAIL_PUMP_MODULES = {
    "dummy": DummyPump,
    "aladdin": AladdinPump,
    "model11plus": Model11plusPump,
    "Harvard11Elite": Harvard11ElitePump
}
