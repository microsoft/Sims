# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
This module contains functions for updating the start and end dates of a period of interest in a map object.
It provides error handling and user feedback through message displays.
"""

from region_similarity.helpers import message


def update_start_date(change, m):
    """
    Updates the start date of the period of interest in the map object.

    Args:
        change (dict): Dictionary containing the new value for the start date.
            Expected to have a 'new' key with the updated date value.
        m (object): Map object containing various attributes and methods.
            Expected to have a 'start' attribute that can be updated.

    Returns:
        None

    Raises:
        Exception: If there's an error updating the start date, it's caught and displayed as a message.
    """
    try:
        m.start = change["new"]
    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)


def update_end_date(change, m):
    """
    Updates the end date of the period of interest in the map object.

    Args:
        change (dict): Dictionary containing the new value for the end date.
            Expected to have a 'new' key with the updated date value.
        m (object): Map object containing various attributes and methods.
            Expected to have an 'end' attribute that can be updated.

    Returns:
        None

    Raises:
        Exception: If there's an error updating the end date, it's caught and displayed as a message.
    """
    try:
        m.end = change["new"]
    except Exception as e:
        message(m, f"Error: {e}", False)
        message(m, f"Error: {e}", True, 5)
