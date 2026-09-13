"""Metrics collection for the PESUAuth API.

This package exports no collector instance. The singleton is created in `app/app.py` alongside the
PESUAcademy client, so importing the package has no side effects and a test can swap the collector
out by patching one module attribute.

Import from the modules directly rather than from this package, following the same convention as
`app.exceptions`. A re-export list here would be one more place to remember when a metric family or
a module is added -- and it had already fallen out of date once.
"""
