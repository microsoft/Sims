# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Main application for the Similarity Search Tool.

This script creates the main Map objects and adds custom GUI widgets to it to enable similarity search and clustering use cases.
"""

import os
import yaml
from datetime import date
from dotenv import load_dotenv

load_dotenv()

import ee
import geemap
import geemap.toolbar
from geemap.toolbar import map_widgets
from geemap.common import search_ee_data, geocode
import ipywidgets as widgets
from ipyleaflet import WidgetControl
import solara
from IPython.core.display import display

from region_similarity.map import (
    reset_map,
    update_mask_dropdown,
    update_distance_dropdown,
    handle_clustering_change,
)
from region_similarity.regions import (
    handle_upload_change,
    set_search_region,
    set_region_of_interest,
    handle_roi_upload_change,
)
from region_similarity.periods import update_end_date, update_start_date
from region_similarity.features import add_feature
from region_similarity.variables import add_alias, update_custom_product
from region_similarity.search import execute, handle_interaction
from region_similarity.export import export_image
from region_similarity.helpers import message, update_map
from region_similarity.use_cases import import_spec, export_spec

# Define host
hostname = os.environ.get("HOST")

# Get authentication credentials
google_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

# Authenticate to Earth Engine using GCP project-based authentication
if not google_credentials:
    raise ValueError(
        "GCP project-based authentication requires both GOOGLE_APPLICATION_CREDENTIALS environment variables to be set"
    )

try:
    credentials = ee.ServiceAccountCredentials("", google_credentials)
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
except Exception as e:
    raise Exception(f"Failed to authenticate with GCP project credentials: {str(e)}")


def ee_data_html(asset):
    """
    Generates HTML from an asset to be used in the HTML widget.

    Args:
        asset (dict): A dictionary containing an Earth Engine asset.

    Returns:
        str: A string containing HTML.
    """
    try:
        asset_title = asset.get("title", "Unknown")
        asset_dates = asset.get("dates", "Unknown")
        ee_id_snippet = asset.get("id", "Unknown")
        asset_uid = asset.get("uid", None)
        asset_url = asset.get("asset_url", "")
        code_url = asset.get("sample_code", None)
        thumbnail_url = asset.get("thumbnail_url", None)

        if not code_url and asset_uid:
            coder_url = f"""https://code.earthengine.google.com/?scriptPath=Examples%3ADatasets%2F{asset_uid}"""
        else:
            coder_url = code_url

        ## ee datasets always have a asset_url, and should have a thumbnail
        catalog = (
            bool(asset_url)
            * f"""
                    <h4>Data Catalog</h4>
                        <p style="margin-left: 40px; margin-bottom: 0px !important;"><a href="{asset_url.replace('terms-of-use','description')}" target="_blank">Description</a></p>
                        <p style="margin-left: 40px; margin-bottom: 0px !important;"><a href="{asset_url.replace('terms-of-use','bands')}" target="_blank">Bands</a></p>
                        <p style="margin-left: 40px; margin-bottom: 0px !important;"><a href="{asset_url.replace('terms-of-use','image-properties')}" target="_blank">Properties</a></p>
                        <p style="margin-left: 40px"><a href="{coder_url}" target="_blank">Example</a></p>
                    """
        )
        thumbnail = (
            bool(thumbnail_url)
            * f"""
                    <h4>Dataset Thumbnail</h4>
                    <img src="{thumbnail_url}">
                    """
        )
        ## only community datasets have a code_url
        alternative = (
            bool(code_url)
            * f"""
                    <h4>Community Catalog</h4>
                        <p style="margin-left: 40px; margin-bottom: 0px !important;">{asset.get('provider','Provider unknown')}</p>
                        <p style="margin-left: 40px; margin-bottom: 0px !important;">{asset.get('tags','Tags unknown')}</p>
                        <p style="margin-left: 40px; margin-bottom: 0px !important;"><a href="{coder_url}" target="_blank">Example</a></p>
                    """
        )

        template = f"""
            <html>
            <body>
                <h3>{asset_title}</h3>
                <h4>Dataset Availability</h4>
                    <p style="margin-left: 40px">{asset_dates}</p>
                <h4>Earth Engine Identifier</h4>
                    <p style="margin-left: 40px">{ee_id_snippet}</p>
                {catalog}
                {alternative}
                {thumbnail}
            </body>
            </html>
        """
        return template

    except Exception as e:
        print(e)


