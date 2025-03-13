# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module provides functionality for exporting clusters, similarity, and feature map images.
It includes utilities for compressing directories, generating file names,
and exporting single or multiple images based on user-defined regions of interest.
"""

import hashlib
import random
import string
import shutil
import contextlib
import io
from pathlib import Path
import ee
import geemap
from shapely.geometry import box, Polygon
from region_similarity.helpers import message
from solara.lab import task


def compress_dir(dir_path, target_dir, delete=True):
    """
    Compress a directory into a zip file.

    Args:
        dir_path (Path): Path to the directory to be compressed.
        target_dir (Path): Path to the directory where the zip file will be saved.
        delete (bool, optional): Whether to delete the original directory after compression. Defaults to True.

    Returns:
        Path: Path to the created zip file.
    """
    zip_path = target_dir / dir_path.name
    shutil.make_archive(zip_path, "zip", dir_path)
    if delete:
        shutil.rmtree(dir_path)
    return zip_path


def generate_random_hash(length=16):
    """
    Generate a random hash string.

    Args:
        length (int, optional): Length of the random string to generate. Defaults to 16.

    Returns:
        str: A random hash string.
    """
    random_string = "".join(
        random.choices(string.ascii_letters + string.digits, k=length)
    )
    hash_object = hashlib.sha256(random_string.encode())
    random_hash = hash_object.hexdigest()
    return random_hash


@task
def export_single_image(img, roi, resolution, m):
    """
    Export a single Earth Engine image to a download URL.

    Args:
        img (ee.Image): Earth Engine image to export.
        roi (ee.Geometry): Region of interest to clip and export the image.
        resolution (float): Spatial resolution of the exported image in meters.
        m: Object containing message and URL information for status updates.

    The function attempts to generate a download URL for the image and displays
    status messages through the provided messaging object. If successful, it shows
    the download URL. If an error occurs, it displays the error message.
    """
    message(m, f"Generating download URL...", False)

    try:
        url = img.getDownloadURL(
            {
                "scale": resolution,
                "region": roi,
                "format": "GEO_TIFF",
                "filePerBand": False,
            }
        )

        message(m, f"Generating download URL...", True)
        message(m, f"Download link: {url}", False)
        message(m, f"Download link: {url}", True, duration=10)

    except Exception as e:
        message(m, f"Error generating download URL: {e}", False)
        message(m, f"Error generating download URL: {e}", True, duration=5)


@task
def export_multiple_images(cells, job_dir, img, resolution, m):
    """
    Export multiple Earth Engine images to download URLs.

    Args:
        cells (list): List of Earth Engine geometries representing image cells.
        job_dir (Path): Directory to save the exported images (unused).
        img (ee.Image): Earth Engine image to export.
        resolution (float): Spatial resolution of the exported images in meters.
        m: Object containing message, URL, and progress bar information.
    """
    message(m, f"Generating download URLs...", False)
    urls = []
    for idx, cell in enumerate(cells):
        try:
            urls.append(
                img.clip(cell).getDownloadURL(
                    {
                        "scale": resolution,
                        "region": cell,
                        "format": "GEO_TIFF",
                        "filePerBand": False,
                    }
                )
            )
        except Exception as ex:
            message(m, f"Error generating URL for cell {idx+1}: {ex}", False)
            message(m, f"Error generating URL for cell {idx+1}: {ex}", True, 5)

    # Save URLs to a file
    random_hash = generate_random_hash()
    url_file = Path("./public") / f"urls_{random_hash}.txt"
    url_file.parent.mkdir(exist_ok=True)
    url_file.write_text("\n".join(urls))

    # Share the URL file location
    message(m, f"Generating download URLs...", True)
    message(
        m,
        f"Download URLs available at: {m.url}/static/public/urls_{random_hash}.txt",
        False,
    )
    message(
        m,
        f"Download URLs available at: {m.url}/static/public/urls_{random_hash}.txt",
        True,
        duration=10,
    )


def export_image(e, m):
    """
    Export an image from Google Earth Engine to a local directory.

    This function handles the entire export process, including:
    - Setting up the download directory
    - Generating a unique job identifier
    - Preparing the Earth Engine image
    - Splitting the region of interest into cells if necessary
    - Exporting single or multiple images based on the region size

    Args:
        e: Earth Engine object.
        m: Map object containing user inputs and map elements.

    Returns:
        None
    """

    try:

        # Set the downloads directory
        tmp = Path.home() / "tmp"
        tmp.mkdir(exist_ok=True)

        # Generate a random hash text for the job using hashlib
        job_dir = tmp / generate_random_hash()
        job_dir.mkdir(exist_ok=True)

        # Get the image based on the mode (clustering vs searching)
        result = m.clustered if m.cluster else m.distances

        # Get the features
        features = m.feature_img

        # Stack the features and the result
        img = ee.Image.cat([features, result]).reproject(crs='EPSG:4326', scale=1000)

        # Set the image resolution in meters
        resolution = 1000

        # Convert the image resolution from meters to degrees
        meters_per_degree = 111320  # Approximation at the equator
        cell_size = 1000 * resolution / meters_per_degree

        # Get the bounding box of the ROI
        coords = m.qr.bounds().getInfo()["coordinates"][0]
        x_coords = [coord[0] for coord in coords]
        y_coords = [coord[1] for coord in coords]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # Create a shapely polygon from `x_coords` and `y_coords`
        qr_geom = Polygon(zip(x_coords, y_coords))

        # Calculate the number of cells needed
        x_cells = int((x_max - x_min) / cell_size) + 1
        y_cells = int((y_max - y_min) / cell_size) + 1

        def split_geometry(x_cells, y_cells):
            cells = []
            for i in range(x_cells):
                for j in range(y_cells):

                    # if the cell does not intersect the ROI, continue
                    if not box(
                        x_min + i * cell_size,
                        y_min + j * cell_size,
                        x_min + (i + 1) * cell_size,
                        y_min + (j + 1) * cell_size,
                    ).intersects(qr_geom):
                        continue

                    # Convert the shapely rectangle to an Earth Engine geometry
                    cell = ee.Geometry.Rectangle(
                        [
                            x_min + i * cell_size,
                            y_min + j * cell_size,
                            x_min + (i + 1) * cell_size,
                            y_min + (j + 1) * cell_size,
                        ]
                    )
                    cells.append(cell)
            return cells

        # Export the image directly if only one cell is needed
        if x_cells <= 1 and y_cells <= 1:
            export_single_image(img, m.qr, resolution, m)
            return

        # Split the geometry and export each cell
        cells = split_geometry(x_cells, y_cells)
        export_multiple_images(cells, job_dir, img, resolution, m)

    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)
