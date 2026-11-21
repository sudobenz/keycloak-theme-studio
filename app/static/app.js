(() => {
  'use strict';

  const STORAGE_KEY = 'keycloak-theme-studio.project.v2';
  const TYPES = ['login', 'account', 'admin', 'email', 'welcome'];
  const TYPE_LABELS = { login: 'Connexion', account: 'Compte', admin: 'Administration', email: 'E-mails', welcome: 'Accueil' };
  const DEFAULT_PARENTS = {
    '26': { login: 'keycloak.v2', account: 'keycloak.v3', admin: 'keycloak.v2', email: 'keycloak', welcome: 'keycloak' },
    '27': { login: 'keycloak.v3', account: 'keycloak.v3', admin: 'keycloak.v2', email: 'keycloak', welcome: 'keycloak' },
  };
  const DEFAULT_PROJECT = {
    schemaVersion: 2,
    name: 'identity-portal',
    displayName: 'Identity Portal',
    description: 'Thème de connexion personnalisé',
    targetVersion: '26.1.4',
    types: [...TYPES],
    parents: { ...DEFAULT_PARENTS['26'] },
    design: {
      primary: '#2563eb', accent: '#06b6d4', background: '#eef2f7', surface: '#ffffff',
      text: '#172033', muted: '#667085', fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif',
      radius: 16, cardWidth: 440, brand: 'Identity Portal', subtitle: 'Connectez-vous à votre espace',
      showBrand: true, showRememberMe: true, showForgotPassword: true, shadow: true, logoData: '', logoName: '',
      backgroundImageData: '', backgroundImageName: '', backgroundImagePosition: 'center', backgroundImageSize: 'cover',
      backgroundOverlay: 0, backgroundAnimation: 'none', backgroundAnimationDuration: 24,
      formPlacement: 'center', formIntegration: 'free', formPositionX: 50, formPositionY: 50,
      formWidth: 440, formFrameEnabled: true, formPadding: 32, formRadius: 16,
      formBackgroundEnabled: true, formBackgroundOpacity: 100, formBorderEnabled: true,
      formBorderColor: '#e6eaf0', formBorderWidth: 1, formShadow: true, formContentAlignment: 'left',
    },
    advanced: { customCss: '', files: {}, assets: {} },
  };
  const PRESETS = {
    corporate: { primary: '#2563eb', accent: '#06b6d4', background: '#eef2f7', surface: '#ffffff', text: '#172033', muted: '#667085' },
    midnight: { primary: '#8b5cf6', accent: '#22d3ee', background: '#101827', surface: '#1b2940', text: '#f1f5fb', muted: '#9cabc0' },
    forest: { primary: '#0f8a68', accent: '#a3c94e', background: '#eff5f0', surface: '#ffffff', text: '#1b342b', muted: '#6b8075' },
  };
  const FORM_PLACEMENTS = {
    center: [50, 50], left: [20, 50], right: [80, 50], top: [50, 22], bottom: [50, 78],
    'top-left': [20, 22], 'top-right': [80, 22], 'bottom-left': [20, 78], 'bottom-right': [80, 78],
  };
  const PREVIEW_PAGES = {
    login: [['login', 'Connexion'], ['register', 'Inscription'], ['reset', 'Mot de passe oublié'], ['otp', 'Code OTP'], ['error', 'Erreur']],
    account: [['login', 'Vue d’ensemble'], ['profile', 'Profil'], ['security', 'Sécurité'], ['sessions', 'Sessions']],
    admin: [['login', 'Tableau de bord'], ['users', 'Utilisateurs'], ['clients', 'Clients']],
    email: [['login', 'Vérification'], ['reset', 'Réinitialisation'], ['action', 'Action requise']],
    welcome: [['login', 'Accueil']],
  };

  const $ = (id) => document.getElementById(id);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const slugify = (value) => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[_\s]+/g, '-').replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 50) || 'custom-theme';
  let project = loadLocalProject();
  let activeView = 'design';
  let currentSourceFile = '__customCss';
  let currentSourceAsset = null;
  let currentDevice = 'desktop';
  let previewZoom = 1;
  let dirty = false;
  let sourceCommitTimer = null;
  let pendingProjectMode = 'create';

  function parentsForVersion(version) {
    const major = Number.parseInt(String(version).split('.')[0], 10) || 26;
    return clone(major >= 27 ? DEFAULT_PARENTS['27'] : DEFAULT_PARENTS['26']);
  }

  function normalizeFrontend(raw) {
    const incoming = raw && typeof raw === 'object' ? raw : {};
    const output = clone(DEFAULT_PROJECT);
    Object.assign(output, incoming);
    output.design = { ...clone(DEFAULT_PROJECT.design), ...(incoming.design || {}) };
    if (!('formPlacement' in (incoming.design || {})) && ('formPositionX' in (incoming.design || {}) || 'formPositionY' in (incoming.design || {}))) {
      output.design.formPlacement = 'custom';
    }
    // Older projects only carried cardWidth/shadow. Keep their appearance while
    // exposing the newer independent form controls.
    if (!('formWidth' in (incoming.design || {})) && 'cardWidth' in (incoming.design || {})) output.design.formWidth = incoming.design.cardWidth;
    if (!('formShadow' in (incoming.design || {})) && 'shadow' in (incoming.design || {})) output.design.formShadow = incoming.design.shadow;
    if (!['free', 'flow', 'panel-left', 'panel-right'].includes(output.design.formIntegration)) output.design.formIntegration = 'free';
    output.design.formWidth = Math.max(240, Math.min(1200, Number(output.design.formWidth) || 440));
    output.design.cardWidth = output.design.formWidth;
    output.design.formPositionX = Math.max(0, Math.min(100, Number(output.design.formPositionX) || 0));
    output.design.formPositionY = Math.max(0, Math.min(100, Number(output.design.formPositionY) || 0));
    output.advanced = { ...clone(DEFAULT_PROJECT.advanced), ...(incoming.advanced || {}) };
    output.advanced.files = { ...(incoming.advanced?.files || {}) };
    output.advanced.assets = { ...(incoming.advanced?.assets || {}) };
    output.types = Array.isArray(incoming.types) ? [...new Set(incoming.types.filter((type) => TYPES.includes(type)))] : [...TYPES];
    if (!output.types.length) output.types = ['login'];
    output.name = slugify(output.name || output.displayName);
    output.displayName = String(output.displayName || output.design.brand || output.name).slice(0, 80);
    output.targetVersion = String(output.targetVersion || '26.1.4');
    output.parents = { ...parentsForVersion(output.targetVersion), ...(incoming.parents || {}) };
    return output;
  }

  function loadLocalProject() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('keycloak-theme-studio.project.v1');
      return normalizeFrontend(saved ? JSON.parse(saved) : DEFAULT_PROJECT);
    } catch {
      return clone(DEFAULT_PROJECT);
    }
  }

  function setSaveState(message, isDirty = dirty) {
    const node = $('saveState');
    if (!node) return;
    node.textContent = message;
    if (node.previousElementSibling) node.previousElementSibling.style.background = isDirty ? '#b98739' : '#38a77c';
    const workspaceStatus = $('workspaceStatus');
    if (workspaceStatus) workspaceStatus.textContent = message;
  }

  function persistLocal(message = 'Modifications locales') {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(project));
      dirty = true;
      setSaveState(message, true);
    } catch (error) {
      dirty = true;
      setSaveState('Stockage navigateur indisponible', true);
      toast(`Sauvegarde locale impossible : ${friendlyError(error)}`, 'error');
    }
  }

  function toast(message, kind = 'success') {
    const region = $('toastRegion');
    if (!region) return;
    const node = document.createElement('div');
    node.className = `toast ${kind}`;
    node.textContent = message;
    region.appendChild(node);
    window.setTimeout(() => node.remove(), 3600);
  }

  function friendlyError(error) {
    let message = String(error?.message || error || 'Erreur inconnue');
    try {
      const parsed = JSON.parse(message);
      message = parsed.detail || parsed.message || message;
    } catch { /* Keep the original message. */ }
    return message.replace(/^Error:\s*/, '').slice(0, 260);
  }

  function updateProjectIdentity() {
    $('sidebarProjectName').textContent = project.name;
    $('sidebarProjectMeta').textContent = `${project.types.length} espace${project.types.length > 1 ? 's' : ''} activé${project.types.length > 1 ? 's' : ''}`;
    $('breadcrumbName').textContent = project.name;
    $('themeName').value = project.name;
    $('activeTypeCount').textContent = `${project.types.length} espace${project.types.length > 1 ? 's' : ''} sélectionné${project.types.length > 1 ? 's' : ''}`;
    $('componentBrandPreview').textContent = project.design.brand;
  }

  function syncControls() {
    currentSourceAsset = null;
    const d = project.design;
    ['brand', 'subtitle', 'primary', 'accent', 'background', 'surface', 'text', 'muted', 'fontFamily', 'radius', 'cardWidth', 'showBrand', 'showRememberMe', 'showForgotPassword', 'shadow', 'backgroundImagePosition', 'backgroundImageSize', 'backgroundOverlay', 'backgroundAnimation', 'backgroundAnimationDuration', 'formPlacement', 'formIntegration', 'formPositionX', 'formPositionY', 'formWidth', 'formFrameEnabled', 'formBackgroundEnabled', 'formBackgroundOpacity', 'formBorderEnabled', 'formBorderColor', 'formBorderWidth', 'formShadow', 'formPadding', 'formRadius', 'formContentAlignment'].forEach((key) => {
      const element = $(key);
      if (!element) return;
      if (element.type === 'checkbox') element.checked = Boolean(d[key]);
      else element.value = d[key];
    });
    ['primary', 'accent', 'background', 'surface', 'text', 'muted'].forEach((key) => { $(`${key}Hex`).textContent = d[key].toUpperCase(); });
    $('radiusValue').textContent = `${d.radius} px`;
    $('targetVersion').value = ['26.1.4', '26.4.0', '26.5.0', '26.6.0', '27.0.0'].includes(project.targetVersion) ? project.targetVersion : 'custom';
    $('removeLogoBtn').hidden = !d.logoData;
    $('logoUploadTitle').textContent = d.logoName || (d.logoData ? 'Logo chargé' : 'Ajouter un logo');
    updateBackgroundImageControls();
    $('backgroundOverlayValue').textContent = `${d.backgroundOverlay}%`;
    $('backgroundAnimationDurationValue').textContent = `${d.backgroundAnimationDuration} s`;
    updateFormControlsState();
    updateFormRangeOutputs();
    applyPreviewZoom();
    document.querySelectorAll('[data-type]').forEach((checkbox) => { checkbox.checked = project.types.includes(checkbox.dataset.type); });
    updateProjectIdentity();
    renderParents();
    if (currentSourceFile !== '__customCss' && !Object.prototype.hasOwnProperty.call(project.advanced.files, currentSourceFile)) currentSourceFile = '__customCss';
    renderSourceFiles();
    $('sourceEditor').value = currentSourceFile === '__customCss' ? project.advanced.customCss : (project.advanced.files[currentSourceFile] || '');
    updateSourceEditorLabel();
    updateSourceLineCount();
    updatePreviewPageOptions();
    renderPreview();
  }

  function setDesign(key, value) {
    project.design[key] = value;
    if (key === 'formWidth') project.design.cardWidth = value;
    if (key === 'cardWidth') project.design.formWidth = value;
    if (key === 'formShadow') project.design.shadow = value;
    if (key === 'formPositionX' || key === 'formPositionY') project.design.formPlacement = 'custom';
    persistLocal();
    if (['primary', 'accent', 'background', 'surface', 'text', 'muted'].includes(key)) $(`${key}Hex`).textContent = value.toUpperCase();
    if (key === 'radius') $('radiusValue').textContent = `${value} px`;
    if (key === 'backgroundOverlay') $('backgroundOverlayValue').textContent = `${value}%`;
    if (key === 'backgroundAnimationDuration') $('backgroundAnimationDurationValue').textContent = `${value} s`;
    if (key === 'backgroundImageData' || key === 'backgroundImageName') updateBackgroundImageControls();
    if (key === 'formBorderColor') $('formBorderColorHex').textContent = value.toUpperCase();
    updateFormControlsState();
    updateFormRangeOutputs();
    if (key === 'brand') { $('componentBrandPreview').textContent = value; project.displayName = value || project.name; }
    renderPreview();
  }

  function updateBackgroundImageControls() {
    const d = project.design;
    const preview = $('backgroundImagePreview');
    const name = $('backgroundImageName');
    const remove = $('removeBackgroundImageBtn');
    if (!preview || !name || !remove) return;
    preview.style.backgroundImage = d.backgroundImageData ? `url("${d.backgroundImageData}")` : 'none';
    preview.classList.toggle('has-image', Boolean(d.backgroundImageData));
    name.textContent = d.backgroundImageData ? (d.backgroundImageName || 'Image chargée') : 'Aucune image sélectionnée';
    remove.hidden = !d.backgroundImageData;
  }

  function applyPreviewZoom() {
    const control = $('previewZoom');
    if (control) previewZoom = Number(control.value || 75) / 100;
    const stage = $('previewStage');
    if (stage) stage.style.setProperty('--preview-scale', String(previewZoom));
    if ($('previewZoomValue')) $('previewZoomValue').textContent = `${Math.round(previewZoom * 100)} %`;
  }

  function navigateInspector(sectionId, button) {
    const target = $(sectionId);
    const panel = document.querySelector('#designInspector .inspector-scroll');
    if (!target || !panel) return;
    if (activeView !== 'design') setActiveView('design');
    const scrollToTarget = () => {
      const top = target.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop - 12;
      panel.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
      document.querySelectorAll('[data-inspector-section]').forEach((item) => {
        const active = item === button;
        item.classList.toggle('active', active);
        if (active) item.setAttribute('aria-current', 'location');
        else item.removeAttribute('aria-current');
      });
      target.classList.add('section-focus');
      window.setTimeout(() => target.classList.remove('section-focus'), 850);
    };
    window.requestAnimationFrame(scrollToTarget);
  }

  function updatePreviewPageOptions() {
    const type = $('previewType').value || 'login';
    const choices = PREVIEW_PAGES[type] || PREVIEW_PAGES.login;
    const previous = $('previewPage').value;
    $('previewPage').innerHTML = choices.map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
    $('previewPage').value = choices.some(([value]) => value === previous) ? previous : choices[0][0];
    $('previewPage').disabled = choices.length <= 1;
    $('previewPage').style.opacity = choices.length <= 1 ? '.45' : '1';
    document.querySelectorAll('[data-preview-space]').forEach((button) => {
      button.classList.toggle('active', button.dataset.previewSpace === type);
    });
  }

  function previewBrand(d) {
    const mark = d.logoData
      ? `<img src="${d.logoData}" alt="Logo ${escapeHtml(d.brand)}">`
      : `<span class="mock-brand-mark">${escapeHtml((d.brand || 'K').charAt(0).toUpperCase())}</span>`;
    return d.showBrand ? `<div class="mock-brand">${mark}<span class="mock-brand-label">${escapeHtml(d.brand)}</span></div>` : '';
  }

  function formPoint(d) {
    if (FORM_PLACEMENTS[d.formPlacement]) return FORM_PLACEMENTS[d.formPlacement];
    return [Math.max(0, Math.min(100, Number(d.formPositionX ?? 50))), Math.max(0, Math.min(100, Number(d.formPositionY ?? 50)))];
  }

  function updateFormRangeOutputs() {
    const d = project.design;
    const [x, y] = formPoint(d);
    const outputs = {
      formPositionXValue: `${x} %`, formPositionYValue: `${y} %`, formWidthValue: `${d.formWidth} px`,
      formBackgroundOpacityValue: `${d.formBackgroundOpacity} %`, formBorderWidthValue: `${d.formBorderWidth} px`,
      formPaddingValue: `${d.formPadding} px`, formRadiusValue: `${d.formRadius} px`,
    };
    Object.entries(outputs).forEach(([id, value]) => { if ($(id)) $(id).textContent = value; });
    if ($('formBorderColorHex')) $('formBorderColorHex').textContent = String(d.formBorderColor || '#e6eaf0').toUpperCase();
  }

  function updateFormControlsState() {
    const d = project.design;
    if ($('formFrameControls')) $('formFrameControls').disabled = !d.formFrameEnabled;
    if ($('formPositionControls')) $('formPositionControls').hidden = d.formIntegration !== 'free';
    if ($('formIntegrationHelp')) {
      const help = {
        free: 'Le formulaire est positionné librement sur la page. Déplacez-le dans l’aperçu ou utilisez les coordonnées.',
        flow: 'Le formulaire reste dans le flux de la page. Sa hauteur s’adapte au contenu, sans position absolue.',
        'panel-left': 'Le formulaire est aligné sur le bord gauche et reste centré verticalement dans la page.',
        'panel-right': 'Le formulaire est aligné sur le bord droit et reste centré verticalement dans la page.',
      };
      $('formIntegrationHelp').textContent = help[d.formIntegration] || help.free;
    }
    document.querySelectorAll('[data-form-preset]').forEach((button) => {
      const active = button.dataset.formPreset === (d.formFrameEnabled ? 'card' : 'bare');
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function applyFormPreset(preset) {
    if (preset === 'bare') {
      project.design.formFrameEnabled = false;
    } else {
      Object.assign(project.design, {
        formFrameEnabled: true, formBackgroundEnabled: true, formBackgroundOpacity: 100,
        formBorderEnabled: true, formBorderWidth: 1, formShadow: true, formPadding: 32, formRadius: 16,
      });
    }
    persistLocal(preset === 'bare' ? 'Cadre du formulaire retiré' : 'Cadre du formulaire rétabli');
    syncControls();
    toast(preset === 'bare' ? 'Le formulaire est maintenant sans cadre.' : 'Le cadre du formulaire est rétabli.');
  }

  function syncFormPositionFromMessage(message) {
    const x = Math.max(0, Math.min(100, Math.round(Number(message.x) || 0)));
    const y = Math.max(0, Math.min(100, Math.round(Number(message.y) || 0)));
    project.design.formIntegration = 'free';
    project.design.formPlacement = 'custom';
    project.design.formPositionX = x;
    project.design.formPositionY = y;
    $('formIntegration').value = 'free';
    $('formPlacement').value = 'custom';
    $('formPositionX').value = String(x);
    $('formPositionY').value = String(y);
    updateFormControlsState();
    updateFormRangeOutputs();
    if (message.phase === 'end') persistLocal('Position du formulaire enregistrée');
  }

  function previewLogin(d, page) {
    let title = 'Bienvenue';
    let subtitle = d.subtitle;
    let fields = '<div class="mock-field"><label>Adresse e-mail ou identifiant</label><div class="mock-input pf-v6-c-form-control">nom.utilisateur@entreprise.fr</div></div><div class="mock-field"><label>Mot de passe</label><div class="mock-input pf-v6-c-form-control">••••••••••••</div></div>';
    let options = `<div class="mock-options">${d.showRememberMe ? '<span class="mock-check">Se souvenir de moi</span>' : '<span></span>'}${d.showForgotPassword ? '<button class="mock-link mock-nav" data-preview-nav="reset">Mot de passe oublié ?</button>' : ''}</div>`;
    let action = 'Se connecter';
    let extra = '<div class="mock-divider"><span>OU</span></div><div class="mock-social">Continuer avec un fournisseur d’identité</div><div class="mock-footnote">Pas encore de compte ? <button class="mock-link mock-nav" data-preview-nav="register">Créer un compte</button></div>';
    if (page === 'register') {
      title = 'Créer un compte'; subtitle = 'Renseignez les informations ci-dessous pour commencer.';
      fields = '<div class="mock-field"><label>Prénom</label><div class="mock-input pf-v6-c-form-control">Alex</div></div><div class="mock-field"><label>Nom</label><div class="mock-input pf-v6-c-form-control">Martin</div></div><div class="mock-field"><label>Adresse e-mail</label><div class="mock-input pf-v6-c-form-control">alex.martin@entreprise.fr</div></div><div class="mock-field"><label>Mot de passe</label><div class="mock-input pf-v6-c-form-control">••••••••••••</div></div>';
      options = ''; action = 'Créer mon compte'; extra = '<div class="mock-footnote">Vous avez déjà un compte ? <button class="mock-link mock-nav" data-preview-nav="login">Se connecter</button></div>';
    } else if (page === 'reset') {
      title = 'Mot de passe oublié'; subtitle = 'Saisissez votre adresse e-mail pour recevoir un lien de réinitialisation.';
      fields = '<div class="mock-field"><label>Adresse e-mail</label><div class="mock-input pf-v6-c-form-control">nom.utilisateur@entreprise.fr</div></div>';
      options = ''; action = 'Envoyer le lien'; extra = '<div class="mock-footnote"><button class="mock-link mock-nav" data-preview-nav="login">← Retour à la connexion</button></div>';
    } else if (page === 'otp') {
      title = 'Vérification en deux étapes'; subtitle = 'Saisissez le code affiché par votre application d’authentification.';
      fields = '<div class="mock-field"><label>Code à usage unique</label><div class="mock-input" style="letter-spacing:7px;justify-content:center">• • • • • •</div></div>';
      options = '<div class="mock-options"><span>Code à 6 chiffres</span><span class="mock-link">Autre méthode</span></div>'; action = 'Vérifier'; extra = '<div class="mock-footnote">Ne partagez jamais ce code.</div>';
    } else if (page === 'error') {
      title = 'Connexion impossible'; subtitle = 'Les informations saisies ne permettent pas de vous authentifier.';
      fields = '<div class="mock-success" style="color:#c8575d;background:#fff0f0;padding:10px;border-radius:6px">Identifiant ou mot de passe incorrect. Veuillez réessayer.</div>';
      options = ''; action = 'Réessayer'; extra = '<div class="mock-footnote"><button class="mock-link mock-nav" data-preview-nav="reset">Mot de passe oublié ?</button></div>';
    }
    return `<div class="mock-login login-pf-page" data-bg-animation="${escapeHtml(d.backgroundAnimation || 'none')}" data-form-integration="${escapeHtml(d.formIntegration || 'free')}" style="${previewVars(d)}"><div class="mock-layout">${previewBrand(d)}<div class="mock-card card-pf kcFormCardClass" data-kts-form-card><button class="mock-form-drag-handle" type="button" data-kts-form-drag aria-label="Déplacer le formulaire"><span aria-hidden="true">⠿</span> Déplacer</button><h2 id="kc-page-title" class="pf-v6-c-title">${escapeHtml(title)}</h2><p class="mock-subtitle">${escapeHtml(subtitle)}</p>${fields}${options}<div id="kc-login" class="mock-submit pf-v6-c-button pf-m-primary">${escapeHtml(action)}</div>${extra}</div><div class="mock-footnote">© ${new Date().getFullYear()} ${escapeHtml(d.brand)} · Accès sécurisé</div></div></div>`;
  }

  function previewVars(d) {
    const safeFont = String(d.fontFamily).replace(/[;{}<>]/g, '');
    // A single quote is intentional: previewVars is inserted into a double-quoted HTML style attribute.
    const safeImage = d.backgroundImageData ? `url('${d.backgroundImageData}')` : 'none';
    const [formX, formY] = formPoint(d);
    const frame = Boolean(d.formFrameEnabled);
    const backgroundOpacity = frame && d.formBackgroundEnabled ? Number(d.formBackgroundOpacity ?? 100) / 100 : 0;
    const borderWidth = frame && d.formBorderEnabled ? Number(d.formBorderWidth ?? 1) : 0;
    const shadow = frame && d.formShadow ? '0 18px 50px rgba(18,33,55,.15)' : 'none';
    const surface = /^#[0-9a-f]{6}$/i.test(String(d.surface || '')) ? d.surface : '#ffffff';
    const surfaceRgb = [1, 3, 5].map((index) => Number.parseInt(surface.slice(index, index + 2), 16)).join(',');
    return `--mock-bg:${d.background};--mock-primary:${d.primary};--mock-accent:${d.accent};--mock-surface:${d.surface};--mock-text:${d.text};--mock-muted:${d.muted};--mock-radius:${d.radius}px;--mock-width:${d.cardWidth}px;--mock-font:${escapeHtml(safeFont)};--mock-shadow:${d.shadow ? '0 18px 50px rgba(18,33,55,.15)' : 'none'};--mock-bg-image:${safeImage};--mock-bg-overlay:${Number(d.backgroundOverlay || 0) / 100};--mock-bg-position:${escapeHtml(d.backgroundImagePosition || 'center')};--mock-bg-size:${escapeHtml(d.backgroundImageSize || 'cover')};--mock-bg-duration:${Number(d.backgroundAnimationDuration || 24)}s;--mock-form-x:${formX}%;--mock-form-y:${formY}%;--mock-form-width:${Number(d.formWidth || d.cardWidth || 440)}px;--mock-form-padding:${Number(d.formPadding ?? 32)}px;--mock-form-radius:${frame ? Number(d.formRadius || 0) : 0}px;--mock-form-background:rgba(${surfaceRgb},${backgroundOpacity});--mock-form-border:${borderWidth}px solid ${d.formBorderColor || '#e6eaf0'};--mock-form-shadow:${shadow};--mock-form-text-align:${escapeHtml(d.formContentAlignment || 'left')}`;
  }

  function renderPreview() {
    const d = project.design;
    const type = $('previewType').value || 'login';
    const page = $('previewPage').value || 'login';
    const vars = previewVars(d);
    let html = '';
    if (type === 'login') {
      html = previewLogin(d, page);
    } else if (type === 'email') {
      const title = page === 'reset' ? 'Réinitialisez votre mot de passe' : page === 'action' ? 'Action requise sur votre compte' : 'Confirmez votre adresse e-mail';
      const action = page === 'reset' ? 'Réinitialiser mon mot de passe' : page === 'action' ? 'Continuer' : 'Vérifier mon adresse e-mail';
      html = `<div class="mock-email" style="${vars}"><div class="mock-email-card"><div class="mock-email-head"><div class="mock-email-logo">${escapeHtml((d.brand || 'K').charAt(0).toUpperCase())}</div><h2>${escapeHtml(d.brand)}</h2></div><h3>${title}</h3><p>Bonjour Alex,</p><p>Pour terminer la configuration de votre compte, veuillez utiliser le bouton ci-dessous.</p><div class="mock-email-btn">${action}</div><p>Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer ce message.</p><small>Message envoyé automatiquement par ${escapeHtml(d.brand)}.</small></div></div>`;
    } else if (type === 'admin' || type === 'account') {
      const admin = type === 'admin';
      const title = admin ? ({ users: 'Users', clients: 'Clients' }[page] || 'Welcome to Keycloak') : ({ profile: 'Personal information', security: 'Account security', sessions: 'Sessions' }[page] || 'My account');
      const nav = admin ? ['Dashboard', 'Manage realms', 'Users', 'Groups', 'Clients', 'Sessions', 'Events'] : ['Personal info', 'Account security', 'Signing in', 'Applications', 'Devices'];
      const rows = admin ? ['Administrator updated realm settings', 'New user registered', 'Client configuration modified'] : ['First name　　Alex', 'Last name　　Martin', 'Email　　alex.martin@entreprise.fr', 'Username　　alex.martin'];
      html = `<div class="mock-console pf-v6-c-page" data-bg-animation="${escapeHtml(d.backgroundAnimation || 'none')}" style="${vars}"><aside class="mock-console-side"><div class="mock-console-brand">◈ ${escapeHtml(d.brand)}</div><div class="mock-console-nav">${nav.map((item) => `<span>${item}</span>`).join('')}</div></aside><div class="mock-console-main pf-v6-c-page__main-section"><div class="mock-console-top"><span>${admin ? 'Master realm / Dashboard' : 'My account'}</span><span>${admin ? 'Administrator' : 'Alex Martin'}　⌄</span></div><h2>${title}</h2><p>${admin ? 'Manage your identity and access infrastructure.' : 'Manage your profile information and account preferences.'}</p>${admin ? '<div class="mock-metric-row"><div class="mock-metric"><b>1,248</b><span>Users</span></div><div class="mock-metric"><b>18</b><span>Clients</span></div><div class="mock-metric"><b>12</b><span>Identity providers</span></div></div>' : ''}<div class="mock-table"><div><b>${admin ? 'Recent activity' : 'Profile details'}</b></div>${rows.map((row) => `<div>${row}</div>`).join('')}</div></div></div>`;
    } else {
      html = `<div class="mock-login" data-bg-animation="${escapeHtml(d.backgroundAnimation || 'none')}" data-form-integration="${escapeHtml(d.formIntegration || 'free')}" style="${vars}"><div class="mock-layout">${previewBrand(d)}<div class="mock-card card-pf kcFormCardClass" data-kts-form-card style="text-align:center"><button class="mock-form-drag-handle" type="button" data-kts-form-drag aria-label="Déplacer le formulaire"><span aria-hidden="true">⠿</span> Déplacer</button><div style="font-size:33px;color:var(--mock-primary);margin-bottom:10px">◈</div><h2 id="kc-page-title" class="pf-v6-c-title">${escapeHtml(d.brand)}</h2><p class="mock-subtitle">${escapeHtml(d.subtitle)}</p><div id="kc-login" class="mock-submit pf-v6-c-button pf-m-primary">Accéder au compte</div><div class="mock-footnote">Identity and access management</div></div></div></div>`;
    }
    const typeCss = Object.entries(project.advanced.files || {}).filter(([path]) => path.startsWith(`${type}/`) && path.toLowerCase().endsWith('.css')).map(([, content]) => content).join('\n');
    const customCss = `${project.advanced.customCss || ''}\n${typeCss}`.replace(/<\/style/gi, '<\\/style');
    const previewDocument = `<!doctype html><html lang="fr" style="height:100%"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/static/styles.css"><style>${customCss}</style></head><body class="kcBodyClass" style="height:100%;margin:0;min-height:100%;overflow:auto">${html}<script>
      document.addEventListener('click',function(event){var control=event.target.closest('[data-preview-nav]');if(control){event.preventDefault();parent.postMessage({type:'kts-preview-nav',page:control.getAttribute('data-preview-nav')},'*');}});
      (function(){var handle=null,root=null,card=null,rect=null,offsetX=0,offsetY=0;function position(event,phase){if(!root||!rect||!rect.width||!rect.height)return;var x=Math.max(0,Math.min(100,Math.round((event.clientX-offsetX-rect.left)/rect.width*100)));var y=Math.max(0,Math.min(100,Math.round((event.clientY-offsetY-rect.top)/rect.height*100)));root.dataset.formIntegration='free';root.style.setProperty('--mock-form-x',x+'%');root.style.setProperty('--mock-form-y',y+'%');parent.postMessage({type:'kts-form-drag',x:x,y:y,phase:phase},'*');}document.addEventListener('pointerdown',function(event){var target=event.target.closest('[data-kts-form-drag]');if(!target)return;root=document.querySelector('.mock-login');card=document.querySelector('[data-kts-form-card]');if(!root||!card)return;event.preventDefault();handle=target;rect=root.getBoundingClientRect();var cardRect=card.getBoundingClientRect();offsetX=event.clientX-(cardRect.left+cardRect.width/2);offsetY=event.clientY-(cardRect.top+cardRect.height/2);try{handle.setPointerCapture(event.pointerId);}catch(e){}position(event,'move');});document.addEventListener('pointermove',function(event){if(handle)position(event,'move');});document.addEventListener('pointerup',function(event){if(!handle)return;position(event,'end');handle=null;root=null;card=null;rect=null;offsetX=0;offsetY=0;});document.addEventListener('pointercancel',function(event){if(!handle)return;position(event,'end');handle=null;root=null;card=null;rect=null;offsetX=0;offsetY=0;});})();
    <\/script></body></html>`;
    $('previewViewport').srcdoc = previewDocument;
    const typeLabels = { login: 'CONNEXION', account: 'COMPTE', admin: 'ADMINISTRATION', email: 'E-MAILS', welcome: 'ACCUEIL' };
    const pageLabels = { login: 'CONNEXION', register: 'INSCRIPTION', reset: 'MOT DE PASSE OUBLIÉ', otp: 'VÉRIFICATION', error: 'ERREUR', action: 'ACTION REQUISE', profile: 'PROFIL', security: 'SÉCURITÉ', sessions: 'SESSIONS', users: 'UTILISATEURS', clients: 'CLIENTS' };
    $('previewPageLabel').textContent = `${typeLabels[type] || type.toUpperCase()} / ${pageLabels[page] || page.toUpperCase()}`;
  }

  function setActiveView(view) {
    if (!['design', 'components', 'sources', 'compat'].includes(view)) return;
    activeView = view;
    document.querySelectorAll('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
    document.querySelectorAll('.view').forEach((node) => node.classList.toggle('active', node.id === `view-${view}`));
    const titles = {
      design: ['Votre thème', 'Apparence du thème', 'Personnalisez l’écran de connexion et les autres pages de votre instance.'],
      components: ['Bibliothèque', 'Composants', 'Éléments visuels utilisés par les pages du thème.'],
      sources: ['Édition avancée', 'Fichiers du thème', 'CSS, JavaScript, propriétés et templates FreeMarker.'],
      compat: ['Configuration', 'Cible Keycloak', 'Types de thèmes et thèmes parents utilisés à la génération.'],
    };
    $('viewEyebrow').textContent = titles[view][0];
    $('viewTitle').textContent = titles[view][1];
    const description = $('viewDescription');
    if (description) description.textContent = titles[view][2];
    document.body.dataset.activeView = view;
  }

  function renderSourceFiles() {
    const files = Object.keys(project.advanced.files || {}).sort();
    const assets = Object.keys(project.advanced.assets || {}).sort();
    $('customFileList').innerHTML = files.map((path) => `<button class="file-item ${!currentSourceAsset && currentSourceFile === path ? 'active' : ''}" data-file="${escapeHtml(path)}"><span class="file-type custom-type">${escapeHtml(path.split('.').pop().slice(0, 1).toUpperCase())}</span><span>${escapeHtml(path)}</span><small>${escapeHtml(path.split('.').pop().toUpperCase())}</small></button>`).join('');
    $('customAssetList').innerHTML = assets.map((path) => `<button class="file-item asset-file-item ${currentSourceAsset === path ? 'active' : ''}" data-asset="${escapeHtml(path)}"><span class="file-type image-type">IMG</span><span>${escapeHtml(path)}</span><small>ASSET</small></button>`).join('');
    $('fileCount').textContent = String(files.length + assets.length + 1);
    document.querySelectorAll('[data-file]').forEach((button) => { button.onclick = () => selectSourceFile(button.dataset.file); });
    document.querySelectorAll('[data-asset]').forEach((button) => { button.onclick = () => selectSourceAsset(button.dataset.asset); });
    $('deleteFileBtn').disabled = currentSourceFile === '__customCss' && !currentSourceAsset;
    $('downloadAssetBtn').hidden = !currentSourceAsset;
    updateSourceEditorLabel();
  }

  function flushPendingSourceEdit() {
    if (sourceCommitTimer) {
      window.clearTimeout(sourceCommitTimer);
      sourceCommitTimer = null;
      applySourceValue(false);
    }
  }

  function selectSourceFile(path) {
    flushPendingSourceEdit();
    currentSourceAsset = null;
    currentSourceFile = path;
    $('sourceEditor').value = path === '__customCss' ? project.advanced.customCss : (project.advanced.files[path] || '');
    renderSourceFiles();
    updateSourceLineCount();
    $('editorState').textContent = 'Prêt';
  }

  function selectSourceAsset(path) {
    flushPendingSourceEdit();
    currentSourceAsset = path;
    $('sourceEditor').value = `Ressource binaire importée : ${path}\n\nCette ressource est conservée sans transformation et incluse dans les exports ZIP/JAR.`;
    renderSourceFiles();
    $('sourceEditor').readOnly = true;
    updateSourceLineCount();
    $('editorState').textContent = 'Ressource binaire';
  }

  function updateSourceEditorLabel() {
    const name = currentSourceFile === '__customCss' ? 'custom.css' : currentSourceFile;
    $('activeFileName').textContent = name;
    $('editorLanguage').textContent = currentSourceAsset ? 'BINARY ASSET' : currentSourceFile === '__customCss' || currentSourceFile.endsWith('.css') ? 'CSS' : currentSourceFile.endsWith('.ftl') ? 'FreeMarker' : currentSourceFile.endsWith('.js') ? 'JavaScript' : currentSourceFile.endsWith('.properties') ? 'Properties' : 'TEXT';
    $('sourceEditor').readOnly = Boolean(currentSourceAsset);
    document.querySelectorAll('[data-file]').forEach((button) => button.classList.toggle('active', button.dataset.file === currentSourceFile));
  }

  function updateSourceLineCount() {
    const lineCount = $('sourceEditor').value.split('\n').length;
    $('sourceLineCount').textContent = `${lineCount} ligne${lineCount > 1 ? 's' : ''}`;
  }

  function applySourceValue(showToast = true) {
    if (currentSourceAsset) return;
    const value = $('sourceEditor').value;
    if (currentSourceFile === '__customCss') project.advanced.customCss = value;
    else project.advanced.files[currentSourceFile] = value;
    persistLocal();
    $('editorState').textContent = 'Appliqué';
    updateSourceLineCount();
    renderPreview();
    if (showToast) toast('Source appliquée au projet.');
  }

  function validateNewFilePath() {
    const type = $('newFileType').value;
    let relative = $('newFilePath').value.trim().replace(/\\/g, '/').replace(/^\/+/, '');
    if (relative.startsWith(`${type}/`)) relative = relative.slice(type.length + 1);
    const segments = relative.split('/');
    if (!relative || segments.some((segment) => !segment || segment === '.' || segment === '..') || !/^[A-Za-z0-9._/-]+$/.test(relative)) return null;
    if (!relative.includes('.')) return null;
    return `${type}/${relative}`;
  }

  function createFile() {
    const path = validateNewFilePath();
    if (!path) { toast('Chemin de fichier invalide. Exemple : resources/css/custom.css', 'error'); return; }
    if (Object.prototype.hasOwnProperty.call(project.advanced.files, path) || Object.prototype.hasOwnProperty.call(project.advanced.assets, path)) {
      toast('Ce fichier existe déjà.', 'error'); return;
    }
    const template = $('newFileTemplate').value;
    const snippets = {
      blank: '',
      css: '/* Custom Keycloak theme styles */\n.kts-custom-component {\n  /* Add your styles here */\n}\n',
      js: "/* Custom JavaScript - loaded by the theme where supported */\ndocument.addEventListener('DOMContentLoaded', () => {\n  // Add your enhancement here.\n});\n",
      ftl: '<#-- Custom FreeMarker template. Check Keycloak context variables before use. -->\n<div class="kts-custom-component">\n  ${msg("doLogIn")}\n</div>\n',
      messages: '# French messages\nktsCustomLabel=Libellé personnalisé\n',
    };
    project.advanced.files[path] = snippets[template] ?? '';
    persistLocal('Nouveau fichier ajouté');
    $('fileModal').hidden = true;
    selectSourceFile(path);
    setActiveView('sources');
    toast(`Fichier ${path} ajouté.`);
  }

  function removeCurrentFile() {
    flushPendingSourceEdit();
    if (currentSourceFile === '__customCss' && !currentSourceAsset) return;
    const path = currentSourceAsset || currentSourceFile;
    if (!window.confirm(`Supprimer le fichier ${path} du projet ?`)) return;
    if (currentSourceAsset) delete project.advanced.assets[currentSourceAsset];
    else delete project.advanced.files[currentSourceFile];
    currentSourceAsset = null;
    currentSourceFile = '__customCss';
    persistLocal('Fichier supprimé');
    selectSourceFile('__customCss');
    toast('Fichier supprimé.');
  }

  function renderParents() {
    const body = $('parentTableBody');
    body.innerHTML = project.types.map((type) => {
      const parent = project.parents[type] || parentsForVersion(project.targetVersion)[type];
      const method = ['login', 'email', 'welcome'].includes(type) ? 'FreeMarker / ressources' : 'Application React / CSS';
      return `<tr><td>${TYPE_LABELS[type]}</td><td><input class="parent-input" data-parent="${type}" value="${escapeHtml(parent)}" maxlength="80" spellcheck="false"></td><td class="type-method">${method}</td></tr>`;
    }).join('') || '<tr><td colspan="3">Sélectionnez au moins un type de thème.</td></tr>';
    body.querySelectorAll('[data-parent]').forEach((input) => input.addEventListener('change', () => {
      project.parents[input.dataset.parent] = input.value.trim();
      persistLocal();
    }));
    $('versionSummary').textContent = `Keycloak ${project.targetVersion}`;
    if ($('statusVersion')) $('statusVersion').textContent = project.targetVersion.startsWith('26.') ? '26.x' : project.targetVersion.startsWith('27.') ? '27.x' : project.targetVersion;
  }

  function changeTargetVersion(value) {
    const oldDefaults = parentsForVersion(project.targetVersion);
    const newVersion = value === 'custom' ? window.prompt('Version Keycloak cible (ex. 26.1.4 ou 27.0.0) :', project.targetVersion) : value;
    if (!newVersion) { $('targetVersion').value = project.targetVersion; return; }
    project.targetVersion = newVersion.trim();
    const newDefaults = parentsForVersion(project.targetVersion);
    TYPES.forEach((type) => { if (!project.parents[type] || project.parents[type] === oldDefaults[type]) project.parents[type] = newDefaults[type]; });
    persistLocal();
    renderParents();
    toast(`Version cible : Keycloak ${project.targetVersion}`);
  }

  function setTypes() {
    const selected = [...document.querySelectorAll('[data-type]:checked')].map((checkbox) => checkbox.dataset.type);
    if (!selected.length) {
      document.querySelector('[data-type="login"]').checked = true;
      toast('Au moins un type de thème est nécessaire.', 'error');
      return;
    }
    project.types = selected;
    persistLocal();
    updateProjectIdentity();
    renderParents();
    renderPreview();
  }

  function applyPreset(name) {
    Object.assign(project.design, PRESETS[name] || PRESETS.corporate);
    persistLocal();
    syncControls();
    toast(`Palette ${name} appliquée.`);
  }

  async function apiJson(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) throw new Error(typeof payload === 'string' ? payload : (payload.detail || `Erreur HTTP ${response.status}`));
    return payload;
  }

  async function saveProject() {
    flushPendingSourceEdit();
    try {
      project.name = slugify($('themeName').value);
      project.displayName = project.design.brand || project.name;
      const result = await apiJson('/api/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project }) });
      dirty = false;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(project));
      setSaveState('Enregistré sur le serveur', false);
      updateProjectIdentity();
      toast(`Projet « ${result.id} » enregistré sur le serveur.`);
    } catch (error) {
      toast(`Échec de l'enregistrement : ${friendlyError(error)}`, 'error');
    }
  }

  async function validateProject() {
    flushPendingSourceEdit();
    try {
      const result = await apiJson('/api/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project }) });
      renderValidation(result);
      $('validationModal').hidden = false;
    } catch (error) { toast(`Validation impossible : ${friendlyError(error)}`, 'error'); }
  }

  function renderValidation(result) {
    const valid = Boolean(result.valid);
    const lines = [];
    (result.errors || []).forEach((item) => lines.push(`<div class="validation-item error">${escapeHtml(item)}</div>`));
    (result.warnings || []).forEach((item) => lines.push(`<div class="validation-item warning">${escapeHtml(item)}</div>`));
    if (valid && !(result.warnings || []).length) lines.push('<div class="validation-item ok">Aucune anomalie détectée par les contrôles de base.</div>');
    if (result.summary) lines.unshift(`<div class="validation-item ok">Thème <strong>${escapeHtml(result.summary.themeName)}</strong> · ${escapeHtml((result.summary.types || []).join(', '))} · Keycloak ${escapeHtml(result.summary.targetVersion)}</div>`);
    $('validationResult').innerHTML = `<div class="validation-summary"><div class="validation-icon ${valid ? '' : 'invalid'}">${valid ? '✓' : '×'}</div><div><strong>${valid ? 'Structure prête à être générée' : 'Le projet contient des erreurs'}</strong><small>${(result.warnings || []).length} avertissement(s) · ${(result.errors || []).length} erreur(s)</small></div></div><div class="validation-list">${lines.join('')}</div>`;
  }

  async function exportArchive(format) {
    flushPendingSourceEdit();
    if (format === 'json') { exportProjectJson(); return; }
    const endpoint = {
      'keycloakify-jar': '/api/export/keycloakify-jar',
      'keycloakify-project': '/api/export/keycloakify-project',
    }[format] || `/api/export/${format}`;
    const button = document.querySelector(`[data-export="${format}"]`);
    const exportLabel = {
      zip: 'Archive ZIP',
      jar: 'JAR natif',
      'keycloakify-jar': 'Compilation du JAR Keycloakify',
      'keycloakify-project': 'Projet React / Keycloakify',
    }[format] || 'Export';
    try {
      if (button) { button.classList.add('is-busy'); button.disabled = true; }
      if (format === 'keycloakify-jar') toast('Compilation du thème React et assemblage du JAR…');
      const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project }) });
      if (!response.ok) {
        let message = await response.text();
        try { const parsed = JSON.parse(message); message = parsed.detail || message; } catch { /* Keep plain response text. */ }
        throw new Error(message);
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const extension = format === 'keycloakify-project' ? 'zip' : format.includes('jar') ? 'jar' : format;
      downloadBlob(blob, match ? match[1] : `keycloak-theme-${project.name}.${extension}`);
      $('exportMenu').hidden = true;
      const engine = response.headers.get('X-KTS-Theme-Engine') || '';
      if (format === 'keycloakify-jar' && engine === 'native-no-login') toast('JAR généré : ce projet ne contient pas de thème Login.');
      else toast(`${exportLabel} généré.`);
    } catch (error) { toast(`Échec de l'export : ${friendlyError(error)}`, 'error'); }
    finally { if (button) { button.classList.remove('is-busy'); button.disabled = false; } }
  }

  async function updateKeycloakifyExportStatus() {
    const button = $('keycloakifyJarExportBtn');
    const note = $('keycloakifyBuildStatus');
    if (!button || !note) return;
    try {
      const response = await fetch('/api/keycloakify/status');
      if (!response.ok) throw new Error('État du moteur indisponible');
      const status = await response.json();
      if (status.ready) {
        button.disabled = false;
        note.className = 'export-engine-status ready';
        note.textContent = `Moteur prêt · Keycloakify ${status.keycloakifyVersion}`;
      } else {
        button.disabled = true;
        note.className = 'export-engine-status unavailable';
        note.textContent = `Chaîne de compilation absente ou incompatible (${(status.missing || []).join(', ')}). Le JAR natif reste disponible.`;
        button.title = 'Reconstruisez le conteneur Studio avec la chaîne Node.js, Java et Maven.';
      }
    } catch {
      button.disabled = true;
      note.className = 'export-engine-status unavailable';
      note.textContent = 'État du moteur inconnu. Le JAR natif reste disponible.';
    }
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadCurrentAsset() {
    if (!currentSourceAsset) return;
    const dataUrl = project.advanced.assets[currentSourceAsset];
    if (!dataUrl) return;
    const [header, encoded] = dataUrl.split(',', 2);
    const mime = header.slice(5).split(';')[0] || 'application/octet-stream';
    const binary = atob(encoded);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    downloadBlob(new Blob([bytes], { type: mime }), currentSourceAsset.split('/').pop());
    toast('Ressource téléchargée.');
  }

  function exportProjectJson() {
    downloadBlob(new Blob([JSON.stringify(project, null, 2)], { type: 'application/json;charset=utf-8' }), `${project.name}.kts-project.json`);
    $('exportMenu').hidden = true;
    toast('Projet JSON téléchargé.');
  }

  async function importProject(file) {
    if (!file) return;
    flushPendingSourceEdit();
    try {
      if (file.size > 25 * 1024 * 1024) throw new Error('Fichier trop volumineux (25 Mo maximum).');
      const lower = file.name.toLowerCase();
      if (lower.endsWith('.json')) {
        const parsed = JSON.parse(await file.text());
        project = normalizeFrontend(parsed.project || parsed);
        persistLocal('Projet importé localement');
        syncControls();
        toast('Projet JSON importé.');
      } else if (lower.endsWith('.zip') || lower.endsWith('.jar')) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = '';
        const chunkSize = 0x8000;
        for (let i = 0; i < bytes.length; i += chunkSize) binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
        const result = await apiJson('/api/import/archive', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: file.name, data: btoa(binary) }),
        });
        project = normalizeFrontend(result.project);
        persistLocal('Thème importé localement');
        syncControls();
        const extra = result.availableThemes?.length > 1 ? ` Premier thème sélectionné : ${result.selectedTheme}.` : '';
        toast(`Thème importé : ${result.importedTypes.join(', ')} · ${result.importedFiles} fichiers.${extra}`);
      } else {
        throw new Error('Format non pris en charge. Utilisez un projet JSON, un thème ZIP ou un JAR Keycloak.');
      }
    } catch (error) { toast(`Import impossible : ${friendlyError(error)}`, 'error'); }
  }

  function openProjectModal(mode) {
    pendingProjectMode = mode;
    $('projectCreatePanel').hidden = mode !== 'create';
    $('projectManagePanel').hidden = mode !== 'manage';
    $('projectModalTitle').textContent = mode === 'create' ? 'Créer un projet' : 'Gestion des projets';
    $('projectModal').hidden = false;
    if (mode === 'manage') refreshProjectList();
    else $('projectNameInput').focus();
  }

  function blankProject(name, preset) {
    const result = clone(DEFAULT_PROJECT);
    result.name = slugify(name);
    result.displayName = name.trim() || result.name;
    result.design.brand = name.trim() || 'My Keycloak Theme';
    if (PRESETS[preset]) Object.assign(result.design, PRESETS[preset]);
    return normalizeFrontend(result);
  }

  function createProject() {
    flushPendingSourceEdit();
    const name = $('projectNameInput').value.trim();
    if (!name) { toast('Donnez un nom au projet.', 'error'); return; }
    project = blankProject(name, $('projectPreset').value);
    currentSourceFile = '__customCss';
    currentSourceAsset = null;
    dirty = true;
    persistLocal('Nouveau projet créé');
    $('projectModal').hidden = true;
    syncControls();
    setActiveView('design');
    toast(`Projet « ${project.name} » créé. Enregistrez-le sur le serveur pour le conserver.`);
  }

  async function refreshProjectList() {
    const list = $('projectList');
    list.innerHTML = '<div class="empty-state">Chargement des projets…</div>';
    try {
      const result = await apiJson('/api/projects');
      const items = result.projects || [];
      if (!items.length) {
        list.innerHTML = '<div class="empty-state">Aucun projet enregistré. Utilisez « Nouveau » puis « Enregistrer » pour créer votre premier projet.</div>';
        return;
      }
      list.innerHTML = items.map((item) => `<div class="project-list-item"><div class="project-list-avatar">${escapeHtml((item.name || 'K').charAt(0).toUpperCase())}</div><div class="project-list-copy"><strong>${escapeHtml(item.displayName || item.name)}</strong><small>${escapeHtml(item.name)} · ${escapeHtml(item.updatedAt || 'Date inconnue')}</small></div><button class="button button-outline project-action" data-project-action="load" data-project-id="${escapeHtml(item.id)}">Ouvrir</button><button class="button button-outline project-action" data-project-action="duplicate" data-project-id="${escapeHtml(item.id)}">Dupliquer</button><button class="icon-button project-action-icon" title="Supprimer" data-project-action="delete" data-project-id="${escapeHtml(item.id)}">✕</button></div>`).join('');
    } catch (error) { list.innerHTML = `<div class="empty-state error-state">${escapeHtml(friendlyError(error))}</div>`; }
  }

  async function handleProjectAction(action, id) {
    try {
      if (action === 'load') {
        flushPendingSourceEdit();
        const loaded = await apiJson(`/api/projects/${encodeURIComponent(id)}`);
        project = normalizeFrontend(loaded);
        currentSourceFile = '__customCss';
        currentSourceAsset = null;
        dirty = false;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(project));
        syncControls();
        setSaveState('Projet chargé depuis le serveur', false);
        $('projectModal').hidden = true;
        setActiveView('design');
        toast(`Projet « ${project.name} » chargé.`);
      } else if (action === 'duplicate') {
        const original = normalizeFrontend(await apiJson(`/api/projects/${encodeURIComponent(id)}`));
        original.name = slugify(`${original.name}-copy`);
        original.displayName = `${original.displayName} (copie)`;
        const result = await apiJson('/api/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project: original }) });
        toast(`Copie créée : ${result.id}.`);
        refreshProjectList();
      } else if (action === 'delete') {
        if (!window.confirm(`Supprimer définitivement le projet « ${id} » du serveur ?`)) return;
        await apiJson(`/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' });
        toast(`Projet « ${id} » supprimé du serveur.`);
        refreshProjectList();
      }
    } catch (error) { toast(friendlyError(error), 'error'); }
  }

  function closeModal(id) { $(id).hidden = true; }

  async function readAsDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error('Lecture de l’image impossible.'));
      reader.readAsDataURL(blob);
    });
  }

  async function optimizeBackgroundImage(file) {
    // Resizing and WebP conversion keep the image below localStorage quotas while
    // retaining enough resolution for a full-width Keycloak login background.
    if (typeof createImageBitmap !== 'function') {
      return { dataUrl: await readAsDataUrl(file), optimized: false };
    }
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
      const maxSide = 2560;
      const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const context = canvas.getContext('2d', { alpha: true });
      if (!context) throw new Error('Préparation de l’image impossible.');
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      let blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', 0.86));
      if (!blob || blob.type !== 'image/webp') {
        return { dataUrl: await readAsDataUrl(file), optimized: false };
      }
      if (blob.size > 2.8 * 1024 * 1024) {
        blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', 0.74));
      }
      if (!blob || blob.size > 3 * 1024 * 1024) {
        throw new Error('L’image reste trop volumineuse après optimisation. Essayez une image plus légère.');
      }
      return { dataUrl: await readAsDataUrl(blob), optimized: true };
    } finally {
      if (bitmap) bitmap.close();
    }
  }

  async function loadBackgroundImage(file) {
    const allowed = ['image/png', 'image/jpeg', 'image/webp'];
    if (!file || !allowed.includes(file.type) || file.size > 3 * 1024 * 1024) {
      toast('Image refusée. Formats acceptés : PNG, JPG ou WebP, 3 Mo maximum.', 'error');
      return;
    }
    try {
      const result = await optimizeBackgroundImage(file);
      project.design.backgroundImageData = result.dataUrl;
      project.design.backgroundImageName = file.name;
      persistLocal('Image d’arrière-plan ajoutée');
      updateBackgroundImageControls();
      renderPreview();
      toast(result.optimized ? 'Image optimisée et appliquée à l’aperçu.' : 'Image ajoutée à l’aperçu.');
    } catch (error) {
      toast(friendlyError(error), 'error');
    }
  }

  function bindEvents() {
    document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => setActiveView(button.dataset.view)));
    document.querySelectorAll('[data-view-link]').forEach((button) => button.addEventListener('click', () => setActiveView(button.dataset.viewLink)));
    document.querySelectorAll('[data-preview-space]').forEach((button) => button.addEventListener('click', () => {
      $('previewType').value = button.dataset.previewSpace;
      updatePreviewPageOptions();
      renderPreview();
      if (activeView !== 'design') setActiveView('design');
    }));
    document.querySelectorAll('[data-inspector-section]').forEach((button) => button.addEventListener('click', () => {
      navigateInspector(button.dataset.inspectorSection, button);
    }));
    const inspectorScroll = document.querySelector('#designInspector .inspector-scroll');
    if (inspectorScroll) inspectorScroll.addEventListener('scroll', () => {
      const sections = [...document.querySelectorAll('.inspector-section')];
      const active = sections.find((section) => {
        const rect = section.getBoundingClientRect();
        const panelRect = inspectorScroll.getBoundingClientRect();
        return rect.top <= panelRect.top + 65 && rect.bottom > panelRect.top + 65;
      }) || sections[0];
      document.querySelectorAll('[data-inspector-section]').forEach((button) => {
        const selected = button.dataset.inspectorSection === active?.id;
        button.classList.toggle('active', selected);
        if (selected) button.setAttribute('aria-current', 'location');
        else button.removeAttribute('aria-current');
      });
    }, { passive: true });
    $('themeName').addEventListener('input', () => { project.name = slugify($('themeName').value); updateProjectIdentity(); persistLocal(); });
    $('themeName').addEventListener('blur', () => { $('themeName').value = project.name; });
    $('targetVersion').addEventListener('change', (event) => changeTargetVersion(event.target.value));

    const numericDesignKeys = new Set(['radius', 'cardWidth', 'backgroundOverlay', 'backgroundAnimationDuration', 'formPositionX', 'formPositionY', 'formWidth', 'formBackgroundOpacity', 'formBorderWidth', 'formPadding', 'formRadius']);
    const formDesignKeys = ['formPlacement', 'formIntegration', 'formPositionX', 'formPositionY', 'formWidth', 'formFrameEnabled', 'formBackgroundEnabled', 'formBackgroundOpacity', 'formBorderEnabled', 'formBorderColor', 'formBorderWidth', 'formShadow', 'formPadding', 'formRadius', 'formContentAlignment'];
    ['brand', 'subtitle', 'primary', 'accent', 'background', 'surface', 'text', 'muted', 'fontFamily', 'radius', 'cardWidth', 'showBrand', 'showRememberMe', 'showForgotPassword', 'shadow', 'backgroundImagePosition', 'backgroundImageSize', 'backgroundOverlay', 'backgroundAnimation', 'backgroundAnimationDuration', ...formDesignKeys].forEach((key) => {
      const element = $(key);
      if (!element) return;
      const update = () => {
        const value = element.type === 'checkbox' ? element.checked : numericDesignKeys.has(key) ? Number(element.value) : element.value;
        if (key === 'formPlacement' && FORM_PLACEMENTS[value]) {
          [project.design.formPositionX, project.design.formPositionY] = FORM_PLACEMENTS[value];
          $('formPositionX').value = String(project.design.formPositionX);
          $('formPositionY').value = String(project.design.formPositionY);
        }
        setDesign(key, value);
      };
      element.addEventListener('input', update);
      element.addEventListener('change', update);
    });
    document.querySelectorAll('[data-form-preset]').forEach((button) => button.addEventListener('click', () => applyFormPreset(button.dataset.formPreset)));
    document.querySelectorAll('[data-preset]').forEach((button) => button.addEventListener('click', () => applyPreset(button.dataset.preset)));
    $('resetDesignBtn').addEventListener('click', () => { project.design = clone(DEFAULT_PROJECT.design); persistLocal(); syncControls(); toast('Design réinitialisé.'); });

    $('previewPage').addEventListener('change', renderPreview);
    $('previewType').addEventListener('change', () => { updatePreviewPageOptions(); renderPreview(); });
    window.addEventListener('message', (event) => {
      if (event.source !== $('previewViewport').contentWindow) return;
      if (event.data?.type === 'kts-preview-nav') {
        const requestedPage = String(event.data.page || '');
        if (PREVIEW_PAGES[$('previewType').value]?.some(([value]) => value === requestedPage)) { $('previewPage').value = requestedPage; renderPreview(); }
      } else if (event.data?.type === 'kts-form-drag') {
        syncFormPositionFromMessage(event.data);
      }
    });
    document.querySelectorAll('[data-device]').forEach((button) => button.addEventListener('click', () => {
      currentDevice = button.dataset.device;
      document.querySelectorAll('[data-device]').forEach((item) => item.classList.toggle('active', item === button));
      $('previewBrowser').classList.toggle('mobile', currentDevice === 'mobile');
    }));
    $('previewZoom').addEventListener('change', applyPreviewZoom);
    $('fitPreviewBtn')?.addEventListener('click', () => { $('previewZoom').value = '100'; applyPreviewZoom(); });

    $('uploadLogoBtn').addEventListener('click', () => $('logoFile').click());
    $('logoZone').addEventListener('click', (event) => { if (event.target === $('logoZone')) $('logoFile').click(); });
    $('logoFile').addEventListener('change', async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 1_500_000) {
        toast('Logo refusé : utilisez PNG/JPEG/WebP de 1,5 Mo maximum.', 'error'); event.target.value = ''; return;
      }
      project.design.logoData = await new Promise((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(file);
      });
      project.design.logoName = file.name;
      persistLocal(); syncControls(); toast('Logo ajouté au projet.');
      event.target.value = '';
    });
    $('removeLogoBtn').addEventListener('click', () => { project.design.logoData = ''; project.design.logoName = ''; persistLocal(); syncControls(); toast('Logo retiré.'); });

    $('uploadBackgroundBtn').addEventListener('click', () => $('backgroundImageFile').click());
    $('backgroundImageZone').addEventListener('click', (event) => {
      if (event.target === $('backgroundImageZone') || event.target.closest('.background-image-picker')) $('backgroundImageFile').click();
    });
    $('backgroundImageZone').addEventListener('dragover', (event) => { event.preventDefault(); $('backgroundImageZone').classList.add('drag-over'); });
    $('backgroundImageZone').addEventListener('dragleave', () => $('backgroundImageZone').classList.remove('drag-over'));
    $('backgroundImageZone').addEventListener('drop', (event) => {
      event.preventDefault(); $('backgroundImageZone').classList.remove('drag-over');
      const file = event.dataTransfer.files?.[0];
      if (file) loadBackgroundImage(file);
    });
    const previewStage = $('previewStage');
    previewStage.addEventListener('dragover', (event) => {
      if (![...(event.dataTransfer?.items || [])].some((item) => item.kind === 'file')) return;
      event.preventDefault();
      previewStage.classList.add('image-drop-active');
    });
    previewStage.addEventListener('dragleave', (event) => {
      if (!previewStage.contains(event.relatedTarget)) previewStage.classList.remove('image-drop-active');
    });
    previewStage.addEventListener('drop', (event) => {
      event.preventDefault();
      previewStage.classList.remove('image-drop-active');
      const file = [...(event.dataTransfer?.files || [])].find((item) => item.type.startsWith('image/'));
      if (file) loadBackgroundImage(file);
    });
    $('backgroundImageFile').addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (file) loadBackgroundImage(file);
      event.target.value = '';
    });
    $('removeBackgroundImageBtn').addEventListener('click', () => {
      project.design.backgroundImageData = '';
      project.design.backgroundImageName = '';
      persistLocal(); updateBackgroundImageControls(); renderPreview();
      toast('Image d’arrière-plan retirée.');
    });

    document.querySelectorAll('[data-type]').forEach((checkbox) => checkbox.addEventListener('change', setTypes));
    $('resetParentsBtn').addEventListener('click', () => { project.parents = parentsForVersion(project.targetVersion); persistLocal(); renderParents(); toast('Parents réinitialisés selon la version cible.'); });

    $('sourceEditor').addEventListener('input', () => {
      $('editorState').textContent = 'Enregistrement local…';
      updateSourceLineCount();
      window.clearTimeout(sourceCommitTimer);
      sourceCommitTimer = window.setTimeout(() => applySourceValue(false), 350);
    });
    $('applySourceBtn').addEventListener('click', () => { window.clearTimeout(sourceCommitTimer); applySourceValue(); });
    $('newFileBtn').addEventListener('click', () => { $('newFileType').value = $('previewType').value || 'login'; $('newFilePath').value = 'resources/css/custom.css'; $('fileModal').hidden = false; $('newFilePath').focus(); });
    $('createFileConfirm').addEventListener('click', createFile);
    $('cancelFileCreate').addEventListener('click', () => closeModal('fileModal'));
    $('closeFileModal').addEventListener('click', () => closeModal('fileModal'));
    $('deleteFileBtn').addEventListener('click', removeCurrentFile);
    $('downloadAssetBtn').addEventListener('click', downloadCurrentAsset);
    $('newFileType').addEventListener('change', () => { /* The type and relative path are combined when creating. */ });

    $('saveBtn').addEventListener('click', saveProject);
    $('validateBtn').addEventListener('click', validateProject);
    $('compatValidateBtn').addEventListener('click', validateProject);
    $('modalExportZip').addEventListener('click', () => { closeModal('validationModal'); exportArchive('zip'); });
    $('closeValidation').addEventListener('click', () => closeModal('validationModal'));
    $('closeValidationBtn').addEventListener('click', () => closeModal('validationModal'));
    ['validationModal', 'projectModal', 'fileModal'].forEach((id) => $(id).addEventListener('click', (event) => { if (event.target === $(id)) closeModal(id); }));
    $('exportBtn').addEventListener('click', () => { $('exportMenu').hidden = !$('exportMenu').hidden; });
    document.querySelectorAll('[data-export]').forEach((button) => button.addEventListener('click', () => exportArchive(button.dataset.export)));
    document.addEventListener('click', (event) => { if (!event.target.closest('.export-wrap')) $('exportMenu').hidden = true; });
    $('importBtn').addEventListener('click', () => $('importFile').click());
    $('importFile').addEventListener('change', (event) => { importProject(event.target.files?.[0]); event.target.value = ''; });

    $('newProjectBtn').addEventListener('click', () => openProjectModal('create'));
    $('projectMenuBtn').addEventListener('click', () => openProjectModal('manage'));
    $('createProjectConfirm').addEventListener('click', createProject);
    $('cancelProjectCreate').addEventListener('click', () => closeModal('projectModal'));
    $('closeProjectModal').addEventListener('click', () => closeModal('projectModal'));
    $('closeProjectManager').addEventListener('click', () => closeModal('projectModal'));
    $('managerNewProject').addEventListener('click', () => openProjectModal('create'));
    $('refreshProjectsBtn').addEventListener('click', refreshProjectList);
    $('projectList').addEventListener('click', (event) => {
      const button = event.target.closest('[data-project-action]');
      if (button) handleProjectAction(button.dataset.projectAction, button.dataset.projectId);
    });
    $('projectNameInput').addEventListener('keydown', (event) => { if (event.key === 'Enter') createProject(); });
    $('newFilePath').addEventListener('keydown', (event) => { if (event.key === 'Enter') createFile(); });
    window.addEventListener('beforeunload', (event) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  }

  bindEvents();
  syncControls();
  updateKeycloakifyExportStatus();
  selectSourceFile('__customCss');
  setActiveView('design');
  try {
    if (localStorage.getItem(STORAGE_KEY)) setSaveState('Projet récupéré du navigateur', false);
    else setSaveState('Nouveau projet local', false);
  } catch {
    setSaveState('Stockage navigateur indisponible', false);
  }
  dirty = false;
})();
