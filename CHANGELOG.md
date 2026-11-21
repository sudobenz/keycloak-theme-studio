# Changelog

## 1.7.0 — 2026-11-21

- Ajout d'un contrôle de disposition du formulaire Login : position libre par coordonnées X/Y en pourcentage, presets de position et déplacement direct dans l'aperçu.
- Ajout de modes d'intégration du formulaire : position libre sur le fond, mise en flux, alignement à gauche et alignement à droite.
- Ajout de réglages indépendants pour la largeur, le fond, l'opacité, la bordure, l'ombre, les arrondis, l'alignement et l'espacement intérieur.
- Ajout d'un préréglage « Sans cadre » qui retire visuellement fond, bordure, ombre et arrondis tout en conservant le conteneur React/Keycloakify requis. L'espacement intérieur reste réglable indépendamment.
- Application des mêmes règles de disposition aux exports natifs et Keycloakify, avec ciblage des classes `kcLoginClass` et `kcFormCardClass`.
- Compatibilité des anciens projets conservée via les alias `cardWidth` et `shadow` ; les coordonnées personnalisées sont reconnues même si le projet ne déclare pas de preset.
- Conservation des endpoints et formats ZIP/JAR existants ; aucun remplacement du JAR natif.
- Ajout de tests de normalisation, de CSS et de non-régression pour les modes d'intégration et l'export sans cadre.

## 1.6.0 — 2026-11-21

- Intégration de Keycloakify 11.16.4 comme moteur React/Vite pour générer le thème Login, à partir des conventions du starter officiel.
- Ajout de l'export direct d'un JAR Keycloakify depuis l'interface : compilation npm + Maven côté serveur, puis assemblage avec les types non-Login générés nativement.
- Ajout de l'export d'un projet React/TypeScript/Vite Keycloakify, accompagné d'un `native-sidecar.jar` pour Account, Admin, Email et Welcome lorsqu'ils sont sélectionnés.
- Conservation intégrale de l'export ZIP/JAR natif historique ; il reste disponible pour les templates FreeMarker Login personnalisés et comme voie de compatibilité.
- Ajout d'un endpoint d'état de la chaîne de compilation et d'un état explicite dans le menu d'export.
- Installation de Node.js, npm, Java 17 et Maven dans l'image Docker ; ajout d'un volume persistant de cache npm/Maven.
- Transmission facultative des variables de proxy HTTP(S) au moteur de compilation pour les déploiements en réseau d'entreprise.
- Contrôles de présence et de compatibilité des versions Node.js, npm, Java et Maven avant compilation.
- Cache npm/Maven persistant, mais fichier Maven temporaire pour ne pas conserver les identifiants de proxy dans le volume durable.
- CI enrichie avec un build Keycloakify réel et une construction de l’image Docker sur GitHub Actions.
- Tests dédiés à la fusion du JAR Keycloakify et du JAR natif, sans remplacer les anciennes routes d'export.

## 1.5.0 — 2026-11-21

- Correction du bug bloquant d’image de fond : les guillemets de l’URL `data:` ne cassent plus l’attribut HTML `style` de la prévisualisation.
- Optimisation des images d’arrière-plan en WebP, redimensionnées à 2560 px maximum, pour limiter la consommation de stockage navigateur.
- Aperçu agrandi : le canevas utilise désormais l’espace disponible, avec un zoom initial à 100 % au lieu d’un rendu limité à 760 × 520 px à 75 %.
- Ajout d’une commande « Ajuster » pour rétablir l’échelle de travail.
- Dépôt direct d’une image sur le canevas pour l’utiliser comme arrière-plan.
- Application des fonds, du cadrage et des animations dans l’aperçu E-mails également.
- Mise à jour des versions API, Docker Compose, cache navigateur, documentation et tests.


## 1.4.0 — 2026-11-21

- Navigation fonctionnelle vers les sections de réglages de l’inspecteur.
- Ajout d’un arrière-plan image, options de cadrage et animation CSS (zoom, déplacement, aurore).
- Aperçu ajustable, icônes SVG cohérentes, composants et vues harmonisés.
- Contrôles de sécurité sur les images et respect des préférences de réduction des mouvements.
- Ajustement du formulaire simulé pour éviter qu’il soit tronqué dans le canevas.
- Correction du débordement horizontal mobile et simplification de la barre d’actions sur petit écran.


## 1.3.0 — 2026-11-21

- Refonte de l'interface autour d'un espace de travail inspiré des logiciels de conception : barre d'outils supérieure, navigation des pages à gauche, canevas central et inspecteur de propriétés à droite.
- Ajout d'une navigation directe entre les cinq espaces Keycloak depuis le panneau gauche, reliée aux contrôles de prévisualisation.
- Ajout de raccourcis vers les sections Identité, Couleurs et Mise en page de l'inspecteur.
- Suppression des grands bandeaux de présentation et des éléments de tableau de bord peu utiles pendant la conception.
- Harmonisation des composants, de l'éditeur de fichiers, de la compatibilité, des modales, des notifications et de la barre d'état.
- Ajustements responsive pour les écrans plus étroits.
- Aucun changement du modèle de projet ni des formats ZIP/JAR.

## 1.2.0 — 2026-11-21

- Refonte de l’interface : navigation claire, fond de travail lumineux, composants plus lisibles et hiérarchie visuelle renforcée.
- Remplacement des slogans et intitulés génériques par des libellés explicites en français courant.
- Clarification des espaces Keycloak : Connexion, Compte utilisateur, Administration, E-mails et Page d’accueil.
- Amélioration de la barre d’actions, des boutons, des menus, des cartes, des champs, des modales et des notifications.
- Reprise de l’éditeur visuel, de l’aperçu et des panneaux de réglages pour une meilleure lisibilité sur desktop, tablette et mobile.
- Clarification de la mention de simulation : l’aperçu n’est pas connecté à Keycloak.
- Mise à jour des métadonnées API, de l’image Docker, de la documentation et des tests vers la version 1.2.0.
- Aucun changement du schéma de projet ni du format d’export ZIP/JAR.

## 1.1.0 — 2026-11-20

- Correction de la génération CSS : propriété native `styles` au lieu de la propriété inconnue `styles.ktsOverrides`.
- Conservation du CSS parent Login avec `css/login.css` suivi de `css/kts-overrides.css`.
- Prévisualisation isolée dans une iframe sandboxée.
- CSS personnalisé et CSS de fichiers ajoutés inclus dans le rendu de prévisualisation.
- Navigation interactive dans la simulation Login (connexion, inscription, réinitialisation, OTP, erreur).
- Création de projets depuis l'interface avec palettes de départ.
- Gestion serveur des projets : liste, ouverture, duplication et suppression.
- Création de fichiers via formulaire, modèles de départ, suppression et application automatique.
- Import de thèmes Keycloak au format ZIP/JAR avec validation des archives, récupération des parents et préservation des ressources binaires.
- Gestion et téléchargement des ressources importées.
- Référencement automatique des feuilles CSS (`styles`) et scripts (`scripts`) ajoutés sous `resources/`, sans écraser les propriétés personnalisées importées.

## 1.0.0 — 2026-11-20

- Première version de Keycloak Theme Studio.
- Éditeur visuel avec identité, palettes, polices, dimensions et logo.
- Prévisualisation simulée des cinq types de thème.
- Mode source et configuration des parents Keycloak.
- API FastAPI, validation et génération ZIP/JAR.
- Docker Compose et documentation initiale.
