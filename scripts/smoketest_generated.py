#!/usr/bin/env python3
"""
Smoke-test the generated Pydantic classes from nidm.linkml.generated.

Confirms:
  1. The generated module imports.
  2. A hand-built Project, Session, and Acquisition validate successfully.
  3. Required-field violations are caught by Pydantic.
  4. Enum values (AcquisitionModalityEnum, etc.) round-trip.

This is intentionally minimal -- the real correctness check lives in the
parity harness (tests/linkml/test_parity.py, task 7).  This script just
proves the generated classes are usable.

Usage
-----
    python scripts/smoketest_generated.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def main() -> int:
    print("=== smoke-testing nidm.linkml.generated.nidm_schema_pydantic ===")

    try:
        from nidm.linkml.generated import nidm_schema_pydantic as gen
    except ImportError as exc:
        print(f"FAIL: cannot import generated module: {exc}", file=sys.stderr)
        print("Run:  python scripts/regen_schema.py  first.", file=sys.stderr)
        return 1

    # Inventory the classes we expect to see.
    expected = {
        "Project", "Session", "Acquisition", "AcquisitionObject",
        "DataElement", "PersonalDataElement", "Derivative",
        "DerivativeObject", "Person", "SoftwareAgent", "Association",
        "Collection", "ExportActivity",
    }
    missing = expected - set(dir(gen))
    if missing:
        print(f"FAIL: generated module is missing classes: {sorted(missing)}",
              file=sys.stderr)
        return 1
    print(f"  [ok] all {len(expected)} expected classes present")

    # Build a tiny project graph and validate.
    try:
        project = gen.Project(
            identifier="niiri:proj-0001",
            title="Smoke Test Project",
            description="One-session, one-acquisition test.",
        )
        session = gen.Session(
            identifier="niiri:sess-0001",
            is_part_of="niiri:proj-0001",
            session_number="1",
        )
        acq = gen.Acquisition(
            identifier="niiri:acq-0001",
            is_part_of="niiri:sess-0001",
        )
        print(f"  [ok] built Project={project.identifier}, "
              f"Session={session.identifier}, Acquisition={acq.identifier}")
    except Exception:
        print("FAIL: could not build minimal Project/Session/Acquisition:",
              file=sys.stderr)
        traceback.print_exc()
        return 1

    # Required-field violation should raise.
    try:
        gen.Project()  # type: ignore[call-arg]  # identifier is required
    except Exception as exc:
        print(f"  [ok] missing-identifier raises: {type(exc).__name__}")
    else:
        print("FAIL: Project() with no identifier should have raised",
              file=sys.stderr)
        return 1

    # Enum smoke test, if the enum is exposed.
    if hasattr(gen, "AcquisitionModalityEnum"):
        try:
            modality = gen.AcquisitionModalityEnum("MagneticResonanceImaging")
            print(f"  [ok] AcquisitionModalityEnum -> {modality}")
        except Exception as exc:
            print(f"  [warn] AcquisitionModalityEnum lookup failed: {exc}")

    # Check that the additional_rdf_types annotation is exposed on
    # linkml_meta for each class that declared it in the schema.  The
    # wrapper layer (task 5 step 2) reads this to know the full list of
    # rdf:type triples to emit per instance.
    expected_additional_types = {
        "Project": "prov:Activity",
        "Session": "prov:Activity",
        "Acquisition": "prov:Activity",
        "AcquisitionObject": "prov:Entity",
        "DataElement": "prov:Entity",
        "PersonalDataElement": "prov:Entity",
        "Derivative": "prov:Activity",
        "DerivativeObject": "prov:Entity",
        "Person": "prov:Agent",
        "SoftwareAgent": "prov:Agent",
        "Collection": "prov:Entity",
    }
    print("\n  checking additional_rdf_types annotations:")
    failures = []
    for cls_name, expected in expected_additional_types.items():
        cls = getattr(gen, cls_name)
        meta = cls.linkml_meta
        # LinkMLMeta supports __getitem__ and __contains__.
        if "annotations" not in meta:
            failures.append(f"    {cls_name}: linkml_meta has no 'annotations' key")
            continue
        annots = meta["annotations"]
        if "additional_rdf_types" not in annots:
            failures.append(f"    {cls_name}: annotations has no 'additional_rdf_types'")
            continue
        # gen-pydantic emits annotations as {'tag': ..., 'value': ...} dicts.
        raw = annots["additional_rdf_types"]
        value = raw["value"] if isinstance(raw, dict) and "value" in raw else raw
        if value != expected:
            failures.append(f"    {cls_name}: expected {expected!r}, got {value!r}")
        else:
            print(f"    [ok] {cls_name}.additional_rdf_types == {value!r}")
    if failures:
        print("FAIL: additional_rdf_types annotation checks failed:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        print("\nDid you re-run `python scripts/regen_schema.py` after the "
              "schema was updated?", file=sys.stderr)
        return 1

    # And confirm Association / ExportActivity do NOT carry the annotation
    # (their class_uri already covers the only rdf:type they emit).
    for cls_name in ("Association", "ExportActivity"):
        cls = getattr(gen, cls_name)
        meta = cls.linkml_meta
        if "annotations" in meta and "additional_rdf_types" in meta["annotations"]:
            print(f"FAIL: {cls_name} should NOT have additional_rdf_types",
                  file=sys.stderr)
            return 1
        print(f"    [ok] {cls_name} correctly has no additional_rdf_types")

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
