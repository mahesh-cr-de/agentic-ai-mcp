"""Concrete adapters implementing the ports in :mod:`mcp_data_tools.ports`.

Each backend package (``bigquery``, ``gcs``, ``airflow``, ``audit``)
exposes a "real" adapter that talks to the corresponding external system,
and an in-memory ``mock`` adapter used by tests, local development, and
the ``examples/`` walkthroughs. Real adapters import their third-party SDK
lazily (inside ``__init__``) so that importing this package never requires
every optional cloud SDK to be installed.
"""
