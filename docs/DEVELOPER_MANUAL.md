# PyNIDM Developer Manual

> **Moved.** This manual now lives in reStructuredText so it builds on
> ReadTheDocs alongside the rest of the docs. The single source of truth is:
>
> - Source: [`docs/source/developer_manual.rst`](source/developer_manual.rst)
> - Published: https://pynidm.readthedocs.io/en/latest/developer_manual.html
>
> Please make edits to the `.rst` source, not to this pointer.

It covers the schema-driven, RDFLib-native architecture: why the model is
schema-driven (LinkML schema → generated Pydantic → wrapper classes → tools),
the package layout, how the schema is the source of truth and how to regenerate
(`python scripts/regen_schema.py`), the wrapper layer, serialization/loading, the
query layer, a worked walkthrough for changing the model, how to add a CLI tool,
testing (the `test_parity.py` round-trip gate), gotchas, a glossary, and a
section on migrating from the legacy prov-toolbox API.
