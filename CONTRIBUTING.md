# Contribuer

Les contributions sont les bienvenues, en particulier sur la compatibilité des thèmes avec les versions Keycloak.

## Avant une Pull Request

1. Ouvrir une issue pour les changements structurants ou les nouveaux moteurs.
2. Ajouter ou adapter les tests de génération.
3. Vérifier que les chemins personnalisés restent confinés à l'arborescence du thème.
4. Documenter toute hypothèse dépendante d'une version Keycloak.
5. Exécuter `python -m unittest discover -s tests -v` et `node --check app/static/app.js`.

## Principes de conception

- Les générateurs doivent être déterministes.
- L'export JAR doit conserver le manifeste Keycloak officiel.
- Ne jamais exécuter un template ou un script fourni dans un projet importé.
- Ne pas supposer qu'une classe CSS, un parent ou une ressource existe sur toutes les versions.
- Les avertissements de compatibilité doivent être explicites.
