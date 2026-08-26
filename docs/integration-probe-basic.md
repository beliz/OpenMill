# Intégrer OpenMill dans Probe Basic

OpenMill 0.5.1 s’intègre comme **onglet utilisateur**, sans modifier le dépôt Probe Basic et sans faire de fork. La même extension fonctionne en simulation et sur une installation LinuxCNC réelle.

> Le chargement du programme et le départ cycle sont volontairement séparés. OpenMill ne démarre jamais une broche, un déplacement ou un programme.

## Installation automatique recommandée

Depuis le dépôt cloné sur la machine LinuxCNC :

```bash
chmod +x installation.sh
./installation.sh --ini /chemin/vers/configuration-machine/machine.ini
```

L’installateur ne passe pas par `pip`. Il ajoute au Python utilisateur un fichier `.pth` pointant vers `src/`, ce qui évite l’erreur `externally-managed-environment` de Debian et permet de mettre le code à jour avec Git. Il sauvegarde l’INI avant modification, respecte un éventuel `USER_TABS_PATH` existant, installe le splash OpenMill, copie l’onglet et lance le diagnostic simulé.

Commandes complémentaires :

```bash
./installation.sh check --ini /chemin/vers/configuration-machine/machine.ini
./installation.sh uninstall --ini /chemin/vers/configuration-machine/machine.ini
```

Après un `git pull`, relancer la commande d’installation met à jour la copie des deux fichiers de l’onglet. L’opération est idempotente.

Le splash est copié sous le nom `openmill-splash.gif` à côté du fichier INI et déclaré dans `[DISPLAY]`. L’ancienne valeur de `INTRO_GRAPHIC` est mémorisée dans un bloc balisé : la désinstallation la restaure automatiquement et n’efface jamais une image modifiée par l’utilisateur.

## 1. Vérifier l’environnement

Pour une installation manuelle, ouvrir sur la machine LinuxCNC un terminal utilisant exactement le même Python que Probe Basic, puis exposer le dossier `src` dans son site utilisateur :

```bash
OPENMILL_SRC="$(realpath /chemin/vers/OpenMill/src)"
PYTHON_USER_SITE="$(python3 -m site --user-site)"
mkdir -p "$PYTHON_USER_SITE"
printf '%s\n' "$OPENMILL_SRC" > "$PYTHON_USER_SITE/openmill-conversational.pth"
python3 -m openmill.integration.check --smoke-test
```

Le diagnostic affiche les versions Python, la présence de PyQt5, PySide6, VTK, LinuxCNC, QtPyVCP et Probe Basic, ainsi que le dossier de programmes détecté.

Cette méthode ne modifie aucun paquet système et fonctionne avec la protection PEP 668 de Debian. Ne pas ajouter `--break-system-packages` par réflexe.

Le test simulé construit réellement le projet de démonstration, génère son G-code, puis le charge dans un hôte simulé. Il ne demande ni connexion machine ni interface graphique.

La sortie structurée est aussi disponible :

```bash
python3 -m openmill.integration.check --json --smoke-test
```

Sous Windows, dans l’environnement virtuel créé par le lanceur :

```powershell
.\.venv\Scripts\python.exe -m openmill.integration.check --smoke-test
```

## 2. Choisir le binding Qt approprié

Les installations historiques Probe Basic sur Debian 12 utilisent généralement PyQt5. Les branches plus récentes comportent également des versions PySide6.

OpenMill détecte le binding déjà chargé par Probe Basic et **n’importe jamais l’autre binding dans le même processus** :

- PyQt5 chargé → OpenMill utilise PyQt5 ;
- PySide6 chargé → OpenMill utilise PySide6 ;
- aucun binding chargé → `QT_API=pyside6` donne priorité à PySide6 ;
- sinon, PyQt5 reste le choix autonome par défaut sous Windows.

Sur LinuxCNC, réutiliser les dépendances Qt et VTK déjà fournies par l’environnement Probe Basic. Le fichier `.pth` ou l’installateur suffit pour OpenMill, dont le noyau ne déclare aucune dépendance Python obligatoire.

