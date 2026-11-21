from __future__ import annotations

from typing import Any


FORM_PLACEMENTS: dict[str, tuple[int, int]] = {
    "center": (50, 50),
    "left": (20, 50),
    "right": (80, 50),
    "top": (50, 22),
    "bottom": (50, 78),
    "top-left": (20, 22),
    "top-right": (80, 22),
    "bottom-left": (20, 78),
    "bottom-right": (80, 78),
}

FORM_INTEGRATIONS = {"free", "flow", "panel-left", "panel-right"}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def form_coordinates(design: dict[str, Any]) -> tuple[int, int]:
    if "formPlacement" not in design and ("formPositionX" in design or "formPositionY" in design):
        return (
            _bounded_int(design.get("formPositionX", 50), 50, 0, 100),
            _bounded_int(design.get("formPositionY", 50), 50, 0, 100),
        )
    placement = str(design.get("formPlacement", "center"))
    if placement in FORM_PLACEMENTS:
        return FORM_PLACEMENTS[placement]
    return (
        _bounded_int(design.get("formPositionX", 50), 50, 0, 100),
        _bounded_int(design.get("formPositionY", 50), 50, 0, 100),
    )


def hex_to_rgba(value: str, opacity: int | float = 100) -> str:
    color = str(value or "#ffffff")
    if len(color) != 7 or not color.startswith("#"):
        color = "#ffffff"
    try:
        red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        red, green, blue = 255, 255, 255
    alpha = max(0, min(100, int(opacity))) / 100
    return f"rgba({red}, {green}, {blue}, {alpha:.2f})"


def form_css_tokens(design: dict[str, Any]) -> str:
    x, y = form_coordinates(design)
    width = _bounded_int(design.get("formWidth", design.get("cardWidth", 440)), 440, 240, 1200)
    frame_enabled = bool(design.get("formFrameEnabled", True))
    padding = _bounded_int(design.get("formPadding", 32), 32, 0, 120)
    radius = _bounded_int(design.get("formRadius", design.get("radius", 16)), 16, 0, 80) if frame_enabled else 0
    border_width = (
        _bounded_int(design.get("formBorderWidth", 1), 1, 0, 8)
        if frame_enabled and design.get("formBorderEnabled", True)
        else 0
    )
    border_color = str(design.get("formBorderColor", "#e6eaf0"))
    if len(border_color) != 7 or not border_color.startswith("#"):
        border_color = "#e6eaf0"
    background = hex_to_rgba(
        str(design.get("surface", "#ffffff")),
        _bounded_int(design.get("formBackgroundOpacity", 100), 100, 0, 100)
        if frame_enabled and design.get("formBackgroundEnabled", True)
        else 0,
    )
    shadow_enabled = frame_enabled and bool(design.get("formShadow", design.get("shadow", True)))
    shadow = "0 24px 70px rgba(15, 23, 42, .14)" if shadow_enabled else "none"
    text_align = str(design.get("formContentAlignment", "left"))
    if text_align not in {"left", "center", "right"}:
        text_align = "left"
    integration = str(design.get("formIntegration", "free"))
    if integration not in FORM_INTEGRATIONS:
        integration = "free"
    return "\n".join((
        f"  --kts-form-x: {x}%;",
        f"  --kts-form-y: {y}%;",
        f"  --kts-form-width: {width}px;",
        f"  --kts-form-padding: {padding}px;",
        f"  --kts-form-radius: {radius}px;",
        f"  --kts-form-background: {background};",
        f"  --kts-form-border-width: {border_width}px;",
        f"  --kts-form-border-color: {border_color};",
        f"  --kts-form-shadow: {shadow};",
        f"  --kts-form-text-align: {text_align};",
        f"  --kts-form-integration: {integration};",
        f"  --kts-form-frame: {1 if frame_enabled else 0};",
    ))


