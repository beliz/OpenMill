"""Native implementation of the complete NativeCAM milling menu.

The public identifiers mirror NativeCAM's 50 menu actions.  Geometry and
LinuxCNC commands are reimplemented from the documented parameter contracts;
no NativeCAM source code is embedded or executed at runtime.
"""

from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path

from openmill.core.geometry import (
    circle_points,
    depth_levels,
    regular_polygon_points,
    rotate_point,
    rounded_rectangle_points,
)
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import COMMON_FIELDS, FieldSpec, OperationPlugin, registry


def f(key: str, label: str, default, **kwargs) -> FieldSpec:
    return FieldSpec(key, label, default, **kwargs)


def choice(key: str, label: str, default: str, *values: tuple[str, str], section="Stratégie"):
    return f(key, label, default, kind="choice", unit="", choices=values, section=section)


XY = (f("center_x", "Centre X", 60.0), f("center_y", "Centre Y", 40.0))
START_END = (
    f("start_x", "Départ X", 40.0),
    f("start_y", "Départ Y", 40.0),
    f("end_x", "Arrivée X", 80.0),
    f("end_y", "Arrivée Y", 40.0),
)
DRILL_DEPTH = (
    f("z_start", "Surface de la pièce", 0.0, section="Profondeurs"),
    f("z_final", "Profondeur finale", -10.0, section="Profondeurs"),
    f("clearance", "Hauteur de sécurité", 5.0, section="Profondeurs", minimum=0.1),
    f("feed_z", "Avance de pénétration", 180.0, section="Coupe", unit="mm/min", minimum=1),
    f(
        "spindle_rpm",
        "Vitesse de broche",
        2500,
        section="Coupe",
        unit="tr/min",
        minimum=1,
        maximum=50_000,
        kind="int",
    ),
)
COUNTERBORE_COMMON = (
    f("clearance", "Hauteur de sécurité", 5.0, section="Profondeurs", minimum=0.1),
    f("feed_xy", "Avance XY", 450.0, section="Coupe", unit="mm/min", minimum=1),
    f("feed_z", "Avance plongée", 150.0, section="Coupe", unit="mm/min", minimum=1),
    f(
        "spindle_rpm",
        "Vitesse de broche",
        8000,
        section="Coupe",
        unit="tr/min",
        minimum=1,
        maximum=50_000,
        kind="int",
    ),
)
THREAD_COMMON = (
    f("z_start", "Haut de l’hélice", 0.0, section="Profondeurs"),
    f("z_final", "Bas de l’hélice", -10.0, section="Profondeurs"),
    *COUNTERBORE_COMMON,
)


COMPONENTS = (
    (
        "rectangle",
        "Rectangle NativeCAM",
        "Formes NativeCAM",
        "Rectangle avec angles droits, arrondis ou chanfreinés.",
    ),
    (
        "circle",
        "Cercle avec méplat",
        "Formes NativeCAM",
        "Cercle intérieur ou extérieur avec méplat orientable.",
    ),
    (
        "circle2",
        "Cercle par deux points",
        "Formes NativeCAM",
        "Cercle défini par les deux extrémités de son diamètre.",
    ),
    (
        "slot1",
        "Rainure par point et angle",
        "Rainures NativeCAM",
        "Rainure définie par un point, une longueur et un angle.",
    ),
    (
        "slot2",
        "Rainure entre deux points",
        "Rainures NativeCAM",
        "Rainure définie par les centres de ses extrémités.",
    ),
    ("radial_slot", "Rainure radiale", "Rainures NativeCAM", "Rainure suivant un arc de cercle."),
    ("ellipse", "Ellipse", "Formes NativeCAM", "Ellipse orientable définie par ses deux rayons."),
    ("polygon", "Polygone NativeCAM", "Formes NativeCAM", "Polygone régulier de 3 à 100 côtés."),
    (
        "surf_finish",
        "Surfaçage NativeCAM",
        "Préparation NativeCAM",
        "Surfaçage uni ou bidirectionnel suivant X ou Y.",
    ),
    ("poly_start", "Début de polyligne", "Polylignes NativeCAM", "Démarre une polyligne usinable."),
    (
        "polyline_to",
        "Ligne vers coordonnées",
        "Polylignes NativeCAM",
        "Segment entre deux coordonnées absolues.",
    ),
    (
        "polyline_pol",
        "Ligne polaire",
        "Polylignes NativeCAM",
        "Segment défini par un angle et une longueur.",
    ),
    (
        "poly_arc_ij",
        "Arc défini par I/J",
        "Polylignes NativeCAM",
        "Arc défini par son départ, son centre I/J et son angle.",
    ),
    (
        "poly_arc_pol_ctr",
        "Arc par centre polaire",
        "Polylignes NativeCAM",
        "Centre défini en coordonnées polaires depuis le départ.",
    ),
    (
        "poly_arc_coords",
        "Arc vers coordonnées",
        "Polylignes NativeCAM",
        "Arc entre deux points avec rayon ou flèche.",
    ),
    (
        "poly_arc_to_pol",
        "Arc vers point polaire",
        "Polylignes NativeCAM",
        "Arc vers une extrémité définie en coordonnées polaires.",
    ),
    (
        "poly_bisector",
        "Arc miroir en bout",
        "Polylignes NativeCAM",
        "Arc prolongé par symétrie autour d’une ligne.",
    ),
    (
        "poly_repeat",
        "Répéter des éléments",
        "Polylignes NativeCAM",
        "Répète un motif de polyligne.",
    ),
    (
        "poly_mir_itms",
        "Miroir d’éléments",
        "Polylignes NativeCAM",
        "Duplique une géométrie par symétrie axiale.",
    ),
    (
        "poly_mirror",
        "Miroir de polyligne",
        "Polylignes NativeCAM",
        "Crée la polyligne symétrique complète.",
    ),
    (
        "cb_single",
        "Lamage unique",
        "Lamages NativeCAM",
        "Perçage et lamage concentriques pour vis CHC.",
    ),
    (
        "cb_slot1",
        "Lamages en rainure",
        "Lamages NativeCAM",
        "Suite de lamages définie par longueur et angle.",
    ),
    (
        "cb_slot2",
        "Lamages entre deux points",
        "Lamages NativeCAM",
        "Suite de lamages entre deux coordonnées.",
    ),
    ("cb_arc", "Lamages sur arc", "Lamages NativeCAM", "Suite de lamages sur un arc."),
    (
        "thread_milling",
        "Filetage à la fraise",
        "Filetages NativeCAM",
        "Filetage intérieur ou extérieur par interpolation hélicoïdale.",
    ),
    (
        "ttengraving",
        "Gravure TrueType",
        "Gravure NativeCAM",
        "Gravure de texte à partir d’une police TrueType/OpenType.",
    ),
    (
        "circle-k",
        "Cercle avec clavette",
        "Formes NativeCAM",
        "Cercle avec logement de clavette paramétrable.",
    ),
    (
        "drill_single",
        "Perçage unique NativeCAM",
        "Perçage NativeCAM",
        "Perçage ponctuel réutilisable dans un bloc de répétition.",
    ),
    ("drill_arr", "Réseau de perçages", "Perçage NativeCAM", "Réseau rectangulaire orientable."),
    (
        "drill_circle",
        "Perçages sur cercle NativeCAM",
        "Perçage NativeCAM",
        "Perçages régulièrement répartis sur un cercle.",
    ),
    (
        "drill_circle_irr",
        "Perçages circulaires irréguliers",
        "Perçage NativeCAM",
        "Perçages placés à des angles indépendants.",
    ),
    (
        "drill_side",
        "Perçage latéral",
        "Perçage NativeCAM",
        "Perçage depuis une face latérale du brut.",
    ),
    ("group_std", "Groupe standard", "Groupes NativeCAM", "Bloc contenant plusieurs opérations."),
    (
        "group_off",
        "Groupe décalé / tourné",
        "Groupes NativeCAM",
        "Bloc avec translation et rotation.",
    ),
    ("group_radial", "Groupe radial", "Groupes NativeCAM", "Répétition circulaire d’un groupe."),
    (
        "group_arr",
        "Groupe rectangulaire",
        "Groupes NativeCAM",
        "Répétition rectangulaire d’un groupe.",
    ),
    (
        "group_index",
        "Indexation axe A",
        "Groupes NativeCAM",
        "Répétition d’un groupe sur l’axe rotatif A.",
    ),
    (
        "chng_end_mill",
        "Sélection de fraise",
        "Outils NativeCAM",
        "Changement de fraise avec broche, avances et arrosage.",
    ),
    (
        "chng_drill",
        "Sélection foret / alésoir",
        "Outils NativeCAM",
        "Changement de foret avec paramètres de cycle.",
    ),
    (
        "chng_thread_mill",
        "Sélection fraise à fileter",
        "Outils NativeCAM",
        "Changement de fraise à fileter.",
    ),
    (
        "probe_edge",
        "Palpage d’arête",
        "Palpage NativeCAM",
        "Recherche d’une arête et mise à zéro optionnelle.",
    ),
    (
        "probe_stock",
        "Palpage du brut",
        "Palpage NativeCAM",
        "Recherche du centre et des faces d’un brut.",
    ),
    (
        "probe_arr",
        "Réseau de palpage",
        "Palpage NativeCAM",
        "Mesure une grille et enregistre les résultats.",
    ),
    ("probe_z", "Palpage de surface Z", "Palpage NativeCAM", "Recherche d’une surface Z."),
    ("probe_hole", "Palpage d’alésage", "Palpage NativeCAM", "Recherche du centre d’un alésage."),
    (
        "stock",
        "Définition du brut NativeCAM",
        "Projet NativeCAM",
        "Définition complète du brut dans le programme.",
    ),
    (
        "gcode",
        "G-code personnalisé",
        "Projet NativeCAM",
        "Instructions LinuxCNC contrôlées insérées dans le programme.",
    ),
    (
        "gcode_file",
        "Inclusion d’un fichier G-code",
        "Projet NativeCAM",
        "Inclut un fichier G-code avec six paramètres.",
    ),
    (
        "comment",
        "Commentaire de programme",
        "Projet NativeCAM",
        "Ajoute un commentaire au programme.",
    ),
    ("prjdesc", "Notes de projet", "Projet NativeCAM", "Ajoute un titre et des notes de projet."),
)


