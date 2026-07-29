"""Private implementation of the Resume Parsing module.

Nothing outside `src/resume_parsing/` may import from this package, and inside
the module only `dependencies.py` may — the router reaches the module through
`service.py` alone. Both `.importlinter` and the architecture test enforce this.
"""
