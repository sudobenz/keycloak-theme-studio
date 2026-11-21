# Sécurité

Cette application manipule des sources de thèmes qui peuvent contenir du code exécuté ultérieurement par Keycloak.

- N'installez que des thèmes et templates provenant de sources de confiance.
- Auditez les fichiers FreeMarker avant leur déploiement : ils sont rendus côté serveur avec les privilèges du processus Keycloak.
- N'exposez pas l'interface de gestion directement sur Internet. Placez-la derrière un reverse proxy HTTPS et une authentification adaptée.
- La V1 ne fournit pas de comptes utilisateurs ni de contrôle d'accès applicatif.
- Les projets sauvegardés sur le volume Docker sont accessibles aux administrateurs de l'hôte Docker.

Pour signaler un problème de sécurité, privilégiez une GitHub Security Advisory privée dans le dépôt du projet.