Ne pas installer simultanément PyQt5 et PySide6 au hasard dans le Python de Probe Basic. Pour un environnement PySide6 autonome et isolé seulement :

```bash
python -m pip install -e ".[gui-pyside6]"
```

VTK reste facultatif : le rendu 3D compatible continue de fonctionner sans lui.

## 3. Ajouter l’onglet utilisateur — méthode recommandée

Dans le fichier INI de la configuration LinuxCNC, ajouter ou conserver :

```ini
[DISPLAY]
USER_TABS_PATH = user_tabs/
INTRO_GRAPHIC = openmill-splash.gif
```

Important : ne pas ajouter de commentaire à la fin de cette ligne. Certains chargeurs Probe Basic interprètent autrement le chemin.

Copier ensuite le dossier fourni :

```text
examples/probe_basic/user_tabs/openmill/
    openmill.py
    openmill.ui
```

dans le dossier de configuration machine :

```text
<configuration-machine>/
    machine.ini
    user_tabs/
        openmill/
            openmill.py
            openmill.ui
```

Exemple depuis le dossier OpenMill :

```bash
mkdir -p /chemin/vers/configuration-machine/user_tabs
cp -R examples/probe_basic/user_tabs/openmill \
      /chemin/vers/configuration-machine/user_tabs/
cp assets/openmill-splash.gif \
   /chemin/vers/configuration-machine/openmill-splash.gif
```

Redémarrer Probe Basic. Un nouvel onglet **CONVERSATIONNEL** doit apparaître.

Probe Basic trouve automatiquement la classe `UserTab`, lit le nom du widget, et l’ajoute à son `tabWidget`. La propriété `sidebar=false` indique qu’il s’agit d’un onglet principal.

## 4. Mode simulation de l’onglet

Pour tester le rendu intégré sans utiliser les outils ni les canaux machine :

```bash
export OPENMILL_SIMULATION=1
```

Puis démarrer LinuxCNC / Probe Basic depuis le même terminal. L’onglet utilise alors :

- `MockMachineAdapter` pour la bibliothèque d’outils ;
- `SimulatedProgramBridge` pour recevoir les programmes ;
- la même interface et le même générateur G-code que le mode réel.

Sans cette variable, `OpenMillConversationalWidget` lit la véritable table d’outils LinuxCNC et utilise le pont machine réel.

## 5. Thème global Probe Basic

L’onglet utilisateur active par défaut le thème sombre partagé entre OpenMill et Probe Basic. Le thème :

- conserve la feuille de style existante de Probe Basic ;
- ajoute les règles OpenMill après celle-ci ;
- harmonise aussi les nombreux styles locaux hérités du fichier `.ui` de Probe Basic ;
- conserve la police condensée et les dimensions prévues par Probe Basic pour éviter les libellés tronqués ;
- exclut les widgets dont le style est piloté dynamiquement par QtPyVCP, notamment l’arrêt d’urgence ;
- peut être retiré immédiatement avec le bouton **Thème PB · moderne/original** dans l’en-tête OpenMill.

Pour démarrer avec le thème Probe Basic d’origine :

```bash
export OPENMILL_THEME=original
linuxcnc /chemin/vers/machine.ini
```

Valeurs reconnues pour désactiver le thème : `original`, `off`, `none`, `0` et `false`.

Pour revenir au thème moderne au prochain lancement :

```bash
unset OPENMILL_THEME
```

La modernisation globale reste expérimentale. Les composants de rendu VTK/OpenGL et les contrôles dont la couleur représente un état machine restent volontairement hors de la seconde passe. Une capture de chaque page aide à compléter progressivement les exceptions sans modifier les comportements machine.

Le mode intégré OpenMill est indépendant du thème global. Il applique toujours une feuille locale lisible, réduit les marges et replie le G-code par défaut. Le bouton **Afficher le programme** permet de le développer ponctuellement.

## 6. Charger un programme généré

Le bouton **Charger dans Probe Basic** :

