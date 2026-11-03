.. _developer_manual:

================
Developer Manual
================

A walkthrough of the schema-driven, RDFLib-native PyNIDM architecture for
developers who want to maintain, extend, or simply understand the codebase.

.. note::

   The maintained implementation lives in ``src/nidm/linkml/`` and is built
   directly on `rdflib <https://rdflib.readthedocs.io>`_. An earlier
   implementation under ``src/nidm/experiment`` and ``src/nidm/core`` remains
   available for backward compatibility as an optional install — see
   :ref:`migrating-from-legacy` at the end of this manual. New code should
   target ``nidm.linkml.experiment``.


.. contents:: On this page
   :local:
   :depth: 2


1. Why schema-driven?
=====================

PyNIDM's data model is described **once**, in a LinkML schema. Everything else
is derived from it. The stack, from ground truth to what a user calls:

.. code-block:: text

   Layer 1: LinkML schema (nidm_schema.yaml)              <- single source of truth
     |  python scripts/regen_schema.py
   Layer 2: Generated Pydantic classes
            (src/nidm/linkml/generated/nidm_schema_pydantic.py)
     |  wrapped by
   Layer 3: Wrapper classes (Project, Session, ...)
            (src/nidm/linkml/experiment/*.py)
     |  used by
   Layer 4: CLI tools (bidsmri2nidm, csv2nidm, query, ...)
            (src/nidm/linkml/experiment/tools/*.py)

Why this arrangement is worth the indirection:

* **One source of truth.** A class, a slot, and the RDF predicate it maps to are
  declared in the schema. The generated Pydantic classes and the runtime triple
  emission both read from that declaration, so they can never drift apart.
* **Validation for free.** The generated Pydantic layer enforces field names,
  types, required fields, and enum values before a single triple is written.
* **No hand-maintained predicate tables.** Because the wrapper layer looks up a
  slot's ``slot_uri`` from the generated metadata at runtime, adding or changing
  a predicate is a schema edit plus a regenerate — no wrapper code changes.
* **The graph is the data.** Wrappers build a plain ``rdflib.Graph``; there is
  no separate document model to keep in sync. Every triple round-trips.
* **Shared helpers, not per-tool copies.** Attribute mapping, export provenance,
  and CDE attachment live in one place (``utils.py``) and are reused by every
  tool.

The concrete effect: to emit ``(Project) → dctypes:title → "ABIDE"`` a tool just
calls ``Project(title="ABIDE")``. Pydantic validates ``title`` is a real field;
the wrapper's ``_emit_field_triples()`` reads the slot's ``slot_uri`` from the
generated ``linkml_meta`` (sourced from the schema), expands the CURIE
(``dctypes:title`` → ``<http://purl.org/dc/dcmitype/title>``), and writes the
triple. **No layer hard-codes the predicate.**


2. Package layout
=================

.. code-block:: text

   src/nidm/linkml/
   ├── experiment/
   │   ├── core.py             # Core: shared rdflib.Graph, serialization, UUIDs
   │   ├── linkml_node.py      # LinkMLBackedNode: schema -> triples engine
   │   ├── project.py, session.py, acquisition.py, ...   # wrapper classes
   │   ├── query.py, navigate.py, cde.py                 # SPARQL query layer
   │   ├── dotgraph.py         # provenance visualization (rdflib -> pydot)
   │   ├── utils.py            # read_nidm + the ported helper toolkit
   │   ├── _constants_compat.py  # Constants bridge for the query layer
   │   └── tools/              # CLI tools (bidsmri2nidm, csv2nidm, rest, ...)
   ├── core/
   │   ├── constants.py        # URIRef term constants
   │   ├── namespaces.py       # prefix -> rdflib.Namespace bindings
   │   └── bids_constants.py   # BIDS key -> NIDM predicate maps
   ├── generated/              # AUTO-GENERATED from the schema (do not edit)
   │   ├── nidm_schema_pydantic.py
   │   └── nidm_schema_meta.py
   └── workflows/              # LinkML NIDM-Statistics (placeholder)

The schema itself lives at ``src/nidm/experiment/schema/nidm_schema.yaml``.


3. The schema is the source of truth
====================================

**File:** ``src/nidm/experiment/schema/nidm_schema.yaml``

This LinkML schema describes every class and slot in the NIDM-Experiment model.
A real excerpt:

.. code-block:: yaml

   classes:
     Project:
       class_uri: nidm:Project
       annotations:
         additional_rdf_types: prov:Activity
       description: Top-level container for a research project or study.
       attributes:
         identifier:
           range: uriorcurie
           identifier: true
         title:
           slot_uri: dctypes:title
           range: string
         is_part_of:               # (on child classes, e.g. Session)
           slot_uri: dct:isPartOf
           range: uriorcurie
         sessions:                 # structural/containment slot -- NO slot_uri
           range: Session
           multivalued: true
           inlined_as_list: true

Three schema conventions drive runtime behavior:

* **``class_uri``** — the wrapper emits one ``rdf:type`` triple for it.
* **``annotations.additional_rdf_types``** — extra ``rdf:type`` triples emitted
  for every instance (e.g. every ``Project`` is also a ``prov:Activity``).
* **``slot_uri``** — an attribute *with* a ``slot_uri`` becomes an RDF predicate
  and is emitted as a triple. An attribute *without* one (e.g. ``sessions``,
  ``acquisitions``) is a **containment/structural** slot the wrapper
  deliberately does not emit — containment is expressed by the *child* pointing
  back via ``dct:isPartOf`` / ``prov:wasGeneratedBy``.

Enum permissible values carry a ``meaning:`` CURIE
(e.g. ``T1Weighted: {meaning: nidm:T1Weighted}``) so an enum value round-trips
to its NIDM URI.

Regenerating the generated layer
--------------------------------

.. code-block:: bash

   pip install '.[linkml]'          # one-time: installs the linkml toolchain
   python scripts/regen_schema.py   # reads the YAML, writes generated/*.py
   python scripts/smoketest_generated.py   # sanity-check the generated classes

``scripts/regen_schema.py`` invokes the LinkML ``PydanticGenerator``
programmatically (equivalent to ``gen-pydantic nidm_schema.yaml``) and writes
**two** files into ``src/nidm/linkml/generated/``:

* ``nidm_schema_pydantic.py`` — the generated Pydantic classes. **Never
  hand-edit this file.** It is excluded from flake8/black/isort.
* ``nidm_schema_meta.py`` — sidecar lookup tables ``ENUM_MEANINGS`` and
  ``FIELD_TO_ENUM_CLASS``. These exist because ``gen-pydantic`` does not
  preserve enum ``meaning:`` URIs or per-field ``range`` info; the script
  recovers them by parsing the YAML directly so the wrapper layer can resolve
  ``ImageContrastTypeEnum.T1Weighted`` back to ``nidm:T1Weighted``.

Both generated files are committed, so downstream users do not need ``linkml``
installed — only contributors editing the schema do.


4. The wrapper layer
====================

**Directory:** ``src/nidm/linkml/experiment/``

Most callers touch the wrappers. Every NIDM class has a wrapper module. The
inheritance chain:

.. code-block:: text

   Core (core.py)                    # shared rdflib.Graph, serialization, UUIDs
     └── LinkMLBackedNode (linkml_node.py)   # schema-driven triple emission
           ├── Project, Session, Acquisition, AcquisitionObject
           ├── Person, SoftwareAgent, Association, Collection
           ├── Derivative, DerivativeObject
           ├── DataElement -> PersonalDataElement
           └── ExportActivity
                 # specializations:
                 #   MRAcquisition, PETAcquisition, AssessmentAcquisition (of Acquisition)
                 #   MRObject, PETObject, AssessmentObject, DemographicsObject (of AcquisitionObject)

What ``LinkMLBackedNode`` does
------------------------------

Each wrapper sets a class attribute ``pydantic_class = gen.<ClassName>``. On
``__init__`` the base class:

#. **Coerces wrapper-valued kwargs to identifier strings** — so
   ``AcquisitionObject(was_generated_by=acq)`` works even though the schema
   stores ``was_generated_by`` as a string slot.
#. **Validates via the generated Pydantic model**
   (``self._model = pydantic_class(**fields)``).
#. **Emits triples by introspecting ``linkml_meta`` at runtime** —
   ``_emit_type_triples()`` (from ``class_uri`` + ``additional_rdf_types`` +
   per-instance ``extra_types``) and ``_emit_field_triples()`` (one triple per
   non-None ``slot_uri`` field; enums resolved via ``ENUM_MEANINGS`` /
   ``FIELD_TO_ENUM_CLASS``; URI-shaped strings become ``URIRef``, primitives
   become typed ``Literal``).

The payoff: **schema changes flow through without touching wrapper code.**
Because predicate/type/enum logic is read from the generated metadata rather
than hard-coded per wrapper, the wrappers stay in lockstep with the schema.

Specialization pattern
----------------------

Subclasses add per-instance ``rdf:type`` triples without redeclaring slots, via
the ``extra_types`` kwarg:

.. code-block:: python

   class AssessmentObject(AcquisitionObject):
       pydantic_class = gen.AssessmentObject

       def __init__(self, acquisition, **fields):
           super().__init__(
               acquisition,
               extra_types=[ONLI["assessment-instrument"]],
               **fields,
           )

The same pattern lets ``Collection`` add ``bids:Dataset``, etc. Pure Python
markers that add no RDF (e.g. ``MRAcquisition``) simply inherit the parent's
``pydantic_class``.

Load-mode constructor
---------------------

``Wrapper.from_existing_subject(graph, identifier)`` binds a wrapper to an
existing subject **without emitting triples**, so you can navigate a parsed
file. This is what ``read_nidm`` uses.

.. code-block:: python

   from nidm.linkml.experiment import Project
   project = Project.from_existing_subject(graph, project_uri)

When to use the wrapper API vs raw rdflib
-----------------------------------------

* **Wrapper API** — when the field is a schema slot; you get Pydantic
  validation and automatic predicate lookup.
* **Raw ``obj.graph.add((s, p, o))``** — when you need a predicate the schema
  does not model (BIDS sidecar keys, ad-hoc attributes). This is exactly what
  the tools do for BIDS-specific data.


5. Serialization and loading
============================

All serialization lives on ``Core`` (inherited by every wrapper). Build a graph
by constructing wrappers against a shared ``rdflib.Graph``, then serialize:

.. code-block:: python

   from nidm.linkml.experiment import Project, Session, Acquisition

   project = Project(title="ABIDE")
   session = Session(project)
   acq = Acquisition(session)

   print(project.serialize_turtle())            # Turtle string
   project.serialize_jsonld()                    # JSON-LD
   project.serialize_trig()                      # TriG (named graph)
   project.write("out.ttl", format="turtle")     # to disk
   project.save_DotGraph("out.svg", format="svg")  # provenance diagram

There is no single ``serialize()`` — the format-specific methods (and their
camelCase aliases) are the API. **The ``rdflib.Graph`` is the data**, so every
triple round-trips.

**Visualization:** ``dotgraph.build_nidm_dotgraph(graph)`` builds a
``pydot.Dot`` directly from RDF triples (nodes categorized as
``prov:Activity`` / ``Entity`` / ``Agent``, ``qualifiedAssociation`` blank nodes
collapsed into direct edges). ``save_dotgraph`` renders svg/png/pdf via the
graphviz ``dot`` executable (a soft runtime dependency; svg works without it).

**Loading:** ``nidm.linkml.experiment.utils.read_nidm(path)`` parses any
rdflib-readable RDF, finds the first ``nidm:Project`` subject, wraps it via
``from_existing_subject``, and reconstructs the child wrappers (Sessions via
``dct:isPartOf``, AcquisitionObjects via ``prov:wasGeneratedBy``, etc.).

.. tip::

   ``read_nidm`` preserves whatever prefixes the file declared, which may omit
   canonical ones. If you then build with the wrapper API and hit
   "Unknown CURIE prefix", call
   ``nidm.linkml.core.namespaces.bind_default_namespaces(project.graph)`` to
   restore the canonical prefix set.


6. The query layer
==================

The SPARQL query API is native to ``nidm.linkml``:

* ``nidm.linkml.experiment.query`` — ``sparql_query_nidm(nidm_file_list, query,
  ...)``, ``GetMergedGraph``, ``OpenGraph``, the ``GetProject*`` /
  ``GetParticipant*`` families, and URI helpers (``URITail``,
  ``trimWellKnownURIPrefix``, ``expandUUID``, ``matchPrefix``). The query engine
  uses Oxigraph when ``oxrdflib`` is installed (set
  ``PYNIDM_QUERY_ENGINE=auto|oxigraph|rdflib``), else falls back to rdflib.
* ``nidm.linkml.experiment.navigate`` — higher-level traversal
  (``getProjects``, ``getSessions``, ``getActivityData``,
  ``GetProjectAttributes``, ``GetDataelements``, ...).
* ``nidm.linkml.experiment.cde`` — ``getCDEs`` / ``download_cde_files`` for the
  bundled FreeSurfer / FSL / ANTS Common Data Element graphs.
* ``nidm.linkml.experiment.tools.rest`` — the ``RestParser`` that backs
  ``pynidm query`` URI routes.

.. note::

   ``_constants_compat.Constants`` is a small bridge that exposes a
   ``Constants``-shaped object (assembled from ``core.constants`` +
   ``core.namespaces``) to the query modules. Its ``namespaces`` map is filtered
   to a specific key set so ``matchPrefix`` / ``trimWellKnownURIPrefix``
   compression matches the historical output byte-for-byte.


7. utils.py — the helper toolkit
================================

**File:** ``src/nidm/linkml/experiment/utils.py``

The functions you will touch most:

* ``read_nidm(path)`` — load a NIDM file, return a ``Project`` wrapper.
* ``add_attributes_with_cde(obj, cde, row_variable, value)`` — emit one triple
  on *obj* for *row_variable*'s mapped CDE predicate. Used by every CSV-style
  tool when materializing a row.
* ``add_export_provenance(...)`` — append the canonical Activity/Agent/Entity
  chain "this tool, this version, at this time, produced this file". Used by
  every tool's write step.
* ``map_variables_to_terms(...)`` — interactively map dataframe columns to
  NIDM/InterLex concepts; returns ``(column_to_terms, cde)``.
* ``csv_dd_to_json_dd`` / ``DD_to_nidm`` — data-dictionary conversion helpers.

``utils.py`` uses lazy imports for heavy deps (``ontquery``, ``cognitiveatlas``,
``github``, ``chardet``) so ``import nidm.linkml.experiment.utils`` does not pull
the entire scientific-Python stack at startup.


8. How to change the model (worked walkthrough)
===============================================

This is the core maintenance workflow. Two cases.

Case A — add or modify a slot on an existing class
--------------------------------------------------

Say you want ``Project`` to carry a ``doi``.

**Step 1 — edit the schema** (``src/nidm/experiment/schema/nidm_schema.yaml``):

.. code-block:: yaml

   classes:
     Project:
       attributes:
         doi:
           slot_uri: dct:identifier
           range: string
           description: Digital Object Identifier for the dataset

**Step 2 — regenerate:**

.. code-block:: bash

   python scripts/regen_schema.py
   python scripts/smoketest_generated.py

**Step 3 — nothing to hand-edit.** ``LinkMLBackedNode`` emits the new predicate
automatically because it reads ``slot_uri`` from the regenerated metadata. You
can immediately do:

.. code-block:: python

   Project(title="ABIDE", doi="10.1234/abide")
   # emits (<project>, <http://purl.org/dc/terms/identifier>, "10.1234/abide")

(If the field deserves a caller-facing convenience or coercion, add a keyword to
the relevant wrapper's ``__init__``.)

**Step 4 — test.** Run ``pytest tests/linkml/ -x``, especially
``tests/linkml/test_parity.py`` (the round-trip correctness gate).

Case B — add a new class
------------------------

**Step 1 — add the class** in the YAML with ``class_uri``, any
``annotations.additional_rdf_types``, and its attributes/``slot_uri``\ s.

**Step 2 — regenerate** (``python scripts/regen_schema.py``).

**Step 3 — write the wrapper** in ``src/nidm/linkml/experiment/your_class.py``:

.. code-block:: python

   from .linkml_node import LinkMLBackedNode
   from ..generated import nidm_schema_pydantic as gen


   class YourClass(LinkMLBackedNode):
       pydantic_class = gen.YourClass

       def __init__(self, parent, **fields):
           # If this is a child node, link it back to its parent:
           fields.setdefault("is_part_of", str(parent.identifier))
           super().__init__(parent, **fields)

For per-instance extra rdf:types, pass ``extra_types=[...]`` to
``super().__init__``.

**Step 4 — expose it** in ``src/nidm/linkml/experiment/__init__.py``
(``from .your_class import YourClass`` and add to ``__all__``). If the parent
should track it, add an ``add_*``/``get_*`` facade on the parent wrapper.

**Step 5 — make it load** (if it should be reconstructed from a file): add a
walk branch in ``_populate_project_children()`` in
``src/nidm/linkml/experiment/utils.py``.

**Step 6 — test:**

.. code-block:: python

   from nidm.linkml.experiment import Project, YourClass
   from rdflib.namespace import RDF
   from nidm.linkml.core.namespaces import NIDM

   def test_constructs_and_emits_type():
       p = Project()
       n = YourClass(p, your_slot="value")
       assert (n.identifier, RDF.type, NIDM.YourClass) in n.graph


9. How to add a CLI tool
========================

The shipped tools live in ``src/nidm/linkml/experiment/tools/`` and register
themselves on the ``pynidm`` click group.

#. **Read the tool's intent** — what does it read (CSV? BIDS dir? NIDM file?),
   what wrapper classes does it materialize per record, and how does it write
   output?
#. **Reuse the shared helpers** — ``add_export_provenance``,
   ``add_attributes_with_cde``, ``getRelPathToBIDS``, ``getsha512``,
   ``check_encoding``, and (for single-file emitters) the ``_write_nidm_graph``
   sequence in ``bidsmri2nidm.py``.
#. **Wire it into the CLI.** A click subcommand decorates a function with
   ``@cli.command()`` where ``cli`` comes from
   ``nidm.linkml.experiment.tools.click_base``; then add the module to the
   imports in ``click_main.py`` (importing it runs the registration side
   effect). An argparse tool (like ``bidsmri2nidm``/``csv2nidm``) exposes a
   ``main()`` and a ``console_scripts`` entry in ``setup.cfg``.
#. **Write tests alongside the code** in ``tests/linkml/test_<tool>.py``. The
   ``_FakeArgs`` pattern (a minimal namespace-shaped object) tests
   argparse-coupled code without hand-rolling argv; fixture builders take
   ``tmp_path`` and return real files.
#. **Verify:** ``pytest tests/linkml/test_<tool>.py -v`` and
   ``pre-commit run --all-files`` (pre-commit may auto-reformat — just
   ``git add`` and re-commit).


10. Testing
===========

.. code-block:: bash

   pytest tests/linkml/ -x                       # maintained suite, stop on first fail
   pytest tests/linkml/test_<file>.py -v         # one file
   pytest tests/linkml/ -k "csv2nidm and derivative"   # filter by name

The key correctness gate is ``tests/linkml/test_parity.py`` — round-trip /
isomorphism tests. It parametrizes over the repo-tracked fixtures in
``FIXTURE_PATHS``; drop your own ``.ttl`` files into the gitignored
``tests/linkml/local_fixtures/`` to stress-test locally without changing anyone
else's collected count. When you add a *shared* fixture, add it to
``FIXTURE_PATHS`` **and commit the file**.

Useful patterns banked in the suite:

* **``_FakeArgs``** — a minimal namespace-shaped class for testing
  argparse-coupled code without hand-rolling argv.
* **Fixture builders return Paths** — helpers take ``tmp_path`` and a few
  kwargs, build a real file, and return the Path.
* **End-to-end fixtures use the tools themselves** — e.g. build a base NIDM
  file with ``csv2nidm`` rather than hand-rolling rdflib graphs.
* **Mock ``builtins.input``** for interactive helpers
  (``monkeypatch.setattr("builtins.input", lambda _: "1")``).


11. Common gotchas
==================

**"Unknown CURIE prefix in 'schema:name'" after read_nidm.**
The wrapper expands CURIEs from the graph's namespace bindings, which reflect
what the file declared. Call ``bind_default_namespaces(project.graph)`` to
restore the canonical set.

**Pydantic ``ValidationError: Extra inputs are not permitted``.**
You passed a kwarg the schema does not model. Either add the slot to the schema
and regenerate, or add the triple manually:
``obj.graph.add((obj.identifier, predicate, value))``.

**Pre-commit modifies files and the commit fails.**
That is pre-commit signaling it reformatted; ``git add`` the changes and commit
again.

**Tests hang in ``annotate_data_element``.**
A test triggered ``map_variables_to_terms`` with a column its json_map does not
cover, so it fell through to an interactive ``input()`` prompt. Pass
``associate_concepts=False`` and a json_map covering every column, or only use
covered columns.


12. Glossary
============

CDE
  Common Data Element — a reusable variable description (label, definition,
  valueType) shared across datasets.

CURIE
  Compact URI. ``dctypes:title`` expands to
  ``<http://purl.org/dc/dcmitype/title>`` via the declared prefix.

LinkML
  The schema-modeling language describing the NIDM-Experiment model. See
  `linkml.io <https://linkml.io>`_.

NIDM
  Neuroimaging Data Model — the W3C-PROV-derived spec this codebase implements.

PROV
  The W3C provenance ontology: Activities, Entities, Agents, and qualified
  relations between them.

slot / slot_uri
  LinkML's term for a class property, and the RDF predicate URI it maps to.

``from_existing_subject``
  Wrapper classmethod that binds a wrapper to an existing graph subject without
  emitting new triples. Used by ``read_nidm``.


13. Appendix: where to find things
==================================

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - If you want to...
     - Look at...
   * - Add a NIDM class or slot
     - ``src/nidm/experiment/schema/nidm_schema.yaml``, then ``python scripts/regen_schema.py``
   * - Add a per-instance rdf:type to a class
     - the wrapper's ``extra_types=[...]`` kwarg
   * - Add a BIDS sidecar JSON key mapping
     - ``src/nidm/linkml/core/bids_constants.py``
   * - Trace what triples a wrapper emits
     - ``LinkMLBackedNode._emit_field_triples()`` in ``src/nidm/linkml/experiment/linkml_node.py``
   * - Understand the SPARQL query helpers
     - ``src/nidm/linkml/experiment/query.py`` and ``navigate.py``
   * - See the canonical prefix set
     - ``NAMESPACES`` in ``src/nidm/linkml/core/namespaces.py``


.. _migrating-from-legacy:

14. Migrating from the legacy API
=================================

PyNIDM 4.x was built on the ``prov`` toolbox (prov-toolbox), with the wrapper
classes and tools under ``nidm.experiment`` / ``nidm.core``. PyNIDM 5 replaces
that implementation entirely with the LinkML/rdflib code under ``nidm.linkml``.
The ``nidm.experiment`` and ``nidm.core`` packages are **not** shipped in 5.x —
there are no compatibility shims. This section is for maintainers of downstream
code that imported from the 4.x packages.

What changed
------------

* The **only** implementation in 5.x is ``nidm.linkml``, installed by
  ``pip install pynidm``. It is built directly on rdflib (no prov-toolbox).
* The legacy prov-toolbox implementation (``nidm.experiment`` wrapper classes,
  ``nidm.core``, and the query / navigation / CDE / REST layers) is a separate,
  frozen release line. Workflows that still need it should pin the 4.x line:

  .. code-block:: bash

     pip install "pynidm<5"

Import migration
----------------

If you are porting code off the 4.x line, update your imports to the
``nidm.linkml`` equivalents:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - PyNIDM 4.x import
     - PyNIDM 5 import
   * - ``from nidm.experiment import Project, Session``
     - ``from nidm.linkml.experiment import Project, Session``
   * - ``from nidm.experiment.Query import sparql_query_nidm``
     - ``from nidm.linkml.experiment.query import sparql_query_nidm``
   * - ``from nidm.experiment import Navigate``
     - ``from nidm.linkml.experiment import navigate``
   * - ``from nidm.experiment.tools.rest import RestParser``
     - ``from nidm.linkml.experiment.tools.rest import RestParser``

The command-line entry points (``pynidm``, ``bidsmri2nidm``, ``csv2nidm``,
``nidm_query``, ``nidm_utils``) keep the same names and behavior; only the
Python import paths moved.

A guard test, ``tests/linkml/test_prov_free.py``, confirms the shipped
``nidm.linkml`` CLI imports without the ``prov`` toolbox present. If you extend
``nidm.linkml``, keep that test passing.
