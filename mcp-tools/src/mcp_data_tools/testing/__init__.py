"""Public test doubles for downstream users of this library.

These are shipped as part of the package (not buried in ``tests/``) so
that anyone building on ``mcp-data-tools`` — e.g. adding a new
:class:`~mcp_data_tools.tools.data_quality.strategies.CheckStrategy` or a
new tool — has an officially supported way to unit test it without a
live backend, the same way this project tests itself.
"""

from mcp_data_tools.testing.scripted_query_engine import ScriptedQueryEngine, single_row_result

__all__ = ["ScriptedQueryEngine", "single_row_result"]
