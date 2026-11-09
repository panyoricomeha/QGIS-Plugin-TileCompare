"""Turn an attribute table with coordinates (DB / TSV / CSV) into points linked to tile images."""
import csv
import io
import json
import os
import re
import unicodedata
from multiprocessing.pool import ThreadPool

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsField, QgsFields, QgsGeometry,
    QgsPointXY, QgsProject, QgsProviderRegistry, QgsTask, QgsVectorLayer,
)

from . import db, tiles
from .translator import tr

PROP_POINTS = 'tile_compare/points'
LINK_FIELDS = ('raster', 'tile_path')
INT, REAL, STR = 'int', 'real', 'str'
_QT_TYPES = {INT: QVariant.LongLong, REAL: QVariant.Double, STR: QVariant.String}
LIST_THREADS = 16
MAX_PLANE_OFFSET = 300000  # plane rectangular coordinates stay within about 300 km of the zone origin

# Japanese prefecture code -> plane rectangular CS zone (main zone for prefectures spanning several)
PREF_ZONE = {
    1: 12, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 9, 8: 9, 9: 9, 10: 9, 11: 9, 12: 9, 13: 9, 14: 9,
    15: 8, 16: 7, 17: 7, 18: 6, 19: 8, 20: 8, 21: 7, 22: 8, 23: 7, 24: 6, 25: 6, 26: 6, 27: 6,
    28: 5, 29: 6, 30: 6, 31: 5, 32: 3, 33: 5, 34: 3, 35: 3, 36: 4, 37: 4, 38: 4, 39: 4,
    40: 2, 41: 2, 42: 1, 43: 2, 44: 2, 45: 2, 46: 2, 47: 15,
}
# Column name candidates (matched against data, so Japanese names stay). Longitude/latitude come first.
X_NAMES = ('l', 'lon', 'lng', 'longitude', '経度', 'x', 'x座標', 'east', 'easting')
Y_NAMES = ('b', 'lat', 'latitude', '緯度', 'y', 'y座標', 'north', 'northing')
LABEL_NAMES = ('attributename', 'name', '名称', '名前', '建物名')
PREF_NAMES = ('prefcode', 'pref_code', '都道府県コード')
_INT_RE = re.compile(r'-?(0|[1-9][0-9]{0,15})$')  # ASCII only: full-width numbers stay text


def zone_crs(zone):
    """JGD2011 plane rectangular CS (zone I = EPSG:6669)."""
    return QgsCoordinateReferenceSystem(f'EPSG:{6668 + zone}')


