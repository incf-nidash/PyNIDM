"""
BIDS term -> NIDM-Experiment URI mappings.

Drop-in port of ``nidm.core.BIDS_Constants``.  Only the import paths
changed -- the dict structure, keys, and values (now URIRefs instead
of prov.model.QualifiedName objects) are identical in semantics.

Three top-level dicts are exposed:

  * ``dataset_description`` -- maps ``dataset_description.json`` keys
    to NIDM-Experiment predicates.
  * ``participants`` -- maps ``participants.tsv`` columns to NIDM
    predicates.
  * ``scans`` -- maps BIDS modality / suffix names to the NIDM URI for
    the corresponding scan type (used to set ``rdf:type`` on
    AcquisitionObject in the legacy bidsmri2nidm).
  * ``json_keys`` -- maps BIDS / DICOM JSON sidecar keys to the
    appropriate NIDM / DICOM / BIDS predicate.

@author: David Keator
"""
from __future__ import annotations
from . import constants as Constants
from .namespaces import BIDS, DICOM, NIDM

# BIDS dataset_description -> NIDM constants mappings
dataset_description = {
    "BIDSVersion": BIDS["BIDSVersion"],
    "Name": Constants.NIDM_PROJECT_NAME,
    "Procedure": Constants.NIDM_PROJECT_DESCRIPTION,
    "License": Constants.NIDM_PROJECT_LICENSE,
    "ReferencesAndLinks": Constants.NIDM_PROJECT_REFERENCES,
    "Authors": Constants.NIDM_AUTHOR,
    "DatasetDOI": Constants.NIDM_DOI,
    "Funding": Constants.NIDM_FUNDING,
    "HowToAcknowledge": Constants.NIDM_ACKNOWLEDGEMENTS,
}

# BIDS Participants file -> NIDM constants mappings
participants = {
    "participant_id": Constants.NIDM_SUBJECTID,
    # The following lines are commented out in the legacy file, preserved here
    # for historical context:
    # "sex": Constants.NIDM_GENDER,
    # "age": Constants.NIDM_AGE,
    # "gender": Constants.NIDM_GENDER,
    # "diagnosis": Constants.NIDM_DIAGNOSIS,
    # "handedness": Constants.NIDM_HANDEDNESS,
}

# Scan metadata -> NIDM constants mappings
scans = {
    "anat": Constants.NIDM_MRI_ANATOMIC_SCAN,
    "func": Constants.NIDM_MRI_FUNCTION_SCAN,
    "dwi": Constants.NIDM_MRI_DWI_SCAN,
    "bval": Constants.NIDM_MRI_DWI_BVAL,
    "bvec": Constants.NIDM_MRI_DWI_BVEC,
    "T1w": Constants.NIDM_MRI_T1,
    "T2w": Constants.NIDM_MRI_T2,
    "inplaneT2": Constants.NIDM_MRI_T2,
    "bold": Constants.NIDM_MRI_FLOW,
    "dti": Constants.NIDM_MRI_DIFFUSION_TENSOR,
    "asl": Constants.NIDM_MRI_ASL,
    # NOTE: the BIDS field-map suffixes (fmap/fieldmap/epi/phasediff/phase1/
    # phase2/magnitude/magnitude1/magnitude2) are intentionally NOT in this
    # table.  The linkml converter models field maps directly in bidsmri2nidm:
    # _resolve_image_usage() sets hadImageUsageType nidm:DistortionCorrection
    # and _FMAP_SUFFIX_TO_RDF_TYPE stamps rdf:type nidm:B0FieldMap (the primary
    # field map) or dctype:Image (its magnitude/phase/EPI images).  This is NOT
    # driven by this scans table; adding these keys here would make
    # _apply_scan_contrast_and_usage emit a spurious hadImageContrastType.
    # (Legacy carries these keys because its converter DOES use the scans table.)
}

