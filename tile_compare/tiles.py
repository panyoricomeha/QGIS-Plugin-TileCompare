"""Helpers for tile folders laid out as {z}/{x}/{y}.ext."""
import os
import re

from qgis.PyQt.QtCore import QUrl
from qgis.core import QgsDataSourceUri, QgsRectangle

ORIGIN = 20037508.342789244  # EPSG:3857 half extent
WHITE_THRESHOLD = 248  # JPEG noise turns white into 251-254, so allow some margin
IMAGE_EXTS = ('png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'gif')
MIN_ZOOM, MAX_ZOOM = 0, 30
_ZOOM_RE = re.compile(r'^(?:z|l|lv|level|zoom)?[_-]?0*(\d{1,2})$', re.IGNORECASE)


def is_remote(path):
    return path.lower().startswith(('http://', 'https://'))


def _digit_entries(path, want_dir):
    try:
        with os.scandir(path) as it:
            return sorted(int(e.name) for e in it if e.name.isdigit() and e.is_dir() == want_dir)
    except OSError:
        return []


def zoom_dirs(root):
    """{zoom: folder name}. Accepts '18', zero padded '05' and prefixed names like 'z18', 'L18', 'level_18'."""
    found = {}
    try:
        with os.scandir(root) as it:
            for e in it:
                m = _ZOOM_RE.match(e.name)
                if m and e.is_dir():
                    z = int(m.group(1))
                    if MIN_ZOOM <= z <= MAX_ZOOM and (z not in found or e.name == str(z)):
                        found[z] = e.name
    except OSError:
        pass
    return found


def zoom_levels(root):
    return sorted(zoom_dirs(root))


def zoom_path(src, z):
    """Folder of zoom z, honoring non-standard folder names recorded in src['zdirs']."""
    return os.path.join(src['path'], (src.get('zdirs') or {}).get(str(z), str(z)))


def _detect_ext(root, zdirs):
    for z in sorted(zdirs):
        zdir = os.path.join(root, zdirs[z])
        for x in _digit_entries(zdir, True)[:5]:
            try:
                with os.scandir(os.path.join(zdir, str(x))) as it:
                    for e in it:
                        stem, ext = os.path.splitext(e.name)
                        ext = ext[1:].lower()
                        if stem.isdigit() and ext in IMAGE_EXTS:
                            return ext
            except OSError:
                continue
    return None


def detect_source(root):
    """Return a source definition if root contains zoom level folders, otherwise None."""
    zdirs = zoom_dirs(root)
    if not zdirs:
        return None
    ext = _detect_ext(root, zdirs)
    if ext is None:
        return None
    src = {
        'name': os.path.basename(os.path.normpath(root)),
        'path': os.path.normpath(root),
        'ext': ext,
        'zmin': min(zdirs),
        'zmax': max(zdirs),
        'tms': False,
    }
    if any(name != str(z) for z, name in zdirs.items()):
        src['zdirs'] = {str(z): name for z, name in zdirs.items()}
    return src


def find_sources(folder):
    """The folder itself if it is a tile folder, otherwise tile folders one level below it."""
    src = detect_source(folder)
    if src:
        return [src]
    found = []
    try:
        with os.scandir(folder) as it:
            subdirs = sorted(e.path for e in it if e.is_dir())
    except OSError:
        return []
    for sub in subdirs:
        src = detect_source(sub)
        if src:
            found.append(src)
    return found


def tile_url(src, server_url=None):
    """Tile URL for QGIS. Local folders go through the tile server when server_url is given."""
    y = '{-y}' if src.get('tms') else '{y}'
    path = src['path']
    if is_remote(path):
        if '{z}' in path:
            return path
        base = path.rstrip('/')
    elif server_url:
        mode = 'w' if src.get('white_transparent') else 'o'
        base = f"{server_url}/{src['uid']}/{mode}"
    else:
        base = QUrl.fromLocalFile(os.path.abspath(path)).toString().rstrip('/')
    return f"{base}/{{z}}/{{x}}/{y}.{src['ext']}"


def layer_uri(src, server_url=None):
    uri = QgsDataSourceUri()
    uri.setParam('type', 'xyz')
    uri.setParam('url', tile_url(src, server_url))
    uri.setParam('zmin', str(src['zmin']))
    uri.setParam('zmax', str(src['zmax']))
    return bytes(uri.encodedUri()).decode()


def tile_extent(src, max_dirs=64):
    """EPSG:3857 extent from tile numbers (local only).
    Low zooms are coarse, so step up until there are more than max_dirs x folders."""
    if is_remote(src['path']):
        return None
    best = None
    for z in zoom_levels(src['path']):
        if not src['zmin'] <= z <= src['zmax']:
            continue
        extent = _extent_at(src, z, max_dirs)
        if extent is None:
            break
        best = extent
    return best


def _extent_at(src, z, max_dirs):
    zdir = zoom_path(src, z)
    xs = _digit_entries(zdir, True)
    if len(xs) > max_dirs:
        return None
    ys = []
    for x in xs:
        try:
            with os.scandir(os.path.join(zdir, str(x))) as it:
                ys.extend(int(os.path.splitext(e.name)[0]) for e in it
                          if os.path.splitext(e.name)[0].isdigit())
        except OSError:
            continue
    if not xs or not ys:
        return None
    n = 2 ** z
    if src.get('tms'):
        ys = [n - 1 - y for y in ys]
    size = 2 * ORIGIN / n
    return QgsRectangle(-ORIGIN + min(xs) * size, ORIGIN - (max(ys) + 1) * size,
                        -ORIGIN + (max(xs) + 1) * size, ORIGIN - min(ys) * size)
