"""Small, version-gated workarounds for known QtPyVCP regressions."""

from __future__ import annotations

import importlib
import inspect


def silence_gcode_properties_debug_output() -> bool:
    """Silence two accidental per-segment prints in affected QtPyVCP builds.

    Some releases print every parsed motion while calculating program extents.
    Large programs can therefore flood the terminal and stall Probe Basic. The
    override is installed only when both known debug statements are present.
    """
    try:
        module = importlib.import_module("qtpyvcp.plugins.gcode_properties")
        method = module.PropertiesCanon.rs274_calc_extents
        source = inspect.getsource(method)
    except (AttributeError, ImportError, OSError, TypeError):
        return False
    if "print(len(sj))" not in source or "print(sj)" not in source:
        return False
    if module.__dict__.get("_openmill_debug_output_silenced", False):
        return True

    def discard_debug_output(*_args, **_kwargs) -> None:
        return None

    # `print` is resolved from the module globals before Python falls back to
    # builtins, so this affects only gcode_properties.py.
    module.__dict__["print"] = discard_debug_output
    module.__dict__["_openmill_debug_output_silenced"] = True
    return True