# JSON sidecar keys
json_keys = {
    # Image terms
    "run": Constants.NIDM_ACQUISITION_ENTITY,
    "ImageType": DICOM["ImageType"],
    "ManufacturerModelName": DICOM["ManufacturerModelName"],
    "Manufacturer": DICOM["Manufacturer"],
    "ScanningSequence": DICOM["ScanningSequence"],
    "SequenceVariant": DICOM["SequenceVariant"],
    "ScanOptions": DICOM["ScanOptions"],
    "MRAcquisitionType": DICOM["MRAcquisitionType"],
    "SequenceName": DICOM["SequenceName"],
    "RepetitionTime": DICOM["RepetitionTime"],
    "RepetitionTimePreparation": BIDS["RepetitionTimePreparation"],
    "ArterialSpinLabelingType": BIDS["ArterialSpinLabelingType"],
    "PostLabelingDelay": BIDS["PostLabelingDelay"],
    "BackgroundSuppression": BIDS["BackgroundSuppression"],
    "BackgroundSuppressionPulseTime": BIDS["BackgroundSuppressionPulseTime"],
    "BackgroundSuppressionNumberPulses": BIDS["BackgroundSuppressionNumberPulses"],
    "LabelingLocationDescription": BIDS["LabelingLocationDescription"],
    "LookLocker": BIDS["LookLocker"],
    "LabelingEfficiency": BIDS["LabelingEfficiency"],
    "LabelingDuration": BIDS["LabelingDuration"],
    "LabelingPulseAverageGradient": BIDS["LabelingPulseAverageGradient"],
    "LabelingPulseMaximumGradient": BIDS["LabelingPulseMaximumGradient"],
    "LabelingPulseDuration": BIDS["LabelingPulseDuration"],
    "LabelingPulseFlipAngle": BIDS["LabelingPulseFlipAngle"],
    "LabelingPulseInterval": BIDS["LabelingPulseInterval"],
    "PCASLType": BIDS["PCASLType"],
    "M0Type": BIDS["M0Type"],
    "TotalAcquiredPairs": BIDS["TotalAcquiredPairs"],
    "VascularCrushing": BIDS["VascularCrushing"],
    "EchoTime": BIDS["EchoTime"],
    "InversionTime": DICOM["InversionTime"],
    "NumberOfAverages": DICOM["NumberOfAverages"],
    "ImagingFrequency": DICOM["ImagingFrequency"],
    "MagneticFieldStrength": DICOM["MagneticFieldStrength"],
    "NumberOfPhaseEncodingSteps": DICOM["NumberOfPhaseEncodingSteps"],
    "EchoTrainLength": DICOM["EchoTrainLength"],
    "PercentSampling": DICOM["PercentSampling"],
    "PercentPhaseFieldOfView": DICOM["PercentPhaseFieldOfView"],
    "PixelBandwidth": DICOM["PixelBandwidth"],
    "AccelerationFactorPE": DICOM["AccelerationFactorPE"],
    "AccelNumReferenceLines": DICOM["AccelNumReferenceLines"],
    "TotalScanTimeSec": DICOM["TotalScanTimeSec"],
    "ReceiveCoilName": DICOM["ReceiveCoilName"],
    "DeviceSerialNumber": DICOM["DeviceSerialNumber"],
    "SoftwareVersions": DICOM["SoftwareVersions"],
    "ProtocolName": DICOM["ProtocolName"],
    "TransmitCoilName": DICOM["TransmitCoilName"],
    "AcquisitionMatrix": DICOM["AcquisitionMatrix"],
    "AcquisitionVoxelSize": BIDS["AcquisitionVoxelSize"],
    "InPlanePhaseEncodingDirection": DICOM["InPlanePhaseEncodingDirection"],
    "FlipAngle": BIDS["FlipAngle"],
    "VariableFlipAngleFlag": DICOM["VariableFlipAngleFlag"],
    "PatientPosition": DICOM["PatientPosition"],
    "PhaseEncodingDirection": BIDS["PhaseEncodingDirection"],
    "SliceTiming": BIDS["SliceTiming"],
    "TotalReadoutTime": BIDS["TotalReadoutTime"],
    "EffectiveEchoSpacing": NIDM["EffectiveEchoSpacing"],
    "NumberDiscardedVolumesByScanner": NIDM["NumberDiscardedVolumesByScanner"],
    "NumberDiscardedVolumesByUser": NIDM["NumberDiscardedVolumesByUser"],
    "DelayTime": NIDM["DelayTime"],
    "PulseSequenceType": DICOM["PulseSequenceName"],
    # Task Stuff
    "TaskName": Constants.NIDM_MRI_FUNCTION_TASK,
}


__all__ = ["dataset_description", "participants", "scans", "json_keys"]
