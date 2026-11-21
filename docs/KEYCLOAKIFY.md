# Intégration Keycloakify — V1.7

Le Studio s'appuie sur le starter officiel Keycloakify (React, TypeScript et Vite) pour construire le thème **Login**. Le projet React généré suit la structure `kc.gen.tsx`, `login/KcContext.ts`, `login/KcPage.tsx`, `login/i18n.ts` et `login/KcPageStory.tsx` du starter.

## Les deux exports JAR sont conservés

### JAR natif

`Exporter → JAR natif` conserve le moteur historique du Studio. Il est autonome et ne nécessite ni Node.js, ni npm, ni Java, ni Maven sur le serveur Studio. Il prend en charge les cinq types (Login, Account, Admin, Email et Welcome), y compris les templates FreeMarker Login ajoutés par l'utilisateur.

### JAR React / Keycloakify

`Exporter → JAR React · Keycloakify` :

1. génère un projet React/Vite à partir des paramètres du Studio ;
2. installe Keycloakify et les dépendances du starter ;
3. compile le Login avec `npm run build-keycloak-theme` ;
4. sélectionne automatiquement l'archive de compatibilité Keycloakify correspondant à la version majeure cible ;
5. fusionne le Login React avec les autres types natifs sélectionnés et leurs ressources ;
6. télécharge un seul JAR hybride contenant `META-INF/keycloak-themes.json`.

Pour les projets qui ne sélectionnent pas Login, l'action retourne le JAR natif. Si un fichier `.ftl` personnalisé est présent sous `login/`, la génération React est refusée explicitement : le JAR natif reste disponible et préserve ce fichier sans perte.

## Disposition du formulaire et conteneur sans cadre

Les réglages de disposition du Studio sont exportés dans `src/login/main.css`. Les classes d'extension du template Keycloakify sont utilisées pour séparer le conteneur de page (`kcLoginClass`) du conteneur du formulaire (`kcFormCardClass`). Les modes disponibles sont la position libre (X/Y), le flux de page, l'alignement gauche et l'alignement droit.

Le préréglage **Sans cadre** ne supprime pas le wrapper React requis pour le rendu Keycloakify : il supprime son habillage visuel (fond, bordure, ombre et arrondis). Le padding reste réglable séparément, y compris en mode sans cadre. Ces règles sont aussi émises par le générateur natif pour garder un comportement cohérent entre les deux JAR.

## Projet React exportable

`Exporter → Projet React / Keycloakify` télécharge les sources React/TypeScript/Vite et un `native-sidecar.jar` complet. Le JAR complémentaire est une sauvegarde native du thème entier ; il conserve également les fichiers Login qui ne sont pas exécutés par le rendu React.

Dans le répertoire extrait :

```bash
npm install
npm run build-keycloak-theme
```

Le dossier `dist_keycloak/` contient le ou les JAR produits par Keycloakify. La documentation Keycloakify distingue les JAR pour Keycloak 11–21 et 26+, et celui pour Keycloak 22–25. Le Studio choisit automatiquement le fichier correspondant lors de l'export serveur.

## Outils nécessaires dans le conteneur Studio

- Node.js 18 ou 20+ (Node 20+ recommandé ; Node 19 n'est pas dans la plage prise en charge du starter)
- npm
- Java 17+
- Maven 3.8+

L'image Studio V1.6 installe Node.js, npm, OpenJDK 21 et Maven. Les dépendances npm, le dépôt Maven, le répertoire temporaire et le répertoire de travail sont placés dans le volume `kts_keycloakify_cache` afin de rester accessibles avec le système racine en lecture seule.

Pour un réseau d'entreprise, renseigner les variables `HTTP_PROXY`, `HTTPS_PROXY` et `NO_PROXY` dans `.env`. Ces paramètres sont utilisés lors du build de l'image et lors du téléchargement des dépendances npm/Maven à l'exécution.

## Limites fonctionnelles actuelles

- Le moteur Keycloakify est utilisé pour Login. Le Studio continue d'utiliser son générateur natif pour Account, Admin, Email et Welcome.
- Le thème Account possède des options Keycloakify (Single-Page et Multi-Page), mais elles ne sont pas encore proposées par le Studio.
- Admin et Welcome restent natifs dans cette version.
- La prévisualisation du Studio reste une simulation. Le JAR final doit être testé sur la version Keycloak de destination.
