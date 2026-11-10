# TaxPulse – historique complet du projet

Ce document réunit tout ce qui a été fait dans la discussion de construction de TaxPulse, pour le projet claude.ai « TaxPulse ».

## Les 10 étapes
1–7. Construction de l'application : profils clients sourcés, analyse des règles, pré-filtre + Matcher, alertes avec preuves, notes d'impact, emails, tableau de bord (Overview, Matrix, Who to call first), animation des agents en petits personnages qui se passent le relais.
8. **Qualité** : test de stabilité (5 passages, 100 % sur les cas sans ambiguïté), page Quality, relances automatiques des erreurs temporaires, budget mensuel IA.
9. **Automatisation** : vérification hebdomadaire, cloche de notifications, flux BFH automatiques, bouton « Send to TaxPulse » pour le BMF (CAPTCHA respecté).
10. **Lancement** : code sur GitHub (public) ✅, démo en ligne sur Render ✅, vidéo de démo ✅, post LinkedIn et ligne CV ⏳.

## Décisions importantes
- Emails professionnels : pas de mention de « source interne », ton prudent (pas d'avis fiscal définitif), phrase de réserve obligatoire (« Our assessment is based on… »), contrôlés par une relecture automatique dans le code.
- Le conseiller peut écrire ses remarques et l'IA réécrit l'email.
- Aucune alerte ne doit être oubliée dans un email : l'email ne peut être rédigé que quand toutes les alertes acceptées ont leur note, et la relecture vérifie qu'il y a un paragraphe par sujet.
- L'animation « moniteur cardiaque » a été refusée, remplacée par une équipe de personnages mignons mais professionnels.
- BMF bloqué par un CAPTCHA : on ne le contourne jamais. BFH automatique + bouton à cliquer pour le BMF.
- Démo publique : rejoue des résultats enregistrés avec Claude, donc aucune clé API en ligne ; la démo arrive préremplie, avec un bouton « Watch the agents work » et « Start the demo over ».
- TaxPulse n'envoie jamais d'email tout seul.

## Problèmes rencontrés et résolus
- Page blanche après « Add update » → protection contre les erreurs d'affichage.
- Bouton BMF « unbound prefix » → lecture directe du flux, analyseur plus tolérant.
- Backend « not running » → start.bat attend que le serveur soit prêt ; diagnose.bat.
- Dépôt GitHub vide et privé → publish.bat qui envoie tout en vérifiant qu'aucun fichier privé ne part.
- Échec de build sur Render → anciens fichiers supprimés par publish.bat.
- Qualité affichée à 95 % au lieu de 100 % → on ne compte plus les cas limites.
- Compteur de mots en rouge (253) alors que la relecture était OK → il compte maintenant sans la salutation ni la signature.

