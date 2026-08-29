# Stub for gspread to satisfy imports when the real library is absent.
# Provides minimal placeholder classes that raise informative errors when used.

class _GSpreadClient:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "gspread is not installed. Install it with 'pip install gspread' to use Google Sheets features."
        )

# Export expected names
Client = _GSpreadClient
Spreadsheet = _GSpreadClient
Worksheet = _GSpreadClient

# Import submodule stubs for compatibility
from . import spreadsheet  # noqa: F401
from . import worksheet  # noqa: F401
from . import spreadsheet
