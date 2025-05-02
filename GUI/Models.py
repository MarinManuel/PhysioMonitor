from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtWidgets import QStyledItemDelegate, QWidget, QDoubleSpinBox

from misc import Drug


class DoubleSpinBoxDelegate(QStyledItemDelegate):
    def createEditor(
        self, parent: QWidget, option, index: QtCore.QModelIndex
    ) -> QWidget:
        editor = QDoubleSpinBox(parent)
        editor.setFrame(False)
        editor.setMinimum(0)
        units = index.model().UNITS[index.column()]
        editor.setSuffix(" {}".format(units) if len(units) > 0 else "")
        return editor

    def setEditorData(self, editor: QWidget, index: QtCore.QModelIndex) -> None:
        value = float(index.model().data(index, role=Qt.EditRole))
        editor.setValue(value)

    def setModelData(
        self,
        editor: QWidget,
        model: QtCore.QAbstractItemModel,
        index: QtCore.QModelIndex,
    ) -> None:
        value = editor.value()
        model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(
        self, editor: QWidget, option, index: QtCore.QModelIndex
    ) -> None:
        editor.setGeometry(option.rect)


class DrugTableModel(QAbstractTableModel):
    HEADER = ["Name", "Dose", "Concentration", "Inj. volume", "Pump"]
    FIELDS = ["name", "dose", "concentration", "volume", "pump"]
    UNITS = [None, "mg/kg", "mg/mL", "μL", None]
    FORMATS = ["{:s}", "{:.2f}", "{:.2f}", "{:d}", "{}"]

    def __init__(self, data=None, pumps=None):
        QAbstractTableModel.__init__(self)
        self._data = [] if data is None else data
        self._pumps = [] if pumps is None else pumps
        self.NCols = len(self.HEADER)

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return self.NCols

    def data(self, index, role=Qt.DisplayRole):
        column = index.column()
        row = index.row()

        if role == Qt.DisplayRole:
            value = self._data[row].as_list()[column]
            if column == 4:
                if value is None:
                    return "Manual"
                else:
                    return self._pumps[value].display_name
            value = self.FORMATS[column].format(value)
            units = self.UNITS[column]
            if units is not None and len(units) > 0:
                value = "{} {}".format(value, units)
            return value
        elif role == Qt.EditRole:
            return self._data[row].as_list()[column]
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.HEADER[section]

            if orientation == Qt.Vertical:
                return ""

    def insertRows(self, position, rows=1, index=QModelIndex()):
        """Insert a row into the model."""
        self.beginInsertRows(QModelIndex(), position, position + rows - 1)

        for row in range(rows):
            self._data.insert(position + row, Drug())

        self.endInsertRows()
        return True

    def removeRows(self, position, rows=1, index=QModelIndex()):
        """Remove a row from the model."""
        self.beginRemoveRows(QModelIndex(), position, position + rows - 1)

        del self._data[position : position + rows]

        self.endRemoveRows()
        return True

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        """Adjust the data (set it to <value>) depending on the given
        index and role.
        """
        if role != Qt.EditRole:
            return False

        if index.isValid() and 0 <= index.row() < len(self._data):
            drug = self._data[index.row()]
            units = self.UNITS[index.column()]
            if isinstance(value, str) and units is not None and units in value:
                value = value[: -(len(units) + 1)]
            try:
                setattr(drug, self.FIELDS[index.column()], value)
            except ValueError:
                return False
            # noinspection PyUnresolvedReferences
            self.dataChanged.emit(index, index)
            return True

        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return (
            Qt.ItemIsSelectable
            | Qt.ItemIsEnabled
            | Qt.ItemIsDragEnabled
            | Qt.ItemIsDropEnabled
        )

    def supportedDropActions(self):
        return Qt.MoveAction

    def mimeTypes(self):
        return ["application/x-qabstractitemmodeldatalist"]

    def mimeData(self, indexes):
        data = super().mimeData(indexes)
        data.setData("application/x-qabstractitemmodeldatalist", b"")
        return data

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.IgnoreAction:
            return False
        if not data.hasFormat("application/x-qabstractitemmodeldatalist"):
            return False
        if row == -1:
            row = self.rowCount()
        self.beginMoveRows(
            QModelIndex(), parent.row(), parent.row(), QModelIndex(), row
        )
        self._data.insert(row, self._data.pop(parent.row()))
        self.endMoveRows()
        return True

    def moveRows(
        self, sourceParent, sourceRow, count, destinationParent, destinationChild
    ):
        if count != 1:
            return False
        self.beginMoveRows(
            sourceParent, sourceRow, sourceRow, destinationParent, destinationChild
        )
        self._data.insert(destinationChild, self._data.pop(sourceRow))
        self.endMoveRows()
        return True
