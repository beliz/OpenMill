# Contribuer

## Préparer l’environnement

```bash
python -m venv .venv
python -m pip install -e ".[gui,dev]"
```

Sous Windows, utiliser `.venv\Scripts\python.exe` ; sous Linux, activer l’environnement avec `source .venv/bin/activate`.

## Règles de conception

1. Le noyau métier ne dépend jamais de Qt, VTK ou LinuxCNC.
2. Toute nouvelle opération possède des tests de géométrie et d’échec.
3. Les chemins rapides et profondeurs doivent rester explicites.
4. Les paramètres incompatibles produisent un message utilisateur exploitable.
5. Les libellés, descriptions, erreurs et documentation sont en français.
6. Les changements d’identifiant ou de format de projet nécessitent une migration.
7. Une intégration Probe Basic doit rester optionnelle et localisée.

## Vérifications avant proposition

```bash
python -m compileall -q src tests run.py
python -m unittest discover -s tests -v
ruff check src tests
```

## Proposition d’une nouvelle opération

Décrire la géométrie, les paramètres, les limites de l’outil, la stratégie d’entrée, les profondeurs successives et les cas dangereux. Fournir des tests qui vérifient les dimensions réellement usinées, et pas seulement le nombre de lignes G-code.

## Sécurité machine

Les tests logiciels ne remplacent jamais la simulation machine. Toute proposition qui modifie l’export `.ngc`, les déplacements rapides, les compensations ou le chargement LinuxCNC doit expliquer les risques et le protocole de validation.
