def classFactory(iface):
    from .plugin import TileComparePlugin
    return TileComparePlugin(iface)
