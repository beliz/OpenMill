#!/usr/bin/env bash
set -Eeuo pipefail

# OpenMill / Probe Basic installer.  It deliberately avoids pip so Debian's
# externally-managed Python (PEP 668) is never modified.

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SOURCE_DIR="${SCRIPT_DIR}/src"
readonly USER_TAB_SOURCE="${SCRIPT_DIR}/examples/probe_basic/user_tabs/openmill"
readonly INI_MARKER_BEGIN="# BEGIN OPENMILL USER TAB"
readonly INI_MARKER_END="# END OPENMILL USER TAB"
readonly MANAGED_MARKER=".openmill-managed"

ACTION="install"
INI_FILE=""
CONFIG_DIR=""
PYTHON_BIN="${PYTHON_BIN:-python3}"
STRICT=0

usage() {
    cat <<'EOF'
Usage : ./installation.sh [install|check|uninstall] [options]

Options :
  --ini CHEMIN         fichier INI LinuxCNC exact
  --config-dir DOSSIER dossier de configuration contenant le fichier INI
  --python COMMANDE    Python utilisé par Probe Basic (défaut : python3)
  --strict             échouer si LinuxCNC, QtPyVCP ou Probe Basic est absent
  --uninstall          raccourci équivalent à l'action uninstall
  -h, --help           afficher cette aide

Sans --ini, le script cherche dans le dossier indiqué puis dans
~/linuxcnc/configs et propose un choix si plusieurs configurations existent.
EOF
}

