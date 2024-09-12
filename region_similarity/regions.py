# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains functions for handling reference region (ROI) and query region (QR) operations.

It provides functionality for setting regions through drawing on a map or uploading files,
and handles the visualization of these regions on the map.
"""

from pathlib import Path
from io import BytesIO
import ee
import tempfile
import zipfile
import geopandas as gpd
from shapely.geometry import shape, mapping
from region_similarity.helpers import message


def set_region_of_interest(e, m):
    """
    Sets the reference region (ROI) based on user-drawn polygons on the map.

    This function processes drawn polygons, converts them to a MultiPolygon geometry,
    sets the ROI as an Earth Engine object, and visualizes it on the map.

    Args:
        e (object): Event object (unused).
        m (object): Map object containing various attributes and methods.

    Returns:
        None

    Raises:
        Exception: If there's an error setting the search region.
    """

    try:

        if len(m.draw_control.data) == 0:
            message(m, "Please draw a reference region on the map.", False)
            message(m, "Please draw a reference region on the map.", True)
            return

        # Get all drawn geometries
        geoms = [
            e["geometry"]["coordinates"]
            for e in m.draw_control.data
            if e["geometry"]["type"] == "Polygon"
        ]

        # Convert to a multipolygon geometry with shapely
        roi_geom = shape({"type": "MultiPolygon", "coordinates": geoms})

        # Set the actual search region as a ee object
        m.roi = ee.Geometry(mapping(roi_geom))

        # Add the new ROI as a GeoDataFrame to the map
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[roi_geom], crs="EPSG:4326"),
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

        # Remove the drawn features
        m._draw_control._clear_draw_control()
        m.layers = tuple(e for e in m.layers if e.name != "Drawn Features")

        # Set the reference region flag to True
        m.roi_set = True

    except Exception as e:
        message(m, f"Error setting search region: {e}", False)
        message(m, f"Error setting search region: {e}", True, 5)


def handle_roi_upload_change(change, m):
    """
    Handles the change event for reference region (ROI) file uploads.

    This function processes uploaded files (shapefiles or other supported formats),
    sets the ROI based on the file content, and visualizes it on the map.

    Args:
        change (dict): Dictionary containing the change information.
        m (object): Map object containing various attributes and methods.

    Returns:
        None

    Raises:
        Exception: If there's an error setting the reference region.
    """
    try:
        # Get the uploaded file from the ROS upload button
        uploaded_file = m.roi_upload_button.value

        if uploaded_file:
            file_content = uploaded_file[0]["content"]
            file_name = uploaded_file[0]["name"]

            # Extract the files in a temporary directory and read the first *.shp file
            if file_name.endswith(".zip"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with zipfile.ZipFile(BytesIO(file_content), "r") as zip_ref:
                        zip_ref.extractall(tmpdir)
                        shp_files = [f for f in Path(tmpdir).rglob("*.shp")]
                        if shp_files:
                            gdf = gpd.read_file(shp_files[0])
            else:
                # Geopandas can infer the format based on the file extension
                gdf = gpd.read_file(BytesIO(file_content))

            m.roi = ee.Geometry(mapping(gdf.unary_union))

            # Add the new query region as a GeoDataFrame to the map
            m.add_gdf(
                gpd.GeoDataFrame(
                    geometry=gpd.GeoSeries([gdf.unary_union]), crs="EPSG:4326"
                ),
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

            # Set the reference region flag to True
            m.roi_set = True

    except Exception as e:
        message(m, f"Error setting reference region: {e}", False)
        message(m, f"Error setting reference region: {e}", True, 5)


def set_search_region(e, m):
    """
    Sets the search region (QR) based on user-drawn polygons on the map.

    This function processes drawn polygons, converts them to a MultiPolygon geometry,
    sets the QR as an Earth Engine object, and visualizes it on the map.

    Args:
        e (object): Event object (unused).
        m (object): Map object containing various attributes and methods.

    Returns:
        None

    Raises:
        Exception: If there's an error setting the search region.
    """

    try:

        if len(m.draw_control.data) == 0:
            message(m, "Please draw a reference region on the map.", False)
            message(m, "Please draw a reference region on the map.", True)
            return

        # Get all drawn geometries
        geoms = [
            e["geometry"]["coordinates"]
            for e in m.draw_control.data
            if e["geometry"]["type"] == "Polygon"
        ]

        # Convert to a multipolygon geometry with shapely
        search_geom = shape({"type": "MultiPolygon", "coordinates": geoms})

        # Set the actual search region as a ee object
        m.qr = ee.Geometry(mapping(search_geom))

        # Add the new ROI as a GeoDataFrame to the map
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[search_geom], crs="EPSG:4326"),
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

        # Remove the drawn features
        m._draw_control._clear_draw_control()
        m.layers = tuple(e for e in m.layers if e.name != "Drawn Features")

        # Set the query region flag to True
        m.qr_set = True

    except Exception as e:
        message(m, f"Error setting search region: {e}", False)
        message(m, f"Error setting search region: {e}", True, 5)


def handle_upload_change(change, m):
    """
    Handles the change event for region of search (ROS) file uploads.

    This function processes uploaded files (shapefiles or other supported formats),
    sets the QR based on the file content, and visualizes it on the map.

    Args:
        change (dict): Dictionary containing the change information.
        m (object): Map object containing various attributes and methods.

    Returns:
        None

    Raises:
        Exception: If there's an error setting the search region.
    """
    try:
        # Get the uploaded file from the ROS upload button
        uploaded_file = m.ros_upload_button.value

        if uploaded_file:
            file_content = uploaded_file[0]["content"]
            file_name = uploaded_file[0]["name"]

            # Extract the files in a temporary directory and read the first *.shp file
            if file_name.endswith(".zip"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with zipfile.ZipFile(BytesIO(file_content), "r") as zip_ref:
                        zip_ref.extractall(tmpdir)
                        shp_files = [f for f in Path(tmpdir).rglob("*.shp")]
                        if shp_files:
                            gdf = gpd.read_file(shp_files[0])
            else:
                # Geopandas can infer the format based on the file extension
                gdf = gpd.read_file(BytesIO(file_content))

            m.qr = ee.Geometry(mapping(gdf.unary_union))

            # Add the new query region as a GeoDataFrame to the map
            m.add_gdf(
                gpd.GeoDataFrame(
                    geometry=gpd.GeoSeries([gdf.unary_union]), crs="EPSG:4326"
                ),
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

            # Set the query region flag to True
            m.qr_set = True

    except Exception as e:
        message(m, f"Error setting search region: {e}", False)
        message(m, f"Error setting search region: {e}", True, 5)