@map_widgets.Theme.apply
class SearchGEEDataGUI(widgets.VBox):
    """
    Custom GUI component for location and data search in GEE.

    This class extends the VBox widget to provide a user interface for searching
    both geographical locations and Earth Engine datasets.
    """

    def __init__(self, m, **kwargs):
        """
        Initialize the SearchGEEDataGUI.

        Args:
            m: The map object to which this GUI is attached.
            **kwargs: Additional keyword arguments for the VBox.
        """
        # Initialize for both location and data search
        m.search_datasets = None
        m.search_loc_marker = None
        m.search_loc_geom = None

        # Location Search Header (similar to Data Catalog header)
        location_header = widgets.HTML(
            value="""
            <h3 style="font-family: Arial, sans-serif; color: var(--jp-ui-font-color1); 
                    padding: 3px 12px; font-weight: bold; background-color: #f7f7f7; 
                    border-radius: 5px; border: 1px solid #ddd; box-shadow: 1px 1px 3px rgba(0,0,0,0.1);">
                Location Search
            </h3>
        """
        )

        # Search location box
        search_location_box = widgets.Text(
            placeholder="Search by place name or address",
            tooltip="Search location",
            layout=widgets.Layout(width="400px"),
        )

        def search_location_callback(text):
            if text.value != "":
                g = geocode(text.value)
                if g:
                    # If a location is found, center the map and zoom in
                    latlon = (g[0].lat, g[0].lng)
                    m.search_loc_geom = ee.Geometry.Point(g[0].lng, g[0].lat)
                    m.center = latlon
                    m.zoom = 12
                    text.value = ""
                else:
                    # If no location was found, send a message to the user
                    message(m, text="No location found. Please try again.", clear=False)
                    message(
                        m,
                        text="No location found. Please try again.",
                        clear=True,
                        duration=1,
                    )

        search_location_box.on_submit(search_location_callback)

        # Search data catalog box
        search_data_box = widgets.Text(
            placeholder="Search data catalog by keywords, e.g., `elevation`",
            tooltip="Search data",
            layout=widgets.Layout(width="400px"),
        )

        search_data_output = widgets.Output(
            layout={
                "max_width": "400px",
                "max_height": "350px",
                "overflow": "scroll",
            }
        )

        assets_dropdown = widgets.Dropdown(
            options=[], layout=widgets.Layout(min_width="350px", max_width="350px")
        )

        import_btn = widgets.Button(
            description="import",
            button_style="primary",
            tooltip="Click to import the selected asset",
            layout=widgets.Layout(min_width="60px", max_width="60px"),
        )

        def import_btn_clicked(b):
            if assets_dropdown.value is not None:
                datasets = m.search_datasets
                dataset = datasets[assets_dropdown.index]
                id_ = dataset["id"]
                m.accordion.selected_index = 2
                m.custom_product_input.value = id_
                search_data_output.clear_output()
                search_data_box.value = ""

        import_btn.on_click(import_btn_clicked)

        html_widget = widgets.HTML()

        def dropdown_change(change):
            dropdown_index = assets_dropdown.index
            if dropdown_index is not None and dropdown_index >= 0:
                search_data_output.append_stdout("Loading ...")
                datasets = m.search_datasets
                dataset = datasets[dropdown_index]
                dataset_html = ee_data_html(dataset)  # Assuming ee_data_html is defined
                html_widget.value = dataset_html
                with search_data_output:
                    search_data_output.clear_output()
                    display(html_widget)

        assets_dropdown.observe(dropdown_change, names="value")

        def search_data_callback(text):
            if text.value != "":
                with search_data_output:
                    print("Searching data catalog ...")
                m.default_style = {"cursor": "wait"}
                ee_assets = search_ee_data(
                    text.value, source="all"
                )  # Assuming search_ee_data is defined
                m.search_datasets = ee_assets
                asset_titles = [x["title"] for x in ee_assets]
                assets_dropdown.options = asset_titles
                if len(ee_assets) > 0:
                    assets_dropdown.index = 0
                    html_widget.value = ee_data_html(
                        ee_assets[0]
                    )  # Assuming ee_data_html is defined
                else:
                    html_widget.value = "No results found."
                with search_data_output:
                    search_data_output.clear_output()
                    display(html_widget)
                m.default_style = {"cursor": "default"}
            else:
                search_data_output.clear_output()
                assets_dropdown.options = []

        search_data_box.on_submit(search_data_callback)
        assets_combo = widgets.HBox([import_btn, assets_dropdown])

        # Data Catalog Header
        data_header = widgets.HTML(
            value="""
            <h3 style="font-family: Arial, sans-serif; color: var(--jp-ui-font-color1); 
                    padding: 3px 12px; font-weight: bold; background-color: #f7f7f7; 
                    border-radius: 5px; border: 1px solid #ddd; box-shadow: 1px 1px 3px rgba(0,0,0,0.1);">
                Data Catalog
            </h3>
        """
        )

        # Stack the search location and search data catalog widgets
        location_search = widgets.VBox([location_header, search_location_box])
        data_search = widgets.VBox(
            [data_header, search_data_box, assets_combo, search_data_output]
        )

        # Combine both searches into the parent VBox
        super().__init__(children=[location_search, data_search], **kwargs)


