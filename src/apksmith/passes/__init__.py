"""Transform passes — each pass rewrites smali for a specific purpose.

A pass is a callable that takes a smali file (as a list of lines) plus
some pass-specific context and returns the rewritten content. Passes
compose: the pipeline can apply several in sequence.

Planned passes:

- ``trace_logger``: emit logcat entries for method entry/exit, branches,
  labels, and target API calls.
- ``branch_flipper``: flip the direction of specific ``if-*``
  instructions, e.g. to bypass anti-emulator checks.
- ``api_hook``: redirect ``invoke-*`` to a user-supplied stub class.
- ``const_patcher``: rewrite constant loads.

Only ``trace_logger`` will ship in v0.1.
"""
