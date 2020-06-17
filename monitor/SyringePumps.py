import re
from enum import IntEnum

import serial
import time

# bolus injection done at 1 mL/min
BOLUS_RATE = 1.0
BOLUS_RATE_UNITS = 1


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

    def __init__(self):
        """
        constructor
        """
        raise NotImplementedError("Constructor needs to be implemented")

    def __del__(self):
        """
        Destructor to cleanly close the serial object if need
        """
        raise NotImplementedError()

    def start(self):
        """
        starts the pump with the parameters defined beforehand
        """
        raise NotImplementedError()

    def stop(self):
        """
        stops the pump
        """
        raise NotImplementedError()

    def reverse(self):
        """
        reverse the flow of the pump (if available)
        """
        raise NotImplementedError()

    def isRunning(self):
        """
        returns True if the pump is running (infusion or withdrawing)
        and False if it is stopped
        """
        raise NotImplementedError()

    def clearAccumulatedVolume(self):
        """
        resets to 0 the volume of liquid pumped
        """
        raise NotImplementedError()

    def clearTargetVolume(self):
        """
        clears the target volume for the pump. This should put the pump in
        continuous injection mode
        """
        raise NotImplementedError()

    def setDirection(self, inValue):
        """
        defines the direction that the pump will run.
        inValue is an int representation of the directions that the pump is capable of running in
        """
        raise NotImplementedError()

    def setSyringeDiameter(self, inValue):
        """
        defines the diameter of the syringe in mm
        """
        raise NotImplementedError()

    def setRate(self, inValue, inUnits):
        """
        sets the rate of the pump
        optionally, one can also change the units (see set units)
        """
        raise NotImplementedError()

    def setTargetVolume(self, inValue):
        """
        puts the pump in fixed amount mode and defines the volume
        after which it will stop pumping
        """
        raise NotImplementedError()

    def getDiameter(self):
        """
        returns the current diameter (in mm) of the syringe
        """
        raise NotImplementedError()

    def getRate(self):
        """
        returns the current rate of pumping as a float
        """
        raise NotImplementedError()

    def getUnits(self):
        """
        return the current units as an int
        """
        raise NotImplementedError()

    def getAccumulatedVolume(self):
        """
        returns the amount of liquid pumped so far as a float. Units might vary
        """
        raise NotImplementedError()

    def getTargetVolume(self):
        """
        returns the target volume for the pump as a float. Units might vary
        """
        raise NotImplementedError()

    def getDirection(self):
        """
        returns the current direction of the pump as an int
        """
        raise NotImplementedError()

    def getPossibleUnits(self):
        """
        returns an array of the possible units accepted by this pump
        """
        raise NotImplementedError()


class SyringePumpException(Exception):
    pass


class valueOORException(SyringePumpException):
    pass


class unknownCommandException(SyringePumpException):
    pass


class pumpNotRunningException(SyringePumpException):
    pass


class pumpNotStoppedException(SyringePumpException):
    pass


class pumpInvalidAnswerException(SyringePumpException):
    pass


class invalidCommandException(SyringePumpException):
    pass


class unforseenException(SyringePumpException):
    pass


