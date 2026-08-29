# Minimal placeholder for the google.genai module.

class Client:
    """Placeholder client that raises an error when used.

    The real `google.generativeai.Client` provides methods for interacting with
    Gemini models. In the test environment we do not have the SDK installed, so
    instantiating this class will raise a clear exception explaining the missing
    dependency.
    """

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "google-generativeai SDK is not installed. Install it with '\n"
            "pip install google-generativeai' to use Gemini functionality."
        )

    # The real client exposes a `generate_content` method. Providing a stub keeps
    # static analysis happy but still fails loudly if called.
    def generate_content(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError(
            "Attempted to call generate_content on a placeholder client."
        )