info() { printf '\033[1;34m[OpenMill]\033[0m %s\n' "$*"; }
success() { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warning() { printf '\033[1;33m[Attention]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[Erreur]\033[0m %s\n' "$*" >&2; exit 1; }

while (($#)); do
    case "$1" in
        install|check|uninstall) ACTION="$1" ;;
        --uninstall) ACTION="uninstall" ;;
        --ini)
            (($# >= 2)) || die "--ini attend un chemin."
            INI_FILE="$2"
            shift
            ;;
        --config-dir)
            (($# >= 2)) || die "--config-dir attend un chemin."
            CONFIG_DIR="$2"
            shift
            ;;
        --python)
            (($# >= 2)) || die "--python attend une commande."
            PYTHON_BIN="$2"
            shift
            ;;
        --strict) STRICT=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Option inconnue : $1" ;;
    esac
    shift
done

[[ -d "$SOURCE_DIR/openmill" ]] || die "Le dossier src/openmill est introuvable."
[[ -f "$USER_TAB_SOURCE/openmill.py" && -f "$USER_TAB_SOURCE/openmill.ui" ]] \
    || die "Les fichiers de l'onglet Probe Basic sont incomplets."
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python introuvable : $PYTHON_BIN"
[[ -z "${SUDO_USER:-}" ]] \
    || die "Ne lance pas cet installateur avec sudo : il doit utiliser le compte de Probe Basic."
"$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' \
    || die "OpenMill nécessite Python 3.11 ou plus récent."

select_ini() {
    if [[ -n "$INI_FILE" ]]; then
        [[ -f "$INI_FILE" ]] || die "Fichier INI introuvable : $INI_FILE"
        INI_FILE="$(realpath "$INI_FILE")"
        CONFIG_DIR="$(dirname "$INI_FILE")"
        return
    fi

    local search_root
    if [[ -n "$CONFIG_DIR" ]]; then
        [[ -d "$CONFIG_DIR" ]] || die "Dossier de configuration introuvable : $CONFIG_DIR"
        search_root="$(realpath "$CONFIG_DIR")"
    elif [[ -n "${INI_FILE_NAME:-}" && -f "${INI_FILE_NAME}" ]]; then
        INI_FILE="$(realpath "${INI_FILE_NAME}")"
        CONFIG_DIR="$(dirname "$INI_FILE")"
        return
    else
        search_root="${HOME}/linuxcnc/configs"
        [[ -d "$search_root" ]] \
            || die "Aucune configuration trouvée. Utilise --ini /chemin/machine.ini."
    fi

    local -a candidates=()
    mapfile -d '' candidates < <(find "$search_root" -maxdepth 4 -type f -name '*.ini' -print0 | sort -z)
    ((${#candidates[@]})) || die "Aucun fichier .ini trouvé dans $search_root."
    if ((${#candidates[@]} == 1)); then
        INI_FILE="${candidates[0]}"
    elif [[ -t 0 ]]; then
        info "Configurations LinuxCNC détectées :"
        local index
        for index in "${!candidates[@]}"; do
            printf '  %d) %s\n' "$((index + 1))" "${candidates[index]}"
        done
        local choice
        read -r -p "Numéro de la configuration à utiliser : " choice
        [[ "$choice" =~ ^[0-9]+$ ]] || die "Choix invalide."
        ((choice >= 1 && choice <= ${#candidates[@]})) || die "Choix hors plage."
        INI_FILE="${candidates[choice - 1]}"
    else
        printf '%s\n' "${candidates[@]}" >&2
        die "Plusieurs fichiers INI trouvés. Relance avec --ini CHEMIN."
    fi
    INI_FILE="$(realpath "$INI_FILE")"
    CONFIG_DIR="$(dirname "$INI_FILE")"
}

has_display_section() {
    awk '
        /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
            line=tolower($0); gsub(/[[:space:]]/, "", line)
            if (line == "[display]") found=1
        }
        END { exit(found ? 0 : 1) }
    ' "$INI_FILE"
}

read_user_tabs_path() {
    awk '
        /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
            line=tolower($0); gsub(/[[:space:]]/, "", line)
            in_display=(line == "[display]")
            next
        }
        in_display && tolower($0) ~ /^[[:space:]]*user_tabs_path[[:space:]]*=/ {
            value=$0
            sub(/^[^=]*=[[:space:]]*/, "", value)
            sub(/[[:space:]]+$/, "", value)
            print value
            exit
        }
    ' "$INI_FILE"
}

resolve_tabs_root() {
    local value="$1"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    [[ "$value" != *'$'* ]] \
        || die "USER_TABS_PATH contient une variable non résolue : $value"
    [[ "$value" != *'#'* && "$value" != *';'* ]] \
        || die "Retire le commentaire placé après USER_TABS_PATH : $value"
    case "$value" in
        /*) realpath -m "$value" ;;
        "~/"*) realpath -m "${HOME}/${value#\~/}" ;;
        *) realpath -m "${CONFIG_DIR}/${value}" ;;
    esac
}

add_ini_block() {
    local temporary backup
    temporary="$(mktemp "${INI_FILE}.openmill.XXXXXX")"
    backup="${INI_FILE}.openmill-backup-$(date +%Y%m%d-%H%M%S)"
    cp -a -- "$INI_FILE" "$backup"
    if ! awk -v begin="$INI_MARKER_BEGIN" -v end="$INI_MARKER_END" '
        function insert_block() {
            print ""
            print begin
            print "USER_TABS_PATH = user_tabs/"
            print end
            inserted=1
        }
        /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
            line=tolower($0); gsub(/[[:space:]]/, "", line)
            if (in_display && !inserted) insert_block()
            in_display=(line == "[display]")
            if (in_display) found_display=1
        }
        { print }
        END {
            if (in_display && !inserted) insert_block()
            if (!found_display) exit 42
        }
    ' "$INI_FILE" > "$temporary"; then
        rm -f -- "$temporary"
        die "Impossible de modifier la section [DISPLAY]."
    fi
    chmod --reference="$INI_FILE" "$temporary" 2>/dev/null || true
    mv -- "$temporary" "$INI_FILE"
    success "INI mis à jour (sauvegarde : $backup)."
}

remove_ini_block() {
    grep -Fq "$INI_MARKER_BEGIN" "$INI_FILE" || return 0
    local temporary
    temporary="$(mktemp "${INI_FILE}.openmill.XXXXXX")"
    awk -v begin="$INI_MARKER_BEGIN" -v end="$INI_MARKER_END" '
        $0 == begin { skipping=1; next }
        $0 == end { skipping=0; next }
        !skipping { print }
    ' "$INI_FILE" > "$temporary"
    chmod --reference="$INI_FILE" "$temporary" 2>/dev/null || true
    mv -- "$temporary" "$INI_FILE"
    success "Déclaration USER_TABS_PATH ajoutée par OpenMill supprimée."
}

python_site_dir() {
    "$PYTHON_BIN" -m site --user-site
}

install_python_link() {
    local site_dir pth_file
    site_dir="$(python_site_dir)"
    [[ -n "$site_dir" ]] || die "Python n'a pas retourné son dossier utilisateur."
    mkdir -p -- "$site_dir"
    pth_file="${site_dir}/openmill-conversational.pth"
    if [[ -f "$pth_file" ]] && ! grep -Fq "Managed by OpenMill installation.sh" "$pth_file"; then
        cp -a -- "$pth_file" "${pth_file}.backup-$(date +%Y%m%d-%H%M%S)"
        warning "Un ancien $pth_file a été sauvegardé avant remplacement."
    fi
    printf '# Managed by OpenMill installation.sh\n%s\n' "$SOURCE_DIR" > "$pth_file"
    success "Python relié au dépôt : $pth_file"
}

remove_python_link() {
    local pth_file
    pth_file="$(python_site_dir)/openmill-conversational.pth"
    [[ -f "$pth_file" ]] || return 0
    if grep -Fq "Managed by OpenMill installation.sh" "$pth_file"; then
        rm -f -- "$pth_file"
        success "Lien Python OpenMill supprimé."
    else
        warning "$pth_file n'est pas géré par cet installateur ; il est conservé."
    fi
}

install_user_tab() {
    local target="$1"
    [[ "$target" == */openmill && "$target" != "/openmill" ]] \
        || die "Destination d'onglet refusée par sécurité : $target"
    mkdir -p -- "$(dirname "$target")"
    if [[ -d "$target" && ! -f "$target/$MANAGED_MARKER" ]]; then
        local backup_root backup
        backup_root="${CONFIG_DIR}/.openmill-backups"
        backup="${backup_root}/openmill-$(date +%Y%m%d-%H%M%S)"
        mkdir -p -- "$backup_root"
        cp -a -- "$target" "$backup"
        warning "L'ancien onglet non géré a été sauvegardé dans $backup."
    fi
    mkdir -p -- "$target"
    install -m 0644 "$USER_TAB_SOURCE/openmill.py" "$target/openmill.py"
    install -m 0644 "$USER_TAB_SOURCE/openmill.ui" "$target/openmill.ui"
    printf 'Managed by OpenMill installation.sh\nSource: %s\n' "$SCRIPT_DIR" \
        > "$target/$MANAGED_MARKER"
    success "Onglet Probe Basic installé : $target"
}

remove_user_tab() {
    local target="$1"
    [[ "$target" == */openmill && "$target" != "/openmill" ]] \
        || die "Destination d'onglet refusée par sécurité : $target"
    [[ -d "$target" ]] || return 0
    if [[ ! -f "$target/$MANAGED_MARKER" ]]; then
        warning "$target n'est pas marqué comme géré par OpenMill ; il est conservé."
        return 0
    fi
    rm -f -- "$target/openmill.py" "$target/openmill.ui" "$target/$MANAGED_MARKER"
    if [[ -d "$target/__pycache__" ]]; then
        find "$target/__pycache__" -maxdepth 1 -type f -name 'openmill*.pyc' -delete
        rmdir -- "$target/__pycache__" 2>/dev/null || true
    fi
    rmdir -- "$target" 2>/dev/null || warning "$target contient d'autres fichiers ; ils sont conservés."
    rmdir -- "$(dirname "$target")" 2>/dev/null || true
    success "Fichiers d'onglet OpenMill supprimés."
}

run_checks() {
    local tabs_root="$1" target="$2" failures=0 version_file version
    info "Vérification de l'installation…"
    [[ -f "$target/openmill.py" && -f "$target/openmill.ui" ]] \
        && success "Onglet utilisateur complet." \
        || { warning "Onglet utilisateur absent ou incomplet dans $target."; failures=$((failures + 1)); }
    [[ -d "$tabs_root" ]] \
        && success "USER_TABS_PATH résolu : $tabs_root" \
        || { warning "USER_TABS_PATH n'existe pas : $tabs_root"; failures=$((failures + 1)); }

    version_file="$(mktemp /tmp/openmill-version.XXXXXX)"
    if OPENMILL_EXPECTED_SOURCE="$SOURCE_DIR" "$PYTHON_BIN" - <<'PY' >"$version_file" 2>/dev/null
import os
from pathlib import Path

import openmill

expected = Path(os.environ["OPENMILL_EXPECTED_SOURCE"]).resolve()
actual = Path(openmill.__file__).resolve()
if expected not in actual.parents:
    raise SystemExit(f"autre installation chargée : {actual}")
print(openmill.__version__)
PY
    then
        version="$(tr -d '\n' < "$version_file")"
        success "Module Python OpenMill ${version} importable."
    else
        warning "Le Python de Probe Basic ne parvient pas à importer openmill."
        failures=$((failures + 1))
    fi
    rm -f -- "$version_file"

    if "$PYTHON_BIN" -m openmill.integration.check --smoke-test; then
        success "Génération et chargement simulé validés."
    else
        warning "Le test d'intégration simulé a échoué."
        failures=$((failures + 1))
    fi

    local missing
    missing="$("$PYTHON_BIN" - <<'PY'
import importlib.util
modules = ("linuxcnc", "qtpyvcp", "probe_basic")
print(" ".join(name for name in modules if importlib.util.find_spec(name) is None))
PY
)"
    if [[ -n "$missing" ]]; then
        warning "Modules non visibles depuis $PYTHON_BIN : $missing"
        warning "C'est normal hors de la machine LinuxCNC ; dans Probe Basic, utilise son Python exact."
        ((STRICT == 0)) || failures=$((failures + 1))
    else
        success "LinuxCNC, QtPyVCP et Probe Basic sont visibles."
    fi
    ((failures == 0)) || die "$failures vérification(s) ont échoué."
}

select_ini
has_display_section || die "La section [DISPLAY] est absente de $INI_FILE."
info "Configuration : $INI_FILE"

tabs_value="$(read_user_tabs_path)"
if [[ "$ACTION" == "install" && -z "$tabs_value" ]]; then
    add_ini_block
    tabs_value="user_tabs/"
elif [[ -z "$tabs_value" ]]; then
    tabs_value="user_tabs/"
fi
tabs_root="$(resolve_tabs_root "$tabs_value")"
tab_target="${tabs_root}/openmill"

case "$ACTION" in
    install)
        install_python_link
        install_user_tab "$tab_target"
        run_checks "$tabs_root" "$tab_target"
        printf '\n'
        success "Installation terminée. Redémarre LinuxCNC / Probe Basic."
        info "Les futures mises à jour se feront avec : git pull"
        ;;
    check)
        run_checks "$tabs_root" "$tab_target"
        ;;
    uninstall)
        remove_user_tab "$tab_target"
        remove_python_link
        remove_ini_block
        success "Désinstallation terminée. Les sauvegardes INI éventuelles sont conservées."
        ;;
esac
