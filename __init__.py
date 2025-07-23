from .plugin import plugin

def classFactory(iface):
    return plugin(iface)
