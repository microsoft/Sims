# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains functions for managing features (GEE expressions of aliases).
It uses Earth Engine (ee) for geospatial operations and ipywidgets for UI components.
"""

import ee
import ipywidgets as widgets
from region_similarity.helpers import message
from solara import display
from solara.lab import task
from multiprocess import Pool


def remove_feature(feature, m):
    """
    Remove a feature from the map and update the UI.

    Args:
        feature (str): The name of the feature to remove.
        m (object): The map object containing layers and features.
    """
    # Remove the feature layer from the map
    m.layers = [layer for layer in m.layers if layer.name != feature]

    # Drop the feature from the features dictionary
    del m.features[feature]

    # Clear the output widget and print the added features
    with m.added_features_output:
        m.added_features_output.clear_output()
        for name, (expression, _) in m.features.items():
            remove_button = widgets.Button(
                description="x",
                layout=widgets.Layout(width="20px", text_align="center", padding="0"),
            )
            spacer = widgets.HBox([], layout=widgets.Layout(flex="1 1 auto"))
            remove_button.on_click(lambda _, a=name: remove_feature(a, m))
            display(
                widgets.HBox(
                    [
                        widgets.Label(f"{name}:{expression}\n"),
                        spacer,
                        remove_button,
                    ],
                    layout=widgets.Layout(width="100%"),
                )
            )


def run_check_feature_img(feature_img):
    """
    Check if a feature image is computable within the timeout.

    Args:
        feature_img (ee.Image): The Earth Engine image to check.

    Returns:
        bool: True if the image is computable, False otherwise.
    """
    try:
        _ = feature_img.getInfo()
        return True
    except Exception as e:
        return False


@task
def async_add_feature(ds, alias, m, timeout_seconds=10, attempts=3):
    """
    Asynchronously add a feature to the map with retry logic.

    Args:
        ds (ee.Image): The Earth Engine image to add.
        alias (str): The name of the feature.
        m (object): The map object to add the feature to.
        timeout_seconds (int): The timeout for each attempt in seconds.
        attempts (int): The number of attempts to make.
    """
    # Add a message
    message(m, f"[Background task] Loading `{alias}`...", False)

    pool = Pool(processes=1)  # Create a single process pool

    for attempt in range(attempts):
        try:

            # Start the process asynchronously using apply_async
            result = pool.apply_async(run_check_feature_img, (ds,))

            # Get the result with a timeout. This will raise a TimeoutError if it exceeds the timeout.
            result.get(timeout=timeout_seconds)

            # Visualization task
            viz = {
                "min": -3.719,
                "max": +3.719,
                "palette": [
                    "#FFFFFF",
                    "#EEEEEE",
                    "#CCCCCC",
                    "#888888",
                    "#444444",
                    "#000000",
                ],
            }

            # Add the layer to the map
            m.addLayer(ds, viz, alias)

            message(m, f"[Background task] Loading `{alias}`...", True, 0.1)

            return  # Successful, so we exit the function

        except Exception as e:

            # We got a failure, it's simple to just say that it failed and move on to the next attempt.
            message(m, f"Attempt {attempt + 1} failed. Retrying...", False)
            message(m, f"Attempt {attempt + 1} failed. Retrying...", True, 1)

            # If it's the last attempt, we will not retry
            if attempt == attempts - 1:
                message(m, f"[Background task] Loading `{alias}`...", True, 0.1)
                message(m, f"Consider a lower resolution.", False)
                message(m, f"Consider a lower resolution.", True, 1)
                return

            else:
                # If it's not the last attempt, we will retry
                continue

    pool.close()  # Close the pool
    pool.join()  # Ensure all processes have finished


def add_feature(e, m, udf_text=None):
    """
    Add a user-defined feature to the map.

    This function processes a user-defined function (UDF) expression,
    creates a new feature based on the expression, and adds it to the map.

    Args:
        e (object): Event object (unused).
        m (object): Map object containing various attributes and methods.
        udf_text (str, optional): The UDF expression text. If None, it's read from m.udf.value.

    Returns:
        None
    """
    # Get the UDF expression
    udf = m.udf.value if udf_text is None else udf_text

    # If the UDF is empty, we will not add it
    if not udf:
        message(m, "Please enter a UDF.", False)
        message(m, "Please enter a UDF.", True)
        return

    if ":" not in udf:
        message(
            m,
            "Please enter a valid UDF expression. Template: `{name}:{expression}`.",
            False,
        )
        message(
            m,
            "Please enter a valid UDF expression. Template: `{name}:{expression}`.",
            True,
        )
        return

    # Get the name and expression
    name, expression = udf.replace(" ", "").split(":")

    try:

        # Crop the image to the query region + reference region
        qr_roi = m.qr if not m.roi else m.qr.union(m.roi)

        # Stack all the bands into a single image
        image = ee.Image.cat([img for _, (_, _, _, _, _, img) in m.aliases.items()])

        # If the expression is equal to any of the aliases, we will use the alias
        if expression in m.aliases:
            feature_img = m.aliases[expression][-1]
        else:
            feature_img = image.expression(
                expression, {k: image.select(k) for k in m.aliases.keys()}
            ).select(0)

        # Calculate the mean and standard deviation
        mean = feature_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=qr_roi,
            scale=100,
            maxPixels=1e3,
            bestEffort=True,
            tileScale=2,
        )
        stdDev = feature_img.reduceRegion(
            reducer=ee.Reducer.stdDev(),
            geometry=qr_roi,
            scale=100,
            maxPixels=1e3,
            bestEffort=True,
            tileScale=2,
        )

        # Verify that the image is computable by calculating the mean. Use a try-except block to stop early if not.
        try:
            mean.values().getInfo()
        except Exception as e:
            message(m, f"Error: {e}.", False)
            message(m, f"Error: {e}.", True)
            return

        # Standardize the feature values using lazy evaluation
        mean_image = ee.Image.constant(mean.values())
        stdDev_image = ee.Image.constant(stdDev.values())

        # Standardize the feature values
        feature_img = feature_img.subtract(mean_image).divide(stdDev_image)

        # Add the feature
        m.features[name] = [expression, feature_img]

        # Clear the output widget and print the added variables
        with m.added_features_output:
            m.added_features_output.clear_output()
            for name, (expression, _) in m.features.items():
                remove_button = widgets.Button(
                    description="x",
                    layout=widgets.Layout(
                        width="20px", text_align="center", padding="0"
                    ),
                )
                spacer = widgets.HBox([], layout=widgets.Layout(flex="1 1 auto"))
                remove_button.on_click(lambda _, a=name: remove_feature(a, m))
                display(
                    widgets.HBox(
                        [
                            widgets.Label(f"{name}:{expression}\n"),
                            spacer,
                            remove_button,
                        ],
                        layout=widgets.Layout(width="100%"),
                    )
                )

        # Empty out the expression field
        m.udf.value = ""

        async_add_feature(feature_img, name, m)

    except Exception as e:
        message(m, f"Error: {e}.", False)
        message(m, f"Error: {e}.", True, 10)