geemap.toolbar.SearchDataGUI = SearchGEEDataGUI


class Map(geemap.Map):
    """
    Custom Map class for the Similarity Search Tool.

    This class extends geemap.Map to include additional functionality specific
    to the Similarity Search Tool, such as custom widgets and controls.
    """

    def __init__(self, **kwargs):
        """
        Initialize the Map object.

        Args:
            **kwargs: Additional keyword arguments for geemap.Map.
        """
        super().__init__(**kwargs)
        self.initialize_map()
        self.create_widgets()
        self.add_controls()
        self.add_layers()
        self.initialize_interaction()

    def initialize_map(self):
        """Initialize map properties and clear existing layers."""
        self.url = hostname
        self.clear_layers()
        self.qr_set = False
        self.roi_set = False
        self.distances = None
        self.start = date(2000, 1, 1)
        self.end = date(2000, 1, 1)
        self.aliases = dict()
        self.features = dict()
        self.mask = "All"
        self.distance_fun = "Euclidean"
        self.cluster = False
        self.roi = None
        self.qr = None

    def create_widgets(self):
        """Create and configure all widgets used in the map interface."""

        self.output_widget = widgets.Output(layout={"border": "1px solid black"})
        self.reset_button = widgets.Button(
            description="Reset Map",
            layout=widgets.Layout(width="100%", height="30px"),
            tooltip="Clear the map and start a new analysis session.",
        )
        self.reset_button.on_click(lambda event: reset_map(event, self))

        self.spec_export_button = widgets.Button(
            description="Export Session",
            tooltip="Download the current specifications as a YAML file.",
            layout=widgets.Layout(width="100%", height="30px"),
        )

        self.spec_export_button.on_click(lambda event: export_spec(event, self))

        self.spec_import_button = widgets.FileUpload(
            description="Import Session",
            accept=".yaml",
            multiple=False,
            tooltip="Upload a specification YAML file to preload parameters.",
            layout=widgets.Layout(width="100%", height="30px"),
        )

        def handle_spec_upload(change):
            if not change["new"]:
                return
            content = change["new"][0]["content"]
            try:
                spec_data = yaml.safe_load(content.decode("utf-8"))
                import_spec(self, spec_data)
            except yaml.YAMLError as e:
                message(self, f"Error parsing YAML file: {str(e)}", False)
                message(self, f"Error parsing YAML file: {str(e)}", True)
            except Exception as e:
                message(self, f"Error importing specification: {str(e)}", False)
                message(self, f"Error importing specification: {str(e)}", True)

        self.spec_import_button.observe(handle_spec_upload, names="value")

        self.set_region_button = widgets.Button(
            description="Use Drawn Shapes",
            layout=widgets.Layout(height="30px"),
            tooltip="Click on the map to select a search region. Once done, click here.",
        )
        self.set_region_button.on_click(lambda event: set_search_region(event, self))
        self.ros_upload_button = widgets.FileUpload(
            description="Upload",
            accept=".geojson,.gpkg,.zip",
            multiple=False,
            tooltip="Upload a GeoJSON, GPKG, or a Shapefile (zipped).",
            layout=widgets.Layout(height="30px", width="27%"),
        )
        self.ros_upload_button.observe(
            lambda event: handle_upload_change(event, self), names="value"
        )

        self.cluster_checkbox = widgets.Checkbox(
            description="Cluster Search Region?",
            value=False,
            indent=False,
            layout=widgets.Layout(width="50%"),
            tooltip="When checked, the search region will be clustered into groups of similar pixels.",
        )
        self.cluster_checkbox.observe(
            lambda event: handle_clustering_change(event, self), names="value"
        )
        self.num_clusters = widgets.BoundedIntText(
            value=3,
            min=2,
            max=20,
            step=1,
            description="Number:",
            disabled=True,
            layout=widgets.Layout(width="50%"),
            tooltip="Number of clusters to create in the search region.",
        )

        self.set_roi_button = widgets.Button(
            description="Use Drawn Shapes",
            layout=widgets.Layout(height="30px"),
            tooltip="Use the 'Draw Polygon' tool on the left to draw before clicking here.",
        )
        self.set_roi_button.on_click(lambda event: set_region_of_interest(event, self))
        self.roi_upload_button = widgets.FileUpload(
            description="Upload",
            accept=".geojson,.gpkg,.zip",
            multiple=False,
            tooltip="Upload a GeoJSON, GPKG, or a Shapefile (zipped).",
            layout=widgets.Layout(height="30px", width="27%"),
        )
        self.roi_upload_button.observe(
            lambda event: handle_roi_upload_change(event, self), names="value"
        )
        self.start_date = widgets.DatePicker(
            description="Start Date:",
            value=date(2000, 1, 1),
            tooltip="Start date for the period of interest.",
        )
        self.start_date.observe(
            lambda event: update_start_date(event, self), names="value"
        )
        self.end_date = widgets.DatePicker(
            description="End Date:",
            value=date(2000, 1, 1),
            tooltip="End date for the period of interest.",
        )
        self.end_date.observe(lambda event: update_end_date(event, self), names="value")
        self.custom_product_input = widgets.Text(
            description="Data ID:",
            placeholder="e.g. `COPERNICUS/S2_SR_HARMONIZED`",
            tooltip="Identifier of the Google Earth Engine dataset to use (search in the top left).",
        )
        self.custom_product_input.observe(
            lambda event: update_custom_product(event, self), names="value"
        )
        self.band_dropdown = widgets.Dropdown(
            description="Band:",
            placeholder="B4",
        )
        self.agg_fun_dropdown = widgets.Dropdown(
            options=["LAST", "FIRST", "MAX", "MIN", "MEAN", "MEDIAN", "SUM", "MODE"],
            description="Aggregation:",
            tooltip="Select the aggregation function to apply to the data.",
        )
        self.layer_alias_input = widgets.Text(
            description="Alias:",
            tooltip="Enter a name for the variable.",
            placeholder="e.g. `red`",
        )
        self.add_button = widgets.Button(
            description="Create Alias",
            layout=widgets.Layout(width="100%"),
            tooltip="Add the selected variable to the list of aliases.",
        )
        self.added_variables_output = widgets.Output(
            layout=widgets.Layout(width="100%")
        )
        self.add_button.on_click(
            lambda event: add_alias(event, self, list_aliases=True)
        )
        self.udf = widgets.Text(
            description="Expression:",
            tooltip="Enter a custom expression to apply.",
            placeholder="e.g. `ndvi:(b8-b4)/(b8+b4)`",
        )
        self.add_feature = widgets.Button(
            description="Add Feature!",
            layout=widgets.Layout(width="100%"),
            tooltip="Add the custom feature to the list of features.",
        )
        self.added_features_output = widgets.Output(layout=widgets.Layout(width="100%"))
        self.add_feature.on_click(lambda event: add_feature(event, self))
        self.mask_dropdown = widgets.Dropdown(
            options=[
                "All",
                "water",
                "trees",
                "grass",
                "flooded_vegetation",
                "crops",
                "shrub_and_scrub",
                "built",
                "bare",
                "snow_and_ice",
            ],
            description="Land cover:",
            tooltip="Select the land cover mask to apply to the data.",
        )
        self.mask_dropdown.observe(
            lambda event: update_mask_dropdown(event, self), names="value"
        )
        self.max_value_slider = widgets.FloatSlider(
            value=3.3,
            min=0.33,
            max=3.3,
            step=0.01,
            description="Threshold:",
            continuous_update=False,
            tooltip="Set the threshold value for the similarity map.",
        )
        self.max_value_slider.observe(
            lambda event: update_map(event, self), names="value"
        )
        self.distance_dropdown = widgets.Dropdown(
            options=["Euclidean", "Manhattan", "Cosine"],
            description="Distance:",
            tooltip="Distance function to use for similarity search or clustering.",
        )
        self.distance_dropdown.observe(
            lambda event: update_distance_dropdown(event, self), names="value"
        )
        self.search_button = widgets.Button(
            description="Search!",
            layout=widgets.Layout(width="100%", height="40px"),
            tooltip="Generate the results map.",
        )
        self.search_button.style.font_weight = "bold"
        self.search_button.style.font_size = "16px"
        self.search_button.on_click(lambda event: execute(event, self))
        self.export_button = widgets.Button(
            description="Download",
            layout=widgets.Layout(width="100%"),
            tooltip="Download the generated map and features.",
        )
        self.export_button.on_click(lambda event: export_image(event, self))

        # Accordion Sections
        set_periods = widgets.VBox([self.start_date, self.end_date])
        set_regions = widgets.VBox(
            [
                widgets.HBox(
                    [
                        widgets.HTML("Search Region:"),
                        self.ros_upload_button,
                        self.set_region_button,
                    ]
                ),
                widgets.HBox([self.cluster_checkbox, self.num_clusters]),
                widgets.HBox(
                    [
                        widgets.HTML("Control Region:"),
                        self.roi_upload_button,
                        self.set_roi_button,
                    ]
                ),
            ]
        )
        set_aliases = widgets.VBox(
            [
                self.custom_product_input,
                self.band_dropdown,
                self.agg_fun_dropdown,
                self.layer_alias_input,
                self.add_button,
                self.added_variables_output,
            ]
        )
        set_features = widgets.VBox(
            [self.udf, self.add_feature, self.added_features_output]
        )
        optional = widgets.VBox([self.mask_dropdown, self.distance_dropdown])

        self.accordion = widgets.Accordion(
            children=[
                set_regions,
                set_periods,
                set_aliases,
                set_features,
                optional,
            ]
        )
        self.accordion.set_title(0, "Step 1: Set Regions")
        self.accordion.set_title(1, "Step 2: Set Period")
        self.accordion.set_title(2, "Set Variables")
        self.accordion.set_title(3, "Set Features")
        self.accordion.set_title(4, "Optional")
        self.accordion.selected_index = 0

        # Close the layers
        toggle_button = self.controls[3].widget.children[0].children[0]
        toggle_button.value = not toggle_button.value

    def add_controls(self):
        """Add control widgets to the map."""

        self.output_control = WidgetControl(
            widget=self.output_widget, position="bottomleft"
        )
        self.add_control(self.output_control)

        controls_vbox = widgets.VBox(
            [
                self.accordion,
                self.search_button,
                self.max_value_slider,
                self.export_button,
                self.reset_button,
                self.spec_export_button,
                self.spec_import_button,
            ],
            layout=widgets.Layout(padding="10px"),
        )

        self.controls_control = WidgetControl(widget=controls_vbox, position="topright")
        self.add_control(self.controls_control)

        # Add branding information
        branding_html = widgets.HTML(
            value="""
            <div class="ctl" style="padding: 2px 10px 2px 10px;
            background: rgba(255, 255, 255, 0.9);
            box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            text-align: center;">
                <div class="title">Similarity Search Tool</div>
                <h3> CGIAR • Microsoft AI4G</h3>
                <div>
                    Backend: <a href="https://earthengine.google.com/" target="_blank">GEE</a>.
                </div>
            </div>
            """,
            layout=widgets.Layout(width="250px"),
        )
        self.branding_control = WidgetControl(widget=branding_html, position="topright")
        self.add_control(self.branding_control)

    def add_layers(self):
        """Add base map layers to the map."""
        self.add_basemap("OpenStreetMap")

    def initialize_interaction(self):
        """Set up map interaction handling."""
        self.on_interaction(lambda **kwargs: handle_interaction(self, **kwargs))


@solara.component
def Page():
    """
    Main component for rendering the Similarity Search Tool page.

    This function sets up the layout and includes the Map component along with
    necessary CSS styling.
    """

    # Added CSS
    css = widgets.HTML(
        """
    <style>
        .leaflet-container {
            font-size: 0.85rem !important;
        }
        .lm-Widget.p-Widget.jupyter-widgets.widget-inline-hbox.widget-checkbox {
            height: 23px !important;
        }
        .leaflet-left.leaflet-bottom {
            position: absolute !important;
            top: 0 !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            padding: 5px;
            z-index: 1000;
        }
    </style>
    """
    )

    # Pass the appropriate spec data to the Map component
    m = Map(
        height="100%",
        width="100%",
        data_ctrl=True,
        search_ctrl=False,
        scale_ctrl=False,
        measure_ctrl=False,
        fullscreen_ctrl=False,
        toolbar_ctrl=True,
        layer_ctrl=True,
        attribution_ctrl=False,
        zoom=3,
        center=(1.6508, 17.7576),
    )

    layout = widgets.VBox(
        [css, m],
        layout=widgets.Layout(width="100%", height="100vh"),
    )
    solara.display(layout)
