import pytest
from src.services.ai.mockup_generator import BrandMockupEngine, MockupRequest

def test_mockup_prompt():
    engine = BrandMockupEngine()
    req = MockupRequest(
        brand_name="Chust Pichoqlari",
        industry="Milliy hunarmandchilik",
        primary_colors=["Qora #1A1A1A"],
        mockup_type="billboard_tashkent",
    )
    res = engine.generate_prompt(req)
    assert res.aspect_ratio == "16:9"
    assert "Chust Pichoqlari" in res.prompt