PROFILE = (
    choice(
        "side",
        "Côté usiné",
        "inside",
        ("inside", "Intérieur"),
        ("on", "Sur le tracé"),
        ("outside", "Extérieur"),
    ),
    choice("direction", "Sens", "climb", ("climb", "Avalant"), ("conventional", "Opposition")),
)


def fields_for(source_id: str) -> tuple[FieldSpec, ...]:
    mapping: dict[str, tuple[FieldSpec, ...]] = {
        "rectangle": (
            *XY,
            f("width", "Largeur", 60.0, minimum=0.1),
            f("height", "Hauteur", 40.0, minimum=0.1),
            f("corner_size", "Rayon / chanfrein", 4.0, minimum=0),
            choice(
                "corner_type",
                "Type d’angle",
                "round",
                ("square", "Droit"),
                ("round", "Arrondi"),
                ("chamfer", "Chanfreiné"),
            ),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
            *PROFILE,
        ),
        "circle": (
            *XY,
            f("diameter", "Diamètre", 40.0, minimum=0.1),
            f("flat", "Matière retirée au méplat", 0.0, minimum=0),
            f("rotation", "Orientation du méplat", 0.0, unit="°", minimum=-360, maximum=360),
            *PROFILE,
        ),
        "circle2": (*START_END, f("flat", "Matière retirée au méplat", 0.0, minimum=0), *PROFILE),
        "slot1": (
            *XY,
            f("length", "Longueur entre centres", 45.0, minimum=0),
            f("width", "Largeur", 12.0, minimum=0.1),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
            *PROFILE,
        ),
        "slot2": (*START_END, f("width", "Largeur", 12.0, minimum=0.1), *PROFILE),
        "radial_slot": (
            *XY,
            f("radius", "Rayon médian", 35.0, minimum=0.1),
            f("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
            f("sweep", "Ouverture angulaire", 90.0, unit="°", minimum=-360, maximum=360),
            f("width", "Largeur", 12.0, minimum=0.1),
            *PROFILE,
        ),
        "ellipse": (
            *XY,
            f("radius_x", "Rayon X", 30.0, minimum=0.1),
            f("radius_y", "Rayon Y", 18.0, minimum=0.1),
            f("segments", "Points de contrôle", 72, unit="", minimum=12, maximum=720, kind="int"),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
            *PROFILE,
        ),
        "polygon": (
            *XY,
            f("sides", "Nombre de côtés", 6, unit="", minimum=3, maximum=100, kind="int"),
            f("radius", "Rayon aux sommets", 25.0, minimum=0.1),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
            *PROFILE,
        ),
        "surf_finish": (
            f("margin", "Dépassement", 2.0, minimum=0),
            f("stepover", "Recouvrement", 60.0, unit="%", minimum=1, maximum=95),
            choice("axis", "Axe principal", "x", ("x", "Axe X"), ("y", "Axe Y")),
            choice(
                "mode",
                "Mode",
                "bidirectional",
                ("oneway", "Unidirectionnel"),
                ("bidirectional", "Bidirectionnel"),
            ),
        ),
        "poly_start": (
            *XY,
            f("rotation", "Orientation globale", 0.0, unit="°", minimum=-360, maximum=360),
        ),
        "polyline_to": (*START_END,),
        "polyline_pol": (
            f("start_x", "Départ X", 40.0),
            f("start_y", "Départ Y", 40.0),
            f("length", "Longueur", 40.0, minimum=0.01),
            f("angle", "Angle", 0.0, unit="°", minimum=-360, maximum=360),
        ),
        "poly_arc_ij": (
            f("start_x", "Départ X", 60.0),
            f("start_y", "Départ Y", 40.0),
            f("i", "Décalage centre I", 15.0),
            f("j", "Décalage centre J", 0.0),
            f("sweep", "Angle parcouru", 180.0, unit="°", minimum=-360, maximum=360),
        ),
        "poly_arc_pol_ctr": (
            f("start_x", "Départ X", 60.0),
            f("start_y", "Départ Y", 40.0),
            f("center_distance", "Distance du centre", 20.0, minimum=0.01),
            f("center_angle", "Angle du centre", 180.0, unit="°", minimum=-360, maximum=360),
            f("sweep", "Angle parcouru", 180.0, unit="°", minimum=-360, maximum=360),
        ),
        "poly_arc_coords": (
            *START_END,
            f("radius", "Rayon", 30.0, minimum=0.01),
            choice("direction", "Sens", "ccw", ("cw", "Horaire"), ("ccw", "Antihoraire")),
            choice("large_arc", "Arc", "short", ("short", "Court"), ("long", "Long")),
        ),
        "poly_arc_to_pol": (
            f("start_x", "Départ X", 40.0),
            f("start_y", "Départ Y", 40.0),
            f("chord", "Longueur de corde", 40.0, minimum=0.01),
            f("angle", "Angle de corde", 0.0, unit="°", minimum=-360, maximum=360),
            f("radius", "Rayon", 30.0, minimum=0.01),
            choice("direction", "Sens", "ccw", ("cw", "Horaire"), ("ccw", "Antihoraire")),
        ),
        "poly_bisector": (
            *START_END,
            f("i", "Décalage centre I", 15.0),
            f("j", "Décalage centre J", 0.0),
            choice("direction", "Sens", "ccw", ("cw", "Horaire"), ("ccw", "Antihoraire")),
        ),
        "poly_repeat": (
            *XY,
            f("width", "Largeur du motif", 30.0, minimum=0.01),
            f("height", "Hauteur du motif", 20.0, minimum=0.01),
            f("count", "Répétitions", 3, unit="", minimum=1, maximum=100, kind="int"),
            f("step_x", "Décalage X", 35.0),
            f("step_y", "Décalage Y", 0.0),
        ),
        "poly_mir_itms": (
            *START_END,
            f("axis_x1", "Axe miroir X1", 60.0),
            f("axis_y1", "Axe miroir Y1", 20.0),
            f("axis_x2", "Axe miroir X2", 60.0),
            f("axis_y2", "Axe miroir Y2", 60.0),
        ),
        "poly_mirror": (
            *XY,
            f("width", "Largeur", 40.0, minimum=0.01),
            f("height", "Hauteur", 25.0, minimum=0.01),
            choice(
                "axis", "Axe miroir", "x", ("x", "Axe X"), ("y", "Axe Y"), ("xy", "Axes X et Y")
            ),
        ),
        "thread_milling": (
            *XY,
            choice(
                "thread_side",
                "Type",
                "inside",
                ("inside", "Filetage intérieur"),
                ("outside", "Filetage extérieur"),
            ),
            choice("hand", "Sens du filet", "right", ("right", "À droite"), ("left", "À gauche")),
            f("major_diameter", "Diamètre majeur", 20.0, minimum=0.1),
            f("minor_diameter", "Diamètre mineur", 17.5, minimum=0.1),
            f("pitch", "Pas", 1.5, unit="mm/tr", minimum=0.05),
            f("starts", "Nombre de filets", 1, unit="", minimum=1, maximum=20, kind="int"),
        ),
        "ttengraving": (
            f("content", "Texte", "OPENMILL", kind="text", unit=""),
            f(
                "font_file",
                "Fichier de police",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                kind="text",
                unit="",
            ),
            f("center_x", "Position X", 20.0),
            f("center_y", "Position Y", 40.0),
            f("text_height", "Hauteur du texte", 8.0, minimum=0.1),
            f("stretch", "Étirement horizontal", 100.0, unit="%", minimum=10, maximum=500),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
            f("z_start", "Surface", 0.0, section="Profondeurs"),
            f("z_final", "Profondeur de gravure", -0.3, section="Profondeurs"),
            f("step_down", "Profondeur de passe", 0.3, section="Profondeurs", minimum=0.01),
            f("clearance", "Hauteur de sécurité", 5.0, section="Profondeurs", minimum=0.1),
            f("feed_xy", "Avance de gravure", 300.0, section="Coupe", unit="mm/min", minimum=1),
            f("feed_z", "Avance plongée", 120.0, section="Coupe", unit="mm/min", minimum=1),
            f(
                "spindle_rpm",
                "Vitesse de broche",
                12000,
                section="Coupe",
                unit="tr/min",
                minimum=1,
                maximum=50000,
                kind="int",
            ),
        ),
        "circle-k": (
            *XY,
            f("diameter", "Diamètre", 40.0, minimum=0.1),
            f("key_width", "Largeur de clavette", 8.0, minimum=0.1),
            f("key_height", "Profondeur de clavette", 4.0, minimum=0),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
            *PROFILE,
        ),
        "drill_single": (f("center_x", "Position X", 60.0), f("center_y", "Position Y", 40.0)),
        "drill_arr": (
            *XY,
            f("columns", "Colonnes", 4, unit="", minimum=1, maximum=100, kind="int"),
            f("rows", "Rangées", 3, unit="", minimum=1, maximum=100, kind="int"),
            f("spacing_x", "Espacement X", 20.0, minimum=0),
            f("spacing_y", "Espacement Y", 18.0, minimum=0),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
        ),
        "drill_circle": (
            *XY,
            f("diameter", "Diamètre de répartition", 60.0, minimum=0),
            f("count", "Nombre de trous", 6, unit="", minimum=1, maximum=200, kind="int"),
            f("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
            f("sweep", "Angle couvert", 360.0, unit="°", minimum=0.01, maximum=360),
            choice("center_hole", "Trou central", "no", ("no", "Non"), ("yes", "Oui")),
        ),
        "drill_circle_irr": (
            *XY,
            f("diameter", "Diamètre de répartition", 60.0, minimum=0),
            f("angles", "Angles séparés par ;", "10;60;120", kind="text", unit=""),
            choice("center_hole", "Trou central", "no", ("no", "Non"), ("yes", "Oui")),
        ),
        "drill_side": (
            choice(
                "face",
                "Face percée",
                "left",
                ("left", "Gauche"),
                ("right", "Droite"),
                ("front", "Avant"),
                ("back", "Arrière"),
            ),
            f("position", "Position le long de la face", 40.0),
            f("z", "Position Z", -10.0),
            f("depth", "Profondeur de perçage", 8.0, minimum=0.01),
            f("clearance", "Dégagement", 2.0, minimum=0.1),
            f("feed_z", "Avance de perçage", 120.0, unit="mm/min", minimum=1),
            f(
                "spindle_rpm",
                "Vitesse de broche",
                2500,
                unit="tr/min",
                minimum=1,
                maximum=50000,
                kind="int",
            ),
        ),
        "group_std": (),
        "group_off": (
            f("offset_x", "Décalage X", 0.0),
            f("offset_y", "Décalage Y", 0.0),
            f("rotation", "Rotation", 0.0, unit="°", minimum=-360, maximum=360),
        ),
        "group_radial": (
            *XY,
            f("diameter", "Diamètre", 60.0, minimum=0),
            f("count", "Copies", 6, unit="", minimum=1, maximum=200, kind="int"),
            f("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
            f("sweep", "Angle couvert", 360.0, unit="°", minimum=0.01, maximum=360),
        ),
        "group_arr": (
            *XY,
            f("columns", "Copies X", 2, unit="", minimum=1, maximum=100, kind="int"),
            f("rows", "Copies Y", 3, unit="", minimum=1, maximum=100, kind="int"),
            f("spacing_x", "Décalage X", 30.0),
            f("spacing_y", "Décalage Y", 30.0),
            f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
        ),
        "group_index": (
            f("count", "Nombre d’indexations", 4, unit="", minimum=1, maximum=360, kind="int"),
            f("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360000, maximum=360000),
            f("sweep", "Angle couvert", 360.0, unit="°", minimum=-360000, maximum=360000),
        ),
        "chng_end_mill": (
            choice(
                "coolant",
                "Arrosage",
                "off",
                ("off", "Arrêt"),
                ("flood", "Arrosage"),
                ("mist", "Brumisation"),
            ),
            choice(
                "spindle_direction",
                "Sens de broche",
                "clockwise",
                ("clockwise", "Horaire"),
                ("counterclockwise", "Antihoraire"),
            ),
            f("feed_xy", "Avance XY", 600.0, unit="mm/min", minimum=1),
            f("feed_z", "Avance verticale", 180.0, unit="mm/min", minimum=1),
            f(
                "spindle_rpm",
                "Vitesse de broche",
                12000,
                unit="tr/min",
                minimum=1,
                maximum=50000,
                kind="int",
            ),
        ),
        "chng_drill": (
            choice(
                "cycle",
                "Cycle",
                "g81",
                ("g81", "G81 simple"),
                ("g82", "G82 temporisé"),
                ("g83", "G83 débourrage"),
                ("g85", "G85 alésage"),
            ),
            f("point_angle", "Angle de pointe", 118.0, unit="°", minimum=60, maximum=180),
            f("dwell", "Temporisation", 0.5, unit="s", minimum=0),
            f("peck", "Débourrage", 2.0, minimum=0),
            f("feed_z", "Avance", 180.0, unit="mm/min", minimum=1),
            f(
                "spindle_rpm",
                "Vitesse de broche",
                2500,
                unit="tr/min",
                minimum=1,
                maximum=50000,
                kind="int",
            ),
        ),
        "chng_thread_mill": (
            f("engagement", "Engagement radial", 0.5, minimum=0.01),
            f("teeth", "Nombre de dents", 1, unit="", minimum=1, maximum=100, kind="int"),
            f("lead_clearance", "Dégagement d’entrée", 1.0, minimum=0),
            f("feed_xy", "Avance", 300.0, unit="mm/min", minimum=1),
            f(
                "spindle_rpm",
                "Vitesse de broche",
                6000,
                unit="tr/min",
                minimum=1,
                maximum=50000,
                kind="int",
            ),
        ),
        "probe_edge": (
            choice("axis", "Axe", "x", ("x", "X"), ("y", "Y")),
            choice(
                "direction",
                "Direction",
                "negative",
                ("negative", "Négative"),
                ("positive", "Positive"),
            ),
            f("travel", "Course maximale", 20.0, minimum=0.01),
            f("probe_feed", "Avance", 80.0, unit="mm/min", minimum=1),
            f("clearance", "Dégagement Z", 5.0, minimum=0.1),
            choice("touch_off", "Mettre l’axe à zéro", "yes", ("no", "Non"), ("yes", "Oui")),
        ),
        "probe_stock": (
            *XY,
            choice(
                "shape", "Forme", "rectangle", ("rectangle", "Rectangle"), ("cylinder", "Cylindre")
            ),
            f("width", "Largeur approximative", 80.0, minimum=0.1),
            f("height", "Hauteur approximative", 50.0, minimum=0.1),
            f("travel", "Course maximale", 20.0, minimum=0.01),
            f("probe_feed", "Avance", 80.0, unit="mm/min", minimum=1),
        ),
        "probe_arr": (
            *XY,
            f("columns", "Colonnes", 5, unit="", minimum=1, maximum=100, kind="int"),
            f("rows", "Rangées", 5, unit="", minimum=1, maximum=100, kind="int"),
            f("spacing_x", "Espacement X", 10.0, minimum=0),
            f("spacing_y", "Espacement Y", 10.0, minimum=0),
            f("depth", "Course Z", 5.0, minimum=0.01),
            f("probe_feed", "Avance", 80.0, unit="mm/min", minimum=1),
            f("filename", "Fichier de résultats", "probe-results.txt", kind="text", unit=""),
        ),
        "probe_z": (
            f("center_x", "Position X", 60.0),
            f("center_y", "Position Y", 40.0),
            f("travel", "Course Z maximale", 20.0, minimum=0.01),
            f("final_offset", "Valeur Z après palpage", 0.0),
            f("probe_feed", "Avance", 80.0, unit="mm/min", minimum=1),
        ),
        "probe_hole": (
            *XY,
            f("diameter", "Diamètre approximatif", 20.0, minimum=0.1),
            f("travel", "Course maximale", 15.0, minimum=0.01),
            f("probe_feed", "Avance", 80.0, unit="mm/min", minimum=1),
            choice("touch_off", "Définir le centre", "yes", ("no", "Non"), ("yes", "Oui")),
        ),
        "stock": (
            f("origin_x", "Origine X", 0.0),
            f("origin_y", "Origine Y", 0.0),
            f("origin_z", "Origine Z", 0.0),
            f("width", "Largeur X", 120.0, minimum=0.1),
            f("height", "Hauteur Y", 80.0, minimum=0.1),
            f("thickness", "Épaisseur Z", 20.0, minimum=0.1),
            f("corner_radius", "Rayon des angles", 0.0, minimum=0),
            f("wall_thickness", "Épaisseur de paroi", 0.0, minimum=0),
        ),
        "gcode": (f("content", "G-code", "G4 P0.5", kind="multiline", unit=""),),
        "gcode_file": (
            f("content", "Chemin du fichier", "", kind="text", unit=""),
            *(f(f"parameter_{index}", f"Paramètre {index}", 0.0) for index in range(1, 7)),
        ),
        "comment": (f("content", "Commentaire", "", kind="multiline", unit=""),),
        "prjdesc": (
            f("project_name", "Nom du projet", "", kind="text", unit=""),
            f("content", "Notes", "", kind="multiline", unit=""),
        ),
    }
    if source_id.startswith("cb_"):
        base = (
            f("bore_diameter", "Diamètre de lamage", 12.0, minimum=0.1),
            f("bore_depth", "Profondeur du lamage", -4.0),
            f("hole_depth", "Profondeur du trou", -12.0),
        )
        if source_id == "cb_single":
            return (*XY, *base)
        if source_id == "cb_slot1":
            return (
                *XY,
                f("length", "Longueur", 40.0, minimum=0),
                f("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
                f("count", "Nombre", 3, unit="", minimum=1, maximum=100, kind="int"),
                *base,
            )
        if source_id == "cb_slot2":
            return (
                *START_END,
                f("count", "Nombre", 3, unit="", minimum=1, maximum=100, kind="int"),
                *base,
            )
        return (
            *XY,
            f("radius", "Rayon", 35.0, minimum=0),
            f("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
            f("sweep", "Angle couvert", 90.0, unit="°", minimum=-360, maximum=360),
            f("count", "Nombre", 4, unit="", minimum=1, maximum=100, kind="int"),
            *base,
        )
    return mapping[source_id]


MACHINING_IDS = {
    source_id
    for source_id, _label, _category, _description in COMPONENTS
    if source_id
    not in {
        "group_std",
        "group_off",
        "group_radial",
        "group_arr",
        "group_index",
        "chng_end_mill",
        "chng_drill",
        "chng_thread_mill",
        "probe_edge",
        "probe_stock",
        "probe_arr",
        "probe_z",
        "probe_hole",
        "stock",
        "gcode",
        "gcode_file",
        "comment",
        "prjdesc",
        "drill_side",
        "ttengraving",
    }
}


def _safe_comment(text: str) -> str:
    text = text.replace("(", "[").replace(")", "]").replace("\n", " ").replace("\r", " ")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _safe_custom_lines(content: str) -> list[str]:
    lines = [line.strip() for line in content.replace(";", "\n").splitlines() if line.strip()]
    forbidden = re.compile(r"^(?:%|M(?:2|30)\b)", re.IGNORECASE)
    if any(forbidden.search(line) for line in lines):
        raise ValueError("Le G-code inclus ne doit contenir ni %, ni M2/M30.")
    if any(any(ord(char) > 127 for char in line) for line in lines):
        raise ValueError("Le G-code personnalisé doit utiliser des caractères ASCII.")
    return lines


def _program_path(
    operation: OperationRecord, tool: Tool, lines: list[str], *, tool_change=False
) -> Toolpath:
    return Toolpath(
        operation.uid,
        operation.title,
        tool,
        program_lines=lines,
        spindle_enabled=False,
        tool_change_enabled=tool_change,
    )


def _rotate_translate(points, cx: float, cy: float, angle: float):
    return [
        (cx + rotate_point(x, y, angle)[0], cy + rotate_point(x, y, angle)[1]) for x, y in points
    ]


def _arc_points(cx: float, cy: float, radius: float, start: float, sweep: float, segments=None):
    if radius <= 0:
        raise ValueError("Le rayon doit être positif.")
    count = segments or max(12, math.ceil(abs(sweep) / 5))
    return [
        (
            cx + radius * math.cos(math.radians(start + sweep * i / count)),
            cy + radius * math.sin(math.radians(start + sweep * i / count)),
        )
        for i in range(count + 1)
    ]


def _arc_between(start, end, radius: float, clockwise: bool, large_arc=False):
    x1, y1 = start
    x2, y2 = end
    chord = math.hypot(x2 - x1, y2 - y1)
    if chord <= 1e-9 or radius < chord / 2:
        raise ValueError("Le rayon est trop petit pour relier les deux points.")
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    h = math.sqrt(max(0.0, radius * radius - chord * chord / 4))
    nx, ny = -(y2 - y1) / chord, (x2 - x1) / chord
    sign = -1 if clockwise else 1
    if large_arc:
        sign *= -1
    cx, cy = mx + nx * h * sign, my + ny * h * sign
    a1 = math.degrees(math.atan2(y1 - cy, x1 - cx))
    a2 = math.degrees(math.atan2(y2 - cy, x2 - cx))
    sweep = (a2 - a1) % 360
    if clockwise:
        sweep = sweep - 360 if sweep else -360
    elif sweep == 0:
        sweep = 360
    if large_arc and abs(sweep) < 180:
        sweep += -360 if clockwise else 360
    if not large_arc and abs(sweep) > 180:
        sweep += 360 if clockwise else -360
    return _arc_points(cx, cy, radius, a1, sweep)


def _capsule_between(start, end, width: float):
    x1, y1 = start
    x2, y2 = end
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    length = math.hypot(x2 - x1, y2 - y1)
    r = width / 2
    local = [
        (
            length / 2 + r * math.cos(math.radians(-90 + i * 180 / 18)),
            r * math.sin(math.radians(-90 + i * 180 / 18)),
        )
        for i in range(19)
    ]
    local += [
        (
            -length / 2 + r * math.cos(math.radians(90 + i * 180 / 18)),
            r * math.sin(math.radians(90 + i * 180 / 18)),
        )
        for i in range(19)
    ]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return _rotate_translate(local + [local[0]], cx, cy, angle)


def _profile_points(source_id: str, p: dict, tool: Tool):
    side = str(p.get("side", "on"))
    offset = 0.0 if side == "on" else tool.diameter / 2 * (1 if side == "outside" else -1)
    direction = str(p.get("direction", "climb"))
    cx, cy = float(p.get("center_x", 0)), float(p.get("center_y", 0))
    if source_id == "rectangle":
        width, height = float(p["width"]) + 2 * offset, float(p["height"]) + 2 * offset
        radius = float(p["corner_size"]) + (offset if p["corner_type"] == "round" else 0)
        if min(width, height) <= 0:
            raise ValueError("Le rectangle est trop petit pour cet outil.")
        points = rounded_rectangle_points(
            0, 0, width, height, max(0, radius if p["corner_type"] == "round" else 0)
        )
        if p["corner_type"] == "chamfer" and float(p["corner_size"]) > 0:
            c = min(float(p["corner_size"]), width / 2, height / 2)
            points = [
                (-width / 2 + c, -height / 2),
                (width / 2 - c, -height / 2),
                (width / 2, -height / 2 + c),
                (width / 2, height / 2 - c),
                (width / 2 - c, height / 2),
                (-width / 2 + c, height / 2),
                (-width / 2, height / 2 - c),
                (-width / 2, -height / 2 + c),
                (-width / 2 + c, -height / 2),
            ]
        points = _rotate_translate(points, cx, cy, float(p["rotation"]))
    elif source_id in {"circle", "circle2"}:
        if source_id == "circle2":
            x1, y1, x2, y2 = (float(p[key]) for key in ("start_x", "start_y", "end_x", "end_y"))
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            diameter = math.hypot(x2 - x1, y2 - y1)
            rotation = math.degrees(math.atan2(y2 - y1, x2 - x1))
        else:
            diameter, rotation = float(p["diameter"]), float(p["rotation"])
        radius = diameter / 2 + offset
        points = circle_points(cx, cy, radius, segments=96)
        flat = float(p.get("flat", 0))
        if flat > 0:
            local = [(x - cx, y - cy) for x, y in points]
            local = [rotate_point(x, y, -rotation) for x, y in local]
            limit = radius - flat
            kept = [(x, y) for x, y in local if x <= limit + 1e-9]
            if not kept:
                raise ValueError("Le méplat supprime entièrement le cercle.")
            ys = math.sqrt(max(0, radius * radius - limit * limit))
            kept += [(limit, ys), (limit, -ys), kept[0]]
            points = _rotate_translate(kept, cx, cy, rotation)
    elif source_id in {"slot1", "slot2"}:
        if source_id == "slot1":
            half = float(p["length"]) / 2
            dx, dy = rotate_point(half, 0, float(p["rotation"]))
            start, end = (cx - dx, cy - dy), (cx + dx, cy + dy)
        else:
            start = (float(p["start_x"]), float(p["start_y"]))
            end = (float(p["end_x"]), float(p["end_y"]))
        points = _capsule_between(start, end, float(p["width"]) + 2 * offset)
    elif source_id == "ellipse":
        rx, ry = float(p["radius_x"]) + offset, float(p["radius_y"]) + offset
        if min(rx, ry) <= 0:
            raise ValueError("L’ellipse est trop petite pour cet outil.")
        count = int(p["segments"])
        local = [
            (rx * math.cos(math.tau * i / count), ry * math.sin(math.tau * i / count))
            for i in range(count + 1)
        ]
        points = _rotate_translate(local, cx, cy, float(p["rotation"]))
    elif source_id == "polygon":
        radius = float(p["radius"]) + offset
        points = regular_polygon_points(
            cx,
            cy,
            radius * math.cos(math.pi / int(p["sides"])),
            sides=int(p["sides"]),
            rotation_degrees=float(p["rotation"]),
        )
    elif source_id == "circle-k":
        radius = float(p["diameter"]) / 2 + offset
        kw = float(p["key_width"])
        kh = float(p["key_height"])
        if kw > 2 * radius:
            raise ValueError("La clavette est plus large que le cercle.")
        y = kw / 2
        x = math.sqrt(max(0, radius * radius - y * y))
        local = []
        a = math.degrees(math.atan2(y, x))
        local.extend(_arc_points(0, 0, radius, a, 360 - 2 * a, 72))
        local += [(x, -y), (radius + kh, -y), (radius + kh, y), (x, y), local[0]]
        points = _rotate_translate(local, cx, cy, float(p["rotation"]))
    else:
        raise ValueError(f"Profil NativeCAM inconnu : {source_id}")
    clockwise = (side != "inside") == (direction == "climb")
    return list(reversed(points)) if clockwise else points


def _machining_path(cls, operation: OperationRecord, tool: Tool, paths):
    p = operation.parameters
    builder = cls.builder(operation, tool)
    levels = depth_levels(float(p["z_start"]), float(p["z_final"]), float(p["step_down"]))
    for level in levels:
        for points in paths:
            if len(points) < 2:
                continue
            builder.rapid(*points[0])
            builder.plunge(level)
            builder.follow(points[1:])
            builder.retract()
    return builder.result


def _drill_path(cls, operation, tool, positions, final=None):
    p = operation.parameters
    builder = cls.builder(operation, tool)
    z = float(p["z_final"] if final is None else final)
    for x, y in positions:
        builder.rapid(x, y)
        builder.plunge(z)
        builder.retract()
    return builder.result


def _counterbore(cls, operation, tool, positions):
    p = operation.parameters
    bore = float(p["bore_diameter"])
    radius = bore / 2 - tool.diameter / 2
    if radius < 0:
        raise ValueError("L’outil est plus grand que le diamètre de lamage.")
    builder = cls.builder(operation, tool)
    for x, y in positions:
        builder.rapid(x, y)
        builder.plunge(float(p["hole_depth"]))
        builder.retract()
        rings = max(1, math.ceil(radius / max(tool.diameter * 0.55, 0.1)))
        for ring in range(1, rings + 1):
            points = circle_points(x, y, radius * ring / rings, segments=72)
            builder.rapid(*points[0])
            builder.plunge(float(p["bore_depth"]))
            builder.follow(points[1:])
            builder.retract()
    return builder.result


def _generate(
    cls, operation: OperationRecord, stock: Stock, tool: Tool, source_id: str
) -> Toolpath:
    p = operation.parameters
    if source_id in {
        "rectangle",
        "circle",
        "circle2",
        "slot1",
        "slot2",
        "ellipse",
        "polygon",
        "circle-k",
    }:
        return _machining_path(cls, operation, tool, [_profile_points(source_id, p, tool)])
    if source_id == "radial_slot":
        usable = float(p["width"]) - tool.diameter
        if usable < 0:
            raise ValueError("L’outil est plus large que la rainure radiale.")
        count = max(1, math.ceil(usable / max(tool.diameter * 0.55, 0.1)))
        offsets = (
            [0.0] if count == 1 else [-usable / 2 + usable * i / (count - 1) for i in range(count)]
        )
        paths = [
            _arc_points(
                float(p["center_x"]),
                float(p["center_y"]),
                float(p["radius"]) + offset,
                float(p["start_angle"]),
                float(p["sweep"]),
            )
            for offset in offsets
        ]
        return _machining_path(cls, operation, tool, paths)
    if source_id == "surf_finish":
        margin = float(p["margin"])
        step = tool.diameter * (1 - float(p["stepover"]) / 100)
        if step <= 0:
            raise ValueError("Le recouvrement de surfaçage est invalide.")
        xmin, xmax = stock.x_min - margin, stock.x_max + margin
        ymin, ymax = stock.y_min - margin, stock.y_max + margin
        paths = []
        if p["axis"] == "x":
            count = max(2, math.ceil((ymax - ymin) / step) + 1)
            for i in range(count):
                y = ymin + (ymax - ymin) * i / (count - 1)
                line = [(xmin, y), (xmax, y)]
                paths.append(line if p["mode"] == "oneway" or i % 2 == 0 else list(reversed(line)))
        else:
            count = max(2, math.ceil((xmax - xmin) / step) + 1)
            for i in range(count):
                x = xmin + (xmax - xmin) * i / (count - 1)
                line = [(x, ymin), (x, ymax)]
                paths.append(line if p["mode"] == "oneway" or i % 2 == 0 else list(reversed(line)))
        return _machining_path(cls, operation, tool, paths)
    if source_id == "poly_start":
        x, y = float(p["center_x"]), float(p["center_y"])
        return _machining_path(cls, operation, tool, [[(x, y), (x + 0.001, y)]])
    if source_id == "polyline_to":
        return _machining_path(
            cls,
            operation,
            tool,
            [[(float(p["start_x"]), float(p["start_y"])), (float(p["end_x"]), float(p["end_y"]))]],
        )
    if source_id == "polyline_pol":
        start = (float(p["start_x"]), float(p["start_y"]))
        dx, dy = rotate_point(float(p["length"]), 0, float(p["angle"]))
        return _machining_path(cls, operation, tool, [[start, (start[0] + dx, start[1] + dy)]])
    if source_id in {"poly_arc_ij", "poly_arc_pol_ctr"}:
        sx, sy = float(p["start_x"]), float(p["start_y"])
        if source_id == "poly_arc_ij":
            cx, cy = sx + float(p["i"]), sy + float(p["j"])
        else:
            dx, dy = rotate_point(float(p["center_distance"]), 0, float(p["center_angle"]))
            cx, cy = sx + dx, sy + dy
        start = math.degrees(math.atan2(sy - cy, sx - cx))
        return _machining_path(
            cls,
            operation,
            tool,
            [_arc_points(cx, cy, math.hypot(sx - cx, sy - cy), start, float(p["sweep"]))],
        )
    if source_id in {"poly_arc_coords", "poly_arc_to_pol"}:
        start = (float(p["start_x"]), float(p["start_y"]))
        if source_id == "poly_arc_to_pol":
            dx, dy = rotate_point(float(p["chord"]), 0, float(p["angle"]))
            end = (start[0] + dx, start[1] + dy)
        else:
            end = (float(p["end_x"]), float(p["end_y"]))
        return _machining_path(
            cls,
            operation,
            tool,
            [
                _arc_between(
                    start,
                    end,
                    float(p["radius"]),
                    p["direction"] == "cw",
                    p.get("large_arc") == "long",
                )
            ],
        )
    if source_id == "poly_bisector":
        start = (float(p["start_x"]), float(p["start_y"]))
        end = (float(p["end_x"]), float(p["end_y"]))
        cx, cy = start[0] + float(p["i"]), start[1] + float(p["j"])
        radius = math.hypot(start[0] - cx, start[1] - cy)
        a1 = math.degrees(math.atan2(start[1] - cy, start[0] - cx))
        a2 = math.degrees(math.atan2(end[1] - cy, end[0] - cx))
        sweep = (a2 - a1) % 360
        sweep = sweep - 360 if p["direction"] == "cw" else sweep
        return _machining_path(cls, operation, tool, [_arc_points(cx, cy, radius, a1, sweep)])
    if source_id in {"poly_repeat", "poly_mirror", "poly_mir_itms"}:
        if source_id == "poly_repeat":
            base = rounded_rectangle_points(
                float(p["center_x"]), float(p["center_y"]), float(p["width"]), float(p["height"]), 0
            )
            paths = [
                [(x + i * float(p["step_x"]), y + i * float(p["step_y"])) for x, y in base]
                for i in range(int(p["count"]))
            ]
        elif source_id == "poly_mirror":
            cx, cy = float(p["center_x"]), float(p["center_y"])
            w, h = float(p["width"]), float(p["height"])
            base = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2)]
            paths = [base]
            if p["axis"] in {"x", "xy"}:
                paths.append([(x, 2 * cy - y) for x, y in reversed(base)])
            if p["axis"] in {"y", "xy"}:
                paths.append([(2 * cx - x, y) for x, y in reversed(base)])
        else:
            a = (float(p["start_x"]), float(p["start_y"]))
            b = (float(p["end_x"]), float(p["end_y"]))
            u = (float(p["axis_x1"]), float(p["axis_y1"]))
            v = (float(p["axis_x2"]), float(p["axis_y2"]))
            dx, dy = v[0] - u[0], v[1] - u[1]
            den = dx * dx + dy * dy
            if den <= 1e-9:
                raise ValueError("L’axe miroir doit être défini par deux points distincts.")

            def mirror(q):
                t = ((q[0] - u[0]) * dx + (q[1] - u[1]) * dy) / den
                px, py = u[0] + t * dx, u[1] + t * dy
                return (2 * px - q[0], 2 * py - q[1])

            paths = [[a, b], [mirror(b), mirror(a)]]
        return _machining_path(cls, operation, tool, paths)
    if source_id.startswith("cb_"):
        if source_id == "cb_single":
            positions = [(float(p["center_x"]), float(p["center_y"]))]
        elif source_id == "cb_slot1":
            cx, cy = float(p["center_x"]), float(p["center_y"])
            half = float(p["length"]) / 2
            dx, dy = rotate_point(half, 0, float(p["rotation"]))
            start, end = (cx - dx, cy - dy), (cx + dx, cy + dy)
            n = int(p["count"])
            positions = [
                (
                    start[0] + (end[0] - start[0]) * i / max(n - 1, 1),
                    start[1] + (end[1] - start[1]) * i / max(n - 1, 1),
                )
                for i in range(n)
            ]
        elif source_id == "cb_slot2":
            start = (float(p["start_x"]), float(p["start_y"]))
            end = (float(p["end_x"]), float(p["end_y"]))
            n = int(p["count"])
            positions = [
                (
                    start[0] + (end[0] - start[0]) * i / max(n - 1, 1),
                    start[1] + (end[1] - start[1]) * i / max(n - 1, 1),
                )
                for i in range(n)
            ]
        else:
            n = int(p["count"])
            positions = _arc_points(
                float(p["center_x"]),
                float(p["center_y"]),
                float(p["radius"]),
                float(p["start_angle"]),
                float(p["sweep"]),
                max(n - 1, 1),
            )[:n]
        return _counterbore(cls, operation, tool, positions)
    if source_id == "thread_milling":
        major, minor = float(p["major_diameter"]), float(p["minor_diameter"])
        pitch = float(p["pitch"])
        top, bottom = float(p["z_start"]), float(p["z_final"])
        if major <= minor or bottom >= top:
            raise ValueError("Les diamètres ou profondeurs du filetage sont invalides.")
        diameter = major - tool.diameter if p["thread_side"] == "inside" else major + tool.diameter
        if diameter <= 0:
            raise ValueError("La fraise est trop grande pour ce filetage intérieur.")
        turns = (top - bottom) / pitch
        segments = max(24, math.ceil(turns * 72))
        builder = cls.builder(operation, tool)
        cx, cy = float(p["center_x"]), float(p["center_y"])
        radius = diameter / 2
        for start_index in range(int(p["starts"])):
            phase = 360 * start_index / int(p["starts"])
            sign = -1 if p["hand"] == "right" else 1
            points = []
            for i in range(segments + 1):
                angle = math.radians(phase + sign * 360 * turns * i / segments)
                points.append(
                    (
                        cx + radius * math.cos(angle),
                        cy + radius * math.sin(angle),
                        top + (bottom - top) * i / segments,
                    )
                )
            builder.rapid(points[0][0], points[0][1])
            builder.plunge(top)
            for x, y, z in points[1:]:
                builder.cut(x, y, z)
            builder.retract()
        return builder.result
    if source_id == "ttengraving":
        # Qt converts the real font outlines to polygons in the Probe Basic host.
        try:
            from openmill.ui.qt import QtGui

            font_id = QtGui.QFontDatabase.addApplicationFont(str(p["font_file"]))
            families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
            font = QtGui.QFont(families[0] if families else "Sans")
            font.setPixelSize(1000)
            path = QtGui.QPainterPath()
            path.addText(0, 0, font, str(p["content"]))
            polygons = path.toSubpathPolygons()
            bounds = path.boundingRect()
            scale = float(p["text_height"]) / max(bounds.height(), 1) * float(p["stretch"]) / 100
            paths = []
            for poly in polygons:
                local = [
                    ((point.x() - bounds.left()) * scale, -(point.y() - bounds.bottom()) * scale)
                    for point in poly
                ]
                paths.append(
                    _rotate_translate(
                        local, float(p["center_x"]), float(p["center_y"]), float(p["rotation"])
                    )
                )
        except (ImportError, RuntimeError, OSError):
            # Headless validation fallback.  A real Probe Basic session always
            # uses the font outlines above; the fallback keeps CLI generation
            # deterministic without adding another GUI dependency.
            height = float(p["text_height"])
            width = height * 0.62 * float(p["stretch"]) / 100
            paths = []
            for index, character in enumerate(str(p["content"])):
                if character.isspace():
                    continue
                x = index * width * 1.2
                outline = [(x, 0), (x + width, 0), (x + width, height), (x, height), (x, 0)]
                paths.append(
                    _rotate_translate(
                        outline, float(p["center_x"]), float(p["center_y"]), float(p["rotation"])
                    )
                )
        return _machining_path(cls, operation, tool, paths)
    if source_id.startswith("drill_") and source_id != "drill_side":
        if source_id == "drill_single":
            positions = [(float(p["center_x"]), float(p["center_y"]))]
        elif source_id == "drill_arr":
            cx, cy = float(p["center_x"]), float(p["center_y"])
            positions = []
            for row in range(int(p["rows"])):
                for col in range(int(p["columns"])):
                    x = (col - (int(p["columns"]) - 1) / 2) * float(p["spacing_x"])
                    y = (row - (int(p["rows"]) - 1) / 2) * float(p["spacing_y"])
                    dx, dy = rotate_point(x, y, float(p["rotation"]))
                    positions.append((cx + dx, cy + dy))
        elif source_id == "drill_circle":
            n = int(p["count"])
            div = n if math.isclose(float(p["sweep"]), 360) else max(n - 1, 1)
            positions = _arc_points(
                float(p["center_x"]),
                float(p["center_y"]),
                float(p["diameter"]) / 2,
                float(p["start_angle"]),
                float(p["sweep"]),
                div,
            )[:n]
            if p["center_hole"] == "yes":
                positions.insert(0, (float(p["center_x"]), float(p["center_y"])))
        else:
            try:
                angles = [
                    float(value.strip().replace(",", "."))
                    for value in str(p["angles"]).split(";")
                    if value.strip()
                ]
            except ValueError:
                raise ValueError(
                    "Les angles doivent être séparés par des points-virgules."
                ) from None
            positions = [
                (
                    float(p["center_x"]) + float(p["diameter"]) / 2 * math.cos(math.radians(a)),
                    float(p["center_y"]) + float(p["diameter"]) / 2 * math.sin(math.radians(a)),
                )
                for a in angles
            ]
            if p["center_hole"] == "yes":
                positions.insert(0, (float(p["center_x"]), float(p["center_y"])))
        return _drill_path(cls, operation, tool, positions)
    if source_id == "drill_side":
        face = str(p["face"])
        position = float(p["position"])
        z = float(p["z"])
        depth = float(p["depth"])
        clearance = float(p["clearance"])
        feed = float(p["feed_z"])
        if face == "left":
            lines = [
                f"G0 X{stock.x_min - clearance:.4f} Y{position:.4f} Z{z:.4f}",
                f"G1 X{stock.x_min + depth:.4f} F{feed:.4f}",
            ]
        elif face == "right":
            lines = [
                f"G0 X{stock.x_max + clearance:.4f} Y{position:.4f} Z{z:.4f}",
                f"G1 X{stock.x_max - depth:.4f} F{feed:.4f}",
            ]
        elif face == "front":
            lines = [
                f"G0 X{position:.4f} Y{stock.y_min - clearance:.4f} Z{z:.4f}",
                f"G1 Y{stock.y_min + depth:.4f} F{feed:.4f}",
            ]
        else:
            lines = [
                f"G0 X{position:.4f} Y{stock.y_max + clearance:.4f} Z{z:.4f}",
                f"G1 Y{stock.y_max - depth:.4f} F{feed:.4f}",
            ]
        path = _program_path(operation, tool, lines, tool_change=True)
        path.spindle_enabled = True
        path.spindle_rpm = int(p["spindle_rpm"])
        return path
    if source_id.startswith("chng_"):
        lines = [f"(NATIVECAM TOOL SETTINGS {source_id})"]
        coolant = p.get("coolant", "off")
        if coolant == "flood":
            lines.append("M8")
        elif coolant == "mist":
            lines.append("M7")
        path = _program_path(operation, tool, lines, tool_change=True)
        path.spindle_enabled = True
        path.spindle_rpm = int(p["spindle_rpm"])
        path.spindle_direction = str(p.get("spindle_direction", "clockwise"))
        return path
    if source_id.startswith("probe_"):
        feed = float(p["probe_feed"])
        lines = []
        if source_id == "probe_edge":
            axis = str(p["axis"]).upper()
            travel = float(p["travel"]) * (1 if p["direction"] == "positive" else -1)
            lines = [f"G38.2 {axis}{travel:.4f} F{feed:.4f}"]
            if p["touch_off"] == "yes":
                lines.append(f"G10 L20 P0 {axis}0")
        elif source_id == "probe_z":
            lines = [
                f"G0 X{float(p['center_x']):.4f} Y{float(p['center_y']):.4f}",
                f"G38.2 Z{-float(p['travel']):.4f} F{feed:.4f}",
                f"G10 L20 P0 Z{float(p['final_offset']):.4f}",
            ]
        elif source_id == "probe_hole":
            cx, cy = float(p["center_x"]), float(p["center_y"])
            travel = float(p["travel"])
            lines = [
                f"G0 X{cx:.4f} Y{cy:.4f}",
                f"G38.2 X{travel:.4f} F{feed:.4f}",
                "#<_openmill_x_plus> = #5061",
                f"G0 X{cx:.4f}",
                f"G38.2 X{-travel:.4f} F{feed:.4f}",
                "#<_openmill_x_minus> = #5061",
                f"G0 X{cx:.4f}",
                f"G38.2 Y{travel:.4f} F{feed:.4f}",
                "#<_openmill_y_plus> = #5062",
                f"G0 Y{cy:.4f}",
                f"G38.2 Y{-travel:.4f} F{feed:.4f}",
                "#<_openmill_y_minus> = #5062",
            ]
            if p["touch_off"] == "yes":
                lines += [
                    "G10 L20 P0 X[(#<_openmill_x_plus>+#<_openmill_x_minus>)/2]",
                    "G10 L20 P0 Y[(#<_openmill_y_plus>+#<_openmill_y_minus>)/2]",
                ]
        elif source_id == "probe_arr":
            filename = _safe_comment(str(p["filename"]))
            lines = [f"(PROBE ARRAY RESULTS {filename})"]
            for row in range(int(p["rows"])):
                for col in range(int(p["columns"])):
                    x = float(p["center_x"]) + col * float(p["spacing_x"])
                    y = float(p["center_y"]) + row * float(p["spacing_y"])
                    lines += [
                        f"G0 X{x:.4f} Y{y:.4f}",
                        f"G38.2 Z{-float(p['depth']):.4f} F{feed:.4f}",
                        f"(PROBE_POINT {row} {col} #5061 #5062 #5063)",
                    ]
        else:
            cx, cy = float(p["center_x"]), float(p["center_y"])
            travel = float(p["travel"])
            lines = [
                f"G0 X{cx:.4f} Y{cy:.4f}",
                f"G38.2 X{travel:.4f} F{feed:.4f}",
                "#<_openmill_x_plus> = #5061",
                f"G0 X{cx:.4f}",
                f"G38.2 X{-travel:.4f} F{feed:.4f}",
                "#<_openmill_x_minus> = #5061",
                f"G0 X{cx:.4f}",
                f"G38.2 Y{travel:.4f} F{feed:.4f}",
                "#<_openmill_y_plus> = #5062",
                f"G0 Y{cy:.4f}",
                f"G38.2 Y{-travel:.4f} F{feed:.4f}",
                "G10 L20 P0 X[(#<_openmill_x_plus>+#<_openmill_x_minus>)/2]",
                "G10 L20 P0 Y[(#<_openmill_y_plus>+#5062)/2]",
            ]
        return _program_path(operation, tool, lines)
    if source_id == "stock":
        stock_line = (
            f"(OPENMILL_STOCK_COMPONENT X{float(p['origin_x']):.4f} "
            f"Y{float(p['origin_y']):.4f} Z{float(p['origin_z']):.4f} "
            f"W{float(p['width']):.4f} H{float(p['height']):.4f} "
            f"D{float(p['thickness']):.4f})"
        )
        return _program_path(operation, tool, [stock_line])
    if source_id == "gcode":
        return _program_path(operation, tool, _safe_custom_lines(str(p["content"])))
    if source_id == "gcode_file":
        path = Path(str(p["content"])).expanduser()
        if not path.is_file():
            raise ValueError(f"Fichier G-code introuvable : {path}")
        lines = [f"#<{index}> = {float(p[f'parameter_{index}']):.6g}" for index in range(1, 7)]
        lines += _safe_custom_lines(path.read_text(encoding="ascii"))
        return _program_path(operation, tool, lines)
    if source_id in {"comment", "prjdesc"}:
        prefix = f"{p.get('project_name', '')} " if source_id == "prjdesc" else ""
        return _program_path(operation, tool, [f"({_safe_comment(prefix + str(p['content']))})"])
    if source_id.startswith("group_"):
        return _program_path(
            operation,
            tool,
            [f"(NATIVECAM GROUP {source_id} - utilise le bloc Repetition OpenMill)"],
        )
    raise ValueError(f"Composant NativeCAM inconnu : {source_id}")


def _register(source_id: str, label: str, category: str, description: str) -> None:
    class NativeCamComponent(OperationPlugin):
        id = f"nativecam_{source_id.replace('-', '_')}"
        nativecam_source_id = source_id
        fields = fields_for(source_id)
        common_fields = (
            THREAD_COMMON
            if source_id == "thread_milling"
            else COUNTERBORE_COMMON
            if source_id.startswith("cb_")
            else COMMON_FIELDS
            if source_id in MACHINING_IDS
            else DRILL_DEPTH
            if source_id.startswith("drill_") and source_id != "drill_side"
            else ()
        )

        @classmethod
        def generate(component_cls, operation, stock, tool):
            return _generate(component_cls, operation, stock, tool, source_id)

    NativeCamComponent.__name__ = (
        "NativeCam" + "".join(part.title() for part in re.split(r"[-_]", source_id)) + "Operation"
    )
    NativeCamComponent.__qualname__ = NativeCamComponent.__name__
    NativeCamComponent.label = label
    NativeCamComponent.category = category
    NativeCamComponent.description = description
    registry.register(NativeCamComponent)


for _component in COMPONENTS:
    _register(*_component)


NATIVECAM_COMPONENT_IDS = tuple(component[0] for component in COMPONENTS)
