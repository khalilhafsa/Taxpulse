# TaxPulse – fiche projet

Projet portfolio (LinkedIn + CV) : plateforme multi-agents IA pour cabinets de conseil fiscal allemands.
Elle repère les anciens clients de due diligence concernés par une nouvelle lettre du BMF ou un nouvel arrêt du BFH, puis prépare les alertes, les notes d'impact et les emails.

## Liens
- Démo publique : https://taxpulse-demo-bh4f.onrender.com
- Code : https://github.com/khalilhafsa/taxpulse
- Dossier sur le PC : `C:\Users\DELL\Documents\taxpulse`
- Vidéo de démo (92 s, 1080p, sous-titres anglais, sans son, avec la réécriture d’email par remarques) : `C:\Users\DELL\Documents\taxpulse\TaxPulse-demo.mp4`. Elle est exclue de GitHub.

## Ce que fait le projet
- Une chaîne de 5 agents IA (Claude Sonnet + Haiku, via CrewAI) et un pré-filtre gratuit à base de règles :
  1. **Profiler** : lit la data room de chaque client et en tire un profil. Chaque fait est sourcé (document + page).
  2. **Regulatory Analyst** : lit chaque nouvelle règle et identifie à qui elle s'applique.
  3. **Pré-filtre** (sans IA, gratuit) : écarte les paires client/règle qui n'ont rien en commun.
  4. **Impact Matcher** : note chaque paire restante et cite les preuves tirées des fichiers du client.
  5. Le conseiller valide chaque alerte.
  6. **Impact Explainer** : rédige une note d'impact pour chaque alerte acceptée.
  7. **Outreach Writer** : rédige un email par client.
- Une relecture automatique (« partner review ») contrôle chaque email : formulations prudentes, aucune mention de source interne, phrase de réserve. Aucun email ne part sans l'accord du conseiller.
- Le conseiller peut écrire ses remarques, et l'IA réécrit l'email en conséquence.
- Les arrêts du BFH arrivent automatiquement grâce à une vérification hebdomadaire et à des notifications. Pour le BMF, protégé par un CAPTCHA, le CAPTCHA est respecté : le conseiller le passe lui-même, puis clique sur le bouton « Send to TaxPulse ».
- Chaque appel à l'IA est enregistré avec son modèle, ses tokens, son coût et sa durée. Un budget mensuel est vérifié avant chaque appel, et les erreurs temporaires sont relancées automatiquement.
- La démo publique rejoue des résultats enregistrés avec Claude. Elle fonctionne donc sans clé API, et ses données sont fictives et signalées comme telles.

## Résultats mesurés
- Sur les cas de test étiquetés : 7 clients concernés trouvés sur 7, et 0 fausse alerte sur 15.
- Test de stabilité, 5 passages : même décision dans 100 % des cas sur les 18 paires sans ambiguïté.
- Coût de la chaîne complète sur la démo : environ 0,72 $. Le test de stabilité a coûté 1,16 $.

## Stack
Python 3.13, FastAPI, SQLModel/SQLite, CrewAI, Claude · React 19, TypeScript, Vite, Tailwind v4 · Docker, Render, GitHub · ~98 tests pytest.

## Pitch 30 secondes (anglais)
"In Germany, tax rules change every week: new letters from the Ministry of Finance, new rulings from the Federal Fiscal Court. Tax firms have former due diligence clients who are affected, but nobody has the time to check which ones.

So I built TaxPulse, a team of five AI agents built with Claude. It reads the client files and the new rules, and tells the advisor: *this ruling affects these three clients, here is why, and here is the email to send them.*

On my test cases, it found every affected client, with zero false alerts, and the advisor always makes the final call."

## Pitch 2–3 minutes (anglais)
**Problem.** In Germany, the tax rules change constantly. Every week, the Federal Ministry of Finance publishes new letters, and the Federal Fiscal Court publishes new rulings. Tax advisory firms have a hidden asset here: their former due diligence clients. They know these companies in detail, because they went through their data rooms. But when a new rule comes out, nobody has the time to check which of those former clients it affects. So the advice is never given, and the business opportunity is lost.

**Solution.** So I built TaxPulse. It's a multi-agent AI platform that watches these new publications and tells the advisor: this new ruling affects these three former clients, here is why, and here is the email to send them.

**How it works.** It's a chain of five AI agents built with Claude and CrewAI, plus one free rule-based filter. The Profiler reads each client's data room and builds a profile, with a source for every fact. The Regulatory Analyst reads each new rule and extracts who it applies to. A free pre-filter drops the pairs that obviously don't match, which saves cost. The Impact Matcher scores every remaining client against every rule, and quotes the evidence from the client's own files. Then the system stops. The advisor reviews each alert. Only after the advisor accepts an alert does the Impact Explainer write a memo, and the Outreach Writer drafts one email per client. An automatic partner review checks every email for cautious wording, and nothing is ever sent without the advisor's approval.

**Proof.** I didn't just build it, I measured it. On labelled test cases, it found 7 out of 7 affected clients with zero false alerts. I ran the same test five times, because AI is not deterministic, and it made the same decision 100% of the time on every clear-cut case. The whole chain costs about 70 cents to run, and every AI call is logged with its tokens and cost.

**Closing.** It's live: there's a public demo where anyone can watch the agents work, and the code is on GitHub. For me, this project was about building AI that a professional can actually trust: grounded in sources, measured, and always with a human in control.

## Règles à respecter
- Ne jamais partager la clé API. Elle reste uniquement dans `.env`, qui n'est pas envoyé sur GitHub.
- Ne jamais contourner le CAPTCHA du BMF.
- La démo utilise uniquement des données fictives, et elles sont signalées comme telles.

## Reste à faire
- [ ] Lancer `publish.bat` pour envoyer les dernières corrections (README, message de réinitialisation, compteur de mots).
- [ ] Supprimer l'ancien service Render `taxpulse-demo`, celui qui a échoué. Garder `taxpulse-demo-bh4f`.
- [ ] Écrire le post LinkedIn, en anglais de préférence, et le publier avec la vidéo.
- [ ] Ajouter une ligne TaxPulse au CV.
- [ ] Marquer l'étape 10 comme terminée dans le README.
