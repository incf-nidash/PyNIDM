#!/usr/bin/env python3
"""
Regenerate Pydantic dataclasses from the NIDM LinkML schema.

Reads:   src/nidm/linkml/schema/nidm_schema.yaml
Writes:  src/nidm/linkml/generated/nidm_schema_pydantic.py

This script is the single source of truth for regenerating the Pydantic
class file under nidm.linkml.generated.  It is intentionally short and
imperative -- run it after every schema change.

Usage
-----
    # from the repo root
    pip install '.[linkml]'          # one-time, installs linkml toolchain
    python scripts/regen_schema.py

Notes
-----
* We invoke the LinkML PydanticGenerator programmatically rather than
  shelling out to the `gen-pydantic` CLI so the script works regardless
  of which Python environment the CLI was installed into.
* The generated file is committed to the repo so downstream consumers
  do not need linkml installed.  Only contributors who edit the schema
  need the [linkml] extras.
"""
from __future__ import annotations
from pathlib import Path
import sys
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "nidm" / "linkml" / "schema" / "nidm_schema.yaml"
OUTPUT_PATH = (
    REPO_ROOT / "src" / "nidm" / "linkml" / "generated" / "nidm_schema_pydantic.py"
)
META_OUTPUT_PATH = (
    REPO_ROOT / "src" / "nidm" / "linkml" / "generated" / "nidm_schema_meta.py"
)
# Derived JSON copy of the schema, consumed by `pynidm queryai` as the AI
# prompt's structural context.  Generated from the YAML so it can never drift.
SCHEMA_JSON_PATH = REPO_ROOT / "src" / "nidm" / "linkml" / "schema" / "nidm_schema.json"


