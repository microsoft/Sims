# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains utility functions for managing and updating a map object
in a region similarity analysis application. It includes functions for updating
dropdowns, handling clustering changes, and resetting the map.
"""

from datetime import date
from region_similarity.helpers import message


def update_distance_dropdown(change, m):
    """
    Updates the distance function dropdown options based on the selected option.

    Args:
        change (dict): Dictionary containing the new category value.
        m (object): Map object containing various attributes and methods.

    Returns:
        None
    """
    try:
        m.distance_fun = change["new"]
    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)


def update_mask_dropdown(change, m):
    """
    Updates the mask dropdown value in the map object.

    Args:
        change (dict): Dictionary containing the new value for the mask dropdown.
        m (object): Map object containing various attributes and methods.

    Returns:
        None
    """
    try:
        m.mask = change["new"]
    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)


def handle_clustering_change(change, m):
    """
    Handles changes in the clustering checkbox, updating various UI elements
    and map object attributes accordingly.

    Args:
        change (dict): Dictionary containing the new value for the clustering checkbox.
        m (object): Map object containing various attributes and methods.

    Returns:
        None
    """
    try:
        if change["new"]:
            m.cluster = True
            m.search_button.description = "Cluster!"
            m.set_roi_button.disabled = True
            m.roi_upload_button.disabled = True
            m.max_value_slider.disabled = True
            m.num_clusters.disabled = False
        else:
            m.cluster = False
            m.search_button.description = "Search!"
            m.set_roi_button.disabled = False
            m.roi_upload_button.disabled = False
            m.max_value_slider.disabled = False
            m.num_clusters.disabled = True
    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)


def reset_map(e, m):
    """
    Resets the map object to its initial state, clearing all layers, outputs,
    and resetting various attributes and UI elements.

    Args:
        e (object): Event object (unused).
        m (object): Map object containing various attributes and methods.

    Returns:
        None
    """
    try:

        # Reset the layers
        m.layers = [
            layer
            for layer in m.layers
            if ("Satellite" in layer.name or "OpenStreetMap" in layer.name)
        ]

        # Clear the output of the added variables widget
        with m.added_variables_output:
            m.added_variables_output.clear_output()

        # Clear the output of the main output widget
        with m.added_features_output:
            m.added_features_output.clear_output()

        # Clear the messaging output
        with m.output_widget:
            m.output_widget.clear_output()

        # Reset various attributes of the map object
        m.level = 0
        m.qr_set = False
        m.roi_set = False
        m.qr = None
        m.roi = None
        m.distances = None
        m.average_distance = None
        m.roi_upload_button.value = tuple()
        m.ros_upload_button.value = tuple()
        m.band_dropdown.value = None
        m.band_dropdown.options = list()
        m.mask_dropdown.value = "All"
        update_mask_dropdown({"new": "All"}, m)
        m.distance_dropdown.value = "Euclidean"
        update_distance_dropdown({"new": "Euclidean"}, m)
        m.custom_product_input.value = ""
        m.agg_fun_dropdown.value = "LAST"
        m.layer_alias_input.value = ""
        m.udf.value = ""
        m.aliases = dict()
        m.features = dict()
        handle_clustering_change({"new": False}, m)
        m.cluster_checkbox.value = False
        m.set_region_button.disabled = False
        m.start_date.value = date(2000, 1, 1)
        m.end_date.value = date(2000, 1, 1)
        m.start = date(2000, 1, 1)
        m.end = date(2000, 1, 1)
        m.max_value_slider.value = 3.3
        m.download_bar.value = 0
        m.download_bar.layout.visibility = "hidden"
        m.download_bar.layout.height = "0px"

    except Exception as e:
        message(m, f"Error resetting map: {e}", False)
        message(m, f"Error resetting map: {e}", True, 5)
