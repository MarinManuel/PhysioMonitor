import sys
from PyQt5.QtWidgets import QApplication, QWidget, QFrame, QMenu, QAction, QWidgetAction, QFormLayout, QSpinBox
from PyQt5.QtCore import Qt, QEvent

t = True
v = 0


class SpinAction(QWidgetAction):
    FocusEvents = QEvent.FocusIn, QEvent.Enter
    ActivateEvents = QEvent.KeyPress, QEvent.Wheel
    WatchedEvents = FocusEvents + ActivateEvents

    def __init__(self, parent):
        super(SpinAction, self).__init__(parent)
        w = QWidget()
        layout = QFormLayout(w)
        self.spin = QSpinBox()
        w.setFocusPolicy(self.spin.focusPolicy())
        w.setFocusProxy(self.spin)
        self.spin.installEventFilter(self)
        layout.addRow('value', self.spin)
        w.setLayout(layout)
        self.setDefaultWidget(w)

    def eventFilter(self, obj, event):
        if obj == self.spin and event.type() in self.WatchedEvents:
            if isinstance(self.parent(), QMenu):
                self.parent().setActiveAction(self)
            if event.type() in self.FocusEvents:
                self.spin.setFocus()
        return super().eventFilter(obj, event)


def _menu(position):
    menu = QMenu()
    test_action = QAction(text="Test", parent=menu, checkable=True)
    test_action.setChecked(t)
    test_action.toggled.connect(toggle_test)

    spin_action = SpinAction(menu)
    spin_action.spin.setValue(v)
    spin_action.spin.valueChanged.connect(spin_changed)

    menu.addAction(test_action)
    menu.addAction(spin_action)
    action = menu.exec_(w.mapToGlobal(position))


def toggle_test(val):
    global t
    t = val


def spin_changed(val):
    global v
    v = val


app = QApplication(sys.argv)

w = QFrame()
w.setContextMenuPolicy(Qt.CustomContextMenu)
w.customContextMenuRequested.connect(_menu)
w.show()
sys.exit(app.exec_())
