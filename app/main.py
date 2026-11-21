from __future__ import annotations

import base64
import json
import os
import re
import zipfile
import mimetypes
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.theme_layout import FORM_PLACEMENTS, form_css_tokens, form_layout_css

from app.keycloakify_engine import (
    KeycloakifyBuildError,
    build_keycloakify_login_jar,
    keycloakify_tool_status,
    make_keycloakify_project_zip,
    merge_keycloakify_and_native_jars,
)

APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"
DATA_DIR = Path(os.environ.get("KTS_DATA_DIR", "./data/projects")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_TYPES = {"login", "account", "admin", "email", "welcome"}
SAFE_FILE_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SLUG_RE = re.compile(r"[^a-z0-9-]+")

app = FastAPI(
    title="Keycloak Theme Studio",
    version="1.7.0",
    description="Éditeur visuel et générateur de thèmes Keycloak.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ProjectPayload(BaseModel):
    project: dict[str, Any] = Field(default_factory=dict)


def slugify(value: str, fallback: str = "custom-theme") -> str:
    value = (value or "").strip().lower().replace("_", "-").replace(" ", "-")
    value = SLUG_RE.sub("-", value).strip("-")
    value = re.sub(r"-+", "-", value)
    return value[:50] or fallback


def default_parents(version: str) -> dict[str, str]:
    major = 26
    match = re.match(r"\s*(\d+)", version or "")
    if match:
        major = int(match.group(1))
    if major >= 27:
        login_parent = "keycloak.v3"
    elif major >= 26:
        login_parent = "keycloak.v2"
    else:
        login_parent = "keycloak"
    return {
        "login": login_parent,
        "account": "keycloak.v3" if major >= 26 else "keycloak",
        "admin": "keycloak.v2" if major >= 26 else "keycloak",
        "email": "keycloak",
        "welcome": "keycloak",
    }


def normalize_project(raw: dict[str, Any]) -> dict[str, Any]:
    project = dict(raw or {})
    project.setdefault("schemaVersion", 1)
    project["name"] = slugify(str(project.get("name") or project.get("displayName") or "custom-theme"))
    project["displayName"] = str(project.get("displayName") or project["name"])[:80]
    project["description"] = str(project.get("description") or "Custom Keycloak theme")[:240]
    project["targetVersion"] = str(project.get("targetVersion") or "26.1.4")[:30]

    types = project.get("types") or ["login"]
    if not isinstance(types, list):
        raise ValueError("La liste des types de thème doit être un tableau.")
    unknown_types = sorted({str(item).lower() for item in types} - SUPPORTED_TYPES)
    if unknown_types:
        raise ValueError("Type(s) de thème non pris en charge : " + ", ".join(unknown_types))
    project["types"] = sorted({str(item).lower() for item in types})
    if not project["types"]:
        raise ValueError("Sélectionnez au moins un type de thème.")

    design = dict(project.get("design") or {})
    # Coordinates supplied without a named preset represent an intentional
    # custom position (API/import callers may not know the UI's "custom" flag).
    if "formPlacement" not in design and ("formPositionX" in design or "formPositionY" in design):
        design["formPlacement"] = "custom"
    defaults = {
        "primary": "#2563eb",
        "accent": "#06b6d4",
        "background": "#eef2f7",
        "surface": "#ffffff",
        "text": "#172033",
        "muted": "#667085",
        "fontFamily": "Inter, system-ui, -apple-system, Segoe UI, sans-serif",
        "radius": 16,
        "cardWidth": 440,
        "brand": "Identity Portal",
        "subtitle": "Connectez-vous à votre espace",
        "showBrand": True,
        "showRememberMe": True,
        "showForgotPassword": True,
        "logoData": "",
        "logoName": "",
        "shadow": True,
        "formPlacement": "center",
        "formIntegration": "free",
        "formPositionX": 50,
        "formPositionY": 50,
        "formWidth": 440,
        "formFrameEnabled": True,
        "formPadding": 32,
        "formRadius": 16,
        "formBackgroundEnabled": True,
        "formBackgroundOpacity": 100,
        "formBorderEnabled": True,
        "formBorderColor": "#e6eaf0",
        "formBorderWidth": 1,
        "formShadow": True,
        "formContentAlignment": "left",
        "backgroundImageData": "",
        "backgroundImageName": "",
        "backgroundImagePosition": "center",
        "backgroundImageSize": "cover",
        "backgroundOverlay": 0,
        "backgroundAnimation": "none",
        "backgroundAnimationDuration": 24,
    }
    for key, value in defaults.items():
        design.setdefault(key, value)
    for key in ("primary", "accent", "background", "surface", "text", "muted"):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(design.get(key, ""))):
            design[key] = defaults[key]
    design["radius"] = max(0, min(40, int(design.get("radius", 16))))
    # cardWidth/shadow are retained as compatibility aliases for projects created
    # before the independent form layout controls were introduced.
    legacy_width = design.get("cardWidth", 440)
    design["formWidth"] = max(240, min(1200, int(design.get("formWidth", legacy_width))))
    design["cardWidth"] = design["formWidth"]
    design["formPlacement"] = str(design.get("formPlacement") or "center")
    design["formIntegration"] = str(design.get("formIntegration") or "free")
    if design["formIntegration"] not in {"free", "flow", "panel-left", "panel-right"}:
        design["formIntegration"] = "free"
    design["formFrameEnabled"] = bool(design.get("formFrameEnabled", True))
    if design["formPlacement"] not in {*FORM_PLACEMENTS.keys(), "custom"}:
        design["formPlacement"] = "center"
    design["formPositionX"] = max(0, min(100, int(design.get("formPositionX", 50))))
    design["formPositionY"] = max(0, min(100, int(design.get("formPositionY", 50))))
    design["formPadding"] = max(0, min(120, int(design.get("formPadding", 32))))
    design["formRadius"] = max(0, min(80, int(design.get("formRadius", design["radius"]))))
    design["formBackgroundEnabled"] = bool(design.get("formBackgroundEnabled", True))
    design["formBackgroundOpacity"] = max(0, min(100, int(design.get("formBackgroundOpacity", 100))))
    design["formBorderEnabled"] = bool(design.get("formBorderEnabled", True))
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(design.get("formBorderColor", ""))):
        design["formBorderColor"] = "#e6eaf0"
    design["formBorderWidth"] = max(0, min(8, int(design.get("formBorderWidth", 1))))
    design["formShadow"] = bool(design.get("formShadow", design.get("shadow", True)))
    design["shadow"] = design["formShadow"]
    design["formContentAlignment"] = str(design.get("formContentAlignment") or "left")
    if design["formContentAlignment"] not in {"left", "center", "right"}:
        design["formContentAlignment"] = "left"
    design["brand"] = str(design.get("brand") or "Identity Portal")[:80]
    design["subtitle"] = str(design.get("subtitle") or "")[:160]
    design["fontFamily"] = re.sub(r"[;{}<>]", "", str(design.get("fontFamily") or defaults["fontFamily"]))[:160]

    logo_data = design.get("logoData") or ""
    if logo_data:
        if not isinstance(logo_data, str) or len(logo_data) > 2_100_000:
            raise ValueError("Le logo dépasse la taille maximale autorisée (1,5 Mo environ).")
        if not re.match(r"^data:image/(png|jpeg|webp);base64,", logo_data):
            raise ValueError("Format de logo non accepté. Utilisez PNG, JPEG ou WebP.")
        try:
            base64.b64decode(logo_data.split(",", 1)[1], validate=True)
        except Exception as exc:
            raise ValueError("Le fichier logo transmis n'est pas un Base64 valide.") from exc

    background_data = design.get("backgroundImageData") or ""
    if background_data:
        if not isinstance(background_data, str) or len(background_data) > 4_300_000:
            raise ValueError("L'image d'arrière-plan dépasse la taille maximale autorisée (3 Mo environ).")
        if not re.match(r"^data:image/(png|jpeg|webp);base64,", background_data):
            raise ValueError("Format d'arrière-plan non accepté. Utilisez PNG, JPEG ou WebP.")
        try:
            decoded_background = base64.b64decode(background_data.split(",", 1)[1], validate=True)
            if len(decoded_background) > 3 * 1024 * 1024:
                raise ValueError("L'image d'arrière-plan dépasse 3 Mo.")
        except Exception as exc:
            if isinstance(exc, ValueError) and "dépasse 3 Mo" in str(exc):
                raise
            raise ValueError("Le fichier d'arrière-plan n'est pas un Base64 valide.") from exc
    design["backgroundImageName"] = re.sub(r"[^A-Za-z0-9._-]", "_", str(design.get("backgroundImageName") or "background"))[:120]
    design["backgroundImagePosition"] = str(design.get("backgroundImagePosition") or "center")
    if design["backgroundImagePosition"] not in {"center", "top", "bottom", "left", "right", "center top", "center bottom"}:
        design["backgroundImagePosition"] = "center"
    design["backgroundImageSize"] = str(design.get("backgroundImageSize") or "cover")
    if design["backgroundImageSize"] not in {"cover", "contain"}:
        design["backgroundImageSize"] = "cover"
    design["backgroundOverlay"] = max(0, min(80, int(design.get("backgroundOverlay", 0))))
    design["backgroundAnimation"] = str(design.get("backgroundAnimation") or "none")
    if design["backgroundAnimation"] not in {"none", "slow-zoom", "drift", "aurora"}:
        design["backgroundAnimation"] = "none"
    design["backgroundAnimationDuration"] = max(8, min(60, int(design.get("backgroundAnimationDuration", 24))))
    project["design"] = design

    advanced = dict(project.get("advanced") or {})
    advanced.setdefault("customCss", "")
    advanced.setdefault("files", {})
    advanced.setdefault("assets", {})
    if not isinstance(advanced["customCss"], str) or len(advanced["customCss"]) > 1_000_000:
        raise ValueError("Le CSS personnalisé dépasse la limite de 1 Mo.")
    if not isinstance(advanced["files"], dict):
        advanced["files"] = {}
    if len(advanced["files"]) > 100:
        raise ValueError("Un projet ne peut pas contenir plus de 100 fichiers personnalisés.")
    cleaned_files: dict[str, str] = {}
    for path, content in advanced["files"].items():
        path = str(path).replace("\\", "/").strip("/")
        parts = PurePosixPath(path).parts
        if (
            not path
            or path.startswith("/")
            or ".." in parts
            or not SAFE_FILE_RE.fullmatch(path)
            or len(parts) < 2
            or parts[0] not in SUPPORTED_TYPES
            or len(str(content)) > 500_000
        ):
            raise ValueError(f"Chemin de fichier personnalisé invalide : {path[:100]}")
        cleaned_files[path] = str(content)
    advanced["files"] = cleaned_files

    if not isinstance(advanced["assets"], dict) or len(advanced["assets"]) > 100:
        raise ValueError("Un projet ne peut pas contenir plus de 100 ressources binaires.")
    cleaned_assets: dict[str, str] = {}
    for path, data_url in advanced["assets"].items():
        path = str(path).replace("\\", "/").strip("/")
        parts = PurePosixPath(path).parts
        if not path or path.startswith("/") or ".." in parts or not SAFE_FILE_RE.fullmatch(path) or len(parts) < 2 or parts[0] not in SUPPORTED_TYPES:
            raise ValueError(f"Chemin de ressource invalide : {path[:100]}")
        if not isinstance(data_url, str) or len(data_url) > 8_500_000 or not re.match(r"^data:[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+;base64,", data_url):
            raise ValueError(f"Ressource binaire invalide : {path[:100]}")
        try:
            base64.b64decode(data_url.split(",", 1)[1], validate=True)
        except Exception as exc:
            raise ValueError(f"Encodage Base64 invalide pour : {path[:100]}") from exc
        cleaned_assets[path] = data_url
    advanced["assets"] = cleaned_assets
    project["advanced"] = advanced

    parents = dict(project.get("parents") or {})
    for key, value in default_parents(project["targetVersion"]).items():
        parents.setdefault(key, value)
    for key in SUPPORTED_TYPES:
        if key in parents:
            parent = str(parents[key]).strip()
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", parent):
                raise ValueError(f"Nom de thème parent invalide pour {key}.")
            parents[key] = parent
    project["parents"] = parents
    return project


