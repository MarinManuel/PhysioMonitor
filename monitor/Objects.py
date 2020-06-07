import datetime
import os
from enum import IntEnum

import typing


class Drug(object):
    def __init__(self, name="", volume=0, dose=0.0, concentration=0.0):
        self._name = name
        self._volume = volume
        self._dose = dose
        self._concentration = concentration

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = int(value)

    @property
    def dose(self):
        return self._dose

    @dose.setter
    def dose(self, value):
        self._dose = float(value)

    @property
    def concentration(self):
        return self._concentration

    @concentration.setter
    def concentration(self, value):
        self._concentration = float(value)

    def asList(self):
        return [self.name, self._dose, self._concentration, self._volume]

    def asStrList(self):
        return [self.name, f'{self._dose:.2f}', f'{self._concentration:.2f}', f'{self._volume:.0f}']

    def __repr__(self):
        return 'Drug(name={:s}, dose={:.2f} mg/kg, concentration={:.2f} mg/mL, volume to injection={:.0f} μL'.format(
            *self.asList()
        )


class Sex(IntEnum):
    MALE = 1
    FEMALE = 2
    UNKNOWN = 3


class Mouse(object):
    __slots__ = '_weight', '_sex', '_genotype', '_dob', '_comments'

    def __init__(self, weight: int = 0, sex: Sex = Sex.UNKNOWN, genotype="",
                 dob: datetime = datetime.date.fromtimestamp(0), comments=""):
        self.weight = weight
        self.sex = sex
        self.genotype = genotype
        self.dob = dob
        self.comments = comments

    @property
    def weight(self):
        return self._weight

    @weight.setter
    def weight(self, value: int):
        self._weight = int(value)

    @property
    def sex(self):
        return self._sex

    @sex.setter
    def sex(self, value: Sex):
        self._sex = value

    @property
    def genotype(self):
        return self._genotype

    @genotype.setter
    def genotype(self, value):
        self._genotype = value

    @property
    def dob(self):
        return self._dob

    @dob.setter
    def dob(self, value: datetime):
        self._dob = value

    @property
    def comments(self):
        return self._comments

    @comments.setter
    def comments(self, value):
        self._comments = value

    def __repr__(self):
        return 'Mouse(dob:{:s}, weight:{:.0f}g, sex:{:s}, genotype:{:s}, comments:{:s})'.format(
            self.dob.isoformat(), self.weight, self.sex.__repr__(), self.genotype, self.comments
        )


class Experiment(object):
    __slots__ = '_investigator', '_comments'

    def __init__(self, investigator='', comments=''):
        self.investigator = investigator
        self.comments = comments

    @property
    def investigator(self):
        return self._investigator

    @investigator.setter
    def investigator(self, value):
        self._investigator = value

    @property
    def comments(self):
        return self._comments

    @comments.setter
    def comments(self, value):
        self._comments = value

    def __repr__(self):
        return 'Experiment(by:{:s}, comments:{:s})'.format(
            self.investigator, self.comments
        )


class Config(object):
    __slots__ = '_configFilePath', '_savePath'

    def __init__(self, configFile=None, savePath=None):
        self.configFile = configFile
        self.savePath = savePath

    @property
    def configFile(self):
        return self._configFilePath

    @configFile.setter
    def configFile(self, value):
        self._configFilePath = value

    @property
    def savePath(self):
        return self._savePath

    @savePath.setter
    def savePath(self, value):
        if value is not None and os.path.isdir(value):
            self._savePath = value
        else:
            # if invalid path, reverts to current directory
            self._savePath = os.getcwd()

    def __repr__(self):
        return """Configuration info:
        configuration file: {:s}
        files are saved in: {:s}""".format(
            self.configFile, self.savePath
        )


class LogFile(object):
    HEADER = """##
Experiment Date: {expDate}

=== Mouse Info ===
Mouse: {mouseGenotype}
Sex: {mouseSex}
DoB: {mouseDoB} ({mouseAge} days-old)
Weight: {mouseWeight} g
Comments:
{mouseComments}

=== Drugs ===
{drugs}

## start log
"""
    DRUGS_HEADER = "Drug name | dose (mg/kg) | concentration (mg/mL) | Volume to inject (μL)"
    SEX = ['Male', 'Female', 'Unknown']

    def __init__(self, path):
        self._path = path
        self.content = ""
        self.widget = None

    @property
    def path(self):
        return self._path

    def getHeader(self, mouse: Mouse, drugList: typing.List[Drug], exp: Experiment):
        mouseAge = (datetime.date.today() - mouse.dob).days
        drugs = self.DRUGS_HEADER + '\n'
        for drug in drugList:
            drugs += ' | '.join(drug.asStrList()) + '\n'
        return self.HEADER.format(expDate=datetime.date.today().isoformat(),
                                  mouseGenotype=mouse.genotype,
                                  mouseSex=self.SEX[mouse.sex-1],
                                  mouseDoB=mouse.dob.isoformat(),
                                  mouseAge=mouseAge,
                                  mouseWeight=mouse.weight,
                                  mouseComments=mouse.comments,
                                  drugs=drugs)

    def append(self, text):
        self.content += text
        with open(self._path, 'a') as f:
            f.write(text)
        if self.widget is not None:
            self.widget.appendPlainText(text.rstrip())
