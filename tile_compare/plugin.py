import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from . import translator
from .translator import tr
from .tileserver import TileServer


class TileComparePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        translator.load(self.plugin_dir)
        self.action = None
        self.dock = None
        self.server = TileServer()

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, 'icon.svg'))
        self.action = QAction(icon, tr('Tile Compare'), self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.toggled.connect(self._toggle_dock)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToRasterMenu(tr('Tile Compare'), self.action)

    def _toggle_dock(self, checked):
        if self.dock is None:
            from .dock import TileCompareDock
            self.server.start()
            self.dock = TileCompareDock(self.iface, self.server if self.server.running else None,
                                        self.iface.mainWindow())
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
            self.dock.visibilityChanged.connect(self.action.setChecked)
        self.dock.setVisible(checked)

    def unload(self):
        if self.dock is not None:
            self.dock.cleanup()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        self.server.stop()
        self.iface.removePluginRasterMenu(tr('Tile Compare'), self.action)
        self.iface.removeToolBarIcon(self.action)
        self.action = None
        translator.unload()
