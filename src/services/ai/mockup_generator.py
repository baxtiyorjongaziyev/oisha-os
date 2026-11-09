from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MockupRequest:
    brand_name: str
    industry: str
    primary_colors: List[str]
    mockup_type: str
    environment: str = "minimal_studio"
    tagline: Optional[str] = None


@dataclass
class MockupPromptResult:
    mockup_type: str
    prompt: str
    prompt_uz: str
    negative_prompt: str
    aspect_ratio: str
    rules_applied: List[str] = field(default_factory=list)


class BrandMockupEngine:
    ASPECT_RATIOS: Dict[str, str] = {
        "billboard_tashkent": "16:9",
        "packaging_box": "1:1",
        "stationery_business_card": "4:3",
        "instagram_grid": "1:1",
        "coffee_cup": "4:5",
        "truck_vehicle": "16:9",
    }

    ENVIRONMENTS_EN: Dict[str, str] = {
        "minimal_studio": "clean neutral grey studio lighting, soft shadows, high-end product photography",
        "outdoor_city": "sunny afternoon in modern Tashkent boulevard, glass skyscrapers, authentic architectural depth",
        "retail_shelf": "modern supermarket display shelf, premium retail lighting, surrounded by elegant packaging",
    }

    ENVIRONMENTS_UZ: Dict[str, str] = {
        "minimal_studio": "toza studiya foni, yumshoq yorugʻlik va professional fotosurat",
        "outdoor_city": "Toshkent shahri zamonaviy koʻchalari va binolari foni",
        "retail_shelf": "doʻkon javonlari va savdo peshtaxtasi foni",
    }

    def generate_prompt(self, request: MockupRequest) -> MockupPromptResult:
        aspect = self.ASPECT_RATIOS.get(request.mockup_type, "1:1")
        env_en = self.ENVIRONMENTS_EN.get(
            request.environment, self.ENVIRONMENTS_EN["minimal_studio"]
        )
        env_uz = self.ENVIRONMENTS_UZ.get(
            request.environment, self.ENVIRONMENTS_UZ["minimal_studio"]
        )

        colors_str = ", ".join(request.primary_colors)
        rules = ["keep_logo", "sharp_typography", "natural_lighting", "no_blur"]

        prompt_en = (
            f"Professional commercial 8k branding mockup of '{request.mockup_type.replace('_', ' ')}' "
            f"for '{request.brand_name}' ({request.industry}). "
            f"Brand colors: {colors_str}. "
            f"Features razor-sharp logo typography, premium textures, {env_en}. "
            f"Shot on 85mm f/1.8 lens, photorealistic, cinematic commercial design."
        )

        prompt_uz = (
            f"'{request.brand_name}' brendi uchun '{request.mockup_type}' maketi. "
            f"Ranglar palitrasi: {colors_str}. Fon: {env_uz}."
        )

        negative_prompt = (
            "blurry, low resolution, warped logo, distorted letters, bad typography, "
            "deformed geometry, oversaturated, amateur photograph, watermark, noise"
        )

        return MockupPromptResult(
            mockup_type=request.mockup_type,
            prompt=prompt_en,
            prompt_uz=prompt_uz,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect,
            rules_applied=rules,
        )
