# Feuille de route

## Phase 1 — atelier portable

- [x] Moteur Python indépendant de LinuxCNC.
- [x] Interface Qt française et lancement Windows.
- [x] Aperçus XY, XZ, YZ et 3D VTK optionnelle.
- [x] Rendu 3D compatible sans OpenGL, rotation et zoom.
- [x] Galerie tactile illustrée et paramètres interactifs.
- [x] Brut rectangulaire et visualisation du diamètre d’outil.
- [x] Surfaçage, poches, hexagones, réseaux de perçage.
- [x] Projets multi-opérations et G-code LinuxCNC.
- [x] Placement unique, répétition linéaire, grille orientée et motif polaire.
- [x] Séparation cycle / motif inspirée de la programmation conversationnelle Heidenhain.
- [x] Perçage simple, profond, temporisé, alésage et taraudage rigide.
- [x] Registre et extensions d’opérations.
- [x] Tests automatisés et CI Windows/Linux.

## Phase 2 — stratégies d’usinage robustes

- [ ] Rampes et entrées hélicoïdales.
- [x] Moteur partagé de surépaisseur et passe de finition pour les profils.
- [x] Sens avalant / opposition pour les profils et rainures modernes.
- [x] Contours rectangulaire, circulaire et polygonal intérieur/extérieur/sur tracé.
- [x] Rainure droite et oblongue orientable.
- [ ] Étendre finition et sens de coupe aux poches historiques.
- [ ] Rainures radiales/circulaires, poches de lamage fraisées et chanfreins.
- [ ] Contours libres et gravure simple.
- [ ] Arcs `G2/G3` et réduction du nombre de segments.
- [ ] Cycles de perçage LinuxCNC lorsque pertinents.
- [ ] Bibliothèque matières, outils et recommandations d’avance.

## Phase 3 — aperçu avancé

- [x] Curseur de progression et lecture de la trajectoire.
- [x] Sélection visuelle des passes et des profondeurs.
- [x] Animation de l’outil avec vitesse réglable.
- [ ] Enlèvement de matière voxelisé ou hauteur 2.5D.
- [ ] Porte-outils, étau, brides et alertes de collision.
- [ ] Vues enregistrées, styles matériaux et captures.

## Phase 4 — LinuxCNC et Probe Basic

- [x] Validation automatisée du parcours Probe Basic simulé.
- [x] Chargement sécurisé du `.ngc` dans LinuxCNC / Probe Basic.
- [x] Lecture de la table d’outils LinuxCNC réelle.
- [ ] Compatibilité VTK Debian / LinuxCNC mesurée.
- [x] Synchronisation optionnelle avec le backplot Probe Basic.
- [x] Documentation et installateur réversible sans modification upstream.
- [x] Chargeur de catalogues Qt/JSON et langue configurable sans fork Probe Basic.
- [x] Interface OpenMill FR/US et catalogue français des commandes usuelles Probe Basic.
- [ ] Traduction des aides HTML rares et contrôle exhaustif des chaînes `notr` upstream.
- [ ] Validation sur plusieurs versions réelles de Probe Basic et proposition upstream.