1. reconstruit et valide toutes les opérations ;
2. refuse les projets vides ou invalides ;
3. choisit `[DISPLAY] PROGRAM_PREFIX` comme dossier cible lorsqu’il existe ;
4. génère un fichier nommé `openmill-<nom-de-piece>.ngc` ;
5. vérifie l’arrêt d’urgence et l’état de l’interpréteur ;
6. utilise l’action QtPyVCP de chargement si disponible ;
7. utilise sinon `linuxcnc.command().program_open(...)` ;
8. ne déclenche jamais le départ cycle, la broche, un déplacement MDI ni un référencement.

Le programme publié est volontairement limité à l’ASCII 7 bits et utilise des fins de ligne Unix. Cette contrainte évite les interprétations erronées de l’UTF-8 observées dans certaines versions historiques de l’éditeur Probe Basic.

Après chargement, OpenMill sélectionne automatiquement l’onglet `MAIN` et son aperçu animé. Le BackPlot Probe Basic d’origine reste accessible avec le bouton **Probe Basic**. Lorsqu’il est affiché, un bouton flottant **OpenMill** permet de revenir à l’aperçu moderne. Les deux moteurs occupent alternativement le même emplacement : OpenMill ne déplace, ne recrée et ne redimensionne pas le widget VTK natif.

Dans l’éditeur G-code de `MAIN`, cliquer sur une ligne positionne la chronologie OpenMill après les mouvements exécutés jusqu’à cette ligne. Probe Basic nomme ce widget `gcodetextedit_2` ; `gcodetextedit` correspond à l’éditeur distinct de l’onglet `FILE`. OpenMill cible prioritairement le premier et conserve le second comme solution de repli pour les anciennes interfaces. Les boutons **Ligne précédente** et **Ligne suivante** au-dessus de l’aperçu déplacent la ligne courante, la maintiennent visible et mettent simultanément à jour la scène 3D. OpenMill dessine son propre marqueur pleine largeur, avec un fond vert sombre et un texte blanc. Il ne dépend donc plus de la surbrillance interne de `GcodeTextEdit`, que certaines versions perdent lorsqu’elles remplacent le document pendant le chargement. Les éventuels marqueurs de recherche QtPyVCP sont conservés. Les événements rapprochés sont regroupés pendant 75 ms afin qu’un déplacement rapide dans un gros programme ne reconstruise pas plusieurs fois la scène VTK. Cette navigation est visuelle uniquement : elle ne change pas la ligne d’exécution LinuxCNC et ne commande aucun mouvement machine.

OpenMill active également la propriété `syntaxHighlighting` du widget `MAIN` et installe immédiatement le moteur de coloration sur le document déjà chargé. La coloration est ainsi active dès le lancement et recréée automatiquement par QtPyVCP lors des chargements suivants. La palette QtPyVCP d’origine étant prévue pour un fond clair — ses nombres sont notamment presque noirs (`#0f0f0f`) — OpenMill remplace seulement les couleurs trop sombres par des variantes lisibles et conserve les catégories syntaxiques. La palette est injectée dans les règles avant la première passe de chaque nouveau colorateur. OpenMill n’appelle jamais `rehighlight()` : QtPyVCP exécute `QApplication.processEvents()` dans chaque bloc coloré et un second `rehighlight()` déclenché par un timer pendant cette passe peut faire planter Qt5 dans `QTextLayout`. Le zoom à la molette modifie toujours la taille du texte, mais il n’est plus nécessaire pour déclencher indirectement la coloration via l’événement de changement de police.

Certaines versions de QtPyVCP contiennent également deux impressions de diagnostic accidentelles dans le calcul des limites G-code. Elles produisent dans le terminal une paire `longueur + coordonnées` pour chaque segment et peuvent ralentir fortement le chargement d’un grand fichier. OpenMill désactive uniquement ces deux impressions lorsqu’il détecte exactement la version de code concernée ; les journaux QtPyVCP normaux restent actifs.

## 7. Aperçu des programmes externes

