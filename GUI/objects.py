import datetime
from enum import Enum

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QColor


class Drug(object):
    def __init__(self, name="", volume=0, dose=0.0, concentration=0.0):
        self._name = name
        self._volume = volume
        self._dose = dose
        self._concentration = concentration

    @property
    def name(self):
        return self._name

    @property
    def volume(self):
        return self._volume

    @property
    def dose(self):
        return self._dose

    @property
    def concentration(self):
        return self._concentration

    def asList(self):
        return [self.name, self._dose, self._concentration, self._volume]


class DrugTableModel(QAbstractTableModel):
    HEADER = ['Name', 'Dose', 'Concentration', 'Inj. volume']
    UNITS = ['', 'mg/kg', 'mg/mL', 'μL']
    FORMATS = ['{:s}', '{:.2f}', '{:.2f}', '{:d}']

    def __init__(self, data=None):
        QAbstractTableModel.__init__(self)
        self._data = data
        self.NRows = len(self._data)
        self.NCols = 0
        if self.NRows > 0:
            self.NCols = len(self._data[0].__dict__.keys())

    def rowCount(self, parent=QModelIndex()):
        return self.NRows

    def columnCount(self, parent=QModelIndex()):
        return self.NCols

    def data(self, index, role=Qt.DisplayRole):
        column = index.column()
        row = index.row()

        if role == Qt.DisplayRole:
            value = self._data[row].asList()[column]
            value = self.FORMATS[column].format(value)
            units = self.UNITS[column]
            if len(units)>0:
                value = '{} {}'.format(value, units)
            return value
        return None

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.HEADER[section]

            if orientation == Qt.Vertical:
                return ''

    def addDrug(self, datum):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._data.append(datum)
        self.endInsertRows()


class Sex(Enum):
    MALE = 1
    FEMALE = 2
    UNKNOWN = 3


class Mouse(object):
    __slots__ = '_weight', '_sex', '_genotype', '_dob', '_comments'

    def __init__(self, weight: int = 0, sex: Sex = Sex.UNKNOWN, genotype="", dob: datetime = None, comments=""):
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