def read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    for enc in ('utf-8-sig', 'cp932'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('cp932', errors='replace')


def parse_table(text):
    """(headers, rows) with the first line as header. Tab separated if the header has tabs, else comma."""
    text = text.strip('\r\n﻿')
    if not text:
        return [], []
    first = text.splitlines()[0]
    delim = '\t' if '\t' in first else ','
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    headers = [h.strip() for h in next(reader)]
    rows = []
    for r in reader:
        if not any(c.strip() for c in r):
            continue
        r = [c.strip() for c in r] + [''] * (len(headers) - len(r))
        rows.append(r[:len(headers)])
    return headers, rows


def _find(headers, names):
    low = [h.lower() for h in headers]
    for n in names:
        if n in low:
            return headers[low.index(n)]
    return None


def guess(headers, rows):
    zone = None
    pref = _find(headers, PREF_NAMES)
    if pref and rows:
        try:
            zone = PREF_ZONE.get(int(to_float(rows[0][headers.index(pref)])))
        except ValueError:
            pass
    return {'x_col': _find(headers, X_NAMES), 'y_col': _find(headers, Y_NAMES),
            'label': _find(headers, LABEL_NAMES), 'zone': zone}


def looks_lonlat(rows, xi, yi, n=50):
    """'lonlat' or 'latlon' if the values are longitude/latitude around Japan, else None."""
    xs, ys = [], []
    for r in rows[:n]:
        try:
            xs.append(to_float(r[xi]))
            ys.append(to_float(r[yi]))
        except (TypeError, ValueError):
            continue
    if not xs:
        return None
    if all(120 <= x <= 155 for x in xs) and all(20 <= y <= 46 for y in ys):
        return 'lonlat'
    if all(20 <= x <= 46 for x in xs) and all(120 <= y <= 155 for y in ys):
        return 'latlon'
    return None


def detect_zone(rows, xi, yi, swap, pref_zone, n=20):
    """If x/y are out of range for the prefecture's zone, find the JGD2011 zone they were actually
    projected with: the zone whose points fall near the prefecture's zone origin. None if not found."""
    pts = []
    for r in rows[:n]:
        try:
            x, y = to_float(r[xi]), to_float(r[yi])
        except (TypeError, ValueError):
            continue
        pts.append((y, x) if swap else (x, y))
    if not pts or not pref_zone:
        return None

    def spread(p_list):
        return max(max(abs(x), abs(y)) for x, y in p_list)

    if spread(pts) <= MAX_PLANE_OFFSET:
        return None
    ctx = QgsProject.instance().transformContext()
    dst = zone_crs(pref_zone)
    best = None
    for z in range(1, 20):
        if z == pref_zone:
            continue
        xform = QgsCoordinateTransform(zone_crs(z), dst, ctx)
        try:
            q = [xform.transform(*p) for p in pts]
        except Exception:
            continue
        s = spread([(p.x(), p.y()) for p in q])
        if s <= MAX_PLANE_OFFSET and (best is None or s < best[1]):
            best = (z, s)
    return best[0] if best else None


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return float(unicodedata.normalize('NFKC', str(s)).replace(',', '').strip())


def _is_float(v):
    if not v.isascii():
        return False
    try:
        float(v)
        return True
    except ValueError:
        return False


def _field_types(headers, rows, numeric):
    """Integer / real / text per column. Codes with leading zeros stay text."""
    types = []
    for i, h in enumerate(headers):
        if h in numeric:
            types.append(REAL)
            continue
        t = INT
        for r in rows:
            v = r[i]
            if v == '':
                continue
            if t == INT and not _INT_RE.match(v):
                t = REAL
            if t == REAL and not _is_float(v):
                t = STR
                break
        types.append(t)
    return types


def _convert(v, t):
    if v == '':
        return None
    try:
        if t == INT:
            return int(v)
        if t == REAL:
            return to_float(v)
    except ValueError:
        return None
    return v


def _xy(x, y, opts):
    try:
        x, y = to_float(x), to_float(y)
    except (TypeError, ValueError):
        return None
    return (y, x) if opts.get('swap') else (x, y)


def raw_point(attrs, opts):
    p = _xy(attrs.get(opts['x_col']), attrs.get(opts['y_col']), opts)
    return QgsPointXY(*p) if p else None


def _transform(src_crs, dst_crs, ctx=None):
    return QgsCoordinateTransform(src_crs, dst_crs, ctx or QgsProject.instance().transformContext())


def _list_dir(path):
    try:
        with os.scandir(path) as it:
            return {e.name for e in it}
    except OSError:
        return set()


class TileLinker:
    """Find the tile image under each point (EPSG:3857), checking sources from the top.
    Per-file existence checks are slow over the network, so x folders are listed in parallel instead."""

    def __init__(self, sources):
        self.sources = [s for s in sources if not tiles.is_remote(s['path'])]
        self._dirs = {}

    def _tiles(self, x, y):
        if not (abs(x) < tiles.ORIGIN and abs(y) < tiles.ORIGIN):
            return
        for s in self.sources:
            z = s['zmax']
            n = 2 ** z
            size = 2 * tiles.ORIGIN / n
            tx = int((x + tiles.ORIGIN) // size)
            ty = int((tiles.ORIGIN - y) // size)
            if s.get('tms'):
                ty = n - 1 - ty
            yield s, os.path.join(tiles.zoom_path(s, z), str(tx)), f"{ty}.{s['ext']}"

    def prefetch(self, pts):
        dirs = {d for p in pts if p for _, d, _ in self._tiles(*p)} - self._dirs.keys()
        if not dirs:
            return
        dirs = sorted(dirs)
        with ThreadPool(min(LIST_THREADS, len(dirs))) as pool:
            for d, names in zip(dirs, pool.map(_list_dir, dirs)):
                self._dirs[d] = names

    def link(self, p):
        if p is None:
            return None, None
        names, first = [], None
        for s, d, f in self._tiles(*p):
            if d not in self._dirs:
                self._dirs[d] = _list_dir(d)
            if f in self._dirs[d]:
                names.append(s['name'])
                first = first or os.path.join(d, f)
        return (','.join(names) or None), first


def _unique(name, used):
    base, i = name, 1
    while name.lower() in used:
        name = f'{base}_{i}'
        i += 1
    used.add(name.lower())
    return name


def build_features(headers, rows, opts, dst_crs, ctx, sources, progress=None, canceled=None):
    """Build point features (safe to call from a worker thread).
    Returns (opts, fields, features, row count, rows without position, rows with a tile image)."""
    progress = progress or (lambda v: None)
    canceled = canceled or (lambda: False)
    src_crs = QgsCoordinateReferenceSystem(opts['crs'])
    xi, yi = headers.index(opts['x_col']), headers.index(opts['y_col'])
    types = _field_types(headers, rows, {opts['x_col'], opts['y_col']})
    used = {'fid', 'geom'}
    names = [_unique(h or f'col{i + 1}', used) for i, h in enumerate(headers)]
    link_names = [_unique(n, used) for n in LINK_FIELDS]
    opts = dict(opts, x_col=names[xi], y_col=names[yi], link_fields=link_names,
                label=names[headers.index(opts['label'])] if opts.get('label') in headers else None)
    progress(10)

    to_dst = _transform(src_crs, dst_crs, ctx)
    to_web = _transform(src_crs, QgsCoordinateReferenceSystem('EPSG:3857'), ctx)
    xys, webs, bad = [], [], 0
    for r in rows:
        p = _xy(r[xi], r[yi], opts)
        d = w = None
        if p is not None:
            try:
                q = to_dst.transform(*p)
                d = (q.x(), q.y())
                q = to_web.transform(*p)
                w = (q.x(), q.y())
            except Exception:
                d = w = None
        if d is None:
            bad += 1
        xys.append(d)
        webs.append(w)
    if canceled():
        return None
    progress(30)

    linker = TileLinker(sources)
    linker.prefetch(webs)
    if canceled():
        return None
    progress(60)
    links = [linker.link(w) for w in webs]
    linked = sum(1 for l in links if l[0])

    fields = QgsFields()
    for n, t in zip(names + link_names, types + [STR, STR]):
        fields.append(QgsField(n, _QT_TYPES[t]))
    feats = []
    for r, l, xy in zip(rows, links, xys):
        f = QgsFeature(fields)
        f.setAttributes([_convert(v, t) for v, t in zip(r, types)] + list(l))
        if xy is not None:
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*xy)))
        feats.append(f)
    progress(100)
    return opts, fields, feats, len(rows), bad, linked