def css_from_design(design: dict[str, Any], extra_css: str = "", background_filename: str = "") -> str:
    font = design["fontFamily"].replace(";", "").replace("{", "").replace("}", "")
    radius = design["radius"]
    shadow = "0 24px 70px rgba(15, 23, 42, .14)" if design.get("shadow", True) else "none"
    overlay = max(0, min(80, int(design.get("backgroundOverlay", 0)))) / 100
    bg_image = f'url("../img/{background_filename}")' if background_filename else "none"
    bg_position = design.get("backgroundImagePosition", "center")
    bg_size = design.get("backgroundImageSize", "cover")
    animation = design.get("backgroundAnimation", "none")
    duration = max(8, min(60, int(design.get("backgroundAnimationDuration", 24))))
    animation_rules = {
        "slow-zoom": "body.kcBodyClass, body.login-pf { animation: kts-background-zoom VAR_DURATION ease-in-out infinite alternate; }",
        "drift": "body.kcBodyClass, body.login-pf { animation: kts-background-drift VAR_DURATION ease-in-out infinite alternate; }",
        "aurora": "body.kcBodyClass, body.login-pf { animation: kts-background-aurora VAR_DURATION ease-in-out infinite alternate; }",
    }
    active_animation = animation_rules.get(animation, "").replace("VAR_DURATION", f"{duration}s")
    css = f'''/* Generated by Keycloak Theme Studio. Review against the selected Keycloak version. */
:root {{
  --kts-primary: {design['primary']};
  --kts-accent: {design['accent']};
  --kts-background: {design['background']};
  --kts-surface: {design['surface']};
  --kts-text: {design['text']};
  --kts-muted: {design['muted']};
  --kts-radius: {radius}px;
  --kts-font-family: {font};
  --kts-card-shadow: {shadow};
{form_css_tokens(design)}
  --kts-background-image: {bg_image};
  --kts-background-overlay: {overlay};
  --kts-background-position: {bg_position};
  --kts-background-size: {bg_size};
}}

/* Login and Welcome background. Image files are placed in resources/img/. */
body.login-pf, body.kcBodyClass, .login-pf body, .kts-welcome {{
  background-color: var(--kts-background);
  background-image: linear-gradient(rgba(10, 16, 28, var(--kts-background-overlay)), rgba(10, 16, 28, var(--kts-background-overlay))), var(--kts-background-image);
  background-position: var(--kts-background-position);
  background-size: var(--kts-background-size);
  background-repeat: no-repeat;
  color: var(--kts-text);
  font-family: var(--kts-font-family);
}}
body.login-pf, body.kcBodyClass {{ background-attachment: fixed; }}
{form_layout_css('.login-pf-page, .kcLoginClass', '.login-pf-page .card-pf, .login-pf-page .kcFormCardClass, .kcLoginClass > .kcFormCardClass, .pf-v5-c-login__main, .pf-v6-c-login__main', '#kc-header', design)}
.login-pf-page .card-pf {{ color: var(--kts-text); }}
#kc-page-title, .login-pf-page h1, .pf-v5-c-title, .pf-v6-c-title {{ color: var(--kts-text); }}
#kc-login, .pf-v5-c-button.pf-m-primary, .pf-v6-c-button.pf-m-primary,
.login-pf-page .btn-primary {{
  background: var(--kts-primary);
  border-color: var(--kts-primary);
  border-radius: max(6px, calc(var(--kts-radius) / 2));
}}
#kc-login:hover, .pf-v5-c-button.pf-m-primary:hover, .pf-v6-c-button.pf-m-primary:hover {{ filter: brightness(.94); }}
.login-pf-page input, .pf-v5-c-form-control, .pf-v6-c-form-control {{ border-radius: max(5px, calc(var(--kts-radius) / 3)); }}
a, .kcFormOptionsWrapperClass a {{ color: var(--kts-primary); }}
.kts-brand-logo {{ max-width: 180px; max-height: 72px; object-fit: contain; }}

/* Optional background motion. Motion is disabled for reduced-motion preferences. */
@keyframes kts-background-zoom {{ from {{ background-size: 100% 100%, 100% 100%; }} to {{ background-size: 100% 100%, 112% 112%; }} }}
@keyframes kts-background-drift {{ from {{ background-position: 48% 50%; }} to {{ background-position: 54% 50%; }} }}
@keyframes kts-background-aurora {{ from {{ background-position: 0% 50%; }} to {{ background-position: 100% 50%; }} }}
{active_animation}
@media (prefers-reduced-motion: reduce) {{ body.kcBodyClass, body.login-pf {{ animation: none !important; }} }}

/* Account and Admin: shared design tokens; deeper SPA changes require a React/Keycloakify build. */
.pf-v5-c-page, .pf-v6-c-page, .pf-v5-c-page__main-section, .pf-v6-c-page__main-section {{
  font-family: var(--kts-font-family);
}}
.pf-v5-c-button.pf-m-primary, .pf-v6-c-button.pf-m-primary {{ background-color: var(--kts-primary); border-color: var(--kts-primary); }}
.pf-v5-c-card, .pf-v6-c-card {{ border-radius: var(--kts-radius); }}

/* Email and Welcome: reusable typography and brand accents. */
.kts-email, .kts-welcome {{ font-family: var(--kts-font-family); color: var(--kts-text); }}
.kts-email a, .kts-welcome a {{ color: var(--kts-primary); }}

{extra_css.strip()}
'''
    return css.rstrip() + "\n"

