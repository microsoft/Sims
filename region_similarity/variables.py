# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains functions for managing user aliases (i.e., GEE variables),
and performing various operations on image collections and layers.
"""

import ee
import requests
import ipywidgets as widgets
from region_similarity.features import remove_feature
from region_similarity.helpers import message
from solara import display
from solara.lab import task
from multiprocess import Pool


def check_image_validity(image):
    """
    Check if an Earth Engine image is valid.

    Args:
        image (ee.Image): The Earth Engine image to check.

    Returns:
        bool: True if the image is valid, False otherwise.
    """
    try:
        return image.bandNames().size().getInfo() > 0
    except Exception as e:
        return False


def get_bands(product, m):
    """
    Retrieve the band names for a given Earth Engine product.

    Args:
        product (str): The Earth Engine product ID.
        m (object): Map object containing various attributes and methods.

    Returns:
        list: A list of band names for the given product.
    """
    try:
        root = "https://storage.googleapis.com/earthengine-stac/catalog"
        pieces = product.split("/")
        category = pieces[0]
        stac_name = "_".join(pieces)
        url = f"{root}/{category}/{stac_name}.json"
        response = requests.get(url)
        data = response.json()
        bands = [band["name"] for band in data["summaries"]["eo:bands"]]
    except Exception as e:
        try:
            dataset = ee.ImageCollection(product).first()
            bands = dataset.bandNames().getInfo()
        except Exception as e:
            try:
                dataset = ee.Image(product)
                bands = dataset.bandNames().getInfo()
            except Exception as e:
                message(m, "Error loading bands.", False)
                message(m, "Error loading bands.", True, 1)
                bands = list()
    return bands


def update_custom_product(e, m):
    """
    Updates the bands dropdown options based on the provided product ID.

    Args:
        e (object): Event object (unused).
        m (object): Map object containing various attributes and methods.

    Returns:
        None
    """

    # Get the product ID
    product_id = m.custom_product_input.value

    # If the string is empty, we set the dropdown to an empty list and its default value to None
    if not product_id:
        m.band_dropdown.options = list()
        m.band_dropdown.value = None
        return

    # Otherwise, we want to show a `loading` message and look for the product!
    message(m, "Loading bands...", False)

    # Get the bands for the product
    bands = get_bands(product_id, m)
    m.band_dropdown.options = bands
    m.band_dropdown.value = bands[0] if bands else None

    # Clear the message
    message(m, "Loading bands...", True, 0.1)


def remove_alias(alias, m):
    """
    Remove an alias from the map and update the UI.

    Args:
        alias (str): The alias to remove.
        m (object): Map object containing various attributes and methods.

    Returns:
        None
    """

    # Remove the alias layer from the map
    m.layers = [layer for layer in m.layers if layer.name != alias]

    # Drop the alias from the aliases dictionary
    del m.aliases[alias]

    # Clear the output widget and print the added variables
    with m.added_variables_output:
        m.added_variables_output.clear_output()
        for alias, (dataset, layer, agg_fun, _, _, _) in m.aliases.items():
            remove_button = widgets.Button(
                description="x",
                layout=widgets.Layout(width="20px", text_align="center", padding="0"),
            )
            spacer = widgets.HBox([], layout=widgets.Layout(flex="1 1 auto"))
            remove_button.on_click(lambda _, a=alias: remove_alias(a, m))
            display(
                widgets.HBox(
                    [
                        widgets.Label(
                            f"{alias}: {dataset.split('/')[-1]}:{layer}:{agg_fun}"
                        ),
                        spacer,
                        remove_button,
                    ],
                    layout=widgets.Layout(width="100%"),
                )
            )

    # Find the features that include the alias
    features_to_remove = [
        name for name, (expression, _) in m.features.items() if alias in expression
    ]

    # Remove the features that include the alias
    for feature in features_to_remove:
        remove_feature(feature, m)


def get_img_minmax(ds, alias, scale=100, tile_scale=1, max_pixels=1e9):
    """
    Calculate the minimum and maximum values of an Earth Engine image.

    Args:
        ds (ee.Image): The Earth Engine image.
        alias (str): The alias for the image band.
        scale (int, optional): The scale in meters. Defaults to 100.
        tile_scale (int, optional): The tile scale. Defaults to 1.
        max_pixels (int, optional): The maximum number of pixels to compute. Defaults to 1e9.

    Returns:
        tuple: A tuple containing the minimum and maximum values.
    """
    min_max = ds.reduceRegion(
        reducer=ee.Reducer.minMax(),
        tileScale=tile_scale,
        scale=scale,
        maxPixels=max_pixels,
        bestEffort=True,
    ).getInfo()
    return min_max[f"{alias}_min"], min_max[f"{alias}_max"]


def run_add_alias(ds, alias):
    """
    Run the process of adding an alias, including computing min/max values.

    Args:
        ds (ee.Image): The Earth Engine image.
        alias (str): The alias for the image band.

    Returns:
        tuple: A tuple containing the minimum and maximum values.
    """

    # Simulate a long operation to get min/max
    min_val, max_val = get_img_minmax(ds=ds, alias=alias)

    # Compute the image
    _ = ds.getInfo()

    return min_val, max_val


@task
def async_add_alias(ds, alias, m, timeout_seconds=10, attempts=3):
    """
    Asynchronously add an alias to the map with retries.

    Args:
        ds (ee.Image): The Earth Engine image.
        alias (str): The alias for the image band.
        m (object): Map object containing various attributes and methods.
        timeout_seconds (int, optional): Timeout for each attempt in seconds. Defaults to 10.
        attempts (int, optional): Number of attempts to try. Defaults to 3.

    Returns:
        None
    """

    # Add a message
    message(m, f"[Background task] Loading `{alias}`...", False)

    pool = Pool(processes=1)  # Create a single process pool

    for attempt in range(attempts):
        try:

            # Start the process asynchronously using apply_async
            result = pool.apply_async(run_add_alias, (ds, alias))

            # Get the result with a timeout. This will raise a TimeoutError if it exceeds the timeout.
            min_val, max_val = result.get(timeout=timeout_seconds)

            # Visualization task
            viz = {
                "min": min_val,
                "max": max_val,
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


def add_alias(
    e,
    m,
    alias_name=None,
    dataset=None,
    layer=None,
    start_date=None,
    end_date=None,
    agg_fun=None,
    list_aliases=False,
):
    """
    Adds the selected layer as an alias to the map and updates the UI.

    Args:
        e (object): Event object (unused).
        m (object): Map object containing various attributes and methods.
        alias_name (str, optional): Custom alias name. Defaults to None.
        dataset (str, optional): Custom dataset ID. Defaults to None.
        layer (str, optional): Custom layer name. Defaults to None.
        start_date (datetime, optional): Start date for filtering. Defaults to None.
        end_date (datetime, optional): End date for filtering. Defaults to None.
        agg_fun (str, optional): Aggregation function. Defaults to None.
        list_aliases (bool, optional): Whether to list aliases after adding. Defaults to False.

    Returns:
        None
    """

    # If the alias is empty, we will set it to be `{dataset}:{layer}`
    alias = m.layer_alias_input.value if alias_name is None else alias_name
    if not alias:
        alias = f"{agg_fun}({layer_id})" if agg_fun != "NONE" else layer_id

    # Get the selected product ID, layer, and alias
    dataset_id = m.custom_product_input.value if dataset is None else dataset
    layer_id = m.band_dropdown.value if layer is None else layer

    # If the dataset or layer is empty, we will not add the alias
    if not dataset_id or not layer_id:
        message(m, "Please select a dataset and layer.", False)
        message(m, "Please select a dataset and layer.", True)
        return

    # Get the aggregation function
    agg_fun = m.agg_fun_dropdown.value if agg_fun is None else agg_fun

    try:

        # Get the start and end dates and format them for querying
        start_date = (m.start if start_date is None else start_date).isoformat()
        end_date = (m.end if end_date is None else end_date).isoformat()

        # Set the region of interest
        qr_roi = m.qr if not m.roi else m.qr.union(m.roi)

        # An attempt to grab an early win if the agg_fun is `LAST` and the user wants an image instead of a collection
        ds = None
        if agg_fun == "LAST":
            img = ee.Image(dataset_id).select(layer_id)
            if check_image_validity(img):
                ds = img

        # If the user does not want an image, we simply load the collection.
        if not ds:
            ds = ee.ImageCollection(dataset_id).select(layer_id)
            ds = ds.filterDate(start_date, end_date)
            ds = ds.filterBounds(qr_roi)
            if not ds.size().getInfo():
                message(
                    m,
                    "No data available for the selected region and time period.",
                    False,
                )
                message(
                    m,
                    "No data available for the selected region and time period.",
                    True,
                )
                m.layer_alias_input.value = ""
                return

        # Only do this if `ds` is a collection
        if isinstance(ds, ee.ImageCollection):
            if agg_fun == "LAST":
                ds = ds.sort("system:time_start", False).first()
            elif agg_fun == "FIRST":
                ds = ds.first()
            elif agg_fun == "MAX":
                ds = ds.max()
            elif agg_fun == "MIN":
                ds = ds.min()
            elif agg_fun == "MEAN":
                ds = ds.mean()
            elif agg_fun == "MEDIAN":
                ds = ds.median()
            elif agg_fun == "SUM":
                ds = ds.sum()
            elif agg_fun == "MODE":
                ds = ds.mode()
            else:
                message(m, f"aggregation function {agg_fun} is invalid", False)
                message(m, f"aggregation function {agg_fun} is invalid", True)
                return

        # Clip the image to the query region
        ds = ds.clip(qr_roi)

        # Rename the band to the alias
        ds = ds.rename(alias)

        # Add the alias to the dictionary
        m.aliases[alias] = [dataset_id, layer_id, agg_fun, start_date, end_date, ds]

        # Clear the output widget and print the added variables
        if list_aliases:
            with m.added_variables_output:
                m.added_variables_output.clear_output()
                for alias_, (dataset, layer, agg_fun, _, _, _) in m.aliases.items():
                    remove_button = widgets.Button(
                        description="x",
                        layout=widgets.Layout(
                            width="20px", text_align="center", padding="0"
                        ),
                    )
                    spacer = widgets.HBox([], layout=widgets.Layout(flex="1 1 auto"))
                    remove_button.on_click(lambda _, a=alias_: remove_alias(a, m))
                    display(
                        widgets.HBox(
                            [
                                widgets.Label(
                                    f"{alias_}: {dataset.split('/')[-1]}:{layer}:{agg_fun}"
                                ),
                                spacer,
                                remove_button,
                            ],
                            layout=widgets.Layout(width="100%"),
                        )
                    )

        # Empty the alias field
        m.layer_alias_input.value = ""

        # Add the alias to the map as a thread
        async_add_alias(ds, alias, m)

    except Exception as e:
        message(m, f"Error: {e}.", False)
        message(m, f"Error: {e}.", True, 10)