OpenMill surveille le programme chargé par LinuxCNC. Lorsqu’un fichier extérieur au conversationnel est ouvert, il construit une scène d’aperçu à partir de :

- G0, G1, G2 et G3 ;
- arcs par centre IJK ou rayon R ;
- plans G17, G18 et G19 ;
- unités G20/G21 ;
- modes G90/G91 ;
- outils T et diamètres lus dans le fichier déclaré par `[EMCIO] TOOL_TABLE`.

OpenMill lit en priorité les enregistrements `T… D…` réellement présents dans ce fichier, résout son chemin relativement au fichier INI et convertit les diamètres si `[TRAJ] LINEAR_UNITS` est en pouces. Cela évite d’afficher les nombreuses entrées résiduelles minuscules que certaines versions de l’API de statut LinuxCNC exposent. Un vrai outil sous 1 mm reste accepté s’il est explicitement configuré ; seules les valeurs nulles ou inférieures à 0,05 mm sont considérées comme des résidus invalides.

Si le fichier contient un commentaire `OPENMILL_STOCK`, les dimensions exactes du brut sont restaurées. Sinon, un brut d’aperçu est estimé à partir des limites de la trajectoire.

Cet importeur est un outil de visualisation : LinuxCNC reste l’unique interpréteur faisant autorité. Les macros, sous-programmes et cycles fixes complexes qui ne sont pas développés en mouvements G0–G3 peuvent être absents de l’aperçu, même si LinuxCNC sait les exécuter.

L’opérateur conserve le contrôle du programme, de l’origine, de l’outil et du départ cycle.

Le statut machine expose également l’origine active `G54` à `G59.3`, l’état des références et le programme actuellement chargé. Ces informations préparent la prochaine étape de synchronisation visuelle avec Probe Basic.

## 8. Alternative officielle : fournisseur Python personnalisé

Si une installation spécifique ne charge pas correctement les onglets utilisateur, une seconde intégration est fournie :

```text
examples/probe_basic/custom_probebasic.py
examples/probe_basic/custom_config.yml
```

Copier `custom_probebasic.py` dans le dossier de configuration machine, puis fusionner ce bloc dans son `custom_config.yml` existant :

```yaml
windows:
  mainwindow:
    provider: custom_probebasic:CustomProbeBasic
    kwargs:
      confirm_exit: false
```

Cette variante hérite de `ProbeBasic` et ajoute explicitement OpenMill au `tabWidget` après l’initialisation de la fenêtre principale. Ne pas activer simultanément cette méthode et `USER_TABS_PATH`, sinon l’onglet apparaîtra deux fois.

## 9. Parcours de validation recommandé

1. Sous Windows : `python -m openmill.integration.check --smoke-test`.
2. Exécuter la suite `python -m unittest discover -s tests -v`.
3. Sur Debian : vérifier `python3 -m openmill.integration.check --json --smoke-test`.
4. Démarrer une configuration LinuxCNC simulée avec l’onglet utilisateur.
5. Ajouter une opération simple, charger le programme et vérifier le backplot Probe Basic.
6. Contrôler l’origine active, le brut, le numéro d’outil et le sens de broche.
7. Exécuter seulement ensuite une simulation, puis un essai machine à vide.

L’affichage graphique réel PyQt5/PySide6 et le comportement exact du chargeur QtPyVCP doivent toujours être confirmés sur une installation Probe Basic effective.

## Références officielles

- [Probe Basic : mécanisme des onglets utilisateur, pull request intégrée](https://github.com/kcjengr/probe_basic/pull/84)
- [Probe Basic : personnalisation Python et custom_config.yml](https://kcjengr.github.io/probe_basic/debian_12_bookworm/extending/custom_ux_hacking.html)
- [Probe Basic : enregistrement des widgets QtPyVCP](https://github.com/kcjengr/probe_basic/blob/main/pyproject.toml)
- [LinuxCNC : API Python, statut et chargement de programme](https://linuxcnc.org/docs/html/config/python-interface.html)