def properties_for_type(
    theme_type: str,
    parent: str,
    version: str = "26.1.4",
    extra_styles: list[str] | None = None,
    extra_scripts: list[str] | None = None,
) -> str:
    """Return Keycloak-native properties and link resources stored under resources/."""
    lines = ["# Generated by Keycloak Theme Studio", f"# Parent theme: {parent}", f"parent={parent}"]
    if theme_type in {"login", "welcome"}:
        lines.append("import=common/keycloak")
    if theme_type == "login":
        # Keep the parent's Login stylesheet before generated/custom overrides.
        styles = ["css/login.css", "css/kts-overrides.css"]
    elif theme_type in {"account", "admin", "welcome"}:
        styles = ["css/kts-overrides.css"]
    else:
        styles = []
    for item in extra_styles or []:
        if item not in styles:
            styles.append(item)
    if styles:
        lines.append("styles=" + " ".join(styles))
    if theme_type != "email" and extra_scripts:
        lines.append("scripts=" + " ".join(dict.fromkeys(extra_scripts)))
    if theme_type in {"login", "account", "email"}:
        lines.append("locales=en,fr")
    return "\n".join(lines) + "\n"


def _resource_references(project: dict[str, Any], theme_type: str, suffix: str) -> list[str]:
    """Convert <type>/resources/<path> files/assets into theme.properties references."""
    prefix = f"{theme_type}/resources/"
    found: set[str] = set()
    for collection in (project["advanced"].get("files", {}), project["advanced"].get("assets", {})):
        for project_path in collection:
            if project_path.startswith(prefix) and project_path.lower().endswith(suffix):
                resource_path = project_path[len(prefix):]
                if resource_path and ".." not in PurePosixPath(resource_path).parts:
                    found.add(resource_path)
    return sorted(found)


