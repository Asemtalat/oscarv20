# -*- coding: utf-8 -*-
"""
Model extensions for Healthy API Integration.

This package adds an ``api_token`` field to the ``res.users`` model,
allowing external applications to authenticate against the REST API using
a pre‑shared token. The token is generated automatically for each user
upon creation but can be reset manually by the administrator.
"""

from . import res_users
from . import sale_order
from . import merchant_visit
from . import api_signup_request
from . import api_rule