class DummyPump(SyringePump):
    def __init__(self, serialport: serial.Serial):
        self.serial = serialport
        self.currState = 0
        self.nextState = 1
        self.currDiameter = 10
        self.currRate = 20
        self.currUnits = 0

    def __del__(self):
        pass

    def getInfo(self):
        retVal = '''fake pump on serial port %s (%s baud)
        syringe diameter: %.2f
        current rate: %.2f
        current state: ''' % (self.serial.port,
                              self.serial.baudrate, self.getDiameter(), self.getRate())
        if self.isRunning():
            if self.getDirection() == 1:
                retVal += 'Infusing...'
            else:
                retVal += 'Withdrawing...'
        else:
            retVal += 'Stopped'
        return retVal

    def start(self):
        if self.currState == 0:
            self.currState = self.nextState
        else:
            raise invalidCommandException("Pump already started")

    def stop(self):
        if self.currState == 1 or self.currState == 2:
            self.nextState = self.currState
            self.currState = 0
        else:
            raise invalidCommandException("Pump already stopped")

    def reverse(self):
        if not self.currState == 0:
            if self.currState == 1:
                self.currState = 2
            else:
                self.currState = 1
        else:
            if self.nextState == 1:
                self.nextState = 2
            else:
                self.nextState = 1

    def isRunning(self):
        return not self.currState == 0

    def clearAccumulatedVolume(self):
        pass

    def clearTargetVolume(self):
        pass

    def setDirection(self, inValue):
        if 0 < inValue <= (len(self.DIRECTIONS) - 1):
            if self.isRunning():
                self.currState = inValue
            else:
                self.nextState = inValue
        else:
            raise unknownCommandException("direction should be either INFUSION or WITHDRAWAL")

    def setSyringeDiameter(self, inValue):
        if inValue <= 0:
            raise valueOORException("Diameter must be a positive value")
        else:
            self.currDiameter = inValue

    def setRate(self, inValue, inUnits):
        if inValue <= 0:
            raise valueOORException("Rate must be a positive value")
        if inUnits < 0 or inUnits > (len(self.UNITS) - 1):
            raise valueOORException("Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1))
        self.currUnits = inValue
        self.currRate = inValue

    def setTargetVolume(self, inValue):
        pass

    def getDiameter(self):
        return self.diameter

    def getRate(self):
        return self.rate

    def getUnits(self):
        return self.units

    def getAccumulatedVolume(self):
        return 0

    def getTargetVolume(self):
        return 0

    def getDirection(self):
        if self.isRunning():
            return self.currState
        else:
            return self.nextState

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

    def __init__(self, serialport):
        self.serial = serialport
        if serialport is not None:
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
        # logging.debug("sending command \"%s\"..." % inCommand)
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
            raise valueOORException()
        elif ans.startswith(self.__ANS_UNKNOWN):
            # print "Unknown command Error encountered!" #DEBUG
            raise unknownCommandException()
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
            raise pumpNotRunningException()

    def start(self):
        self.run()

    def stop(self):
        self.sendCommand(self.__CMD_STOP)
        ans = self.getDirection()
        if ans == "STOPPED":
            pass
        else:
            raise pumpNotStoppedException()

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
            raise valueOORException("Rate must be a positive value")
        if inUnits < 0 or (inUnits > len(self.UNITS) - 1):
            raise valueOORException("Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1))
        self.sendCommand((self.__CMD_SET_RATE[self.currUnits]) % inValue)  # FIXME: this needs fixin'

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
    __CMD_GET_RATE = 'RAT\r'  # get the rate of inf/withd, including unit
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
    __CMD_SET_RATE = 'RAT%05.3f%s\r'  # set the rate of inf/withdr, including unit
    __CMD_SET_TARVOL = 'VOL%05.3f\r'  # set target volume, units depends on diameter
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

    def __init__(self, serialport, address=0):
        self.address = address
        self.ansParser = re.compile(self.__ANS_PATTERN)
        self.serial = serialport
        if serial is not None:
            self.serial.flush()
            self.serial.flushInput()
            self.serial.flushOutput()

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
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        # logging.debug("~~sending command \"%02d%s\"..." % (self.address, inCommand.replace('\r', '\\r')))
        self.serial.write(inCommand.encode())
        sendTime = time.time()
        ans = ''
        nbBytes = 0
        while ans[-1:] != '\x03':
            nbChar = self.serial.inWaiting()
            nbBytes += nbChar
            ans += self.serial.read(nbChar).decode()
            if (time.time() - sendTime) > self._readTimeout:
                raise readTimeoutException("Timeout while waiting for an answer")
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()
        # logging.debug("~~reading %d bytes in response: \"%s\"" % (nbBytes, repr(ans)))
        address, status, message = self.parse(ans)
        if 'A?' in status:
            raise alarmException(status)
        if '?' in message:
            raise errorException(message)
        if returnAll:
            return address, status, message
        else:
            return message

    def parse(self, inVal):
        m = self.ansParser.match(inVal)
        if not m:
            raise pumpInvalidAnswerException
        # logging.debug("~~received valid answer from pump [%02s]. Status is '%s' and answer is '%s'" % m.groups())
        return m.groups()

    def start(self):
        _, status, _ = self.sendCommand(self.__CMD_SET_RUNPHASE % (1), True)
        if 'A?' in status:
            self.alarm(status)
        if not ('I' in status or 'W' in status):
            raise unforseenException("Pump did not start!")

    def stop(self):
        _, status, _ = self.sendCommand(self.__CMD_SET_STOP, True)
        if 'A?' in status:
            self.alarm(status)
        if '?' in status:
            self.error(status)
        if 'P' not in status:
            raise unforseenException("Pump did not stop")

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
            raise invalidCommandException()

    def setSyringeDiameter(self, inValue):
        if inValue <= 0:
            raise valueOORException("Diameter must be a positive float value")
        else:
            self.sendCommand(self.__CMD_SET_DIAMETER % (float(inValue)))

    def setRate(self, inValue, inUnits):
        if inValue <= 0:
            raise valueOORException("Rate must be a positive value")
        if inUnits < 0 or inUnits > len(self.UNITS) - 1:
            raise valueOORException("Units must be an integer between %d and %d" % (0, len(self.UNITS) - 1))
        ans = self.sendCommand(self.__CMD_SET_RATE % (inValue, self.__ANS_UNITS[int(inUnits)]))
        if '?' in ans:
            raise invalidCommandException(ans)

    def setTargetVolume(self, inValue):
        if inValue <= 0:
            raise valueOORException("Target volume must be a positive float value")
        else:
            self.sendCommand(self.__CMD_SET_TARVOL % (float(inValue)))

    def getDiameter(self):
        ans = self.sendCommand(self.__CMD_GET_DIAMETER)
        return float(ans)

    def getRate(self):
        ans = self.sendCommand(self.__CMD_GET_RATE)
        return float(ans[:-2])  # strips units

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
            raise unforseenException("ERROR while parsing rate value")

    def getAccumulatedInfusionVolume(self):
        ans = self.sendCommand(self.__CMD_GET_DISVOL)
        m = re.match(self.__ANS_DISVOL_PATTERN, ans)
        if m:
            return float(m.group(1))
        else:
            raise unforseenException("Error while parsing accumulated volume")

    def getAccumulatedWithdrawalVolume(self):
        ans = self.sendCommand(self.__CMD_GET_DISVOL)
        m = re.match(self.__ANS_DISVOL_PATTERN, ans)
        if m:
            return float(m.group(2))
        else:
            raise unforseenException("Error while parsing accumulated volume")

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
            raise unforseenException("Error while parsing version number")
        else:
            return 'Model #%s, firmware v%s.%s' % (m.groups())

    def doBeep(self, nbBeeps=1):
        self.sendCommand(self.__CMD_SET_BUZZ % (1, nbBeeps))


class errorException(SyringePumpException):
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


class alarmException(SyringePumpException):
    pass


class readTimeoutException(SyringePumpException):
    pass