def _append_property_values(content: str, key: str, values: list[str], defaults: list[str] | None = None) -> str:
    """Append de-duplicated space-separated resource paths to a theme.properties key."""
    if not values and not defaults:
        return content
    lines = content.splitlines()
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=(.*)$")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            current = match.group(1).strip().split()
            merged = list(dict.fromkeys(current + values))
            lines[index] = f"{key}=" + " ".join(merged)
            return "\n".join(lines).rstrip() + "\n"
    merged = list(dict.fromkeys((defaults or []) + values))
    if merged:
        lines.append(f"{key}=" + " ".join(merged))
    return "\n".join(lines).rstrip() + "\n"


def messages_for_type(theme_type: str, design: dict[str, Any]) -> str:
    brand = design["brand"].replace("\n", " ")
    if theme_type == "login":
        pairs = {
            "loginAccountTitle": f"Connexion à {brand}",
            "usernameOrEmail": "Adresse e-mail ou identifiant",
            "password": "Mot de passe",
            "doLogIn": "Se connecter",
            "doRegister": "Créer un compte",
            "doForgotPassword": "Mot de passe oublié ?",
            "rememberMe": "Se souvenir de moi",
            "loginTitle": "Connexion",
            "registerTitle": "Créer un compte",
            "email": "Adresse e-mail",
            "firstName": "Prénom",
            "lastName": "Nom",
            "backToLogin": "Retour à la connexion",
        }
    elif theme_type == "email":
        pairs = {
            "passwordResetSubject": f"Réinitialisation de votre mot de passe — {brand}",
            "passwordResetBody": "Pour réinitialiser votre mot de passe, cliquez sur le lien suivant : {0}",
            "passwordResetBodyHtml": '<p>Pour réinitialiser votre mot de passe, <a href="{0}">cliquez ici</a>.</p>',
            "emailVerificationSubject": f"Vérifiez votre adresse e-mail — {brand}",
            "emailVerificationBody": "Pour vérifier votre adresse e-mail, cliquez sur le lien suivant : {0}",
            "emailVerificationBodyHtml": '<p>Pour vérifier votre adresse e-mail, <a href="{0}">cliquez ici</a>.</p>',
        }
    else:
        pairs = {"locale_fr": "Français", "locale_en": "English"}
    return "# UTF-8 — generated by Keycloak Theme Studio\n" + "\n".join(f"{k}={v}" for k, v in pairs.items()) + "\n"


