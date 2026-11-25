# -*- coding: utf-8 -*-
"""
Controllers for the Healthy API Integration module.

This module exposes a JSON REST API for external applications. All routes
implemented here are grouped in the ``healthy_api`` namespace under the
``/api/`` prefix. Each controller checks for a valid API token before
executing business logic and returns JSON structures that mirror the
requirements described in the uploaded specification document.
"""

from . import api
