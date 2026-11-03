"""
Auto-generated meaning maps for the NIDM LinkML schema.

DO NOT EDIT BY HAND.  Regenerate with::

    python scripts/regen_schema.py

Source schema:   src/nidm/linkml/schema/nidm_schema.yaml
Generated with:  linkml 1.11.1

gen-pydantic does not preserve permissible_value ``meaning:`` URIs or
per-slot ``range:`` info on the generated classes, so the wrapper
layer reads them from these static maps instead.
"""
# ruff: noqa  -- generated file
# fmt: off

# (enum_class_name, permissible_value_name) -> meaning CURIE
ENUM_MEANINGS = {
    ('AcquisitionModalityEnum', 'MagneticResonanceImaging'): 'nidm:MagneticResonanceImaging',
    ('AcquisitionModalityEnum', 'PositronEmissionTomography'): 'nidm:PositronEmissionTomography',
    ('ImageContrastTypeEnum', 'ArterialSpinLabeling'): 'nidm:ArterialSpinLabeling',
    ('ImageContrastTypeEnum', 'DiffusionTensor'): 'nidm:DiffusionTensor',
    ('ImageContrastTypeEnum', 'DiffusionWeighted'): 'nidm:DiffusionWeighted',
    ('ImageContrastTypeEnum', 'FlowWeighted'): 'nidm:FlowWeighted',
    ('ImageContrastTypeEnum', 'T1Weighted'): 'nidm:T1Weighted',
    ('ImageContrastTypeEnum', 'T2StarWeighted'): 'nidm:T2StarWeighted',
    ('ImageContrastTypeEnum', 'T2Weighted'): 'nidm:T2Weighted',
    ('ImageUsageTypeEnum', 'Anatomical'): 'nidm:Anatomical',
    ('ImageUsageTypeEnum', 'DiffusionWeighted'): 'nidm:DiffusionWeighted',
    ('ImageUsageTypeEnum', 'DistortionCorrection'): 'nidm:DistortionCorrection',
    ('ImageUsageTypeEnum', 'Functional'): 'nidm:Functional',
}

# (class_name, field_name) -> enum_class_name
FIELD_TO_ENUM_CLASS = {
    ('AcquisitionObject', 'acquisition_modality'): 'AcquisitionModalityEnum',
    ('AcquisitionObject', 'image_contrast_type'): 'ImageContrastTypeEnum',
    ('AcquisitionObject', 'image_usage_type'): 'ImageUsageTypeEnum',
}
