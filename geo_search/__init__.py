"""QGIS plugin entrypoint.

Avoid heavy imports at module import time to prevent circular imports during
QGIS plugin loading. Import the compatibility shim here inside classFactory so
it runs before the plugin instance is created but does not execute during
partial package initialization.
"""

def classFactory(iface):
    # Ensure sys.stderr is usable: some embeders set it to None which breaks
    # third-party libraries (numpy writes to sys.stderr during import). If it
    # is None, restore from sys.__stderr__ or provide a small logging wrapper.
    try:
        import sys, logging
        if getattr(sys, 'stderr', None) is None or not hasattr(sys.stderr, 'write'):
            if getattr(sys, '__stderr__', None) is not None and hasattr(sys.__stderr__, 'write'):
                sys.stderr = sys.__stderr__
            else:
                class _StderrProxy:
                    def write(self, s):
                        try:
                            logging.getLogger('geo_search').error(str(s).rstrip())
                        except Exception:
                            pass
                    def flush(self):
                        return
                sys.stderr = _StderrProxy()
    except Exception:
        # best-effort: do not prevent plugin from loading
        pass

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
