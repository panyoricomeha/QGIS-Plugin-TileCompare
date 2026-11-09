import json
import os
import uuid

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)
from qgis.core import (
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsLayerTreeLayer,
    QgsMessageLog, QgsProject, QgsRasterLayer, QgsSettings,
)
from qgis.gui import QgsDockWidget

from . import points, tiles
from .translator import tr
from .pointdialog import PointImportDialog
from .styles import style_points

PROP_UID = 'tile_compare/uid'
SETTINGS_KEY = 'tile_compare/sources'
LAST_DIR_KEY = 'tile_compare/last_dir'
LOG_TAG = 'Tile Compare'
COL_VIS, COL_NAME, COL_ZOOM, COL_EXT, COL_WHITE = range(5)

CHECKED = Qt.CheckState.Checked
UNCHECKED = Qt.CheckState.Unchecked


class TileCompareDock(QgsDockWidget):
    def __init__(self, iface, server=None, parent=None):
        super().__init__(tr('Tile Compare'), parent)
        self.setObjectName('TileCompareDock')
        self.iface = iface
        self.server = server
        self.canvas = iface.mapCanvas()
        self.group_name = tr('Tile Compare')
        self.sources = self._load()
        self._updating = False
        self._import_task = None

        self._build_ui()
        self._fill_table()

        project = QgsProject.instance()
        project.layerTreeRoot().visibilityChanged.connect(self._update_checks)
        project.layersRemoved.connect(self._update_checks)
        project.readProject.connect(self._update_checks)
        project.readProject.connect(self._relink_layers)
        self._relink_layers()

    def _server_url(self):
        return self.server.base_url if self.server is not None else None

    def _relink_layers(self, *args):
        """Point project layers at the current settings and tile server port."""
        if self.server is not None:
            self.server.set_sources(self.sources)
        for src in self.sources:
            lyr = self._layer(src['uid'])
            uri = tiles.layer_uri(src, self._server_url())
            if lyr and lyr.source() != uri:
                lyr.setDataSource(uri, lyr.name(), 'wms')
                lyr.triggerRepaint()

    # UI
    def _build_ui(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        bar = QHBoxLayout()
        for text, tip, slot in [
            (tr('Load Folder'), tr('Select the parent of the zoom level folders (any of 0-30).\n'
                                   'Selecting a folder without tiles searches its subfolders.'), self._add_folder),
            (tr('Remove Selected'), tr('Remove the selected sources from the list and the map'),
             self._remove_selected),
        ]:
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([tr('Visible'), tr('Name'), tr('Zoom'), tr('Format'),
                                              tr('White transparent')])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col in (COL_VIS, COL_ZOOM, COL_EXT, COL_WHITE):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        lay.addWidget(self.table)

        row = QHBoxLayout()
        b = QPushButton(tr('Zoom to Selected'))
        b.clicked.connect(self._zoom_to_selected)
        row.addWidget(b)
        self.import_btn = QPushButton(tr('Import XY Attribute Table'))
        self.import_btn.setToolTip(tr('Turn an attribute table with x / y columns (database, TSV, CSV, clipboard)\n'
                                      'into points in the project CRS, linked to the tile images under them'))
        self.import_btn.clicked.connect(self._import_points)
        row.addWidget(self.import_btn)
        lay.addLayout(row)

        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        self.setWidget(scroll)

    def _fill_table(self):
        self._updating = True
        self.table.setRowCount(0)
        editable = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        checkable = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
        readonly = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for row, src in enumerate(self.sources):
            self.table.insertRow(row)
            vis = QTableWidgetItem()
            vis.setFlags(checkable)
            vis.setCheckState(CHECKED if self._is_visible(src) else UNCHECKED)
            self.table.setItem(row, COL_VIS, vis)

            name = QTableWidgetItem(src['name'])
            name.setFlags(editable)
            name.setToolTip(src['path'])
            self.table.setItem(row, COL_NAME, name)

            zoom = QTableWidgetItem(f"{src['zmin']}-{src['zmax']}")
            zoom.setFlags(editable)
            zoom.setToolTip(tr('e.g. 5-20'))
            self.table.setItem(row, COL_ZOOM, zoom)

            ext = QTableWidgetItem(src['ext'])
            ext.setFlags(readonly)
            self.table.setItem(row, COL_EXT, ext)

            white = QTableWidgetItem()
            white.setFlags(checkable)
            white.setCheckState(CHECKED if src.get('white_transparent') else UNCHECKED)
            white.setToolTip(tr('Make white margins transparent so layers below show through'))
            self.table.setItem(row, COL_WHITE, white)
        self._updating = False

    # persistence
    def _load(self):
        raw = QgsSettings().value(SETTINGS_KEY, '[]')
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = []
        return [self._normalize(s) for s in data if isinstance(s, dict) and s.get('path')]

    @staticmethod
    def _normalize(src):
        src = dict(src)
        src.setdefault('uid', uuid.uuid4().hex)
        src.setdefault('name', os.path.basename(os.path.normpath(src['path'])) or src['path'])
        src.setdefault('ext', 'png')
        src.setdefault('zmin', 5)
        src.setdefault('zmax', 20)
        src.setdefault('tms', False)
        src.setdefault('white_transparent', src['ext'] in ('jpg', 'jpeg'))
        if 'zdirs' not in src and not tiles.is_remote(src['path']):
            # sources saved before non-standard zoom folder names were supported
            zdirs = tiles.zoom_dirs(src['path'])
            src['zdirs'] = ({str(z): n for z, n in zdirs.items()}
                            if any(n != str(z) for z, n in zdirs.items()) else None)
        return src

    def save(self):
        QgsSettings().setValue(SETTINGS_KEY, json.dumps(self.sources, ensure_ascii=False))
        if self.server is not None:
            self.server.set_sources(self.sources)

    # layers
    @staticmethod
    def _layer(uid):
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.customProperty(PROP_UID) == uid:
                return lyr
        return None

    @staticmethod
    def _node(lyr):
        return QgsProject.instance().layerTreeRoot().findLayer(lyr.id()) if lyr else None

    def _group(self):
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(self.group_name)
        if group is None:
            group = root.insertGroup(0, self.group_name)
        return group

    def _is_visible(self, src):
        node = self._node(self._layer(src['uid']))
        return bool(node and node.itemVisibilityChecked())

    def _ensure_layer(self, src):
        lyr = self._layer(src['uid'])
        if lyr:
            return lyr
        if self.server is not None:
            self.server.set_sources(self.sources)
        lyr = QgsRasterLayer(tiles.layer_uri(src, self._server_url()), src['name'], 'wms')
        if not lyr.isValid():
            self._message(tr('Could not create a layer: {path}').format(path=src['path']), warn=True)
            return None
        lyr.setCustomProperty(PROP_UID, src['uid'])
        project = QgsProject.instance()
        before = project.crs()
        project.addMapLayer(lyr, False)
        self._group().addLayer(lyr)
        self._sync_order()
        self._keep_project_crs(before, src)
        return lyr

    def _keep_project_crs(self, before, src):
        """Keep the project CRS when tiles (EPSG:3857) are added; tiles are reprojected on the fly.
        If QGIS adopted 3857 for an empty project, use the plane rectangular CS guessed from the
        city code in the folder name (e.g. 142131)."""
        project = QgsProject.instance()
        if before.isValid():
            if project.crs() != before:
                project.setCrs(before)
            return
        crs = self._crs_from_path(src['path'])
        if crs is not None and crs.isValid():
            project.setCrs(crs)
            self._message(tr('Project CRS set to {authid} ({name}). Tiles are reprojected to it.').format(
                authid=crs.authid(), name=crs.description()))

    @staticmethod
    def _crs_from_path(path):
        if tiles.is_remote(path):
            return None
        for part in reversed(os.path.normpath(path).split(os.sep)):
            if part.isdigit() and len(part) in (5, 6):
                zone = points.PREF_ZONE.get(int(part[:2]))
                if zone:
                    return points.zone_crs(zone)
        return None

    def _set_visible(self, src, visible):
        lyr = self._ensure_layer(src) if visible else self._layer(src['uid'])
        node = self._node(lyr)
        if node is None:
            return None
        node.setItemVisibilityChecked(visible)
        if visible:
            parent = node.parent()
            while parent is not None:
                parent.setItemVisibilityChecked(True)
                parent = parent.parent()
        return lyr

    def _sync_order(self):
        """Match the layer tree order to the list (top of the list is drawn on top)."""
        group = self._group()
        pos = 0
        for src in self.sources:
            lyr = self._layer(src['uid'])
            if lyr is None:
                continue
            idx = next((i for i, c in enumerate(group.children())
                        if isinstance(c, QgsLayerTreeLayer) and c.layerId() == lyr.id()), None)
            if idx is None:  # moved out of the group by the user
                continue
            if idx != pos:
                node = group.children()[idx]
                group.insertChildNode(pos, node.clone())
                group.removeChildNode(node)
            pos += 1

    def _rebuild_layer(self, src):
        if self.server is not None:
            self.server.set_sources(self.sources)
        lyr = self._layer(src['uid'])
        if lyr is not None:
            lyr.setDataSource(tiles.layer_uri(src, self._server_url()), lyr.name(), 'wms')
            lyr.triggerRepaint()

    def _update_checks(self, *args):
        if self._updating:
            return
        self._updating = True
        for row, src in enumerate(self.sources):
            item = self.table.item(row, COL_VIS)
            if item:
                item.setCheckState(CHECKED if self._is_visible(src) else UNCHECKED)
        self._updating = False

    # list
    def _on_item_changed(self, item):
        if self._updating:
            return
        src = self.sources[item.row()]
        col = item.column()
        if col == COL_VIS:
            self._set_visible(src, item.checkState() == CHECKED)
            self._update_checks()
        elif col == COL_NAME:
            src['name'] = item.text().strip() or src['name']
            lyr = self._layer(src['uid'])
            if lyr:
                lyr.setName(src['name'])
        elif col == COL_ZOOM:
            try:
                zmin, zmax = (int(v) for v in item.text().replace('~', '-').split('-'))
                if not tiles.MIN_ZOOM <= zmin <= zmax <= tiles.MAX_ZOOM:
                    raise ValueError
            except ValueError:
                self._message(tr('Enter zoom as "5-20"'), warn=True)
                self._fill_table()
                return
            src['zmin'], src['zmax'] = zmin, zmax
            self._rebuild_layer(src)
        elif col == COL_WHITE:
            src['white_transparent'] = item.checkState() == CHECKED
            self._rebuild_layer(src)
        self.save()

    def _on_double_click(self, row, col):
        if col == COL_EXT:
            src = self.sources[row]
            ext, ok = QInputDialog.getText(self, tr('Format'), tr('File extension'), text=src['ext'])
            if ok and ext.strip():
                src['ext'] = ext.strip().lstrip('.').lower()
                self._fill_table()
                self._rebuild_layer(src)
                self.save()

    def _selected_rows(self):
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _last_dir(self):
        return QgsSettings().value(LAST_DIR_KEY, '')

    def _add_sources(self, found):
        known = {os.path.normcase(s['path']) for s in self.sources}
        added = []
        for src in found:
            if os.path.normcase(src['path']) in known:
                continue
            src = self._normalize(src)
            self.sources.append(src)
            added.append(src)
        self._fill_table()
        self.save()
        if len(added) == 1:
            self._set_visible(added[0], True)
            self._update_checks()
            self._zoom_to(added[0])
        skipped = len(found) - len(added)
        msg = tr('Loaded {n}').format(n=len(added))
        if skipped:
            msg += ' ' + tr('({n} already loaded were skipped)').format(n=skipped)
        if len(added) > 1:
            msg += '. ' + tr('Check "Visible" to add them to the map')
        self._message(msg)
        return added

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, tr('Select a source folder (parent of the zoom level folders)'), self._last_dir())
        if not path:
            return
        QgsSettings().setValue(LAST_DIR_KEY, os.path.dirname(path))
        found = tiles.find_sources(path)
        if not found:
            QMessageBox.warning(self, tr('Tile Compare'),
                                tr('No zoom level folder structure such as {z}/{x}/{y}.png was found.') +
                                f'\n{path}')
            return
        self._add_sources(found)

    def _remove_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        if QMessageBox.question(self, tr('Tile Compare'),
                                tr('Remove {n} source(s)?\n'
                                   '(Their map layers are removed too. The folders are not deleted.)'
                                   ).format(n=len(rows))) != QMessageBox.StandardButton.Yes:
            return
        for row in reversed(rows):
            src = self.sources.pop(row)
            lyr = self._layer(src['uid'])
            if lyr:
                QgsProject.instance().removeMapLayer(lyr.id())
        self._fill_table()
        self.save()

    def _zoom_to_selected(self):
        rows = self._selected_rows()
        if rows:
            self._zoom_to(self.sources[rows[0]])

    def _zoom_to(self, src):
        extent = tiles.tile_extent(src)
        if extent is None:
            lyr = self._ensure_layer(src)
            if lyr is None:
                return
            extent = lyr.extent()
        xform = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:3857'),
                                       self.canvas.mapSettings().destinationCrs(),
                                       QgsProject.instance())
        self.canvas.setExtent(xform.transformBoundingBox(extent))
        self.canvas.refresh()

    # XY attribute table
    def _import_points(self):
        dlg = PointImportDialog(self._last_dir(), self)
        if not dlg.exec():
            return
        opts = dict(dlg.options(), headers=dlg.headers)
        table = None if dlg.db_source else (dlg.headers, dlg.rows)
        task = points.ImportTask(dlg.name, opts, QgsProject.instance().crs(), self.sources,
                                 self._on_import_done, table=table, db_source=dlg.db_source)
        task.progressChanged.connect(lambda v: self._message(
            tr('Importing XY attribute table... {percent}% (QGIS stays usable)').format(percent=f'{v:.0f}')))
        self._import_task = task
        self.import_btn.setEnabled(False)
        self._message(tr('Importing XY attribute table...'))
        QgsApplication.taskManager().addTask(task)

    def _on_import_done(self, task, ok):
        self._import_task = None
        self.import_btn.setEnabled(True)
        if not ok:
            if task.error is not None:
                QgsMessageLog.logMessage(repr(task.error), LOG_TAG, Qgis.MessageLevel.Critical)
                self._message(tr('Failed to import the XY attribute table: {error}').format(error=task.error),
                              warn=True)
            else:
                self._message(tr('Import of the XY attribute table was canceled'))
            return
        opts, fields, feats, count, bad, linked = task.result
        lyr = points.make_layer(task.name, fields, feats, task.dst_crs)
        lyr.setCustomProperty(points.PROP_POINTS, json.dumps(opts, ensure_ascii=False))
        style_points(lyr, opts.get('label'))
        QgsProject.instance().addMapLayer(lyr, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, lyr)
        if hasattr(self.iface, 'setActiveLayer'):
            self.iface.setActiveLayer(lyr)
        text = tr('Imported {n} points (with tile image: {linked})').format(n=count, linked=linked)
        if bad:
            text += ' ' + tr('{n} rows have no valid position').format(n=bad)
        if linked == 0:
            text += '\n' + tr('No points overlap the images. Check the source CRS and the X / Y columns.')
        self._message(text, warn=linked == 0)
        ext = self.canvas.mapSettings().layerExtentToOutputExtent(lyr, lyr.extent())
        if not ext.isEmpty() or count - bad == 1:
            self.canvas.setExtent(ext.buffered(max(ext.width(), ext.height()) * 0.1 or 200))
            self.canvas.refresh()

    # misc
    def _message(self, text, warn=False):
        self.status.setText(text)
        self.status.setStyleSheet('color: #c62828;' if warn else '')

    def cleanup(self):
        if self._import_task is not None:
            self._import_task.cancel()
        self.save()
        project = QgsProject.instance()
        for sig, slot in ((project.layerTreeRoot().visibilityChanged, self._update_checks),
                          (project.layersRemoved, self._update_checks),
                          (project.readProject, self._update_checks),
                          (project.readProject, self._relink_layers)):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass
