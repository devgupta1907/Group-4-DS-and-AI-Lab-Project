"""The parse pipeline, one module per stage.

route -> preprocess -> extract -> postprocess -> validate, with `events` shared
across all of them. Stages are pure functions over values from `domain.py`; the
orchestration and all I/O live in `service_impl.py`.
"""
