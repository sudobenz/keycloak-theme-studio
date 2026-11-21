import json
import unittest
import zipfile
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.keycloakify_engine import (
    KEYCLOAKIFY_VERSION,
    KeycloakifyBuildError,
    keycloakify_project_files,
    make_keycloakify_project_zip,
    merge_keycloakify_and_native_jars,
)
from app.main import app, make_archive, normalize_project


class KeycloakifyEngineTests(unittest.TestCase):
    def setUp(self):
        self.project = normalize_project({
            "name": "keycloakify-regression-test",
            "displayName": "Keycloakify Regression Test",
            "targetVersion": "26.1.4",
            "types": ["login", "account", "admin", "email", "welcome"],
            "advanced": {
                "customCss": ".studio-custom { color: #123456; }",
                "files": {
                    "login/resources/css/custom.css": ".custom-login { color: red; }",
                    "login/resources/js/custom.js": "window.ktsCustom = true;",
                    "login/theme.properties": "# imported theme\nparent=keycloak.v2\nlocales=fr,en\ncustomProperty=preserved\nstyles=css/custom.css\nscripts=js/custom.js\n",
                    "email/html/email-verification.ftl": "<html>Verification</html>",
                },
                "assets": {},
            },
        })

    def _fake_keycloakify_jar(self):
        result = BytesIO()
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("META-INF/keycloak-themes.json", json.dumps({"themes": [{"name": self.project["name"], "types": ["login"]}]}))
            archive.writestr(
                f"theme/{self.project['name']}/login/theme.properties",
                "parent=keycloak\nstyles=css/main.css\n",
            )
            archive.writestr(f"theme/{self.project['name']}/login/resources/css/main.css", "/* Keycloakify CSS */")
        return result.getvalue()

    def test_keycloakify_login_css_contains_background_and_reduced_motion_rules(self):
        from app.keycloakify_engine import keycloakify_login_css
        project = normalize_project({
            **self.project,
            "design": {
                **self.project["design"],
                "backgroundImageData": "data:image/png;base64,aGVsbG8=",
                "backgroundAnimation": "slow-zoom",
                "backgroundAnimationDuration": 30,
            },
        })
        css = keycloakify_login_css(project)
        self.assertIn("data:image/png;base64,aGVsbG8=", css)
        self.assertIn("kts-bg-zoom 30s", css)
        self.assertIn("prefers-reduced-motion: reduce", css)


    def test_keycloakify_login_css_exports_form_position_and_cardless_layout(self):
        from app.keycloakify_engine import keycloakify_login_css
        project = normalize_project({
            **self.project,
            "design": {
                **self.project["design"],
                "formIntegration": "free", "formPlacement": "custom", "formPositionX": 18, "formPositionY": 66,
                "formWidth": 720, "formFrameEnabled": False, "formPadding": 28,
                "surface": "#f2f5fb",
            },
        })
        css = keycloakify_login_css(project)
        self.assertIn(".kcLoginClass > .kcFormCardClass", css)
        self.assertIn("--kts-form-x: 18%", css)
        self.assertIn("--kts-form-y: 66%", css)
        self.assertIn("--kts-form-width: 720px", css)
        self.assertIn("--kts-form-padding: 28px", css)
        self.assertIn("--kts-form-background: rgba(242, 245, 251, 0.00)", css)
        self.assertIn("--kts-form-border-width: 0px", css)
        self.assertIn("--kts-form-shadow: none", css)

    def test_keycloakify_login_css_supports_panel_and_flow_integrations(self):
        from app.keycloakify_engine import keycloakify_login_css
        expectations = {
            "flow": "align-items: center !important",
            "panel-left": "align-items: flex-start !important",
            "panel-right": "align-items: flex-end !important",
        }
        for mode, expected in expectations.items():
            with self.subTest(mode=mode):
                project = normalize_project({**self.project, "design": {**self.project["design"], "formIntegration": mode}})
                self.assertIn(expected, keycloakify_login_css(project))

    def test_generated_project_uses_official_keycloakify_vite_starter_conventions(self):
        files = keycloakify_project_files(self.project)
        package = json.loads(files["package.json"])
        self.assertEqual(package["dependencies"]["keycloakify"], KEYCLOAKIFY_VERSION)
        self.assertEqual(package["engines"]["node"], "^18.0.0 || >=20.0.0")
        self.assertEqual(package["scripts"]["build-keycloak-theme"], "npm run build && keycloakify build")
        self.assertIn(b"keycloakify/vite-plugin", files["vite.config.ts"])
        self.assertIn(b'accountThemeImplementation: "none"', files["vite.config.ts"])
        self.assertIn(b"DefaultPage", files["src/login/KcPage.tsx"])
        self.assertIn(b"getKcContextMock", files["src/login/KcPageStory.tsx"])
        self.assertIn(b"type I18n = typeof ofTypeI18n", files["src/login/i18n.ts"])
        self.assertIn("src/vite-env.d.ts", files)

    def test_project_zip_contains_complete_native_sidecar_without_regression(self):
        native, _, _ = make_archive(self.project, "jar")
        archive_buffer, filename = make_keycloakify_project_zip(self.project, native.getvalue())
        self.assertTrue(filename.endswith(".zip"))
        with zipfile.ZipFile(archive_buffer) as archive:
            names = set(archive.namelist())
            readme = archive.read(f"keycloakify-{self.project['name']}/README.md").decode()
            sidecar = archive.read(f"keycloakify-{self.project['name']}/native-sidecar.jar")
        self.assertIn(f"keycloakify-{self.project['name']}/package.json", names)
        self.assertIn(f"keycloakify-{self.project['name']}/native-sidecar.jar", names)
        self.assertIn("JAR natif", readme)
        with zipfile.ZipFile(BytesIO(sidecar)) as native:
            self.assertIn(f"theme/{self.project['name']}/login/resources/js/custom.js", native.namelist())
            self.assertIn(f"theme/{self.project['name']}/login/theme.properties", native.namelist())
            self.assertIn(f"theme/{self.project['name']}/account/theme.properties", native.namelist())
            self.assertIn(f"theme/{self.project['name']}/admin/theme.properties", native.namelist())
            self.assertIn(f"theme/{self.project['name']}/email/html/email-verification.ftl", native.namelist())
            self.assertIn(f"theme/{self.project['name']}/welcome/theme.properties", native.namelist())

    def test_hybrid_jar_keeps_keycloakify_login_and_native_types_without_regression(self):
        native_buffer, _, _ = make_archive(self.project, "jar")
        hybrid = merge_keycloakify_and_native_jars(self._fake_keycloakify_jar(), native_buffer.getvalue(), self.project)
        with zipfile.ZipFile(BytesIO(hybrid)) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("META-INF/keycloak-themes.json"))
            login_properties = archive.read(f"theme/{self.project['name']}/login/theme.properties").decode()
        self.assertIn(f"theme/{self.project['name']}/login/resources/css/main.css", names)
        self.assertIn(f"theme/{self.project['name']}/login/resources/css/custom.css", names)
        self.assertIn(f"theme/{self.project['name']}/login/resources/js/custom.js", names)
        self.assertIn(f"theme/{self.project['name']}/email/html/email-verification.ftl", names)
        self.assertIn(f"theme/{self.project['name']}/admin/theme.properties", names)
        self.assertIn(f"theme/{self.project['name']}/welcome/theme.properties", names)
        self.assertEqual(set(manifest["themes"][0]["types"]), {"login", "account", "admin", "email", "welcome"})
        self.assertIn("parent=keycloak.v2", login_properties)
        self.assertIn("customProperty=preserved", login_properties)
        self.assertIn("styles=css/main.css css/custom.css", login_properties)
        self.assertIn("scripts=js/custom.js", login_properties)
        self.assertNotIn("kts-overrides.css", login_properties)

    def test_keycloakify_merge_rejects_custom_login_ftl(self):
        project = normalize_project({
            **self.project,
            "advanced": {"customCss": "", "files": {"login/login.ftl": "custom"}, "assets": {}},
        })
        native_buffer, _, _ = make_archive(project, "jar")
        with self.assertRaises(KeycloakifyBuildError):
            merge_keycloakify_and_native_jars(self._fake_keycloakify_jar(), native_buffer.getvalue(), project)

    def test_native_jar_endpoint_is_unchanged_and_still_downloads(self):
        client = TestClient(app)
        response = client.post("/api/export/jar", json={"project": self.project})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/java-archive")
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            manifest = json.loads(archive.read("META-INF/keycloak-themes.json"))
            self.assertIn(f"theme/{self.project['name']}/login/theme.properties", archive.namelist())
        self.assertEqual(set(manifest["themes"][0]["types"]), set(self.project["types"]))

    def test_keycloakify_project_endpoint_exports_source_zip(self):
        client = TestClient(app)
        response = client.post("/api/export/keycloakify-project", json={"project": self.project})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/zip")
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertIn(f"keycloakify-{self.project['name']}/package.json", archive.namelist())
            sidecar = archive.read(f"keycloakify-{self.project['name']}/native-sidecar.jar")
        with zipfile.ZipFile(BytesIO(sidecar)) as native:
            self.assertIn(f"theme/{self.project['name']}/login/resources/js/custom.js", native.namelist())

    def test_keycloakify_jar_endpoint_uses_hybrid_builder_and_downloads_combined_jar(self):
        client = TestClient(app)
        with patch("app.main.build_keycloakify_login_jar", return_value=self._fake_keycloakify_jar()):
            response = client.post("/api/export/keycloakify-jar", json={"project": self.project})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-kts-theme-engine"), "keycloakify-react-hybrid")
        self.assertTrue(response.headers["content-disposition"].endswith('-keycloakify.jar"'))
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertIn(f"theme/{self.project['name']}/login/resources/css/main.css", archive.namelist())
            self.assertIn(f"theme/{self.project['name']}/email/theme.properties", archive.namelist())

    def test_keycloakify_jar_endpoint_preserves_no_login_projects_with_native_generator(self):
        client = TestClient(app)
        project = normalize_project({"name": "email-only", "types": ["email"]})
        response = client.post("/api/export/keycloakify-jar", json={"project": project})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-kts-theme-engine"), "native-no-login")
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertIn("theme/email-only/email/theme.properties", archive.namelist())

    def test_keycloakify_jar_refuses_login_ftl_with_explicit_native_fallback(self):
        client = TestClient(app)
        project = normalize_project({
            **self.project,
            "advanced": {"customCss": "", "files": {"login/login.ftl": "custom"}, "assets": {}},
        })
        response = client.post("/api/export/keycloakify-jar", json={"project": project})
        self.assertEqual(response.status_code, 409)
        self.assertIn("JAR natif", response.json()["detail"])

    def test_tool_status_rejects_unsupported_node_major(self):
        from types import SimpleNamespace
        versions = {
            "node": ("v19.9.0", ""),
            "npm": ("10.2.0", ""),
            "java": ("", 'openjdk version "21.0.1"'),
            "mvn": ("Apache Maven 3.9.6", ""),
        }
        def fake_run(command, **kwargs):
            stdout, stderr = versions[command[0]]
            return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)
        with patch("app.keycloakify_engine.shutil.which", return_value="/usr/bin/tool"), patch("app.keycloakify_engine.subprocess.run", side_effect=fake_run):
            from app.keycloakify_engine import keycloakify_tool_status
            status = keycloakify_tool_status()
        self.assertFalse(status["ready"])
        self.assertIn("node", status["incompatible"])

    def test_tool_status_accepts_supported_toolchain_versions(self):
        from types import SimpleNamespace
        versions = {
            "node": ("v22.16.0", ""),
            "npm": ("10.9.2", ""),
            "java": ("", 'openjdk version "21.0.1"'),
            "mvn": ("Apache Maven 3.9.9", ""),
        }
        def fake_run(command, **kwargs):
            stdout, stderr = versions[command[0]]
            return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)
        with patch("app.keycloakify_engine.shutil.which", return_value="/usr/bin/tool"), patch("app.keycloakify_engine.subprocess.run", side_effect=fake_run):
            from app.keycloakify_engine import keycloakify_tool_status
            status = keycloakify_tool_status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["incompatible"], [])

    def test_keycloakify_tool_status_endpoint_is_available(self):
        response = TestClient(app).get("/api/keycloakify/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine"], "Keycloakify")
        self.assertIn("node", response.json()["commands"])
        self.assertEqual(response.json()["keycloakifyVersion"], KEYCLOAKIFY_VERSION)


if __name__ == "__main__":
    unittest.main()
