import logging
import re
from enum import IntEnum
import serial
import time

from PyQt5.QtCore import QTimer

logger = logging.getLogger(__name__)

# bolus injection done at 1 mL/min
BOLUS_RATE = 1.0
BOLUS_RATE_UNITS: int = 1


class SyringePump(object):
    """
    This is an abstract class that declares the functions available
    to control a syringe pump of any brand
    """
    UNITS = ['mL/hr', 'mL/min', 'uL/hr', 'uL/min']

    class STATE(IntEnum):
        STOPPED = 0
        INFUSING = 1
        WITHDRAWING = 2

    minVal = 0.001
    maxVal = 9999

    def __init__(self):
        """
        constructor
        """
        pass

    def __del__(self):
        """
        Destructor to cleanly close the serial object if need
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

    def isRunning(self):
        """
        returns True if the pump is running (infusion or withdrawing)
        and False if it is stopped
        """
        pass

    def clearAccumulatedVolume(self):
        """
        resets to 0 the volume of liquid pumped
        """
        pass

    def clearTargetVolume(self):
        """
        clears the target volume for the pump. This should put the pump in
        continuous injection mode
        """
        pass

    def setDirection(self, inValue):
        """
        defines the direction that the pump will run.
        inValue is an int representation of the directions that the pump is capable of running in
        """
        pass

    def setSyringeDiameter(self, inValue):
        """
        defines the diameter of the syringe in mm
        """
        pass

    def setRate(self, inValue, inUnits):
        """
        sets the rate of the pump
        optionally, one can also change the units (see set units)
        """
        pass

    def setTargetVolume(self, inValue):
        """
        puts the pump in fixed amount mode and defines the volume
        after which it will stop pumping
        """
        pass

    def getDiameter(self):
        """
        returns the current diameter (in mm) of the syringe
        """
        pass

    def getRate(self):
        """
        returns the current rate of pumping as a float
        """
        pass

    def getUnits(self):
        """
        return the current units as an int
        """
        pass

    def getAccumulatedVolume(self):
        """
        returns the amount of liquid pumped so far as a float. Units might vary
        """
        pass

    def getTargetVolume(self):
        """
        returns the target volume for the pump as a float. Units might vary
        """
        pass

    def getDirection(self):
        """
        returns the current direction of the pump as an int
        """
        pass

    def getPossibleUnits(self):
        """
        returns an array of the possible units accepted by this pump
        """
        pass


class SyringePumpException(Exception):
    pass


class ValueOORException(SyringePumpException):
    pass


class UnknownCommandException(SyringePumpException):
    pass


class PumpNotRunningException(SyringePumpException):
    pass


class PumpNotStoppedException(SyringePumpException):
    pass


class PumpInvalidAnswerException(SyringePumpException):
    pass


class SyringeAlarmException(SyringePumpException):
    pass


class InvalidCommandException(SyringePumpException):
    pass


class UnforeseenException(SyringePumpException):
    pass


class DummyPump(SyringePump):
    # noinspection PyMissingConstructor
    def __init__(self, serial_port: serial.Serial, diameter=10, rate=20, units=0):
        self.serial = serial_port
        self.currDir = self.STATE.INFUSING
        self.currState = self.STATE.STOPPED
        self.currDiameter = diameter
        self.currRate = rate
        self.currUnits = units
        self.targetVolume = 0

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

    def isRunning(self):
        return not self.currState == self.STATE.STOPPED

    def clearAccumulatedVolume(self):
        pass

    def clearTargetVolume(self):
        self.targetVolume = 0

    def setDirection(self, inValue: SyringePump.STATE):
        self.currDir = inValue

    def setSyringeDiameter(self, inValue: int):
        if inValue <= 0:
            raise ValueOORException("Diameter must be a positive value")
        else:
            self.currDiameter = inValue

    def setRate(self, inRate: int, inUnits: int):
        if inRate <= 0:
            raise ValueOORException("Rate must be a positive value")
        if inUnits < 0 or inUnits > (len(self.UNITS) - 1):
            raise ValueOORException("Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1))
        self.currRate = inRate
        self.currUnits = inUnits

    def setTargetVolume(self, inValue):
        self.targetVolume = inValue

    def getDiameter(self):
        return self.currDiameter

    def getRate(self):
        return self.currRate

    def getUnits(self):
        return self.currUnits

    def getAccumulatedVolume(self):
        return 0

    def getTargetVolume(self):
        return 0

    def getDirection(self):
        return self.currDir

    def getPossibleUnits(self):
        return self.UNITS


class Model11plusPump(SyringePump):
    __PROMPT_STP = '\r\n:'
    __PROMPT_FWD = '\r\n>'
    __PROMPT_REV = '\r\n<'
    __ANS_OOR = '\r\nOOR'
    __ANS_UNKNOWN = '\r\n?'
    __CMD_RUN = 'RUN\r'
    __CMD_STOP = 'STP\r'
    __CMD_CLEAR_VOLUME = 'CLV\r'
    __CMD_CLEAR_TARGET = 'CLT\r'
    __CMD_REV = 'REV\r'
    __CMD_SET_DIAMETER = 'MMD %5.4f\r'
    __CMD_SET_FLOW_UL_H = 'ULH %5.4f\r'
    __CMD_SET_FLOW_UL_MIN = 'ULM %5.4f\r'
    __CMD_SET_FLOW_ML_H = 'MLH %5.4f\r'
    __CMD_SET_FLOW_ML_MIN = 'MLM %5.4f\r'
    __CMD_SET_RATE = [__CMD_SET_FLOW_ML_H, __CMD_SET_FLOW_ML_MIN, __CMD_SET_FLOW_UL_H, __CMD_SET_FLOW_UL_MIN]
    __CMD_SET_TARGET = 'MLT %5.4f\r'
    __CMD_GET_DIAMETER = 'DIA\r'
    __CMD_GET_RATE = 'RAT\r'
    __CMD_GET_UNITS = 'RNG\r'
    __CMD_GET_VOLUME = 'VOL\r'
    __CMD_GET_VERSION = 'VER\r'
    __CMD_GET_TARGET = 'TAR\r'
    __CMD_QUIT_REMOTE = 'KEY\r'

    # noinspection PyMissingConstructor
    def __init__(self, serial_port):
        self.serial = serial_port
        if serial_port is not None:
            self.serial.flush()
            self.serial.flushInput()
            self.serial.flushOutput()
        self.currUnits = 0

    def __del__(self):
        if self.serial is not None:
            self.sendCommand(self.__CMD_QUIT_REMOTE)
            self.serial.flush()
            self.serial.flushInput()
            self.serial.flushOutput()
            self.serial.close()

    def getInfo(self):
        return self.getStatus()

    def sendCommand(self, inCommand):
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        logger.debug("sending command \"%s\"..." % inCommand)
        self.serial.write(inCommand)
        time.sleep(0.3)
        nbChar = self.serial.inWaiting()
        ans = str(self.serial.read(nbChar))
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        # print "reading %d bytes in response: \"%s\""%(nbChar,repr(ans)) #DEBUG
        if ans.startswith(self.__ANS_OOR):
            # print "OOR Error encountered!" #DEBUG
            raise ValueOORException()
        elif ans.startswith(self.__ANS_UNKNOWN):
            # print "Unknown command Error encountered!" #DEBUG
            raise UnknownCommandException()
        else:
            return ans

    def stripPrompt(self, inString):
        inString = inString.replace(self.__PROMPT_STP, '')
        inString = inString.replace(self.__PROMPT_FWD, '')
        inString = inString.replace(self.__PROMPT_REV, '')
        inString = inString.strip()
        return inString

    def run(self):
        self.sendCommand(self.__CMD_RUN)
        ans = self.getDirection()
        if ans == "FWD" or ans == "REV":
            pass
        else:
            raise PumpNotRunningException()

    def start(self):
        self.run()

    def stop(self):
        self.sendCommand(self.__CMD_STOP)
        ans = self.getDirection()
        if ans == "STOPPED":
            pass
        else:
            raise PumpNotStoppedException()

    def clearAccumulatedVolume(self):
        self.sendCommand(self.__CMD_CLEAR_VOLUME)

    def clearTargetVolume(self):
        self.sendCommand(self.__CMD_CLEAR_TARGET)

    def reverse(self):
        self.sendCommand(self.__CMD_REV)

    def setSyringeDiameter(self, inDiameter):
        self.sendCommand(self.__CMD_SET_DIAMETER % inDiameter)

    def setRate(self, inValue, inUnits):
        if inValue <= 0:
            raise ValueOORException("Rate must be a positive value")
        if inUnits < 0 or (inUnits > len(self.UNITS) - 1):
            raise ValueOORException("Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1))
        self.sendCommand((self.__CMD_SET_RATE[self.currUnits]) % inValue)  # FIXME: this needs fixing

    def setTargetVolume(self, inValue):
        self.sendCommand(self.__CMD_SET_TARGET % inValue)

    def getDiameter(self):
        diameter = self.sendCommand(self.__CMD_GET_DIAMETER)
        diameter = self.stripPrompt(diameter)
        return float(diameter)

    def getRate(self):
        rate = self.sendCommand(self.__CMD_GET_RATE)
        rate = self.stripPrompt(rate)
        return float(rate)

    def getAccumulatedVolume(self):
        volume = self.sendCommand(self.__CMD_GET_VOLUME)
        volume = self.stripPrompt(volume)
        return float(volume)

    def getVersion(self):
        version = self.sendCommand(self.__CMD_GET_VERSION)
        version = self.stripPrompt(version)
        return version

    def getTargetVolume(self):
        target = self.sendCommand(self.__CMD_GET_TARGET)
        target = self.stripPrompt(target)
        return float(target)

    def getUnits(self):
        units = self.sendCommand(self.__CMD_GET_UNITS)
        units = self.stripPrompt(units)
        if units == 'ML/HR':
            return 'ML/HR'
        elif units == 'ML/MIN':
            return 'ML/MIN'
        elif units == 'UL/HR':
            return 'UL/HR'
        elif units == 'UL/MIN':
            return 'UL/MIN'
        else:
            raise LookupError

    def getDirection(self):
        _ = self.sendCommand("\r")
        _ = self.sendCommand("\r")
        ans = self.sendCommand("\r")
        if ans == self.__PROMPT_FWD:
            return "FWD"
        elif ans == self.__PROMPT_REV:
            return "REV"
        elif ans == self.__PROMPT_STP:
            return "STOPPED"

    def getStatus(self):
        port = self.serial.portstr
        version = self.getVersion()
        diameter = self.getDiameter()
        rate = self.getRate()
        units = self.getUnits()
        target = self.getTargetVolume()
        volume = self.getAccumulatedVolume()
        direction = self.getDirection()
        return "Syringe Pump v.%s (%s) {direction: %s, diameter: %.4f mm, rate: %.4f %s, accumulated volume: %.4f, " \
               "target volume: %.4f}" \
               % (version, port, direction, diameter, rate, units, volume, target)

    def printStatus(self):
        print(self.getStatus())

    def setDirection(self, inValue):
        pass

    def isRunning(self):
        return True

    def getPossibleUnits(self):
        return ''


# noinspection SpellCheckingInspection
class AladdinPump(SyringePump):
    _readTimeout = 1  # second
    # ******* PUMP ANSWERS ******
    __ANS_TRUE = '1'
    __ANS_FALSE = '0'
    # direction
    __ANS_DIR_INF = 'INF'
    __ANS_DIR_WDR = 'WDR'
    __ANS_DIR_REV = 'REV'
    # units
    __ANS_UNITS_ML = 'ML'
    __ANS_UNITS_UL = 'UL'
    __ANS_UNITS_ULMIN = 'UM'
    __ANS_UNITS_ULHR = 'UH'
    __ANS_UNITS_MLMIN = 'MM'
    __ANS_UNITS_MLHR = 'MH'
    __ANS_UNITS = [__ANS_UNITS_MLHR, __ANS_UNITS_MLMIN, __ANS_UNITS_ULHR, __ANS_UNITS_ULMIN]
    # status message
    __ANS_STATUS_INFUSING = 'I'
    __ANS_STATUS_WITHDRAWING = 'W'
    __ANS_STATUS_STOPPED = 'S'
    __ANS_STATUS_PAUSED = 'P'
    __ANS_STATUS_PAUSEPHASE = 'T'
    __ANS_STATUS_TRIGGERWAIT = 'U'
    # alarm message
    __ANS_ALARM_RESET = 'R'
    __ANS_ALARM_STALLED = 'S'
    __ANS_ALARM_TIMEOUT = 'T'
    __ANS_ALARM_PROGERROR = 'E'
    __ANS_ALARM_PHASEOOR = 'O'
    # regexp to extract status and message in response packet
    __ANS_PATTERN = r'''^\x02([0-9]{2})([''' + \
                    __ANS_STATUS_INFUSING + \
                    __ANS_STATUS_WITHDRAWING + \
                    __ANS_STATUS_STOPPED + \
                    __ANS_STATUS_PAUSED + \
                    __ANS_STATUS_PAUSEPHASE + \
                    __ANS_STATUS_TRIGGERWAIT + \
                    ''']|A\?[''' + \
                    __ANS_ALARM_RESET + \
                    __ANS_ALARM_STALLED + \
                    __ANS_ALARM_TIMEOUT + \
                    __ANS_ALARM_PROGERROR + \
                    __ANS_ALARM_PHASEOOR + \
                    '''])(.*)\x03$'''
    # regexp to extract model and version numbers
    __ANS_VER_PATTERN = r'^NE([0-9]+)V([0-9]+).([0-9]+)$'
    # regexp to extract dispensed volume
    __ANS_DISVOL_PATTERN = r'^I([0-9\.]+)W([0-9\.]+)([UML]{2})$'
    # error codes
    __ANS_ERROR_UNRECOGNIZED = '?'
    __ANS_ERROR_NOTAPPLICABLE = '?NA'
    __ANS_ERROR_OOR = '?OOR'
    __ANS_ERROR_COMERR = '?COM'
    __ANS_ERROR_IGNORED = '?IGN'
    # trigger modes
    __ANS_TRIG_FOOT = 'FT'
    __ANS_TRIG_TTL = 'LE'
    __ANS_TRIG_START = 'ST'

    # ******* Commands *******
    # GET commands
    __CMD_GET_DIAMETER = 'DIA\r'  # get the syringe diameter
    __CMD_GET_PHASE = 'PHN\r'  # get the phase number
    __CMD_GET_PHASEFUNCTION = 'FUN\r'  # get the program's phase function
    __CMD_GET_RATE = 'RAT\r'  # get the rate of inf/withdraw, including unit
    __CMD_GET_TARVOL = 'VOL\r'  # get target volume, incl units
    __CMD_GET_DIR = 'DIR\r'  # get the direction of the pump
    __CMD_GET_DISVOL = 'DIS\r'  # get the volume dispensed in infusion as well as in withdrawal
    __CMD_GET_ALARM = 'AL\r'  # get current alarm mode
    __CMD_GET_POWERFAIL = 'PF\r'  # get current power failure mode
    __CMD_GET_TRIGMODE = 'TRG\r'  # get current trigger mode
    __CMD_GET_TTLDIR = 'DIN\r'  # get TTL directional control mode
    __CMD_GET_TTLOUT = 'ROM\r'  # get TTL output mode
    __CMD_GET_KEYLOCK = 'LOC\r'  # get state of keypad lock
    __CMD_GET_KEYBEEP = 'BP\r'  # get keypad beep mode
    __CMD_GET_TTLIO = 'IN\r'  # get ttl level of TTL I/O connector
    __CMD_GET_BUZZ = 'BUZ\r'  # gets whether buzzer is buzzing
    __CMD_GET_VERSION = 'VER\r'  # gets the model number and the firmware version
    # SET commands
    __CMD_SET_DIAMETER = 'DIA%.2f\r'  # set the syringe diameter
    __CMD_SET_PHASE = 'PHN%d\r'  # set the phase number
    __CMD_SET_PHASEFUNCTION = 'FUN%d\r'  # set the program's phase function
    # ... bunch of other instructions could be here. cf p50 of the manual
    __CMD_SET_RATE = 'RAT%s%s\r'  # set the rate of inf/withdraw, including unit
    __CMD_SET_TARVOL = 'VOL%s\r'  # set target volume, units depends on diameter
    __CMD_SET_DIR = 'DIR%s\r'  # set the direction of the pump
    __CMD_SET_RUNPHASE = 'RUN%d\r'  # start the pumping program
    __CMD_SET_STOP = 'STP\r'  # stops the pump
    __CMD_CLEAR_DISVOL = 'CLD%s\r'  # clears dispensed volume in INF or WITHDR
    __CMD_SET_ADDRESS = 'ADR%02d\r'  # sets the network address
    __CMD_SET_SAFEMODE = 'SAF%03d\r'  # enables safe mode communication
    __CMD_SET_ALARM = 'AL%d\r'  # set the alarm mode
    __CMD_SET_POWERFAIL = 'PF%d\r'  # set current power failure mode
    __CMD_SET_TRIGMODE = 'TRG%s\r'  # set current trigger mode
    __CMD_SET_TTLDIR = 'DIN%d\r'  # set TTL directional control mode
    __CMD_SET_TTLOUT = 'ROM%d\r'  # set TTL output mode
    __CMD_SET_KEYLOCK = 'LOC%d\r'  # set state of keypad lock
    __CMD_SET_KEYBEEP = 'BP%d\r'  # set keypad beep mode
    __CMD_SET_TTLIO = 'OUT5%s\r'  # set ttl level of TTL I/O connector pin 5
    __CMD_SET_BUZZ = 'BUZ%d%d\r'  # sets whether buzzer is buzzing

    @staticmethod
    def format_float(val):
        return '{:05.3f}'.format(val)[:5]

    # noinspection PyMissingConstructor
    def __init__(self, serial_port, address=0):
        self.address = address
        self.ansParser = re.compile(self.__ANS_PATTERN)
        self.serial = serial_port
        if self.serial is not None:
            self.serial.flush()
            self.serial.flushInput()
            self.serial.flushOutput()
        self.doBeep()

    def __del__(self):
        pass

    def getInfo(self):
        port = self.serial.portstr
        version = self.getVersion()
        diameter = self.getDiameter()
        rate = self.getRate()
        units = self.UNITS[self.getUnits()]
        target = self.getTargetVolume()
        volume = self.getAccumulatedVolume()
        direction = self.getDirection().name
        return "Syringe Pump %s (%s) {direction: %s, diameter: %04f mm, rate: %04f %s, accumulated volume: %04f, " \
               "target volume: %04f}" \
               % (version, port, direction, diameter, rate, units, volume, target)

    def sendCommand(self, inCommand, returnAll=False):
        if self.serial is None:
            raise UnforeseenException('No serial port connected')
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        logger.debug(">>sending command \"%02d%s\"..." % (self.address, inCommand.replace('\r', '\\r')))
        self.serial.write(inCommand.encode())
        sendTime = time.time()
        ans = ''
        nbBytes = 0
        while ans[-1:] != '\x03':
            nbChar = self.serial.inWaiting()
            nbBytes += nbChar
            ans += self.serial.read(nbChar).decode()
            if (time.time() - sendTime) > self._readTimeout:
                raise ReadTimeoutException("Timeout while waiting for an answer")
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        logger.debug("<<reading %d bytes in response: \"%s\"" % (nbBytes, repr(ans)))
        address, status, message = self.parse(ans)
        if 'A?' in status:
            raise AlarmException(status)
        if '?' in message:
            if '?OOR' in message:
                raise ValueOORException(message)
            elif '?NA' in message:
                raise InvalidCommandException(message)
            else:
                raise UnforeseenException(message)
        if returnAll:
            return address, status, message
        else:
            return message

    def parse(self, inVal):
        m = self.ansParser.match(inVal)
        if m is None:
            raise PumpInvalidAnswerException
        # noinspection PyStringFormat
        logger.debug("<<received valid answer from pump [%02s]. Status is '%s' and answer is '%s'" % m.groups())
        return m.groups()

    def start(self):
        _, status, _ = self.sendCommand(self.__CMD_SET_RUNPHASE % 1, True)
        if 'A?' in status:
            raise SyringeAlarmException(status)
        if not ('I' in status or 'W' in status):
            raise UnforeseenException("Pump did not start!")

    def stop(self):
        _, status, _ = self.sendCommand(self.__CMD_SET_STOP, True)
        if 'A?' in status:
            raise AladdinAlarmException(status)
        if '?' in status:
            raise AladdinErrorException(status)
        if 'P' not in status:
            raise UnforeseenException("Pump did not stop")

    def reverse(self):
        self.sendCommand(self.__CMD_SET_DIR % self.__ANS_DIR_REV)

    def isRunning(self):
        _, status, _ = self.sendCommand('\r', True)
        return status == self.__ANS_STATUS_INFUSING or status == self.__ANS_STATUS_WITHDRAWING

    def clearAccumulatedVolume(self):
        self.sendCommand(self.__CMD_CLEAR_DISVOL % self.__ANS_DIR_INF)
        self.sendCommand(self.__CMD_CLEAR_DISVOL % self.__ANS_DIR_WDR)

    def clearTargetVolume(self):
        self.sendCommand(self.__CMD_SET_TARVOL % 0.0)

    def setDirection(self, inValue):
        if inValue == self.STATE.INFUSING:
            self.sendCommand(self.__CMD_SET_DIR % self.__ANS_DIR_INF)
        elif inValue == self.STATE.WITHDRAWING:
            self.sendCommand(self.__CMD_SET_DIR % self.__ANS_DIR_WDR)
        else:
            raise InvalidCommandException()

    def setSyringeDiameter(self, inValue):
        if inValue <= 0:
            raise ValueOORException("Diameter must be a positive float value")
        else:
            self.sendCommand(self.__CMD_SET_DIAMETER % (self.format_float(inValue)))

    def setRate(self, inValue, inUnits):
        if inValue <= 0:
            raise ValueOORException("Rate must be a positive value")
        if inUnits < 0 or inUnits > len(self.UNITS) - 1:
            raise ValueOORException("Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1))
        ans = self.sendCommand(self.__CMD_SET_RATE % (self.format_float(inValue), self.__ANS_UNITS[int(inUnits)]))
        if '?' in ans:
            raise InvalidCommandException(ans)

    def setTargetVolume(self, inValue):
        if inValue <= 0:
            raise ValueOORException("Target volume must be a positive float value")
        else:
            self.sendCommand(self.__CMD_SET_TARVOL % (self.format_float(inValue)))

    def getDiameter(self):
        ans = self.sendCommand(self.__CMD_GET_DIAMETER)
        return float(ans)

    def getRate(self):
        ans = self.sendCommand(self.__CMD_GET_RATE)
        return float(ans[:-3])  # strips units

    def getUnits(self):
        ans = self.sendCommand(self.__CMD_GET_RATE)
        # [-2:] keeps only the last two char, corresponding to the units
        if ans[-2:] == self.__ANS_UNITS_MLHR:
            return 0
        elif ans[-2:] == self.__ANS_UNITS_MLMIN:
            return 1
        elif ans[-2:] == self.__ANS_UNITS_ULHR:
            return 2
        elif ans[-2:] == self.__ANS_UNITS_ULMIN:
            return 3
        else:
            raise UnforeseenException("ERROR while parsing rate value")

    def getAccumulatedInfusionVolume(self):
        ans = self.sendCommand(self.__CMD_GET_DISVOL)
        m = re.match(self.__ANS_DISVOL_PATTERN, ans)
        if m:
            return float(m.group(1))
        else:
            raise UnforeseenException("Error while parsing accumulated volume")

    def getAccumulatedWithdrawalVolume(self):
        ans = self.sendCommand(self.__CMD_GET_DISVOL)
        m = re.match(self.__ANS_DISVOL_PATTERN, ans)
        if m:
            return float(m.group(2))
        else:
            raise UnforeseenException("Error while parsing accumulated volume")

    def getAccumulatedVolume(self):
        return self.getAccumulatedInfusionVolume()

    def getTargetVolume(self):
        ans = self.sendCommand(self.__CMD_GET_TARVOL)
        return float(ans[:-2])  # strips units

    def getDirection(self):
        if self.isRunning():
            ans = self.sendCommand(self.__CMD_GET_DIR)
            if ans == self.__ANS_DIR_INF:
                return self.STATE.INFUSING
            elif ans == self.__ANS_DIR_WDR:
                return self.STATE.WITHDRAWING
            else:
                return LookupError('Error while parsing direction')
        else:
            return self.STATE.STOPPED

    def getPossibleUnits(self):
        return self.UNITS

    def getVersion(self):
        ans = self.sendCommand(self.__CMD_GET_VERSION)
        m = re.match(self.__ANS_VER_PATTERN, ans)
        if not m:
            raise UnforeseenException("Error while parsing version number")
        else:
            # noinspection PyStringFormat
            return 'Model #%s, firmware v%s.%s' % m.groups()

    def doBeep(self, nbBeeps=1):
        self.sendCommand(self.__CMD_SET_BUZZ % (1, nbBeeps))


class AladdinErrorException(SyringePumpException):
    def __init__(self, status):
        if status == '?COM':
            Exception.__init__(self, "Invalid communications packet received")
        elif status == '?IGN':
            Exception.__init__(self, "Command ignored due to a simultaneous new phase start")
        elif status == '?NA':
            Exception.__init__(self, "Command is not currently applicable")
        elif status == '?OOR':
            Exception.__init__(self, "Command data is out of range")
        elif status == '?':
            Exception.__init__(self, "Command is not recognized")
        else:
            Exception.__init__(self, status)


class AlarmException(SyringePumpException):
    pass


class ReadTimeoutException(SyringePumpException):
    pass


class AladdinAlarmException(SyringePumpException):
    def __init__(self, status):
        if status == 'A?R':
            Exception.__init__(self, "Pump was reset")
        elif status == 'A?S':
            Exception.__init__(self, "Pump motor stalled")
        elif status == 'A?T':
            Exception.__init__(self, "Safe mode communications time out")
        elif status == 'A?E':
            Exception.__init__(self, "Pumping program error")
        elif status == 'A?O':
            Exception.__init__(self, "Pumping program phase is out of range")
        else:
            Exception.__init__(self, status)


AVAIL_PUMP_MODULES = {'dummy': DummyPump,
                      'aladdin': AladdinPump,
                      'model11plus': Model11plusPump}
