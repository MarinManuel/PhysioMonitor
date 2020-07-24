import datetime
import os
import re
import typing
from enum import IntEnum

from tabulate import tabulate


class Drug(object):
    def __init__(self, name="", volume=0, dose=0.0, concentration=0.0, pump=None):
        self._name = name
        self._volume = volume
        self._dose = dose
        self._concentration = concentration
        self._pump = pump

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

    @property
    def pump(self):
        return self._pump

    @pump.setter
    def pump(self, value):
        self._pump = value

    def asList(self):
        return [self.name, self._dose, self._concentration, self._volume, self._pump]

    def asStrList(self):
        pump = 'Manual' if self.pump is None else f'Pump #{self.pump}'
        return [self.name, f'{self._dose:.2f}', f'{self._concentration:.2f}', f'{self._volume:.0f}',
                pump]

    def __repr__(self):
        return 'Drug(name={:s}, dose={:.2f} mg/kg, concentration={:.2f} mg/mL, ' \
               'volume to injection={:.0f} μL, pump={})'.format(*self.asList())


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
    def weight(self) -> int:
        return self._weight

    @weight.setter
    def weight(self, value: int):
        self._weight = int(value)

    @property
    def sex(self) -> IntEnum:
        return self._sex

    @sex.setter
    def sex(self, value: Sex):
        self._sex = value

    @property
    def genotype(self) -> str:
        return self._genotype

    @genotype.setter
    def genotype(self, value):
        self._genotype = value

    @property
    def dob(self) -> datetime:
        return self._dob

    @dob.setter
    def dob(self, value: datetime):
        self._dob = value

    @property
    def comments(self) -> str:
        return self._comments

    @comments.setter
    def comments(self, value):
        self._comments = value

    def __repr__(self) -> str:
        return 'Mouse(dob:{:s}, weight:{:.0f}g, sex:{:s}, genotype:{:s}, comments:{:s})'.format(
            self.dob.isoformat(), self.weight, self.sex.__repr__(), self.genotype, self.comments
        )


class LogFile(object):
    HEADER = """## Experiment Date: {expDate}
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
    RE_MOUSE_INFO = re.compile(r'''=== Mouse Info ===''')
    RE_MOUSE_DATA = re.compile(r'''^Mouse: (?P<genotype>.*)$
^Sex: (?P<sex>.*)$
^DoB: (?P<dob>[0-9-]{10}) .*$
^Weight: (?P<weight>\d+) g$
^Comments:$
^(?P<comments>.*)
^===''', re.MULTILINE | re.DOTALL)
    RE_DRUG_DATA = re.compile(
        r"^\| (?P<name>.*) *\| *(?P<dose>[0-9.]+) \| *(?P<concentration>[0-9.]+) \|"
        r" *(?P<volume>[0-9.]+) \| (?P<pump>.*) *\|$",
        re.MULTILINE)
    RE_PUMP = re.compile('Pump #([0-9]+)')
    DRUGS_HEADER = ['Drug name', 'dose (mg/kg)', 'concentration (mg/mL)', 'Volume to inject (μL)', 'Pump or Manual']
    SEX = ['Male', 'Female', 'Unknown']

    def __init__(self, path):
        self._path = path
        self.content = ""
        self.widget = None

    @property
    def path(self):
        return self._path

    def getHeader(self, mouse: Mouse, drugList: typing.List[Drug]):
        mouseAge = (datetime.date.today() - mouse.dob).days
        # use tabulate module to get a nicely formatted drug list
        drugs = tabulate([a.asStrList() for a in drugList], headers=self.DRUGS_HEADER,
                         tablefmt="github", floatfmt=('', '.2f', '.2f', '.0f'))
        return self.HEADER.format(expDate=datetime.date.today().isoformat(),
                                  mouseGenotype=mouse.genotype,
                                  mouseSex=self.SEX[mouse.sex - 1],
                                  mouseDoB=mouse.dob.isoformat(),
                                  mouseAge=mouseAge,
                                  mouseWeight=mouse.weight,
                                  mouseComments=mouse.comments,
                                  drugs=drugs)

    def append(self, text):
        self.content += text
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'a+', encoding='utf-8') as f:
            f.write(text)
        if self.widget is not None:
            self.widget.appendPlainText(text)

    @staticmethod
    def parse(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        mouse = None
        drugs = []

        mouse_matches = list(LogFile.RE_MOUSE_INFO.finditer(content))
        if len(mouse_matches) > 0:
            mouse_match = mouse_matches[-1]  # keep the last match in case there are several
            mouse_data = LogFile.RE_MOUSE_DATA.match(content[mouse_match.end() + 1:])
            if mouse_data is not None:
                mouseWeight = int(mouse_data.group('weight'))
                mouseSex = mouse_data.group('sex')
                if mouseSex == 'Male':
                    mouseSex = Sex.MALE
                elif mouseSex == 'Female':
                    mouseSex = Sex.FEMALE
                else:
                    mouseSex = Sex.UNKNOWN
                mouseGenotype = mouse_data.group('genotype')
                mouseDoB = datetime.date.fromisoformat(mouse_data.group('dob'))
                mouseComments = mouse_data.group('comments')
                mouse = Mouse(weight=mouseWeight, sex=mouseSex, genotype=mouseGenotype,
                              dob=mouseDoB, comments=mouseComments)

                drug_matches = LogFile.RE_DRUG_DATA.finditer(content[mouse_match.start():])
                for drug_match in drug_matches:
                    pump = None
                    match = LogFile.RE_PUMP.match(drug_match.group('pump'))
                    if match is not None:
                        pump = int(match.group(1))
                    drug = Drug(name=drug_match.group('name'),
                                dose=float(drug_match.group('dose')),
                                concentration=float(drug_match.group('concentration')),
                                volume=int(drug_match.group('volume')),
                                pump=pump)
                    drugs.append(drug)
        return mouse, drugs