def decode_logo(project: dict[str, Any]) -> tuple[bytes, str] | None:
    data_url = project["design"].get("logoData")
    if not data_url:
        return None
    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";", 1)[0]
    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    return base64.b64decode(encoded), f"logo.{extension}"


def decode_background(project: dict[str, Any]) -> tuple[bytes, str] | None:
    data_url = project["design"].get("backgroundImageData")
    if not data_url:
        return None
    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";", 1)[0]
    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    return base64.b64decode(encoded), f"background.{extension}"


def build_theme_files(raw_project: dict[str, Any]) -> tuple[dict[str, bytes], dict[str, Any]]:
    project = normalize_project(raw_project)
    theme_name = project["name"]
    files: dict[str, bytes] = {}
    logo = decode_logo(project)
    background = decode_background(project)

    for theme_type in project["types"]:
        base = f"{theme_name}/{theme_type}"
        extra_styles = _resource_references(project, theme_type, ".css") if theme_type in {"login", "account", "admin", "welcome"} else []
        extra_scripts = _resource_references(project, theme_type, ".js") if theme_type != "email" else []
        custom_properties = project["advanced"]["files"].get(f"{theme_type}/theme.properties")
        if custom_properties is None:
            properties_text = properties_for_type(
                theme_type, project["parents"][theme_type], project["targetVersion"],
                extra_styles=extra_styles, extra_scripts=extra_scripts,
            )
        else:
            properties_text = str(custom_properties)
            # Keep an explicit imported/custom property file, but fill in a parent
            # only when the author did not provide one.
            if not re.search(r"(?m)^\s*parent\s*=", properties_text):
                properties_text = properties_text.rstrip() + f"\nparent={project['parents'][theme_type]}\n"
            if theme_type in {"login", "welcome"} and not re.search(r"(?m)^\s*import\s*=", properties_text):
                properties_text = properties_text.rstrip() + "\nimport=common/keycloak\n"
            if theme_type in {"login", "account", "admin", "welcome"}:
                default_styles = ["css/login.css"] if theme_type == "login" and not re.search(r"(?m)^\s*styles\s*=", properties_text) else []
                if "css/kts-overrides.css" not in extra_styles:
                    extra_styles.append("css/kts-overrides.css")
                properties_text = _append_property_values(properties_text, "styles", extra_styles, defaults=default_styles)
            if extra_scripts:
                properties_text = _append_property_values(properties_text, "scripts", extra_scripts)
        files[f"{base}/theme.properties"] = properties_text.encode("utf-8")
        if theme_type in {"login", "account", "admin", "welcome"}:
            background_filename = background[1] if background and theme_type in {"login", "account", "admin", "welcome"} else ""
            css = css_from_design(project["design"], project["advanced"].get("customCss", ""), background_filename)
            files[f"{base}/resources/css/kts-overrides.css"] = css.encode("utf-8")
            if background and theme_type in {"login", "account", "admin", "welcome"}:
                background_bytes, background_name = background
                files[f"{base}/resources/img/{background_name}"] = background_bytes
        if theme_type in {"login", "account", "email"}:
            files[f"{base}/messages/messages_fr.properties"] = messages_for_type(theme_type, project["design"]).encode("utf-8")
            files[f"{base}/messages/messages_en.properties"] = "# English fallback. Add translations as required.\n".encode("utf-8")
        if logo:
            logo_bytes, logo_name = logo
            files[f"{base}/resources/img/{logo_name}"] = logo_bytes

    for relative_path, content in project["advanced"]["files"].items():
        # Do not emit source files belonging to a type that is not part of this export.
        if relative_path.split("/", 1)[0] not in project["types"]:
            continue
        # theme.properties has already been merged with generated styles/scripts above.
        if relative_path in {f"{theme_type}/theme.properties" for theme_type in project["types"]}:
            continue
        full_path = f"{theme_name}/{relative_path}"
        files[full_path] = content.encode("utf-8")

    for relative_path, data_url in project["advanced"].get("assets", {}).items():
        if relative_path.split("/", 1)[0] not in project["types"]:
            continue
        files[f"{theme_name}/{relative_path}"] = base64.b64decode(data_url.split(",", 1)[1])

    manifest = {
        "themes": [{"name": theme_name, "types": project["types"]}]
    }
    return files, manifest


