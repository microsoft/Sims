# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains helper functions for working with Google Earth Engine (GEE) objects
and map visualizations. It provides utilities for displaying messages, validating GEE objects,
and updating map visualizations based on thresholds.
"""

import ee
import time


def message(m, text="", clear=True, duration=3):
    """
    Displays a message in the output widget of the map object.

    Args:
        m (object): Map object containing the output widget.
        text (str): The message to display.
        clear (bool): Whether to clear the output widget after displaying the message.
        duration (int): The duration in seconds to wait before clearing the message.

    Returns:
        None
    """
    with m.output_widget:
        if clear:
            time.sleep(duration)
            m.output_widget.outputs = tuple(
                [e for e in m.output_widget.outputs if e["text"] != f"{text}\n"]
            )
        elif text:
            m.output_widget.append_stdout(f"{text}\n")


def is_valid_gee_object(m, object):
    """
    Checks if a given Google Earth Engine (GEE) object is valid by performing light sanity checks based on object type.
    If it's valid, return `True`, if it's invalid, share the error message and return False so that parent functions gracefully stop execution.

    Args:
        m (object): Map object containing various attributes and methods.
        object (ee.ComputedObject): The GEE object to check.

    Returns:
        bool: True if the object is valid, False otherwise.

    Raises:
        ee.EEException: If there's an error while checking the object.
    """
    if isinstance(object, ee.ImageCollection):
        # Check if the ImageCollection contains more than 1 image
        count = object.size().getInfo()
        if count > 0:
            return True
        else:
            message(m, "Error: ImageCollection contains no images.", False)
            message(m, "Error: ImageCollection contains no images.", True, 5)
            return False

    if isinstance(object, ee.Image):
        # Check if the image has bands
        bands = object.bandNames().getInfo()
        if bands:
            return True
        else:
            message(m, "Image has no bands.", False)
            message(m, "Image has no bands.", True, 5)
            return False

    elif isinstance(object, ee.Geometry):
        # Check if the geometry area is more than 0
        area = object.area().getInfo()
        if area > 0:
            return True
        else:
            message(m, "Error: Geometry area is 0.", False)
            message(m, "Error: Geometry area is 0.", True, 5)
            return False

    elif isinstance(object, ee.FeatureCollection):
        # Check if the FeatureCollection contains more than 1 feature
        count = object.size().getInfo()
        if count > 0:
            return True
        else:
            message(m, "Error: FeatureCollection contains no features.", False)
            message(m, "Error: FeatureCollection contains no features.", True, 5)
            return False

    elif isinstance(object, ee.Feature):
        # Check if the feature has valid geometry
        area = object.geometry().area().getInfo()
        if area > 0:
            return True
        else:
            message(m, "Error: Feature has invalid geometry.", False)
            message(m, "Error: Feature has invalid geometry.", True, 5)
            return False

    else:
        # For other types, use a generic check
        try:
            _ = object.getInfo()
            return True
        except ee.EEException as e:
            message(m, f"Error: {e}", False)
            message(m, f"Error: {e}", True, 5)
            return False


def update_map(change, m):
    """
    Updates the map visualization by applying a threshold to the average distance image.

    This function creates a binary image based on the new threshold value and adds it
    as a layer to the map with specified visualization parameters.

    Args:
        change (dict): Dictionary containing the new threshold value.
        m (object): Map object containing various attributes and methods, including
                    the average_distance image.

    Returns:
        None

    Note:
        This function assumes that m.average_distance is a valid ee.Image object.
    """
    max_val = change.new

    if m.average_distance != None:

        # Create a binary image with `1==similar` and `0==dissimilar`
        binary_image = m.average_distance.lte(max_val)

        # Visualization parameters for the masked image as binary mask
        viz_params = {"palette": ["00000000", "FF00007F"], "opacity": 0.5}

        # Add the binary image layer to the map with the specified visualization parameters
        m.addLayer(binary_image, viz_params, "Average Distance")
