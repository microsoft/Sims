# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains functions for importing and exporting use case spec files for either similarity search or clustering analysis.
It provides functionality to load and save use case configurations, including regions, aliases, features, and other parameters.
"""

from datetime import datetime, date
import uuid
import yaml
from pathlib import Path
import geopandas as gpd
from solara.lab import task
import ee
from shapely.geometry import shape, mapping
from region_similarity.variables import add_alias
from region_similarity.features import add_feature
from region_similarity.helpers import message


@task
def import_spec(m, spec_data):
    """
    Import and process use case information for region similarity analysis.

    This function takes a specification in dictionary format and sets up the analysis parameters,
    including task type, regions, aliases, features, and other settings.

    Args:
        m: The map object to update with the imported specification.
        spec_data (dict): The specification data containing task details, regions, aliases, and features.

    Returns:
        None. Updates the map object and displays messages about the import process.
    """
    # Check for required fields
    if (
        "task" not in spec_data
        or "aliases" not in spec_data
        or not spec_data["aliases"]
    ):
        message(
            m,
            "Error: 'task' and at least one 'alias' are required in the spec file.",
            False,
        )
        message(
            m,
            "Error: 'task' and at least one 'alias' are required in the spec file.",
            True,
        )
        return

    task = spec_data["task"]
    regions = spec_data.get("regions", {})
    aliases = spec_data["aliases"]
    features = spec_data.get("features", [])
    distance = spec_data.get("distance")
    land_cover = spec_data.get("land_cover")

    # Handle regions
    query_region = regions.get("query_region")
    if not query_region:
        if not m.qr:
            message(m, "Error: No query region provided in spec or set on map.", False)
            message(m, "Error: No query region provided in spec or set on map.", True)
            return
        query_region = m.qr.coordinates().getInfo()[0]

    if task == "search":
        reference_region = regions.get("reference_region")
        if not reference_region:
            if not m.roi:
                message(
                    m,
                    "Error: No reference region provided in spec or set on map for search task.",
                    False,
                )
                message(
                    m,
                    "Error: No reference region provided in spec or set on map for search task.",
                    True,
                )
                return
            reference_region = m.roi

    # Set default period
    default_start = m.start_date.value
    default_end = m.end_date.value
    default_period = (
        None
        if default_start == date(2000, 1, 1) and default_end == date(2000, 1, 1)
        else (default_start, default_end)
    )

    # Process aliases
    processed_aliases = []
    for alias in aliases:
        alias_parts = alias.split(":")
        if len(alias_parts) != 6:
            message(m, f"Error: Invalid alias format: {alias}", False)
            message(m, f"Error: Invalid alias format: {alias}", True)
            return

        alias_name, product, layer, start, end, agg = alias_parts

        if not product or not layer or not agg:
            message(m, f"Error: Incomplete alias specification for {alias_name}", False)
            message(m, f"Error: Incomplete alias specification for {alias_name}", True)
            return

        if not start or not end:
            if default_period is None:
                message(
                    m,
                    f"Error: Missing period for alias {alias_name} and no default period set.",
                    False,
                )
                message(
                    m,
                    f"Error: Missing period for alias {alias_name} and no default period set.",
                    True,
                )
                return
            start, end = default_period
        else:
            start = datetime.strptime(start, "%d/%m/%Y").date()
            end = datetime.strptime(end, "%d/%m/%Y").date()

        processed_aliases.append((alias_name, product, layer, start, end, agg))

    # Set task-specific parameters
    if task == "cluster":
        m.cluster_checkbox.value = True
        m.num_clusters.disabled = False
        m.num_clusters.value = regions.get("number_of_clusters", 5)
    else:
        m.cluster_checkbox.value = False
        m.num_clusters.disabled = True

    # Set regions
    if query_region:
        query_geom = shape({"type": "Polygon", "coordinates": [query_region]})
        m.qr = ee.Geometry(mapping(query_geom))
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[query_geom], crs="EPSG:4326"),
            "Query Region",
            style={
                "color": "red",
                "fillColor": "#ff0000",
                "fillOpacity": 0.01,
                "weight": 3,
            },
            hover_style={"fillColor": "#ff0000", "fillOpacity": 0},
            info_mode=None,
            zoom_to_layer=False,
        )
        m.qr_set = True

    if task == "search" and reference_region:
        reference_geom = shape({"type": "Polygon", "coordinates": [reference_region]})
        m.roi = ee.Geometry(mapping(reference_geom))
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[reference_geom], crs="EPSG:4326"),
            "Reference Region",
            style={
                "color": "green",
                "fillColor": "#ff0000",
                "fillOpacity": 0.01,
                "weight": 3,
            },
            hover_style={"fillColor": "#ff0000", "fillOpacity": 0},
            info_mode=None,
            zoom_to_layer=False,
        )
        m.roi_set = True

    # Add aliases
    for i, (alias_name, product, layer, start, end, agg) in enumerate(
        processed_aliases
    ):
        if i == len(processed_aliases) - 1:
            add_alias(
                None, m, alias_name, product, layer, start, end, agg, list_aliases=True
            )
        else:
            add_alias(None, m, alias_name, product, layer, start, end, agg)

    # Add features
    for feature in features:
        name, expression = feature.split(":")
        if expression:
            add_feature(None, m, f"{name}:{expression}")

    # Set optional parameters
    if distance:
        m.distance_dropdown.value = distance
    if land_cover:
        m.mask_dropdown.value = land_cover

    message(m, "Specification loaded successfully.", False)
    message(m, "Specification loaded successfully.", True)


def export_spec(e, m):
    """
    Export the current region similarity analysis configuration to a YAML file.

    This function collects the current configuration, including aliases, features, regions,
    and other parameters, and saves them to a YAML file in the public directory.

    Args:
        e: The event object (unused in this function).
        m: The map object containing the current analysis configuration.

    Returns:
        None. Generates a YAML file and displays a download link message.
    """
    # Generate aliases
    aliases = list()
    for alias_name, (dataset, layer, agg_fun, start, end, _) in m.aliases.items():
        start = (
            datetime.strptime(start, "%Y-%m-%d").date()
            if isinstance(start, str)
            else start
        )
        end = datetime.strptime(end, "%Y-%m-%d").date() if isinstance(end, str) else end
        alias_str = f"{alias_name}:{dataset}:{layer}:{start.strftime('%d/%m/%Y')}:{end.strftime('%d/%m/%Y')}:{agg_fun}"
        aliases.append(alias_str)

    # If there are no aliases, stop
    if not aliases:
        message(m, "No aliases found. Please add at least one alias.", False)
        message(m, "No aliases found. Please add at least one alias.", True)
        return

    # Generate features
    features = list()
    for name, (expression, _) in m.features.items():
        features.append(f"{name}:{expression}")

    # Get geometries
    query_region = m.qr.coordinates().getInfo()[0] if m.qr else []
    reference_region = m.roi.coordinates().getInfo()[0] if m.roi else []

    # If there is no query region, return
    if not query_region:
        message(m, "No query region found. Please set the query region.", False)
        message(m, "No query region found. Please set the query region.", True)
        return

    # Determine task
    task = "cluster" if m.cluster else "search"

    # Construct spec data
    spec_data = {
        "aliases": aliases,
        "features": features,
        "land_cover": m.mask_dropdown.value,
        "distance": m.distance_dropdown.value,
        "regions": {
            "number_of_clusters": m.num_clusters.value,
            "query_region": query_region,
            "reference_region": reference_region,
        },
        "task": task,
    }

    # Generate a random hash for the filename
    filename = f"{str(uuid.uuid4())}.yaml"

    # Save the file in the public directory
    public_dir = Path("../public")
    public_dir.mkdir(exist_ok=True)
    file_path = public_dir / filename

    # Convert to YAML and save
    with open(file_path, "w") as file:
        yaml.dump(spec_data, file)

    # Generate download link
    download_link = f"{m.url}/static/public/{filename}"

    message(m, f"Download link: {download_link}", False)
    message(m, f"Download link: {download_link}", True, duration=5)
