import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_all_javascript_id_references_exist_in_html(self):
        html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
        js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
        html_ids = set(re.findall(r'id="([^"]+)"', html))
        js_ids = set(re.findall(r"\$\('([^']+)'\)", js))
        self.assertEqual(sorted(js_ids - html_ids), [])

    def test_interactive_workflows_are_present(self):
        html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
        js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
        for element_id in ("newProjectBtn", "projectList", "newFileBtn", "deleteFileBtn", "downloadAssetBtn", "previewViewport"):
            self.assertIn(f'id="{element_id}"', html)
        for action in ("createProject", "refreshProjectList", "handleProjectAction", "createFile", "importProject", "downloadCurrentAsset"):
            self.assertIn(f"function {action}", js)
        self.assertIn("kts-preview-nav", js)
        self.assertIn("function flushPendingSourceEdit", js)
        self.assertIn("flushPendingSourceEdit();", js)
        self.assertIn("document.querySelectorAll('[data-preview-space]')", js)
        self.assertIn("document.querySelectorAll('[data-inspector-section]')", js)
        self.assertIn("panel.scrollTo", js)

    def test_ui_copy_uses_clear_french_labels(self):
        html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
        js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
        for label in ("Apparence", "Composants", "Fichiers et code", "Compatibilité", "Nouveau projet", "Vérifier"):
            self.assertIn(label, html)
        self.assertNotIn("Un thème. Cinq expériences.", html)
        self.assertNotIn("Concevez, testez et exportez votre identité Keycloak.", html)
        self.assertIn("Apparence du thème", js)
        self.assertIn('data-preview-space="login"', html)
        self.assertIn('data-inspector-section="inspector-colors"', html)
        self.assertIn('data-inspector-section="inspector-background"', html)
        for element_id in ("backgroundImageFile", "backgroundAnimation", "backgroundOverlay", "previewZoom"):
            self.assertIn(f'id="{element_id}"', html)
        for action in ("loadBackgroundImage", "navigateInspector", "applyPreviewZoom"):
            self.assertIn(f"function {action}", js)

    def test_refined_stylesheet_and_release_version_are_present(self):
        css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
        main = (ROOT / "app/main.py").read_text(encoding="utf-8")
        self.assertIn("professional theme editor workspace", css)
        self.assertIn('version="1.7.0"', main)



    def test_form_position_and_frame_controls_are_fully_wired(self):
        html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
        js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
        css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
        for element_id in (
            "formIntegration", "formPlacement", "formPositionX", "formPositionY", "formWidth",
            "formFrameEnabled", "formBackgroundEnabled", "formBorderEnabled", "formPadding",
            "formRadius", "formContentAlignment",
        ):
            self.assertIn(f'id="{element_id}"', html)
        for mode in ("free", "flow", "panel-left", "panel-right"):
            self.assertIn(f'<option value="{mode}"', html)
        self.assertIn("function syncFormPositionFromMessage", js)
        self.assertIn("function applyFormPreset", js)
        self.assertIn("data-kts-form-drag", js)
        self.assertIn("kts-form-drag", js)
        self.assertIn("--mock-form-background:rgba(${surfaceRgb},${backgroundOpacity})", js)
        self.assertIn('.mock-login[data-form-integration="panel-left"]', css)
        self.assertIn('.mock-login[data-form-integration="panel-right"]', css)
        self.assertIn(".mock-form-drag-handle", css)
        self.assertIn("Espacement autour du contenu", html)

    def test_keycloakify_export_controls_and_status_are_wired(self):
        html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
        js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
        self.assertIn('data-export="keycloakify-jar"', html)
        self.assertIn('data-export="keycloakify-project"', html)
        self.assertIn('id="keycloakifyBuildStatus"', html)
        self.assertIn("/api/export/keycloakify-jar", js)
        self.assertIn("/api/export/keycloakify-project", js)
        self.assertIn("updateKeycloakifyExportStatus", js)
        self.assertIn("JAR natif reste disponible", js)

    def test_background_image_url_does_not_break_inline_style_attribute(self):
        js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("url('${d.backgroundImageData}')", js)
        self.assertIn("const safeImage = d.backgroundImageData ? `url('${d.backgroundImageData}')` : 'none';", js)
        self.assertIn("async function optimizeBackgroundImage", js)
        self.assertIn("createImageBitmap(file)", js)

    def test_canvas_uses_available_space_at_full_size_by_default(self):
        html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
        self.assertIn('<option value="100" selected>100 %</option>', html)
        self.assertIn('id="fitPreviewBtn"', html)
        self.assertIn("width: min(100%, 1500px)", css)
        self.assertIn("height: min(100%, 920px)", css)
        self.assertIn("--preview-scale: 1", css)
        self.assertIn("image-drop-active", css)

    def test_background_appearance_is_applied_to_email_preview(self):
        css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.mock-email\s*\{[^}]*background-image:[^}]*var\(--mock-bg-image")
        self.assertIn('.mock-email[data-bg-animation="slow-zoom"]', css)


if __name__ == "__main__":
    unittest.main()
