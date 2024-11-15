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
def export_single_image(job_dir, img, roi, resolution, m):
    """
    Export a single Earth Engine image to a local file.

    Args:
        job_dir (Path): Directory to save the exported image.
        img (ee.Image): Earth Engine image to export.
        roi (ee.Geometry): Region of interest to clip the image.
        resolution (float): Spatial resolution of the exported image in meters.
        m: Object containing message and URL information.
    """
    fp = job_dir / "image.tif"
    message(m, f"Exporting image...", False)
    geemap.ee_export_image(
        img.clip(roi),
        filename=fp,
        scale=resolution,
        region=roi,
        file_per_band=False,
    )
    # Compress the job directory using zip
    zip_path = compress_dir(job_dir, Path("../public/"))
    message(m, f"Exporting image...", True)
    message(m, f"Download link: {m.url}/static/public/{zip_path.name}.zip", False)
    message(
        m,
        f"Download link: {m.url}/static/public/{zip_path.name}.zip",
        True,
        duration=10,
    )


@task
def export_multiple_images(cells, job_dir, img, resolution, m):
    """
    Export multiple Earth Engine images to local files.

    Args:
        cells (list): List of Earth Engine geometries representing image cells.
        job_dir (Path): Directory to save the exported images.
        img (ee.Image): Earth Engine image to export.
        resolution (float): Spatial resolution of the exported images in meters.
        m: Object containing message, URL, and progress bar information.
    """
    for idx, cell in enumerate(cells):
        m.download_bar.value = idx + 1
        cell_fp = job_dir / f"image_{str(idx+1).zfill(2)}.tif"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                geemap.ee_export_image(
                    img.clip(cell),
                    filename=cell_fp,
                    scale=resolution,
                    region=cell,
                    file_per_band=False,
                )
        except Exception as ex:
            message(m, f"Error exporting cell {idx+1}: {ex}", False)
            message(m, f"Error exporting cell {idx+1}: {ex}", True, 5)

    # Compress the job directory using zip
    zip_path = compress_dir(job_dir, Path("../public/"))
    message(m, f"Download link: {m.url}/static/public/{zip_path.name}.zip", False)
    message(
        m,
        f"Download link: {m.url}/static/public/{zip_path.name}.zip",
        True,
        duration=10,
    )

    # Reset the progress bar
    m.download_bar.layout.visibility = "hidden"
    m.download_bar.layout.height = "0px"
    m.download_bar.value = m.download_bar.max = 0


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
        img = ee.Image.cat([features, result])

        # Set the image resolution in meters
        resolution = 100

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
            export_single_image(job_dir, img, m.qr, resolution, m)
            return

        # Split the geometry and export each cell
        cells = split_geometry(x_cells, y_cells)
        m.download_bar.max = len(cells)
        m.download_bar.layout.visibility = "visible"
        m.download_bar.layout.height = "--jp-widgets-inline-height"
        m.download_bar.description = f"{len(cells)} cells:"

        export_multiple_images(cells, job_dir, img, resolution, m)

    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)
