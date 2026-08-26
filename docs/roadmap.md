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
- [x] Registre et extensions d’opérations.
- [x] Tests automatisés et CI Windows/Linux.

## Phase 2 — stratégies d’usinage robustes

- [ ] Rampes et entrées hélicoïdales.
- [ ] Passe de finition et surépaisseur.
- [ ] Sens avalant / opposition.
- [ ] Rainures, oblongs, lamages et chanfreins.
- [ ] Contours libres, polygones et gravure simple.
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

- [ ] Validation du widget dans Probe Basic simulé.
- [ ] Chargement du `.ngc` dans LinuxCNC.
- [ ] Lecture des outils et offsets actifs en direct.
- [ ] Compatibilité VTK Debian / LinuxCNC mesurée.
- [ ] Synchronisation optionnelle avec le backplot Probe Basic.
- [ ] Documentation d’installation et proposition upstream.