def make_layer(name, fields, feats, crs):
    """Temporary (memory) layer. Call from the main thread."""
    lyr = QgsVectorLayer('Point', name, 'memory')
    lyr.setCrs(crs)
    pr = lyr.dataProvider()
    pr.addAttributes(fields.toList())
    lyr.updateFields()
    pr.addFeatures(feats)
    lyr.updateExtents()
    return lyr


class ImportTask(QgsTask):
    """Reads the table and builds features in the background; the layer is created in finished()."""

    def __init__(self, name, opts, dst_crs, sources, on_done, table=None, db_source=None):
        super().__init__(tr('Import XY attribute table: {name}').format(name=name))
        self.name = name
        self.opts = opts
        self.dst_crs = dst_crs
        self.ctx = QgsProject.instance().transformContext()
        self.sources = [dict(s) for s in sources]
        self.on_done = on_done
        self.table = table
        self.db_source = db_source
        self.result = None
        self.error = None

    def run(self):
        try:
            if self.db_source is not None:
                provider, uri, config, sql, fields = self.db_source
                # connections cannot be shared across threads, so open a new one here
                conn = QgsProviderRegistry.instance().providerMetadata(provider).createConnection(uri, config)
                headers, rows = db.query(conn, sql, fields)
            else:
                headers, rows = self.table
            if self.isCanceled():
                return False
            self.setProgress(5)
            self.result = build_features(headers, rows, self.opts, self.dst_crs, self.ctx, self.sources,
                                         lambda v: self.setProgress(5 + v * 0.95), self.isCanceled)
            return self.result is not None
        except Exception as e:
            self.error = e
            return False

    def finished(self, result):
        self.on_done(self, result)


def offset_hint(p_src, crs):
    """Warning text if the values cannot be plane rectangular coordinates."""
    if crs.isGeographic() or p_src is None:
        return ''
    if max(abs(p_src.x()), abs(p_src.y())) > MAX_PLANE_OFFSET:
        return tr('Coordinates exceed ±300 km. The source CRS may be wrong. '
                  'Use longitude/latitude columns (such as l / b) if available.')
    return ''
