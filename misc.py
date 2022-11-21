import datetime
import logging
import os
import re
import typing
from enum import IntEnum

from PyQt5.QtWidgets import QPlainTextEdit
from tabulate import tabulate

logger = logging.getLogger(__name__)


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

    def as_list(self):
        return [self.name, self._dose, self._concentration, self._volume, self._pump]

    def as_strings(self):
        pump = "Manual" if self.pump is None else f"Pump #{self.pump}"
        return [
            self.name,
            f"{self._dose:.2f}",
            f"{self._concentration:.2f}",
            f"{self._volume:.0f}",
            pump,
        ]

    def __repr__(self):
        return (
            "Drug(name={:s}, dose={:.2f} mg/kg, concentration={:.2f} mg/mL, "
            "volume to injection={:.0f} μL, pump={})".format(*self.as_list())
        )


class Sex(IntEnum):
    MALE = 1
    FEMALE = 2
    UNKNOWN = 3


class Subject(object):
    __slots__ = "_weight", "_sex", "_genotype", "_dob", "_comments"

    def __init__(
        self,
        weight: int = 0,
        sex: Sex = Sex.UNKNOWN,
        genotype="",
        dob: datetime = datetime.date.today(),  # if unknown, use today's date as DoB cannot be very far from there
        comments="",
    ):
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
        return "Subject(dob:{:s}, weight:{:.0f}g, sex:{:s}, genotype:{:s}, comments:{:s})".format(
            self.dob.isoformat(),
            self.weight,
            self.sex.__repr__(),
            self.genotype,
            self.comments,
        )


class LogBox(object):
    HEADER = """## Experiment Date: {expDate}
=== Subject Info ===
Subject: {subjectGenotype}
Sex: {subjectSex}
DoB: {subjectDoB} ({subjectAge} days-old)
Weight: {subjectWeight} g
Comments:
{subjectComments}

=== Drugs ===
{drugs}

## start log

"""
    RE_SUBJECT_INFO = re.compile(r"""=== Subject Info ===""")
    RE_SUBJECT_DATA = re.compile(
        r"""^Subject: (?P<genotype>.*)$
^Sex: (?P<sex>.*)$
^DoB: (?P<dob>[\d-]{10}) .*$
^Weight: (?P<weight>\d+) g$
^Comments:$
^(?P<comments>.*)

^===""",
        re.MULTILINE | re.DOTALL,
    )
    RE_DRUG_DATA = re.compile(
        r"^\| (?P<name>.*) *\| *(?P<dose>[\d.]+) \| *(?P<concentration>[\d.]+) \|"
        r" *(?P<volume>[\d.]+) \| (?P<pump>.*) *\|$",
        re.MULTILINE,
    )
    RE_PUMP = re.compile(r"Pump #(\d+)")
    DRUGS_HEADER = [
        "Drug name",
        "dose (mg/kg)",
        "concentration (mg/mL)",
        "Volume to inject (μL)",
        "Pump or Manual",
    ]
    SEX = ["Male", "Female", "Unknown"]
    SEP = "\t|\t"

    def __init__(self, path, widget: QPlainTextEdit, nb_measurements):
        self._path = path
        self.content = ""
        self.widget = widget
        self.nbMeasurements = nb_measurements

    @property
    def path(self):
        return self._path

    def get_header(self, subject: Subject, drug_list: typing.List[Drug]):
        subject_age = (datetime.date.today() - subject.dob).days
        # use tabulate module to get a nicely formatted drug list
        drugs = tabulate(
            [a.as_strings() for a in drug_list],
            headers=self.DRUGS_HEADER,
            tablefmt="github",
            floatfmt=("", ".2f", ".2f", ".0f"),
        )
        return self.HEADER.format(
            expDate=datetime.date.today().isoformat(),
            subjectGenotype=subject.genotype,
            subjectSex=self.SEX[subject.sex - 1],
            subjectDoB=subject.dob.isoformat(),
            subjectAge=subject_age,
            subjectWeight=subject.weight,
            subjectComments=subject.comments,
            drugs=drugs,
        )

    def append(self, text):
        text += "\n" if text[-1] != "\n" else ""  # ensure line ends with newline
        self.content += text
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "a+", encoding="utf-8") as f:
            f.write(text)
        if self.widget is not None:
            self.widget.appendPlainText(text[:-1])  # dont include \n

    @staticmethod
    def parse(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        subject = None
        drugs = []

        subject_matches = list(LogBox.RE_SUBJECT_INFO.finditer(content))
        if len(subject_matches) > 0:
            subject_match = subject_matches[
                -1
            ]  # keep the last match in case there are several
            subject_data = LogBox.RE_SUBJECT_DATA.match(
                content[subject_match.end() + 1 :]
            )
            if subject_data is not None:
                subject_weight = int(subject_data.group("weight"))
                subject_sex = subject_data.group("sex")
                if subject_sex == "Male":
                    subject_sex = Sex.MALE
                elif subject_sex == "Female":
                    subject_sex = Sex.FEMALE
                else:
                    subject_sex = Sex.UNKNOWN
                subject_genotype = subject_data.group("genotype")
                subject_dob = datetime.date.fromisoformat(subject_data.group("dob"))
                subject_comments = subject_data.group("comments")
                subject = Subject(
                    weight=subject_weight,
                    sex=subject_sex,
                    genotype=subject_genotype,
                    dob=subject_dob,
                    comments=subject_comments,
                )

                drug_matches = LogBox.RE_DRUG_DATA.finditer(
                    content[subject_match.start() :]
                )
                for drug_match in drug_matches:
                    pump = None
                    match = LogBox.RE_PUMP.match(drug_match.group("pump"))
                    if match is not None:
                        pump = int(match.group(1))
                    drug = Drug(
                        name=drug_match.group("name").strip(),
                        dose=float(drug_match.group("dose")),
                        concentration=float(drug_match.group("concentration")),
                        volume=int(drug_match.group("volume")),
                        pump=pump,
                    )
                    drugs.append(drug)
        return subject, drugs

    def write_to_log(self, measurements: typing.List, note=""):
        # to get consistent results, make sure that `measurement` is same size a nb of plots
        m = len(measurements)
        measurements += [""] * (self.nbMeasurements - m)
        curr_time = datetime.datetime.now().strftime("%H:%M:%S")
        text = self.SEP.join([curr_time] + measurements[: self.nbMeasurements] + [note])
        self.append(text)