def validate_project(raw_project: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        project = normalize_project(raw_project)
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": [], "summary": {}}

    if not project["types"]:
        errors.append("Sélectionnez au moins un type de thème.")
    major_match = re.match(r"\s*(\d+)", project["targetVersion"])
    target_major = int(major_match.group(1)) if major_match else 26
    if "login" in project["types"] and target_major >= 27 and project["parents"].get("login") in {"keycloak", "keycloak.v2"}:
        warnings.append("Keycloak 27 et versions ultérieures ne fournissent plus les parents Login 'keycloak' et 'keycloak.v2'. Utilisez 'keycloak.v3' ou un parent disponible dans votre distribution.")
    if project["advanced"].get("customCss", "").strip():
        warnings.append("Le CSS personnalisé est injecté dans kts-overrides.css pour Login, Account, Admin et Welcome. Les emails nécessitent des templates HTML avec styles adaptés aux clients de messagerie.")
    if any(path.endswith(".ftl") for path in project["advanced"]["files"]):
        warnings.append("Un template FreeMarker personnalisé est présent. Il doit être audité et testé : un template non fiable peut exécuter du code avec les privilèges du processus Keycloak.")
    if "login" in project["types"]:
        warnings.append("Le moteur React/Keycloakify est disponible pour Login. Le JAR natif reste proposé pour conserver à l'identique les templates FreeMarker personnalisés.")
    if any(t in project["types"] for t in ("admin", "account")):
        warnings.append("Account et Admin restent générés par le moteur natif du Studio dans cette version. Keycloakify peut également personnaliser Account, mais cette intégration React dédiée n'est pas encore activée ici ; Admin et Welcome ne sont pas couverts par Keycloakify.")
    if "welcome" in project["types"]:
        warnings.append("La prévisualisation Welcome est illustrative. Contrôlez le rendu sur votre distribution Keycloak et ses ressources intégrées.")
    if len(project["advanced"]["files"]) == 0:
        warnings.append("Aucun template FreeMarker n'est remplacé : les templates fournis par le parent sont conservés, ce qui réduit les risques lors des mises à jour.")

    parents = {t: project["parents"][t] for t in project["types"]}
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "themeName": project["name"],
            "types": project["types"],
            "targetVersion": project["targetVersion"],
            "parents": parents,
            "customFiles": len(project["advanced"]["files"]),
        },
    }


def make_archive(raw_project: dict[str, Any], fmt: str) -> tuple[BytesIO, str, str]:
    project = normalize_project(raw_project)
    files, manifest = build_theme_files(project)
    buffer = BytesIO()
    if fmt == "zip":
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, content in sorted(files.items()):
                archive.writestr(path, content)
            readme = (
                f"{project['displayName']} — Keycloak Theme\n\n"
                f"Theme: {project['name']}\n"
                f"Target version: {project['targetVersion']}\n"
                f"Types: {', '.join(project['types'])}\n\n"
                "Copy the theme directory into the Keycloak themes/ directory.\n"
                "Review compatibility and validate the theme on a non-production Keycloak instance.\n"
            )
            archive.writestr(f"{project['name']}/README.txt", readme.encode("utf-8"))
        filename = f"keycloak-theme-{project['name']}.zip"
        media_type = "application/zip"
    elif fmt == "jar":
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("META-INF/keycloak-themes.json", json.dumps(manifest, indent=2).encode("utf-8"))
            for path, content in sorted(files.items()):
                # Keycloak theme archives place the theme under theme/<theme-name>/...
                archive.writestr(f"theme/{path}", content)
        filename = f"keycloak-theme-{project['name']}.jar"
        media_type = "application/java-archive"
    else:
        raise ValueError("Format d'export non pris en charge.")
    buffer.seek(0)
    return buffer, filename, media_type


MAX_IMPORT_SIZE = 25 * 1024 * 1024
MAX_ARCHIVE_FILES = 500
MAX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024


