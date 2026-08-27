# Architecture et principes de maintenance

## Séparation des responsabilités

Le noyau `openmill.core` dépend exclusivement de la bibliothèque standard Python. Il ne connaît ni PyQt, ni VTK, ni LinuxCNC. Cette contrainte permet de tester les stratégies sous Windows, en CI, dans un futur service ou dans une interface différente.

Les responsabilités sont réparties en quatre couches :

1. **Métier** : brut, outils, mouvements, trajectoires, projet, validation et G-code.
2. **Stratégies** : chaque opération décrit ses champs et génère des mouvements explicites.
3. **Machine** : un protocole unique expose les outils disponibles, quelle que soit la plateforme.
4. **Présentation** : formulaire Qt, vues 2D/3D, fenêtre autonome et intégration embarquée.

Un widget ne calcule jamais sa propre stratégie d’usinage. Une opération ne dessine jamais elle-même son aperçu. L’aperçu et le G-code consomment la même liste de mouvements : ce qui est affiché correspond aux déplacements exportés.

## Contrat d’une opération

Une extension hérite de `OperationPlugin` et définit :

- un `id` stable utilisé dans les fichiers JSON ;
- un `label`, une `category` et une `description` en français ;
- une séquence de `FieldSpec` pour les paramètres spécifiques ;
- une méthode `generate(operation, stock, tool)` retournant un `Toolpath`.

Les paramètres communs — profondeurs, sécurité, avances et broche — sont ajoutés automatiquement. Chaque `FieldSpec` indique ses limites, son unité et son type ; l’interface construit donc le formulaire sans code dédié.

Une opération doit lever `ValueError` si sa géométrie est impossible. Le moteur isole cette erreur, continue de calculer les autres opérations et l’interface interdit l’export tant qu’une opération activée reste invalide.

## Géométrie et stratégie réutilisables

Les nouvelles opérations ne doivent pas dupliquer leur logique de compensation. Le module `operations.profiles` centralise désormais :

- la position intérieur / sur tracé / extérieur ;
- la compensation du rayon d’outil ;
- le sens avalant / opposition ;
- la surépaisseur d’ébauche ;
- la passe latérale de finition.

Les profils rectangle, cercle et polygone fournissent seulement une fabrique de contour compensé à ce moteur. La rainure utilise la même convention de sens et de finition avec une géométrie capsule dédiée dans `core.geometry`.

Cette séparation combine désormais une géométrie et sa stratégie d’usinage avec une définition de placement indépendante. Une même opération peut être appelée une fois, en ligne, sur une grille cartésienne orientée ou sur un motif polaire. Les anciens réseaux de perçage restent lisibles dans les projets existants, mais le catalogue propose désormais des cycles de trou séparés de leur motif, dans l’esprit `CYCL DEF` puis `PATTERN DEF` d’une commande conversationnelle.

Le module `core.placement` calcule les positions absolues, transforme les trajectoires et insère les liaisons entre occurrences. Ces liaisons remontent systématiquement à la hauteur de sécurité avant tout déplacement latéral. Le moteur de validation, les aperçus, le temps estimé et le générateur G-code consomment ensuite la même trajectoire développée.

## Modèle de trajectoire

Les mouvements décrivent le **centre de l’outil**, avec position initiale, position finale, type et avance :

- `RAPID` : déplacement rapide, représenté en pointillés en 2D ;
- `PLUNGE` : plongée avec avance Z ;
- `CUT` : déplacement d’usinage avec avance XY.
- `DWELL` : temporisation au fond d’un cycle ;
- `TAP` / `TAP_RETURN` : descente et retour synchronisés d’un taraudage rigide LinuxCNC.

Les aperçus élargissent les mouvements avec le diamètre réel de l’outil. La sécurité de repli est centralisée dans `ToolpathBuilder`.

## Aperçu animé indépendant du moteur

`ToolpathPlayback`, dans `openmill.core.playback`, transforme une liste de trajectoires en image temporelle partielle. Il interpole la position de l’outil, expose les profondeurs disponibles et peut filtrer les passes Z sans dépendre de Qt ou VTK.

Deux moteurs consomment actuellement ces images : le rendu VTK accéléré et un rendu orthographique compatible construit avec `QPainter`. Ce dernier ne demande aucun contexte OpenGL et prend automatiquement le relais si l’initialisation VTK échoue ou produit une image noire.

Ce découplage permet de réutiliser le même contrôleur pour un futur aperçu global de programmes G-code : il suffira de transformer les instructions lues en objets `Motion` et `Toolpath`.

## Interface tactile

Le catalogue d’opérations génère ses cartes directement depuis le registre de plugins. Les illustrations sont vectorielles, dessinées en code, et les opérations tierces bénéficient d’un schéma de secours sans devoir fournir une image.

Les contrôles de paramètres sont eux aussi générés depuis `FieldSpec` :

- les valeurs numériques reçoivent des boutons `+` / `−` et un ajustement par glissement ;
- les pourcentages reçoivent un fader ;
- les angles disposent d’un cadran circulaire sur 360° ;
- les choix courts deviennent des boutons segmentés.

Les règles de sélection et les incréments sont testés dans le noyau Python, indépendamment de l’interface.

## Projet et compatibilité

Le projet JSON contient un `schema_version`, le brut, l’origine, l’ordre des opérations, leurs paramètres et leur placement. Les fichiers antérieurs sans bloc `placement` restent chargés comme des opérations à position unique. Les identifiants d’opération ne doivent jamais changer silencieusement : toute évolution incompatible nécessite une migration explicite.

Le générateur `.ngc` ajoute aussi un commentaire JSON `OPENMILL_STOCK`. Une future intégration Probe Basic pourra récupérer ces dimensions pour initialiser son propre aperçu de brut.

## Extensions installées séparément

Les opérations internes utilisent `@registry.register`. Les extensions distribuées séparément sont découvertes via :

```toml
[project.entry-points."openmill.operations"]
ma_fonctionnalite = "mon_paquet.module:MaClasseOperation"
```

L’installation de l’extension suffit pour ajouter l’opération au formulaire et au menu. En cas de conflit d’identifiant, le chargement échoue explicitement plutôt que de remplacer silencieusement un module existant.

## Pourquoi un dépôt indépendant ?

Un dépôt distinct permet des releases, des tests Windows, des prototypes d’interface et des évolutions rapides sans modifier Probe Basic. Le point de contact upstream reste petit : `OpenMillConversationalWidget` et `LinuxCNCMachineAdapter`.

Lorsque l’intégration sera suffisamment mûre, deux stratégies resteront possibles : conserver un paquet optionnel ou proposer les composants génériques au projet Probe Basic / QtPyVCP. Cette architecture ne verrouille pas ce choix.

Le script `installation.sh` respecte cette frontière : il ne modifie aucun fichier Probe Basic. Il expose le dépôt au Python utilisateur, déploie uniquement les deux fichiers conventionnels de l’onglet et ajoute un bloc identifié dans l’INI. La désinstallation peut donc retirer exclusivement ce qu’OpenMill a créé.