def _linkml_version() -> str:
    """Return the installed ``linkml`` version string (or ``"unknown"``).

    Stamped into the generated file headers so a regenerated diff caused by a
    LinkML upgrade (generator output drifts across releases) is immediately
    explainable rather than looking like a schema change.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("linkml")
        except PackageNotFoundError:
            return "unknown"
    except ImportError:  # pragma: no cover -- py<3.8 only
        return "unknown"


HEADER_TEMPLATE = dedent(
    '''\
    """
    Auto-generated Pydantic classes for the NIDM-Experiment LinkML schema.

    DO NOT EDIT BY HAND.  Regenerate with::

        python scripts/regen_schema.py

    Source schema:   src/nidm/linkml/schema/nidm_schema.yaml
    Generated with:  linkml {linkml_version}
    """
    # ruff: noqa  -- generated file
    # fmt: off
    '''
)


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 1

    try:
        from linkml.generators.pydanticgen import PydanticGenerator
    except ImportError:
        print(
            "ERROR: linkml is not installed in this environment.\n"
            "Install it with:  pip install '.[linkml]'  (from the repo root)",
            file=sys.stderr,
        )
        return 2

    linkml_version = _linkml_version()
    print(f"Reading schema:  {SCHEMA_PATH.relative_to(REPO_ROOT)}")
    print(f"linkml version:  {linkml_version}")
    generator = PydanticGenerator(str(SCHEMA_PATH))
    body = generator.serialize()

    header = HEADER_TEMPLATE.format(linkml_version=linkml_version)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(header + body)
    print(f"Wrote generated module: {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(body.splitlines())} lines, {len(body)} bytes")

    # Also generate the meta module (enum meanings, field->enum maps).
    # gen-pydantic does not preserve permissible_value `meaning:` URIs or
    # per-field `range:` info, so we parse the YAML directly and emit
    # static lookup tables alongside the Pydantic classes.
    _write_meta_module()

    # Also (re)generate the JSON copy consumed by `pynidm queryai`, flattening
    # schema-level annotations to plain strings (the form queryai expects).
    _write_schema_json()

    print("\nDone.  Smoke-test with:  python scripts/smoketest_generated.py")
    return 0


def _write_schema_json() -> None:
    """Write ``nidm_schema.json`` from the YAML, flattening annotations.

    ``queryai`` reads schema-level annotations (graph_hierarchy, sparql_*,
    important_notes) as plain strings.  LinkML annotations may be written in
    the explicit ``{tag:, value:}`` form; flatten each to its string value so
    the JSON stays queryai-friendly and in sync with the YAML (no manual edits).
    """
    import json
    import yaml

    with open(SCHEMA_PATH) as f:
        schema = yaml.safe_load(f)

    anns = schema.get("annotations")
    if isinstance(anns, dict):
        flat = {}
        for tag, val in anns.items():
            if isinstance(val, dict) and "value" in val:
                flat[tag] = val["value"]
            else:
                flat[tag] = val
        schema["annotations"] = flat

    SCHEMA_JSON_PATH.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote schema JSON:      {SCHEMA_JSON_PATH.relative_to(REPO_ROOT)}")


def _write_meta_module() -> None:
    """
    Write src/nidm/linkml/generated/nidm_schema_meta.py with two static
    maps derived from the YAML schema:

      ENUM_MEANINGS[(enum_class_name, permissible_value)] -> meaning_curie
      FIELD_TO_ENUM_CLASS[(class_name, field_name)] -> enum_class_name

    The wrapper layer uses these to translate enum-valued fields to
    their meaning URIs without having to introspect Pydantic
    annotations or re-parse the YAML at runtime.
    """
    import yaml

    with open(SCHEMA_PATH) as f:
        schema = yaml.safe_load(f)

    schema_enums = schema.get("enums") or {}
    schema_classes = schema.get("classes") or {}

    enum_meanings: dict = {}
    for enum_name, enum_def in schema_enums.items():
        for pv_name, pv_def in (enum_def.get("permissible_values") or {}).items():
            if isinstance(pv_def, dict) and pv_def.get("meaning"):
                enum_meanings[(enum_name, pv_name)] = pv_def["meaning"]

    field_to_enum: dict = {}
    for cls_name, cls_def in schema_classes.items():
        for attr_name, attr_def in (cls_def.get("attributes") or {}).items():
            if not isinstance(attr_def, dict):
                continue
            range_name = attr_def.get("range")
            if range_name and range_name in schema_enums:
                field_to_enum[(cls_name, attr_name)] = range_name

    lines = [
        '"""',
        "Auto-generated meaning maps for the NIDM LinkML schema.",
        "",
        "DO NOT EDIT BY HAND.  Regenerate with::",
        "",
        "    python scripts/regen_schema.py",
        "",
        "Source schema:   src/nidm/linkml/schema/nidm_schema.yaml",
        f"Generated with:  linkml {_linkml_version()}",
        "",
        "gen-pydantic does not preserve permissible_value ``meaning:`` URIs or",
        "per-slot ``range:`` info on the generated classes, so the wrapper",
        "layer reads them from these static maps instead.",
        '"""',
        "# ruff: noqa  -- generated file",
        "# fmt: off",
        "",
        "# (enum_class_name, permissible_value_name) -> meaning CURIE",
        "ENUM_MEANINGS = {",
    ]
    for (enum_name, pv_name), meaning in sorted(enum_meanings.items()):
        lines.append(f"    ({enum_name!r}, {pv_name!r}): {meaning!r},")
    lines.append("}")
    lines.append("")
    lines.append("# (class_name, field_name) -> enum_class_name")
    lines.append("FIELD_TO_ENUM_CLASS = {")
    for (cls_name, field_name), enum_name in sorted(field_to_enum.items()):
        lines.append(f"    ({cls_name!r}, {field_name!r}): {enum_name!r},")
    lines.append("}")
    lines.append("")

    META_OUTPUT_PATH.write_text("\n".join(lines))
    print(
        f"Wrote meta module:      {META_OUTPUT_PATH.relative_to(REPO_ROOT)}"
        f"  ({len(enum_meanings)} enum meanings,"
        f" {len(field_to_enum)} field->enum mappings)"
    )


if __name__ == "__main__":
    raise SystemExit(main())
