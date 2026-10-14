# -*- coding: utf-8 -*-
"""What's New - pyRevit Shift-click/config action.

The config action explicitly loads the shared What's New implementation without
automatically running normal mode, then calls main(show_all=True). No pyRevit
runtime Shift/config detection, persistent globals, or environment flags are
used to decide the mode.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "WhatsNew_script.py")

with open(MAIN, "rb") as f:
    source = f.read()

namespace = {
    "__name__": "pypipie_whats_new_shared",
    "__file__": MAIN,
    "WHATS_NEW_LIBRARY_MODE": True,
}
exec(compile(source, MAIN, "exec"), namespace)
namespace["main"](True)
