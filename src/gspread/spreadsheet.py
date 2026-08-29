# Minimal placeholder for gspread.spreadsheet module.

class Spreadsheet:
    """Placeholder Spreadsheet class.
    Raises RuntimeError on use to indicate the real gspread library is missing.
    """
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "gspread is not installed. Install it with 'pip install gspread' to use Google Sheets features."
        )

class Worksheet(Spreadsheet):
    """Placeholder Worksheet class inheriting from Spreadsheet."""
    pass
