# PyNIDM Developer Manual

The full, up-to-date developer manual is published on ReadTheDocs and built from
[`docs/source/developer_manual.rst`](docs/source/developer_manual.rst):

- **Developer manual:**
  https://pynidm.readthedocs.io/en/latest/developer_manual.html

It covers:

- Why the model is schema-driven: LinkML schema → generated Pydantic → wrapper
  classes → CLI tools
- Package layout
- **The schema is the source of truth** — `nidm_schema.yaml` and
  `python scripts/regen_schema.py`
- The wrapper layer (`LinkMLBackedNode`), serialization, loading, and the query layer
- **How to change the model** (worked walkthrough) and how to add a CLI tool
- Testing (the `test_parity.py` round-trip gate)
- Common gotchas and a glossary
- Migrating from the legacy prov-toolbox API (the optional `[legacy]` extra and
  import mapping)

> This file is a pointer. Please edit the reStructuredText source at
> `docs/source/developer_manual.rst` rather than this stub.
