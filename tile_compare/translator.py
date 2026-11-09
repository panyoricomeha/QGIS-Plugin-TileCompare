"""Translation support. Strings are English in code; translations live in i18n/tile_compare_<lang>.ts.

Translations are looked up only by this plugin's tr(); nothing is installed into QGIS, so other
QGIS texts are never affected.
"""
import os
import xml.etree.ElementTree as ET

from qgis.core import QgsApplication

_messages = {}


def tr(text):
    return _messages.get(text, text)


def load(plugin_dir):
    """Load the .ts file for the QGIS UI language, if there is one."""
    _messages.clear()
    lang = (QgsApplication.locale() or 'en')[:2]
    path = os.path.join(plugin_dir, 'i18n', f'tile_compare_{lang}.ts')
    if not os.path.exists(path):
        return
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return
    for msg in root.iter('message'):
        source = msg.findtext('source')
        trans = msg.find('translation')
        if source and trans is not None and trans.text and trans.get('type') not in ('unfinished', 'obsolete'):
            _messages[source] = trans.text


def unload():
    _messages.clear()
