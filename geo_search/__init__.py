"""QGIS plugin entrypoint.

Avoid heavy imports at module import time to prevent circular imports during
QGIS plugin loading. Import the compatibility shim here inside classFactory so
it runs before the plugin instance is created but does not execute during
partial package initialization.
"""

def classFactory(iface):
    # Ensure qt_compat is imported so its runtime monkey-patches (e.g. for
    # QgsMessageLog) are applied before the plugin runs, but do this lazily to
    # avoid circular imports during package initialization.
    try:
        import importlib
        importlib.import_module('geo_search.qt_compat')
    except Exception:
        # best-effort: if importing the shim fails, continue; plugin should
        # still try to run without the compatibility helpers.
        pass

    # Import plugin implementation and return an instance
    from .plugin import plugin
    return plugin(iface)
