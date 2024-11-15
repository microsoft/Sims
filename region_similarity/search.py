# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains functions for performing region similarity searches and clustering
using Earth Engine imagery. It includes methods for calculating distances between image
pixels and mean vectors, executing searches or clustering operations, and handling map
interactions.
"""

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import ee
import geemap
from shapely.geometry import Point, mapping
from region_similarity.features import add_feature
from region_similarity.helpers import message
from solara.lab import task


def calc_distance(map, image, mean_vector, fun):
    """
    Calculates the distance between image pixel values and a mean vector using the specified distance function.

    Args:
        map (object): Map object for displaying messages.
        image (ee.Image): Earth Engine image.
        mean_vector (ee.Dictionary): Mean vector of pixel values.
        fun (str): Distance function to use. Options are 'Euclidean', 'Manhattan', 'Cosine'.

    Returns:
        ee.Image: Image representing the calculated distances.
    """
    try:
        roi_mean = ee.Image.constant(mean_vector.values())

        if fun == "Euclidean":
            diff = image.subtract(roi_mean)
            squared_diff = diff.pow(ee.Number(2))
            distance = squared_diff.reduce("sum").sqrt()

        elif fun == "Manhattan":
            diff = image.subtract(roi_mean).abs()
            distance = diff.reduce("sum")

        elif fun == "Cosine":
            dot_product = image.multiply(roi_mean).reduce("sum")
            image_norm = image.pow(2).reduce("sum").sqrt()
            mean_norm = roi_mean.pow(2).reduce("sum").sqrt()
            cosine_similarity = dot_product.divide(image_norm.multiply(mean_norm))
            distance = ee.Image.constant(1).subtract(cosine_similarity)

        return distance

    except Exception as e:
        if map:
            message(map, f"Error: {e}.", False)
            message(map, f"Error: {e}.", True, 5)
        return None


def execute(e, m):
    """
    Executes when the user clicks on either the `Search` or `Cluster` button.
    It ensures features are defined and routes to either `search` or `cluster`.

    Args:
        e (object): Event object.
        m (object): Map object containing various attributes and methods.
    """

    # If no features are defined, add variable features one by one
    if not m.features:
        for alias in m.aliases.keys():
            feature_name = alias
            feature_expression = alias
            udf_text = f"{feature_name}:{feature_expression}"
            add_feature(None, m, udf_text)

    # Execute the appropriate function based on the cluster flag
    cluster(e, m) if m.cluster else search(e, m)


def generate_color_palette(n_clusters):
    """
    Generates a color palette for visualizing clusters.

    Args:
        n_clusters (int): Number of clusters.

    Returns:
        list: List of color hexcodes.
    """
    cmap = plt.get_cmap("tab20")
    colors = [mcolors.rgb2hex(cmap(i % 20)) for i in range(n_clusters)]
    return colors


@task
def async_add_clusters(n_clusters, m):
    """
    Asynchronously adds clustered image to the map.

    Args:
        n_clusters (int): Number of clusters.
        m (object): Map object.
    """

    # Display a message
    message(m, f"[Background task] Creating {n_clusters} clusters...", False)

    # Define visualization parameters
    vis_params = {
        "min": 1,
        "max": n_clusters,
        "palette": generate_color_palette(n_clusters),
    }

    # Add the clustered image to the map
    m.addLayer(m.clustered, vis_params, "Clusters")

    message(m, f"[Background task] Creating {n_clusters} clusters...", True)


@task
def async_add_distance_map(m, region_of_search):
    """
    Asynchronously adds distance map to the map and updates slider values.

    Args:
        m (object): Map object.
        region_of_search (ee.Geometry): Region of search.
    """

    # Display a message
    message(m, f"[Background task] Calculating distance maps...", False)

    # Get the minimum and maximum values for the visualization
    min_val = m.average_distance.reduceRegion(
        reducer=ee.Reducer.min(),
        geometry=region_of_search,
        scale=100,
        bestEffort=True,
    ).getInfo()["mean"]
    max_val = m.average_distance.reduceRegion(
        reducer=ee.Reducer.max(),
        geometry=region_of_search,
        scale=100,
        bestEffort=True,
    ).getInfo()["mean"]

    # Update the minimum/maximum values for thresholding
    if min_val >= m.max_value_slider.max:
        m.max_value_slider.max = max_val
        m.max_value_slider.min = min_val
    else:
        m.max_value_slider.min = min_val
        m.max_value_slider.max = max_val
    m.max_value_slider.value = (min_val + max_val) / 2
    m.max_value_slider.min = min_val - 0.1 * (max_val - min_val)

    m.max_value_slider.min, m.max_value_slider.max = min_val, max_val

    # Add the average distance map to the map
    average_viz_params = {
        "min": min_val,
        "max": max_val,
        "palette": ["red", "orange", "yellow", "white", "lightblue", "blue"],
    }
    m.addLayer(m.average_distance, average_viz_params, "Average Distance")

    message(m, f"[Background task] Calculating distance maps...", True)


def cluster(e, m):
    """
    Performs clustering on the pixels within the search or query region using KMeans algorithm.

    Args:
        e (object): Event object.
        m (object): Map object containing various attributes and methods.
    """

    try:

        # Get the number of clusters
        n_clusters = m.num_clusters.value

        # Get the distance function
        if m.distance_fun == "Euclidean":
            distance_fun = "Euclidean"
        elif m.distance_fun == "Manhattan":
            distance_fun = "Manhattan"
        else:
            message(
                m,
                "Warning: Cosine similarity is not supported for clustering. Defaulting to Euclidean distance.",
                False,
            )
            distance_fun = "Euclidean"
            message(
                m,
                "Warning: Cosine similarity is not supported for clustering. Defaulting to Euclidean distance.",
                True,
            )

        # Stack the features
        m.feature_img = ee.Image.cat(
            [feature_img for _, (_, feature_img) in m.features.items()]
        )

        # Apply dynamic world-masking if specified
        if m.mask != "All":
            classes = [
                "water",
                "trees",
                "grass",
                "flooded_vegetation",
                "crops",
                "shrub_and_scrub",
                "built",
                "bare",
                "snow_and_ice",
            ]

            # Get the mosaic dynamic world image
            landcover = geemap.dynamic_world(
                m.qr,
                m.start.isoformat(),
                m.end.isoformat(),
                return_type="class",
            ).select("label_mode")

            # Mask the image using the class of interest
            m.feature_img = m.feature_img.updateMask(
                landcover.eq(classes.index(m.mask))
            )

        # Create the training dataset
        training = m.feature_img.sample(
            region=m.qr,
            scale=100,
            numPixels=5_000,
        )

        # Train the clusterer
        clusterer = ee.Clusterer.wekaKMeans(
            n_clusters, distanceFunction=distance_fun
        ).train(training)

        # Cluster the input features
        m.clustered = m.feature_img.cluster(clusterer).add(
            1
        )  # `0` is reserved for `nodata`

        # Add the clustered image to the map
        async_add_clusters(n_clusters, m)

    except Exception as e:
        message(m, f"Error: {e}.", False)
        message(map, f"Error: {e}.", True, 5)


def search(e, m):
    """
    Performs a search operation on the map, calculating distance maps for specified variables.

    Args:
        e (object): Event object.
        m (object): Map object containing various attributes and methods.
    """

    try:

        # Stack the features
        m.feature_img = ee.Image.cat(
            [feature_img for _, (_, feature_img) in m.features.items()]
        )

        # Now that we have the aliases and images, we can calculate the distances for each feature
        distance_maps = list()

        # Iterate over the features and calculate the distance maps
        for _, (_, feature_img) in m.features.items():

            # Calculate the mean of pixel vectors within the region of interest
            roi_mean_vector = feature_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=m.roi,
                bestEffort=True,
                scale=100,
            )

            # Apply the distance calculation function
            distance_map = calc_distance(
                m, feature_img, roi_mean_vector, m.distance_fun
            )

            # Save the layer to the list
            distance_maps.append(distance_map)

        # Stack the distance maps
        m.distances = ee.Image.cat(distance_maps)

        # Calculate the average distance across the bands
        m.average_distance = m.distances.reduce(ee.Reducer.mean())

        # Calculate the difference
        m.diff = m.qr.difference(right=m.roi, maxError=0.01)

        # Clip it to remove the region of interest
        m.average_distance = m.average_distance.clip(m.diff)

        # Apply dynamic world-masking if specified
        if m.mask != "All":
            classes = [
                "water",
                "trees",
                "grass",
                "flooded_vegetation",
                "crops",
                "shrub_and_scrub",
                "built",
                "bare",
                "snow_and_ice",
            ]

            # Get the mosaic dynamic world image
            landcover = geemap.dynamic_world(
                m.diff,
                m.start.isoformat(),
                m.end.isoformat(),
                return_type="class",
            ).select("label_mode")

            # Mask the image using the class of interest
            m.average_distance = m.average_distance.updateMask(
                landcover.eq(classes.index(m.mask))
            )

            # Mask the image using the class of interest
            m.feature_img = m.feature_img.updateMask(
                landcover.eq(classes.index(m.mask))
            )

        async_add_distance_map(m, m.qr)

    except Exception as e:
        message(m, f"Error: {e}.", False)
        message(map, f"Error: {e}.", True, 5)


def handle_interaction(m, **kwargs):
    """
    Handles user interactions with the map, such as clicking to select regions or display distances.

    Args:
        m (object): Map object containing various attributes and methods.
        **kwargs: Additional keyword arguments containing interaction details.
    """

    try:

        latlon = kwargs.get("coordinates")
        if kwargs.get("type") == "click":

            # Handle click events for displaying similarity percentages
            if type(m.distances) == ee.image.Image:
                p0, p1 = latlon[1], latlon[0]
                p = ee.Geometry(mapping(Point(p0, p1)))
                fs = m.distances.sample(p, 1).getInfo()["features"]
                click_distances = list(fs[0]["properties"].values())
                scale = 3
                percents = [
                    str(int(((scale - min(scale, e)) / scale) * 100))
                    for e in click_distances
                ]
                message(m, "% Similarity: " + ", ".join(percents), False)
                message(m, "% Similarity: " + ", ".join(percents), True)

    except Exception as e:
        message(m, f"Error: {e}.", False)
        message(m, f"Error: {e}.", True, 5)
