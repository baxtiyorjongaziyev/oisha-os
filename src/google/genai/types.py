# Minimal placeholder types for the google.genai module.

class GenerationConfig:
    """Placeholder for GenerationConfig used by the real SDK.
    It accepts arbitrary kwargs but does nothing.
    """
    def __init__(self, **kwargs):
        pass

class HarmBlockThreshold:
    """Placeholder enum-like class for harm block thresholds.
    The real SDK defines several class attributes (BLOCK_NONE, BLOCK_LOW, ...).
    We'll define a single default value.
    """
    BLOCK_NONE = "BLOCK_NONE"

class HarmCategory:
    """Placeholder enum-like class for harm categories.
    The real SDK defines many categories (HARM_CATEGORY_DANGEROUS_CONTENT, ...).
    We'll provide a single dummy category.
    """
    HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"