def _safe_archive_member(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not normalized or normalized.endswith("/"):
        return None
    return str(path)


def import_theme_archive(filename: str, archive_bytes: bytes) -> dict[str, Any]:
    """Import a Keycloak theme ZIP/JAR without extracting it to the filesystem."""
    if len(archive_bytes) > MAX_IMPORT_SIZE:
        raise ValueError("Archive trop volumineuse (25 Mo maximum).")
    try:
        archive = zipfile.ZipFile(BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Le fichier fourni n'est pas une archive ZIP/JAR valide.") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_FILES:
            raise ValueError("L'archive contient trop de fichiers (500 maximum).")
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_SIZE:
            raise ValueError("Taille décompressée excessive (100 Mo maximum).")
        if any(info.file_size > 20 * 1024 * 1024 for info in infos):
            raise ValueError("Un fichier de l'archive dépasse 20 Mo.")

        entries: dict[str, bytes] = {}
        for info in infos:
            safe_name = _safe_archive_member(info.filename)
            if safe_name is None:
                raise ValueError(f"Chemin non autorisé dans l'archive : {info.filename[:100]}")
            if info.is_dir():
                continue
            # Ignore metadata unrelated to the theme and symlink entries.
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if (unix_mode & 0o170000) == 0o120000:
                raise ValueError("Les liens symboliques ne sont pas autorisés dans une archive de thème.")
            entries[safe_name] = archive.read(info)

    # Locate one or more theme roots in common Keycloak ZIP/JAR layouts.
    roots: dict[str, dict[str, str]] = {}
    for path in entries:
        parts = PurePosixPath(path).parts
        for index, part in enumerate(parts):
            if part in SUPPORTED_TYPES and index > 0:
                theme_name = parts[index - 1]
                if index + 1 < len(parts) and parts[index + 1] == "theme.properties":
                    roots.setdefault(theme_name, {})[part] = "/".join(parts[:index + 1])

    if not roots:
        raise ValueError("Aucun thème Keycloak détecté. L'archive doit contenir <theme>/<type>/theme.properties ou theme/<theme>/<type>/theme.properties.")
    if len(roots) > 1:
        # First theme is selected for this Studio project; the import response informs
        # the user that multi-theme archives are not split into separate projects yet.
        theme_name = sorted(roots)[0]
    else:
        theme_name = next(iter(roots))

    root_map = roots[theme_name]
    imported_types = sorted(root_map)
    parents = default_parents("26.1.4")
    files: dict[str, str] = {}
    assets: dict[str, str] = {}
    design = {
        "brand": theme_name.replace("-", " ").title(),
        "primary": "#2563eb", "accent": "#06b6d4", "background": "#eef2f7",
        "surface": "#ffffff", "text": "#172033", "muted": "#667085",
        "fontFamily": "Inter, system-ui, -apple-system, Segoe UI, sans-serif",
        "radius": 16, "cardWidth": 440, "showBrand": True, "showRememberMe": True,
        "showForgotPassword": True, "shadow": True, "logoData": "", "logoName": "",
    }

    for theme_type, prefix in root_map.items():
        for path, content in entries.items():
            if not path.startswith(prefix + "/"):
                continue
            relative = path[len(prefix) + 1:]
            if not relative:
                continue
            project_path = f"{theme_type}/{relative}"
            if relative == "theme.properties":
                text_content = content.decode("utf-8", errors="replace")
                files[project_path] = text_content
                parent_match = re.search(r"(?m)^\s*parent\s*=\s*([^\s#]+)", text_content)
                if parent_match:
                    parents[theme_type] = parent_match.group(1).strip()
                if theme_type in {"login", "account", "admin", "welcome"}:
                    styles_match = re.search(r"(?m)^\s*styles\s*=\s*(.*)$", text_content)
                    if styles_match:
                        styles = styles_match.group(1).strip()
                        if "css/kts-overrides.css" not in styles.split():
                            text_content = re.sub(r"(?m)^\s*styles\s*=\s*.*$", f"styles={styles} css/kts-overrides.css", text_content, count=1)
                    else:
                        default_styles = "css/login.css css/kts-overrides.css" if theme_type == "login" else "css/kts-overrides.css"
                        text_content = text_content.rstrip() + f"\nstyles={default_styles}\n"
                    files[project_path] = text_content
                continue
            mime, _ = mimetypes.guess_type(relative)
            suffix = PurePosixPath(relative).suffix.lower()
            is_binary_asset = bool(mime and ((mime.startswith("image/") and suffix != ".svg") or mime.startswith("font/")))
            try:
                if is_binary_asset or b"\x00" in content:
                    raise UnicodeDecodeError("utf-8", content, 0, min(1, len(content)), "binary")
                text_content = content.decode("utf-8")
                files[project_path] = text_content
                if relative.endswith(".css"):
                    color_match = re.search(r"--kts-primary\s*:\s*(#[0-9a-fA-F]{6})", text_content)
                    if color_match:
                        design["primary"] = color_match.group(1)
            except UnicodeDecodeError:
                mime = mime or "application/octet-stream"
                if len(content) <= 6 * 1024 * 1024:
                    assets[project_path] = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"

    project = normalize_project({
        "schemaVersion": 2,
        "name": theme_name,
        "displayName": theme_name.replace("-", " ").title(),
        "description": f"Imported from {filename}",
        "targetVersion": "26.1.4",
        "types": imported_types,
        "parents": parents,
        "design": design,
        "advanced": {"customCss": "", "files": files, "assets": assets},
    })
    return {
        "project": project,
        "importedFiles": len(files) + len(assets),
        "importedTypes": imported_types,
        "availableThemes": sorted(roots),
        "selectedTheme": theme_name,
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "app": "Keycloak Theme Studio", "version": app.version}


@app.get("/api/defaults")
async def defaults(version: str = "26.1.4") -> dict[str, Any]:
    return {"parents": default_parents(version), "supportedTypes": sorted(SUPPORTED_TYPES)}


@app.post("/api/import/archive")
async def import_archive(payload: dict[str, Any]) -> dict[str, Any]:
    filename = str(payload.get("filename") or "theme.zip")[:180]
    encoded = payload.get("data")
    if not isinstance(encoded, str) or len(encoded) > 35 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Données d'archive absentes ou trop volumineuses.")
    try:
        archive_bytes = base64.b64decode(encoded, validate=True)
        result = import_theme_archive(filename, archive_bytes)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/validate")
async def validate(payload: ProjectPayload) -> dict[str, Any]:
    return validate_project(payload.project)


@app.get("/api/keycloakify/status")
async def keycloakify_status() -> dict[str, Any]:
    return keycloakify_tool_status()


@app.post("/api/export/keycloakify-project")
async def export_keycloakify_project(payload: ProjectPayload) -> StreamingResponse:
    """Download a complete React/Vite source project based on the official Keycloakify starter."""
    try:
        project = normalize_project(payload.project)
        # Keep a complete native JAR beside the React source project. It is the lossless
        # fallback for custom FTL and resources that are intentionally not rendered by React.
        native_buffer, _, _ = make_archive(project, "jar")
        native_sidecar = native_buffer.getvalue()
        buffer, filename = make_keycloakify_project_zip(project, native_sidecar)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/keycloakify-jar")
async def export_keycloakify_jar(payload: ProjectPayload) -> StreamingResponse:
    """Build Login with Keycloakify and preserve non-login theme types with the native generator."""
    try:
        project = normalize_project(payload.project)
        if "login" not in project["types"]:
            buffer, filename, media_type = make_archive(project, "jar")
            return StreamingResponse(
                buffer,
                media_type=media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-KTS-Theme-Engine": "native-no-login",
                },
            )
        custom_ftl = [
            path for path in project["advanced"]["files"]
            if path.startswith("login/") and path.lower().endswith(".ftl")
        ]
        if custom_ftl:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ce projet contient des templates FreeMarker Login personnalisés ("
                    + ", ".join(custom_ftl[:5])
                    + "). Ils ne peuvent pas être superposés au moteur React Keycloakify. "
                    "Utilisez « JAR natif » pour les conserver sans modification."
                ),
            )
        keycloakify_jar = await run_in_threadpool(build_keycloakify_login_jar, project)
        native_buffer, _, _ = make_archive(project, "jar")
        merged_jar = merge_keycloakify_and_native_jars(keycloakify_jar, native_buffer.getvalue(), project)
        filename = f"keycloak-theme-{project['name']}-keycloakify.jar"
    except HTTPException:
        raise
    except KeycloakifyBuildError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Échec de la génération du JAR Keycloakify : {exc}") from exc
    return StreamingResponse(
        BytesIO(merged_jar),
        media_type="application/java-archive",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-KTS-Theme-Engine": "keycloakify-react-hybrid",
        },
    )


