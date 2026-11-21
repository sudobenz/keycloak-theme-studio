import base64
import json
import unittest
import zipfile
import tempfile
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient

import app.main as main_module
from app.theme_layout import form_css_tokens, form_layout_css
from app.main import (
    app,
    build_theme_files,
    default_parents,
    import_theme_archive,
    make_archive,
    normalize_project,
    validate_project,
)


class ThemeGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "schemaVersion": 2,
            "name": "test-studio-theme",
            "displayName": "Test Studio Theme",
            "targetVersion": "26.1.4",
            "types": ["login", "email", "admin"],
            "design": {"brand": "Test Studio"},
            "advanced": {
                "customCss": ".my-custom-class { outline: 1px solid red; }",
                "files": {"login/footer.ftl": "<#macro content>Footer</#macro>", "welcome/custom.css": "body { color: red; }"},
                "assets": {},
            },
        }

    def test_parent_defaults_by_keycloak_major(self):
        self.assertEqual(default_parents("26.1.4")["login"], "keycloak.v2")
        self.assertEqual(default_parents("27.0.0")["login"], "keycloak.v3")
        self.assertEqual(default_parents("27.0.0")["account"], "keycloak.v3")

    def test_normalize_rejects_path_traversal(self):
        bad = dict(self.project)
        bad["advanced"] = {"files": {"login/../../evil.ftl": "bad"}}
        with self.assertRaises(ValueError):
            normalize_project(bad)


    def test_form_layout_options_are_normalized_and_bounded(self):
        project = normalize_project({
            **self.project,
            "design": {
                "formIntegration": "panel-right", "formPositionX": 130, "formPositionY": -10,
                "formWidth": 1800, "formPadding": 140, "formRadius": 100,
                "formBorderWidth": 9, "formFrameEnabled": False,
            },
        })
        design = project["design"]
        self.assertEqual(design["formIntegration"], "panel-right")
        self.assertEqual(design["formPositionX"], 100)
        self.assertEqual(design["formPositionY"], 0)
        self.assertEqual(design["formWidth"], 1200)
        self.assertEqual(design["formPadding"], 120)
        self.assertEqual(design["formRadius"], 80)
        self.assertEqual(design["formBorderWidth"], 8)
        self.assertFalse(design["formFrameEnabled"])

    def test_cardless_form_removes_frame_but_keeps_content_spacing(self):
        project = normalize_project({
            **self.project,
            "design": {
                "surface": "#dceeff", "formFrameEnabled": False, "formPadding": 44,
                "formBackgroundEnabled": True, "formBorderEnabled": True, "formShadow": True,
            },
        })
        tokens = form_css_tokens(project["design"])
        self.assertIn("--kts-form-padding: 44px", tokens)
        self.assertIn("--kts-form-radius: 0px", tokens)
        self.assertIn("--kts-form-background: rgba(220, 238, 255, 0.00)", tokens)
        self.assertIn("--kts-form-border-width: 0px", tokens)
        self.assertIn("--kts-form-shadow: none", tokens)

    def test_form_layout_css_supports_all_integration_modes(self):
        expected = {
            "free": "position: absolute !important",
            "flow": "flex-direction: column !important",
            "panel-left": "align-items: flex-start !important",
            "panel-right": "align-items: flex-end !important",
        }
        for mode, expected_rule in expected.items():
            with self.subTest(mode=mode):
                css = form_layout_css(".kcLoginClass", ".kcLoginClass > .kcFormCardClass", design={"formIntegration": mode})
                self.assertIn(expected_rule, css)
                self.assertIn("--kts-form-x", form_css_tokens({"formIntegration": mode}))
                self.assertIn("@media (max-width: 640px)", css)

    def test_native_login_css_includes_free_position_and_cardless_tokens(self):
        project = json.loads(json.dumps(self.project))
        project["types"] = ["login"]
        project["design"].update({
            "formIntegration": "free", "formPositionX": 17, "formPositionY": 63,
            "formWidth": 680, "formFrameEnabled": False, "formPadding": 22,
        })
        files, _ = build_theme_files(project)
        css = files[f"{project['name']}/login/resources/css/kts-overrides.css"].decode()
        self.assertIn("--kts-form-x: 17%", css)
        self.assertIn("--kts-form-y: 63%", css)
        self.assertIn("--kts-form-width: 680px", css)
        self.assertIn("--kts-form-padding: 22px", css)
        self.assertIn("--kts-form-background: rgba(255, 255, 255, 0.00)", css)
        self.assertIn(".kcLoginClass > .kcFormCardClass", css)

    def test_generated_files_only_include_selected_types(self):
        files, manifest = build_theme_files(self.project)
        self.assertIn("test-studio-theme/login/theme.properties", files)
        self.assertIn("test-studio-theme/email/messages/messages_fr.properties", files)
        self.assertIn("test-studio-theme/admin/resources/css/kts-overrides.css", files)
        properties = files["test-studio-theme/login/theme.properties"].decode()
        self.assertIn("styles=css/login.css css/kts-overrides.css", properties)
        self.assertNotIn("styles.ktsOverrides", properties)
        self.assertNotIn("test-studio-theme/email/resources/css/kts-overrides.css", files)
        self.assertIn("test-studio-theme/login/footer.ftl", files)
        self.assertNotIn("test-studio-theme/welcome/custom.css", files)
        self.assertEqual(set(manifest["themes"][0]["types"]), {"login", "email", "admin"})

    def test_custom_resource_css_and_javascript_are_linked_in_theme_properties(self):
        project = json.loads(json.dumps(self.project))
        project["types"] = ["login"]
        project["advanced"]["files"] = {
            "login/resources/css/custom.css": ".custom { color: red; }",
            "login/resources/js/custom.js": "console.log('theme');",
        }
        files, _ = build_theme_files(project)
        properties = files["test-studio-theme/login/theme.properties"].decode()
        self.assertIn("styles=css/login.css css/kts-overrides.css css/custom.css", properties)
        self.assertIn("scripts=js/custom.js", properties)
        self.assertIn("test-studio-theme/login/resources/css/custom.css", files)
        self.assertIn("test-studio-theme/login/resources/js/custom.js", files)

    def test_imported_theme_properties_keep_custom_values_and_link_generated_resources(self):
        project = json.loads(json.dumps(self.project))
        project["types"] = ["login"]
        project["advanced"]["files"] = {
            "login/theme.properties": "# Existing theme\nparent=keycloak.v2\nstyles=css/original.css\ncustomProperty=kept\n",
            "login/resources/css/custom.css": ".custom { color: red; }",
            "login/resources/js/custom.js": "console.log('theme');",
        }
        files, _ = build_theme_files(project)
        properties = files["test-studio-theme/login/theme.properties"].decode()
        self.assertIn("styles=css/original.css css/custom.css css/kts-overrides.css", properties)
        self.assertIn("scripts=js/custom.js", properties)
        self.assertIn("customProperty=kept", properties)

    def test_zip_package_contains_theme_folder(self):
        buffer, filename, media_type = make_archive(self.project, "zip")
        self.assertTrue(filename.endswith(".zip"))
        self.assertEqual(media_type, "application/zip")
        with zipfile.ZipFile(buffer) as archive:
            names = set(archive.namelist())
        self.assertIn("test-studio-theme/login/theme.properties", names)
        self.assertIn("test-studio-theme/login/resources/css/kts-overrides.css", names)
        self.assertIn("test-studio-theme/README.txt", names)

    def test_jar_package_contains_keycloak_manifest_and_theme_prefix(self):
        buffer, filename, media_type = make_archive(self.project, "jar")
        self.assertTrue(filename.endswith(".jar"))
        self.assertEqual(media_type, "application/java-archive")
        with zipfile.ZipFile(buffer) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("META-INF/keycloak-themes.json"))
        self.assertIn("theme/test-studio-theme/login/theme.properties", names)
        self.assertEqual(manifest["themes"][0]["name"], "test-studio-theme")
        self.assertIn("admin", manifest["themes"][0]["types"])

    def test_validation_warns_for_admin_spa_and_ftl(self):
        result = validate_project(self.project)
        self.assertTrue(result["valid"])
        self.assertTrue(any("React" in warning for warning in result["warnings"]))
        self.assertTrue(any("FreeMarker" in warning for warning in result["warnings"]))

    def test_unknown_theme_type_is_rejected(self):
        bad = dict(self.project)
        bad["types"] = ["login", "custom-spi"]
        with self.assertRaises(ValueError):
            normalize_project(bad)

    def test_logo_svg_is_rejected_as_brand_logo(self):
        bad = dict(self.project)
        bad["design"] = {"logoData": "data:image/svg+xml;base64,PHN2Zz4="}
        with self.assertRaises(ValueError):
            normalize_project(bad)

    def test_binary_assets_are_included_in_both_formats(self):
        project = json.loads(json.dumps(self.project))
        pixel = base64.b64encode(b"fake-image-bytes").decode()
        project["advanced"]["assets"] = {"login/resources/img/background.webp": f"data:image/webp;base64,{pixel}"}
        files, _ = build_theme_files(project)
        self.assertEqual(files["test-studio-theme/login/resources/img/background.webp"], b"fake-image-bytes")

    def test_import_keycloak_zip_archive(self):
        archive_buffer = BytesIO()
        with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("imported-theme/login/theme.properties", "parent=keycloak.v2\nstyles=css/login.css\n")
            archive.writestr("imported-theme/login/resources/css/login.css", "body { color: red; }")
            archive.writestr("imported-theme/login/messages/messages_fr.properties", "loginTitle=Connexion\n")
        result = import_theme_archive("imported-theme.zip", archive_buffer.getvalue())
        imported = result["project"]
        self.assertEqual(imported["name"], "imported-theme")
        self.assertEqual(imported["types"], ["login"])
        self.assertEqual(imported["parents"]["login"], "keycloak.v2")
        props = imported["advanced"]["files"]["login/theme.properties"]
        self.assertIn("styles=css/login.css css/kts-overrides.css", props)
        self.assertIn("login/resources/css/login.css", imported["advanced"]["files"])

    def test_import_keycloak_jar_archive(self):
        archive_buffer = BytesIO()
        with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("META-INF/keycloak-themes.json", '{"themes":[{"name":"jar-theme","types":["email"]}]}')
            archive.writestr("theme/jar-theme/email/theme.properties", "parent=keycloak\nlocales=fr,en\n")
            archive.writestr("theme/jar-theme/email/messages/messages_fr.properties", "passwordResetSubject=Reset\n")
        result = import_theme_archive("jar-theme.jar", archive_buffer.getvalue())
        self.assertEqual(result["project"]["name"], "jar-theme")
        self.assertEqual(result["project"]["types"], ["email"])
        self.assertIn("email/messages/messages_fr.properties", result["project"]["advanced"]["files"])

    def test_import_preserves_binary_resources(self):
        archive_buffer = BytesIO()
        binary = b"sample-png-bytes"
        with zipfile.ZipFile(archive_buffer, "w") as archive:
            archive.writestr("asset-theme/login/theme.properties", "parent=keycloak.v2\n")
            archive.writestr("asset-theme/login/resources/img/company.png", binary)
        result = import_theme_archive("asset-theme.zip", archive_buffer.getvalue())
        data_url = result["project"]["advanced"]["assets"]["login/resources/img/company.png"]
        self.assertEqual(base64.b64decode(data_url.split(",", 1)[1]), binary)

    def test_import_rejects_zip_traversal(self):
        archive_buffer = BytesIO()
        with zipfile.ZipFile(archive_buffer, "w") as archive:
            archive.writestr("../evil.txt", "no")
        with self.assertRaises(ValueError):
            import_theme_archive("bad.zip", archive_buffer.getvalue())

    def test_background_image_and_animation_are_generated_for_web_themes(self):
        project = json.loads(json.dumps(self.project))
        image_bytes = b"background-image-bytes"
        project["types"] = ["login", "welcome", "email"]
        project["design"].update({
            "backgroundImageData": "data:image/webp;base64," + base64.b64encode(image_bytes).decode(),
            "backgroundImageName": "campus.webp",
            "backgroundImagePosition": "center top",
            "backgroundImageSize": "cover",
            "backgroundOverlay": 35,
            "backgroundAnimation": "slow-zoom",
            "backgroundAnimationDuration": 30,
        })
        files, _ = build_theme_files(project)
        for theme_type in ("login", "welcome"):
            image_path = f"test-studio-theme/{theme_type}/resources/img/background.webp"
            css_path = f"test-studio-theme/{theme_type}/resources/css/kts-overrides.css"
            self.assertEqual(files[image_path], image_bytes)
            css = files[css_path].decode()
            self.assertIn('url("../img/background.webp")', css)
            self.assertIn("kts-background-zoom 30s", css)
            self.assertIn("--kts-background-overlay: 0.35", css)
        self.assertNotIn("test-studio-theme/email/resources/img/background.webp", files)

    def test_background_animation_and_position_values_are_constrained(self):
        project = json.loads(json.dumps(self.project))
        project["design"].update({
            "backgroundAnimation": "evil-animation;body{display:none}",
            "backgroundAnimationDuration": 1000,
            "backgroundImagePosition": "url(javascript:alert(1))",
            "backgroundOverlay": 1000,
        })
        normalized = normalize_project(project)
        self.assertEqual(normalized["design"]["backgroundAnimation"], "none")
        self.assertEqual(normalized["design"]["backgroundAnimationDuration"], 60)
        self.assertEqual(normalized["design"]["backgroundImagePosition"], "center")
        self.assertEqual(normalized["design"]["backgroundOverlay"], 80)

    def test_background_image_rejects_svg_data_url(self):
        project = json.loads(json.dumps(self.project))
        project["design"]["backgroundImageData"] = "data:image/svg+xml;base64,PHN2Zz4="
        with self.assertRaises(ValueError):
            normalize_project(project)

    def test_api_health_and_import_endpoint(self):
        client = TestClient(app)
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["version"], "1.7.0")
        archive_buffer = BytesIO()
        with zipfile.ZipFile(archive_buffer, "w") as archive:
            archive.writestr("api-theme/login/theme.properties", "parent=keycloak.v2\n")
        response = client.post("/api/import/archive", json={
            "filename": "api-theme.zip",
            "data": base64.b64encode(archive_buffer.getvalue()).decode(),
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["project"]["name"], "api-theme")

    def test_api_project_create_load_and_delete(self):
        client = TestClient(app)
        previous_data_dir = main_module.DATA_DIR
        with tempfile.TemporaryDirectory() as temporary_dir:
            main_module.DATA_DIR = Path(temporary_dir)
            try:
                project = json.loads(json.dumps(self.project))
                project["name"] = "crud-test-project"
                created = client.post("/api/projects", json={"project": project})
                self.assertEqual(created.status_code, 200, created.text)
                loaded = client.get("/api/projects/crud-test-project")
                self.assertEqual(loaded.status_code, 200, loaded.text)
                self.assertEqual(loaded.json()["name"], "crud-test-project")
                deleted = client.delete("/api/projects/crud-test-project")
                self.assertEqual(deleted.status_code, 200, deleted.text)
                missing = client.get("/api/projects/crud-test-project")
                self.assertEqual(missing.status_code, 404)
            finally:
                main_module.DATA_DIR = previous_data_dir


if __name__ == "__main__":
    unittest.main()
