"""harness_manager — manifest-driven adapter installer for agentic-stack.

This package is the implementation backend for `./install.sh` and `./install.ps1`.
The user-facing surface is plain verbs: install, add, remove, doctor, status.
The "harness_manager" name is internal only and never appears in CLI help, docs,
or error messages users see.
"""
__version__ = "0.14.0"
