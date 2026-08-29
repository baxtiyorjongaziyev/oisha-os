# Minimal placeholder for gspread.worksheet module.

class Worksheet:
    """Placeholder Worksheet class.
    Raises RuntimeError on use to indicate missing real gspread library.
    """
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "gspread is not installed. Install it with 'pip install gspread' to use Google Sheets features."
        )
