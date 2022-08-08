# -*- coding: utf-8 -*-


def classFactory(iface):
    from .plugin import plugin

    return plugin(iface)
