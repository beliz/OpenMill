# Couverture du catalogue NativeCAM fraisage

Référence : `cnc-proton/nativecam-py3-gtk3`, commit
`7f64517dfd42577d739c71383fcb0538ebec8e4d`, fichier `catalogs/mill/menu.xml`.

OpenMill 0.11 expose les 50 composants du menu NativeCAM comme composants OpenMill
explicites, y compris ceux qui doublonnent Probe Basic ou une opération OpenMill moderne.
Chaque entrée est paramétrable et produit une trajectoire, une commande LinuxCNC ou un
élément de programme sauvegardable.

Les cinq composants `group_*` créent directement les blocs de répétition OpenMill
correspondants. `group_index` utilise le motif **Axe A** et émet une indexation avant chaque
appel. La gravure convertit les contours de la police via Qt dans Probe Basic. Les cycles de
palpage restent à simuler et valider sur la configuration HAL réelle de chaque machine.

| # | ID NativeCAM | Composant | Statut | ID OpenMill |
|---:|---|---|---|---|
| 1 | `rectangle` | Rectangle | Disponible | `nativecam_rectangle` |
| 2 | `circle` | Cercle avec méplat | Disponible | `nativecam_circle` |
| 3 | `circle2` | Cercle par deux points | Disponible | `nativecam_circle2` |
| 4 | `slot1` | Rainure par point et angle | Disponible | `nativecam_slot1` |
| 5 | `slot2` | Rainure par deux points | Disponible | `nativecam_slot2` |
| 6 | `radial_slot` | Rainure radiale | Disponible | `nativecam_radial_slot` |
| 7 | `ellipse` | Ellipse | Disponible | `nativecam_ellipse` |
| 8 | `polygon` | Polygone | Disponible | `nativecam_polygon` |
| 9 | `surf_finish` | Surfaçage | Disponible | `nativecam_surf_finish` |
| 10 | `poly_start` | Début de polyligne | Disponible | `nativecam_poly_start` |
| 11 | `polyline_to` | Ligne vers coordonnées | Disponible | `nativecam_polyline_to` |
| 12 | `polyline_pol` | Ligne polaire | Disponible | `nativecam_polyline_pol` |
| 13 | `poly_arc_ij` | Arc I/J | Disponible | `nativecam_poly_arc_ij` |
| 14 | `poly_arc_pol_ctr` | Arc par centre polaire | Disponible | `nativecam_poly_arc_pol_ctr` |
| 15 | `poly_arc_coords` | Arc vers coordonnées | Disponible | `nativecam_poly_arc_coords` |
| 16 | `poly_arc_to_pol` | Arc vers point polaire | Disponible | `nativecam_poly_arc_to_pol` |
| 17 | `poly_bisector` | Arc miroir en bout | Disponible | `nativecam_poly_bisector` |
| 18 | `poly_repeat` | Répéter une polyligne | Disponible | `nativecam_poly_repeat` |
| 19 | `poly_mir_itms` | Miroir d’éléments | Disponible | `nativecam_poly_mir_itms` |
| 20 | `poly_mirror` | Miroir de polyligne | Disponible | `nativecam_poly_mirror` |
| 21 | `cb_single` | Lamage unique | Disponible | `nativecam_cb_single` |
| 22 | `cb_slot1` | Lamages en rainure | Disponible | `nativecam_cb_slot1` |
| 23 | `cb_slot2` | Lamages entre deux points | Disponible | `nativecam_cb_slot2` |
| 24 | `cb_arc` | Lamages sur arc | Disponible | `nativecam_cb_arc` |
| 25 | `thread_milling` | Filetage à la fraise | Disponible | `nativecam_thread_milling` |
| 26 | `ttengraving` | Gravure TrueType | Disponible | `nativecam_ttengraving` |
| 27 | `circle-k` | Cercle avec clavette | Disponible | `nativecam_circle_k` |
| 28 | `drill_single` | Perçage unique | Disponible | `nativecam_drill_single` |
| 29 | `drill_arr` | Réseau de perçages | Disponible | `nativecam_drill_arr` |
| 30 | `drill_circle` | Perçages sur cercle | Disponible | `nativecam_drill_circle` |
| 31 | `drill_circle_irr` | Cercle irrégulier | Disponible | `nativecam_drill_circle_irr` |
| 32 | `drill_side` | Perçage latéral | Disponible | `nativecam_drill_side` |
| 33 | `group_std` | Groupe standard | Disponible | `nativecam_group_std` |
| 34 | `group_off` | Groupe décalé/tourné | Disponible | `nativecam_group_off` |
| 35 | `group_radial` | Groupe radial | Disponible | `nativecam_group_radial` |
| 36 | `group_arr` | Groupe rectangulaire | Disponible | `nativecam_group_arr` |
| 37 | `group_index` | Indexation axe A | Disponible | `nativecam_group_index` |
| 38 | `chng_end_mill` | Sélection fraise | Disponible | `nativecam_chng_end_mill` |
| 39 | `chng_drill` | Sélection foret/alésoir | Disponible | `nativecam_chng_drill` |
| 40 | `chng_thread_mill` | Sélection fraise à fileter | Disponible | `nativecam_chng_thread_mill` |
| 41 | `probe_edge` | Palpage d’arêtes | Disponible | `nativecam_probe_edge` |
| 42 | `probe_stock` | Palpage du brut | Disponible | `nativecam_probe_stock` |
| 43 | `probe_arr` | Réseau de palpage | Disponible | `nativecam_probe_arr` |
| 44 | `probe_z` | Palpage de surface Z | Disponible | `nativecam_probe_z` |
| 45 | `probe_hole` | Palpage d’alésage | Disponible | `nativecam_probe_hole` |
| 46 | `stock` | Matière brute | Disponible | `nativecam_stock` |
| 47 | `gcode` | G-code personnalisé | Disponible | `nativecam_gcode` |
| 48 | `gcode_file` | Inclusion de fichier | Disponible | `nativecam_gcode_file` |
| 49 | `comment` | Commentaire | Disponible | `nativecam_comment` |
| 50 | `prjdesc` | Notes de projet | Disponible | `nativecam_prjdesc` |

## Bilan OpenMill 0.11

| Couverture | Nombre |
|---|---:|
| Disponible | 50 |
| Partiel | 0 |
| Fourni par Probe Basic | 0 |
| Manquant | 0 |
| **Total audité** | **50** |
