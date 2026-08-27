# Couverture du catalogue NativeCAM fraisage

Audit effectué sur `cnc-proton/nativecam-py3-gtk3`, commit
`7f64517dfd42577d739c71383fcb0538ebec8e4d` du 19 juin 2026. La référence est
`catalogs/mill/menu.xml` : ses 50 composants sont tous présents dans la matrice ci-dessous.

Statuts :

- **Disponible** : fonction directement réalisable dans OpenMill ;
- **Partiel** : même géométrie ou fonction de base, mais paramètres/mode de saisie manquants ;
- **Hôte** : disponible dans Probe Basic, pas comme opération conversationnelle OpenMill ;
- **Manquant** : aucune fonction équivalente dans OpenMill 0.10.

| # | ID NativeCAM | Composant | Statut | Équivalent OpenMill / écart |
|---:|---|---|---|---|
| 1 | `rectangle` | Rectangle | Disponible | `profile_rectangle` et `pocket_rectangle` |
| 2 | `circle` | Cercle avec méplat optionnel | Partiel | Profil/poche circulaire, sans méplat D |
| 3 | `circle2` | Cercle défini par deux points | Partiel | Même géométrie par centre/diamètre, pas cette saisie |
| 4 | `slot1` | Rainure par point, angle et longueur | Disponible | `slot_straight` |
| 5 | `slot2` | Rainure définie par deux points | Partiel | Même géométrie, pas cette saisie |
| 6 | `radial_slot` | Rainure radiale | Manquant | — |
| 7 | `ellipse` | Ellipse | Manquant | — |
| 8 | `polygon` | Polygone | Disponible | `profile_polygon` et hexagone dédié |
| 9 | `surf_finish` | Surfaçage | Disponible | `facing` |
| 10 | `poly_start` | Début de polyligne | Manquant | — |
| 11 | `polyline_to` | Ligne vers coordonnées | Manquant | — |
| 12 | `polyline_pol` | Ligne polaire | Manquant | — |
| 13 | `poly_arc_ij` | Arc I/J | Manquant | — |
| 14 | `poly_arc_pol_ctr` | Arc par centre polaire | Manquant | — |
| 15 | `poly_arc_coords` | Arc vers coordonnées | Manquant | — |
| 16 | `poly_arc_to_pol` | Arc vers point polaire | Manquant | — |
| 17 | `poly_bisector` | Arc miroir en bout | Manquant | — |
| 18 | `poly_repeat` | Répéter des éléments de polyligne | Manquant | Répétitions OpenMill ne modifient pas une polyligne |
| 19 | `poly_mir_itms` | Miroir d’éléments | Manquant | — |
| 20 | `poly_mirror` | Miroir de polyligne | Manquant | — |
| 21 | `cb_single` | Lamage de trou unique | Manquant | Le G82 OpenMill temporise mais ne crée pas le diamètre étagé |
| 22 | `cb_slot1` | Lamage en rainure par un point | Manquant | — |
| 23 | `cb_slot2` | Lamage en rainure par deux points | Manquant | — |
| 24 | `cb_arc` | Lamage en rainure radiale | Manquant | — |
| 25 | `thread_milling` | Filetage à la fraise | Manquant | — |
| 26 | `ttengraving` | Gravure TrueType | Manquant | — |
| 27 | `circle-k` | Cercle avec clavette | Manquant | — |
| 28 | `drill_single` | Perçage unique | Disponible | Cinq cycles ponctuels : G81, G82, G83, G85 et G33.1 |
| 29 | `drill_arr` | Réseau de perçages | Disponible | Bloc Répétition Ligne ou Grille |
| 30 | `drill_circle` | Perçages sur cercle régulier | Disponible | Bloc Répétition Cercle |
| 31 | `drill_circle_irr` | Cercle de perçages irrégulier | Manquant | — |
| 32 | `drill_side` | Perçage latéral | Manquant | — |
| 33 | `group_std` | Groupe standard | Disponible | Bloc Répétition contenant plusieurs opérations |
| 34 | `group_off` | Groupe décalé/tourné | Partiel | Décalage et rotation via répétitions, pas de transformée libre dédiée |
| 35 | `group_radial` | Réseau radial | Disponible | Bloc Répétition Cercle |
| 36 | `group_arr` | Réseau rectangulaire | Disponible | Bloc Répétition Grille |
| 37 | `group_index` | Indexation axe A | Manquant | — |
| 38 | `chng_end_mill` | Sélection fraise | Disponible | Outil sélectionné dans chaque opération |
| 39 | `chng_drill` | Sélection foret/alésoir | Disponible | Outil sélectionné dans chaque opération |
| 40 | `chng_thread_mill` | Sélection fraise à fileter | Manquant | Cycle de filetage à la fraise absent |
| 41 | `probe_edge` | Palpage d’arêtes | Hôte | Onglet Palpage de Probe Basic |
| 42 | `probe_stock` | Palpage du brut | Hôte | Onglet Palpage de Probe Basic |
| 43 | `probe_arr` | Réseau de palpage vers fichier | Hôte | Fonctions de palpage Probe Basic, pas une étape OpenMill |
| 44 | `probe_z` | Palpage de surface Z | Hôte | Onglet Palpage de Probe Basic |
| 45 | `probe_hole` | Palpage d’alésage | Hôte | Onglet Palpage de Probe Basic |
| 46 | `stock` | Matière brute | Disponible | Définition X/Y/Z et origine dans la colonne Pièce |
| 47 | `gcode` | G-code personnalisé | Manquant | — |
| 48 | `gcode_file` | Inclusion d’un fichier G-code | Manquant | — |
| 49 | `comment` | Commentaire de programme | Manquant | — |
| 50 | `prjdesc` | Notes de projet | Partiel | Nom de pièce disponible, champ notes absent |

## Bilan OpenMill 0.10

| Couverture | Nombre |
|---|---:|
| Disponible | 13 |
| Partiel | 5 |
| Fourni par Probe Basic | 5 |
| Manquant | 27 |
| **Total audité** | **50** |

Les composants manquants doivent être implémentés comme opérations natives OpenMill et testés
avant de pouvoir annoncer une parité NativeCAM complète. Les fonctions de palpage ne doivent pas
être dupliquées sans raison : Probe Basic les fournit déjà dans la même interface machine.
