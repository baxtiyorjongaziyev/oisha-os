"""Compose the private CAPI console from local, fixed presentation assets."""
from pathlib import Path


def render_console(*, can_manage: bool) -> str:
    templates = Path(__file__).parent / "templates"
    html = (templates / "capi_platform.html").read_text(encoding="utf-8")
    for marker, filename in (
        ("/* CAPI_STYLES */", "capi_platform.css"),
        ("/* CAPI_MODEL */", "capi_platform_model.js"),
        ("/* CAPI_DRILLDOWN */", "capi_platform_drilldown.js"),
        ("/* CAPI_UI */", "capi_platform_ui.js"),
    ):
        target = templates / filename
        if target.exists():
            html = html.replace(marker, target.read_text(encoding="utf-8"))
    return html.replace("__CAPI_CAN_MANAGE__", "true" if can_manage else "false")