def form_layout_css(
    root_selector: str,
    card_selector: str,
    header_selector: str = "#kc-header",
    design: dict[str, Any] | None = None,
) -> str:
    """Position the Keycloakify/native form container independently from form contents."""
    design = design or {}
    integration = str(design.get("formIntegration", "free"))
    if integration not in FORM_INTEGRATIONS:
        integration = "free"

    root_common = f'''{root_selector} {{
  position: relative !important;
  width: 100% !important;
  min-width: 0 !important;
  min-height: 100vh !important;
  min-height: 100svh !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}'''

    if integration == "free":
        root_layout = f'''{root_selector} {{
  display: block !important;
  padding: 0 !important;
}}
{card_selector} {{
  position: absolute !important;
  left: clamp(12px, var(--kts-form-x), calc(100% - 12px)) !important;
  top: clamp(12px, var(--kts-form-y), calc(100% - 12px)) !important;
  transform: translate(-50%, -50%) !important;
}}'''
    elif integration == "flow":
        root_layout = f'''{root_selector} {{
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  padding: clamp(72px, 9vh, 120px) 24px 56px !important;
}}
{card_selector} {{
  position: relative !important;
  inset: auto !important;
  transform: none !important;
  align-self: center !important;
  margin: 0 auto !important;
}}'''
    elif integration == "panel-left":
        root_layout = f'''{root_selector} {{
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: center !important;
  padding: clamp(72px, 9vh, 120px) clamp(24px, 6vw, 104px) 56px !important;
}}
{card_selector} {{
  position: relative !important;
  inset: auto !important;
  transform: none !important;
  align-self: flex-start !important;
  margin: 0 !important;
}}'''
    else:  # panel-right
        root_layout = f'''{root_selector} {{
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-end !important;
  justify-content: center !important;
  padding: clamp(72px, 9vh, 120px) clamp(24px, 6vw, 104px) 56px !important;
}}
{card_selector} {{
  position: relative !important;
  inset: auto !important;
  transform: none !important;
  align-self: flex-end !important;
  margin: 0 !important;
}}'''

    return f'''/* Form position, integration and frame are independently configurable. */
{root_common}
{root_layout}
{header_selector} {{
  position: absolute !important;
  z-index: 4 !important;
  top: 20px !important;
  left: 24px !important;
  max-width: calc(100% - 48px);
}}
{card_selector} {{
  z-index: 3 !important;
  box-sizing: border-box !important;
  width: min(var(--kts-form-width), calc(100vw - 32px)) !important;
  max-width: min(var(--kts-form-width), calc(100vw - 32px)) !important;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  padding: var(--kts-form-padding) !important;
  border: var(--kts-form-border-width) solid var(--kts-form-border-color) !important;
  border-radius: var(--kts-form-radius) !important;
  background: var(--kts-form-background) !important;
  box-shadow: var(--kts-form-shadow) !important;
  color: var(--kts-text) !important;
  text-align: var(--kts-form-text-align) !important;
}}
{card_selector} .kcFormHeaderClass,
{card_selector} #kc-page-title,
{card_selector} #kc-content,
{card_selector} #kc-content-wrapper {{
  text-align: var(--kts-form-text-align) !important;
}}
@media (max-width: 640px) {{
  {root_selector} {{
    min-height: 100svh !important;
    padding: {"0" if integration == "free" else "64px 12px 24px"} !important;
    {"display: block !important;" if integration == "free" else "align-items: center !important;"}
  }}
  {card_selector} {{
    width: min(var(--kts-form-width), calc(100vw - 24px)) !important;
    max-width: calc(100vw - 24px) !important;
    max-height: calc(100svh - 88px);
    padding: min(var(--kts-form-padding), 24px) !important;
    {"left: clamp(12px, var(--kts-form-x), calc(100% - 12px)) !important; top: clamp(12px, var(--kts-form-y), calc(100% - 12px)) !important; transform: translate(-50%, -50%) !important;" if integration == "free" else "left: auto !important; top: auto !important; transform: none !important;"}
  }}
  {header_selector} {{
    top: 10px !important;
    left: 12px !important;
    max-width: calc(100% - 24px);
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  {card_selector} {{ transition: none !important; animation: none !important; }}
}}
'''
