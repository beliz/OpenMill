"""Desktop application entry point."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenMill Conversational")
    parser.add_argument("project", nargs="?", help="Projet OpenMill à ouvrir")
    parser.add_argument("--demo", action="store_true", help="Ouvrir le projet de démonstration")
    args = parser.parse_args(argv)

    try:
        from openmill.ui.application import run_application
    except ImportError as error:
        missing = getattr(error, "name", "une dépendance graphique")
        print(
            f"Dépendance introuvable : {missing}.\n"
            'Installe l’interface avec : pip install -e ".[gui]"',
            file=sys.stderr,
        )
        return 1

    return run_application(project_path=args.project, demo=args.demo)


if __name__ == "__main__":
    raise SystemExit(main())

