# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QVariant

from qgis.core import QgsProject, QgsFeatureRequest
from qgis.utils import iface


def name2layer(name):
    project = QgsProject.instance()
    layers = project.mapLayersByName(name)
    for layer in layers:
        return layer


def unique_values(layer, field_name):
    fields = layer.fields()
    field_index = fields.indexFromName(field_name)
    if field_index == -1:
        return []
    attrs = []
    for attr in layer.uniqueValues(field_index):
        if isinstance(attr, QVariant) and attr.isNull():
            continue
        if attr is None:
            continue
        attrs.append(attr)
    return attrs


def get_feature_by_id(layer, feature_id):
    request = QgsFeatureRequest()
    request.setFilterFid(feature_id)
    for feature in layer.getFeatures(request):
        return feature