@app.post("/api/export/{fmt}")
async def export_theme(fmt: str, payload: ProjectPayload) -> StreamingResponse:
    if fmt not in {"zip", "jar"}:
        raise HTTPException(status_code=404, detail="Format inconnu. Utilisez zip ou jar.")
    try:
        buffer, filename, media_type = make_archive(payload.project, fmt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/projects")
async def list_projects() -> dict[str, Any]:
    projects = []
    for path in sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            projects.append({"id": path.stem, "name": data.get("name", path.stem), "displayName": data.get("displayName", path.stem), "updatedAt": data.get("updatedAt")})
        except Exception:
            continue
    return {"projects": projects}


@app.post("/api/projects")
async def save_project(payload: ProjectPayload) -> dict[str, Any]:
    try:
        project = normalize_project(payload.project)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    project["updatedAt"] = datetime.now(timezone.utc).isoformat()
    path = DATA_DIR / f"{project['name']}.json"
    path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "id": path.stem, "updatedAt": project["updatedAt"]}


@app.get("/api/projects/{project_id}")
async def load_project(project_id: str) -> dict[str, Any]:
    safe_id = slugify(project_id, "")
    if safe_id != project_id or not safe_id:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")
    path = DATA_DIR / f"{safe_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de lire le projet.") from exc


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    safe_id = slugify(project_id, "")
    if safe_id != project_id or not safe_id:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")
    path = DATA_DIR / f"{safe_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    path.unlink()
    return {"deleted": True}
