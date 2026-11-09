from qgis.core import (
    QgsMarkerSymbol, QgsPalLayerSettings, QgsSingleSymbolRenderer, QgsTextBufferSettings, QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
)


def style_points(layer, label_field=None):
    """Red dots with a white outline; labels only when zoomed in beyond 1:5000."""
    sym = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': '255,0,0', 'outline_color': '255,255,255',
                                        'outline_width': '0.4', 'size': '2.4'})
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    if not label_field:
        return
    s = QgsPalLayerSettings()
    s.fieldName = label_field
    fmt = QgsTextFormat()
    fmt.setSize(9)
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(1)
    fmt.setBuffer(buf)
    s.setFormat(fmt)
    s.scaleVisibility = True
    s.minimumScale = 5000
    s.maximumScale = 1
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
    layer.setLabelsEnabled(True)
