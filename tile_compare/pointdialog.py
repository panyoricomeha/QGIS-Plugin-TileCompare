import json
import os

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)
from qgis.core import QgsCoordinateReferenceSystem, QgsSettings
from qgis.gui import QgsProjectionSelectionWidget

from . import db, points
from .translator import tr

LAST_KEY = 'tile_compare/points_last'
DB_KEY = 'tile_compare/points_db'
PREVIEW_ROWS = 20


class PointImportDialog(QDialog):
    def __init__(self, start_dir, parent=None):
        super().__init__(parent)
        self.title = tr('Import XY Attribute Table')
        self.setWindowTitle(self.title)
        self.resize(820, 620)
        self.start_dir = start_dir
        self.headers, self.rows, self.name = [], [], tr('XY attribute table')
        self.db_source = None  # (provider, uri, configuration, sql, field names) when read from a database
        self._zone_note = ''

        lay = QVBoxLayout(self)
        self.src_tabs = QTabWidget()
        self.src_tabs.addTab(self._build_db_tab(), tr('Database'))
        file_tab = QWidget()
        row = QHBoxLayout(file_tab)
        self.path = QLineEdit()
        self.path.setPlaceholderText(tr('TSV / CSV file (UTF-8 or Shift_JIS)'))
        self.path.editingFinished.connect(lambda: self._load_file(self.path.text()))
        b = QPushButton(tr('Browse…'))
        b.clicked.connect(self._browse)
        row.addWidget(self.path)
        row.addWidget(b)
        b = QPushButton(tr('From Clipboard'))
        b.setToolTip(tr('Import a table copied from Excel or a database tool (with a header row)'))
        b.clicked.connect(self._paste)
        row.addWidget(b)
        self.src_tabs.addTab(file_tab, tr('File / Clipboard'))
        lay.addWidget(self.src_tabs)

        self.preview = QTableWidget(0, 0)
        self.preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.preview, 1)

        g = QGridLayout()
        self.x_col, self.y_col, self.label_col = QComboBox(), QComboBox(), QComboBox()
        for c in (self.x_col, self.y_col):
            c.currentIndexChanged.connect(self._auto_crs)
            c.currentIndexChanged.connect(self._update_hint)
        self.swap = QCheckBox(tr('Treat the X column as north (vertical)'))
        self.swap.setToolTip(tr('Survey coordinates use X for north and Y for east. '
                                'Check this if the points look rotated by 90°.'))
        self.swap.toggled.connect(self._update_hint)
        self.crs = QgsProjectionSelectionWidget()
        self.crs.setCrs(points.zone_crs(9))
        self.crs.crsChanged.connect(self._update_hint)

        g.addWidget(QLabel(tr('X column')), 0, 0)
        g.addWidget(self.x_col, 0, 1)
        g.addWidget(QLabel(tr('Y column')), 0, 2)
        g.addWidget(self.y_col, 0, 3)
        g.addWidget(self.swap, 1, 1, 1, 3)
        g.addWidget(QLabel(tr('Source CRS')), 2, 0)
        g.addWidget(self.crs, 2, 1, 1, 3)
        g.addWidget(QLabel(tr('Label column')), 3, 0)
        g.addWidget(self.label_col, 3, 1)
        lay.addLayout(g)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Import'))
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    # database
    def _build_db_tab(self):
        t = QWidget()
        g = QGridLayout(t)
        self.db_conn, self.db_schema, self.db_table = QComboBox(), QComboBox(), QComboBox()
        for c in (self.db_conn, self.db_schema, self.db_table):
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.db_table.setEditable(True)
        self.db_table.setMinimumContentsLength(40)
        self.db_table.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.db_table.setMaxVisibleItems(30)
        self.db_table.view().setMinimumWidth(500)
        self.db_table.setMinimumHeight(30)
        font = self.db_table.font()
        font.setPointSizeF(font.pointSizeF() * 1.2)
        self.db_table.setFont(font)
        self.db_sql = QPlainTextEdit()
        self.db_sql.setPlaceholderText(tr('SELECT * FROM ... (WHERE can be used to filter)'))
        self.db_sql.setMaximumHeight(70)
        refresh = QToolButton()
        refresh.setText('↻')
        refresh.setToolTip(tr('Refresh connections (add connections in the Browser panel)'))
        refresh.clicked.connect(self._fill_connections)
        run = QPushButton(tr('Load'))
        run.clicked.connect(self._run_query)
        self.db_conn.currentIndexChanged.connect(self._fill_schemas)
        self.db_schema.currentIndexChanged.connect(self._fill_tables)
        self.db_table.activated.connect(self._table_chosen)

        g.addWidget(QLabel(tr('Connection')), 0, 0)
        g.addWidget(self.db_conn, 0, 1)
        g.addWidget(refresh, 0, 2)
        g.addWidget(QLabel(tr('Schema')), 1, 0)
        g.addWidget(self.db_schema, 1, 1, 1, 2)
        g.addWidget(QLabel(tr('Table')), 2, 0)
        g.addWidget(self.db_table, 2, 1, 1, 2)
        g.addWidget(QLabel('SQL'), 3, 0)
        g.addWidget(self.db_sql, 3, 1, 1, 2)
        g.addWidget(run, 4, 2)
        self._db_conns = []
        QTimer.singleShot(0, self._fill_connections)
        return t

    def _db_current(self):
        i = self.db_conn.currentIndex()
        return self._db_conns[i] if 0 <= i < len(self._db_conns) else (None, None, None)

    def _fill_connections(self):
        try:
            self._db_conns = db.connections()
        except Exception as e:
            self._db_conns = []
            self.hint.setText(tr('Cannot get database connections: {error}').format(error=e))
        last = QgsSettings().value(DB_KEY, '')
        self.db_conn.blockSignals(True)
        self.db_conn.clear()
        for label, _, _ in self._db_conns:
            self.db_conn.addItem(label)
        if not self._db_conns:
            self.db_conn.addItem(tr('(No connections: add a database connection in the Browser panel)'))
        i = self.db_conn.findText(last)
        self.db_conn.setCurrentIndex(max(i, 0))
        self.db_conn.blockSignals(False)
        self._fill_schemas()

    def _fill_schemas(self, *args):
        _, _, conn = self._db_current()
        self.db_schema.blockSignals(True)
        self.db_schema.clear()
        if conn is not None:
            try:
                for s in db.schemas(conn):
                    self.db_schema.addItem(s)
            except Exception as e:
                self.hint.setText(tr('Cannot get schemas: {error}').format(error=e))
        last = QgsSettings().value(DB_KEY + '_schema', '')
        i = self.db_schema.findText(last)
        if i < 0:
            i = max(self.db_schema.findText('dbo'), self.db_schema.findText('public'), 0)
        self.db_schema.setCurrentIndex(i)
        self.db_schema.blockSignals(False)
        self._fill_tables()

    def _fill_tables(self, *args):
        _, _, conn = self._db_current()
        self.db_table.clear()
        if conn is None:
            return
        try:
            self.db_table.addItems(db.tables(conn, self.db_schema.currentText()))
        except Exception as e:
            self.hint.setText(tr('Cannot get tables: {error}').format(error=e))
        last = QgsSettings().value(DB_KEY + '_table', '')
        if self.db_table.findText(last) >= 0:
            self.db_table.setCurrentIndex(self.db_table.findText(last))
            self.db_sql.setPlainText(QgsSettings().value(DB_KEY + '_sql', '') or '')
        else:
            self._table_chosen()

    def _table_chosen(self, *args):
        _, provider, _ = self._db_current()
        table = self.db_table.currentText()
        if provider and table:
            self.db_sql.setPlainText(db.select_sql(provider, self.db_schema.currentText(), table))

    def _run_query(self):
        label, _, conn = self._db_current()
        sql = self.db_sql.toPlainText().strip()
        if conn is None or not sql:
            QMessageBox.warning(self, self.title, tr('Specify a connection and SQL'))
            return
        schema, table = self.db_schema.currentText(), self.db_table.currentText()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # only the first rows are read here; all rows are read in the background on import
            fields = db.field_names(conn, schema, table)
            headers, rows = db.query(conn, sql, fields, limit=PREVIEW_ROWS)
        except Exception as e:
            QMessageBox.warning(self, self.title, tr('SQL failed:\n{error}').format(error=e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        s = QgsSettings()
        s.setValue(DB_KEY, label)
        s.setValue(DB_KEY + '_schema', schema)
        s.setValue(DB_KEY + '_table', table)
        s.setValue(DB_KEY + '_sql', sql)
        self.set_table(headers, rows, table or 'DB')
        _, provider, _ = self._db_current()
        self.db_source = (provider, conn.uri(), conn.configuration(), sql, fields)
        self._update_hint()

    # file / clipboard
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Open XY Attribute Table'), self.start_dir,
                                              tr('Tables (*.tsv *.csv *.txt);;All files (*.*)'))
        if path:
            self.path.setText(path)
            self._load_file(path)

    def _load_file(self, path):
        if not path or not os.path.isfile(path):
            return
        try:
            text = points.read_text(path)
        except OSError as e:
            QMessageBox.warning(self, self.title, str(e))
            return
        self.set_text(text, os.path.splitext(os.path.basename(path))[0])

    def _paste(self):
        self.set_text(QApplication.clipboard().text(), tr('XY attribute table'))

    def set_text(self, text, name):
        self.set_table(*points.parse_table(text), name)

    def set_table(self, headers, rows, name):
        self.db_source = None
        self.headers, self.rows = headers, rows
        self.name = name
        self.preview.setColumnCount(len(self.headers))
        self.preview.setHorizontalHeaderLabels(self.headers)
        self.preview.setRowCount(min(len(self.rows), PREVIEW_ROWS))
        for i, r in enumerate(self.rows[:PREVIEW_ROWS]):
            for j, v in enumerate(r):
                self.preview.setItem(i, j, QTableWidgetItem(v))
        self.preview.resizeColumnsToContents()

        g = points.guess(self.headers, self.rows)
        for combo, key, blank in ((self.x_col, 'x_col', False), (self.y_col, 'y_col', False),
                                  (self.label_col, 'label', True)):
            combo.blockSignals(True)
            combo.clear()
            if blank:
                combo.addItem(tr('(None)'), None)
            for h in self.headers:
                combo.addItem(h, h)
            if g[key] in self.headers:
                combo.setCurrentIndex(combo.findData(g[key]))
            combo.blockSignals(False)
        if g['zone']:
            self.crs.setCrs(points.zone_crs(g['zone']))
        self._restore_last()
        self._auto_crs()
        self._update_hint()

    def _auto_crs(self, *args):
        """EPSG:4326 for longitude/latitude values, or the zone the x/y were actually projected with."""
        xc, yc = self.x_col.currentData(), self.y_col.currentData()
        self._zone_note = ''
        if not self.rows or xc not in self.headers or yc not in self.headers:
            return
        xi, yi = self.headers.index(xc), self.headers.index(yc)
        kind = points.looks_lonlat(self.rows, xi, yi)
        if kind is not None:
            self.crs.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
            self.swap.setChecked(kind == 'latlon')
            return
        pref_zone = points.guess(self.headers, self.rows)['zone']
        zone = points.detect_zone(self.rows, xi, yi, self.swap.isChecked(), pref_zone)
        if zone is not None:
            crs = points.zone_crs(zone)
            self.crs.setCrs(crs)
            self._zone_note = tr('x / y appear to be projected with zone {zone} ({authid}) instead of the '
                                 "prefecture's zone {pref_zone}; the source CRS was set accordingly."
                                 ).format(zone=zone, authid=crs.authid(), pref_zone=pref_zone)

    def _restore_last(self):
        """Reuse the previous CRS and axis swap for a table with the same columns."""
        try:
            last = json.loads(QgsSettings().value(LAST_KEY, '') or '{}')
        except ValueError:
            return
        if last.get('headers') != self.headers:
            return
        self.crs.setCrs(QgsCoordinateReferenceSystem(last['crs']))
        self.swap.setChecked(bool(last.get('swap')))

    def _update_hint(self, *args):
        if not self.rows:
            self.hint.setText(tr('Load from a database, or import a table from a file or the clipboard.'))
            return
        o = self.options()
        p = points.raw_point(dict(zip(self.headers, self.rows[0])), o) if o['x_col'] else None
        crs = self.crs.crs()
        if self.db_source is not None:
            text = tr('Showing the first {n} rows (all rows are read in the background on import)').format(
                n=len(self.rows))
        else:
            text = tr('{n} rows').format(n=len(self.rows))
        if p is not None:
            text += ' / ' + tr('First row ({authid}): {x}, {y}').format(
                authid=crs.authid(), x=f'{p.x():.3f}', y=f'{p.y():.3f}')
        note = self._zone_note
        warn = '' if note else points.offset_hint(p, crs)
        self.hint.setText(text + ('\n' + note if note else '') + ('\n' + warn if warn else ''))
        self.hint.setStyleSheet('color: #c62828;' if warn else '')

    def options(self):
        crs = self.crs.crs()
        return {'x_col': self.x_col.currentData(), 'y_col': self.y_col.currentData(),
                'label': self.label_col.currentData(), 'swap': self.swap.isChecked(),
                'crs': crs.authid() or crs.toWkt()}

    def _accept(self):
        o = self.options()
        if not self.rows or not o['x_col'] or not o['y_col'] or o['x_col'] == o['y_col']:
            QMessageBox.warning(self, self.title, tr('Specify a table and the X / Y columns'))
            return
        if not self.crs.crs().isValid():
            QMessageBox.warning(self, self.title, tr('Specify the source CRS'))
            return
        save_last(self.headers, o)
        self.accept()


def save_last(headers, opts):
    QgsSettings().setValue(LAST_KEY, json.dumps(
        {'headers': headers, 'crs': opts['crs'], 'swap': opts.get('swap', False)}, ensure_ascii=False))
