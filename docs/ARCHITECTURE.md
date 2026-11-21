# Architecture technique — V1.7

## Principes

La V1.7 conserve la séparation entre l’interface (HTML/CSS/JavaScript natif), l’API (FastAPI), le modèle JSON de projet et les générateurs ZIP/JAR. L’interface reprend une organisation de type outil de conception : navigation Keycloak à gauche, canevas au centre et inspecteur à droite. La navigation latérale pilote la sélection de prévisualisation ; les raccourcis de réglage font défiler l’inspecteur. Le contrat du modèle et les routes API restent inchangés.

- Le navigateur conserve une copie de travail dans `localStorage`.
- Les projets enregistrés sur le serveur sont persistés en JSON dans le volume Docker.
- La prévisualisation est rendue dans une iframe `sandbox="allow-scripts"` ; le code JavaScript importé n'y est pas exécuté.
- Les modifications CSS globales et les fichiers CSS du type sélectionné sont injectés dans cette iframe de prévisualisation.
- Les ressources binaires importées sont stockées sous forme de data URLs Base64 dans `advanced.assets`, puis réémises sans transformation lors de l'export.
- `normalize_project()` valide les types, les chemins, les tailles, les couleurs et les formats des ressources.
- `import_theme_archive()` lit les ZIP/JAR sans extraction sur le système de fichiers, bloque les traversées de chemins, les liens symboliques et les archives excessives.
- `build_theme_files()` génère la structure native de thème et `make_archive()` crée le ZIP de déploiement ou le JAR avec manifeste Keycloak.

## Contrat de projet

```json
{
  "schemaVersion": 2,
  "name": "identity-portal",
  "displayName": "Identity Portal",
  "targetVersion": "26.1.4",
  "types": ["login", "account", "admin", "email", "welcome"],
  "parents": {
    "login": "keycloak.v2",
    "account": "keycloak.v3",
    "admin": "keycloak.v2",
    "email": "keycloak",
    "welcome": "keycloak"
  },
  "design": {},
  "advanced": {
    "customCss": "/* CSS additionnel */",
    "files": {"login/footer.ftl": "..."},
    "assets": {}
  }
}
```

## Styles Keycloak

Keycloak reconnaît les propriétés `styles` et `scripts` de `theme.properties`. Lorsqu'un thème enfant définit ses propres styles Login, il doit également charger explicitement la feuille CSS du parent. Le Studio génère donc `styles=css/login.css css/kts-overrides.css` pour Login. Les CSS ajoutés sous `<type>/resources/css/` et les scripts sous `<type>/resources/js/` sont automatiquement convertis en chemins relatifs et déclarés dans les propriétés correspondantes. Les déclarations d'un `theme.properties` importé sont conservées et enrichies sans doublons. Les parents et feuilles disponibles peuvent varier selon la version : contrôler chaque package sur une instance de test.

## Disposition du formulaire Login

Le modèle `design` contient les propriétés `formIntegration`, `formPlacement`, `formPositionX`, `formPositionY`, `formWidth`, `formFrameEnabled`, `formBackgroundEnabled`, `formBackgroundOpacity`, `formBorderEnabled`, `formBorderColor`, `formBorderWidth`, `formShadow`, `formPadding`, `formRadius` et `formContentAlignment`. Les coordonnées sont exprimées en pourcentage du conteneur, et `formPlacement=custom` indique que les coordonnées X/Y doivent être utilisées directement. Si une API ou un projet importé fournit des coordonnées sans `formPlacement`, le normaliseur les considère comme personnalisées.

`app/theme_layout.py` est la source commune des tokens CSS et des règles de positionnement utilisées par le générateur natif et Keycloakify. Les quatre modes sont `free`, `flow`, `panel-left` et `panel-right`. Pour Keycloakify, les règles ciblent le conteneur de page `kcLoginClass` et le conteneur de formulaire `kcFormCardClass`. Le mode sans cadre maintient le wrapper React nécessaire au contexte Keycloakify mais le rend transparent, sans bordure, rayon ni ombre. Le padding reste indépendant afin que le contenu puisse conserver son espacement.

L'aperçu local reflète la même disposition : le glisser-déposer de la poignée « Déplacer » enregistre les coordonnées X/Y et bascule en position libre. Le JAR natif reste généré par `build_theme_files()` ; le CSS du JAR Keycloakify provient de `keycloakify_login_css()`. Les tests couvrent les quatre modes et les deux moteurs.

## Import ZIP/JAR

Les formes reconnues incluent :

- `<theme>/<type>/theme.properties`
- `theme/<theme>/<type>/theme.properties`
- `themes/<theme>/<type>/theme.properties`

L'import ne lance ni n'interprète le code importé. Le contenu texte est éditable ; les ressources binaires sont préservées et téléchargeables depuis l'arborescence des sources. Une archive multi-thèmes sélectionne le premier thème détecté.

## API

| Route | Rôle |
|---|---|
| `GET /api/health` | Santé du service |
| `GET /api/defaults` | Parents disponibles par défaut |
| `POST /api/validate` | Validation du projet |
| `POST /api/import/archive` | Import ZIP/JAR |
| `POST /api/export/zip` | Export ZIP |
| `POST /api/export/jar` | Export JAR natif historique |
| `GET /api/projects` | Liste des projets |
| `POST /api/projects` | Sauvegarde |
| `GET /api/projects/{id}` | Chargement |
| `DELETE /api/projects/{id}` | Suppression |

## Moteur React / Keycloakify — V1.6

Le moteur de génération Keycloakify est séparé du générateur natif :

- `app/keycloakify_engine.py` construit un projet React / TypeScript / Vite à partir du modèle Studio, selon les conventions du starter officiel Keycloakify ;
- le point d'entrée Login s'appuie sur `KcContext`, `KcPage`, `DefaultPage`, `Template` et les fonctions i18n de Keycloakify ;
- la feuille CSS issue du modèle visuel applique les couleurs, typographies, dimensions, images et animations ;
- `npm run build-keycloak-theme` compile le projet et crée un JAR Keycloakify dans `dist_keycloak/` ;
- le Studio sélectionne le JAR correspondant à la version majeure cible, puis le fusionne avec les types natifs sélectionnés ;
- le JAR natif historique reste généré indépendamment et n'est jamais remplacé par l'export React.

Les templates FreeMarker Login personnalisés ne peuvent pas être fusionnés avec le rendu React sans adaptation. L'export hybride est donc refusé explicitement pour ces projets ; l'export natif conserve le thème complet. L'export du projet React inclut également un `native-sidecar.jar` intégral comme sauvegarde.

Les compilations serveur utilisent les outils Node.js, npm, Java et Maven installés dans l'image Docker. Les caches npm et Maven sont conservés dans `kts_keycloakify_cache`. Le fichier Maven contenant une éventuelle configuration de proxy est créé dans le répertoire temporaire de compilation, et non dans le cache persistant.

## Routes Keycloakify

| Route | Rôle |
|---|---|
| `GET /api/keycloakify/status` | Vérifie présence et versions minimales de Node, npm, Java et Maven |
| `POST /api/export/keycloakify-project` | Télécharge les sources React / Vite et le JAR natif de sauvegarde |
| `POST /api/export/keycloakify-jar` | Compile le Login React et renvoie le JAR hybride |

L'export `/api/export/jar` continue d'utiliser le générateur natif historique.
