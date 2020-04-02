#!/usr/bin/env python
''' BIDS Terms -> NIDM-Exp Mappings
@author: David Keator <dbkeator@uci.edu>
'''
from . import Constants
#BIDS dataset_description -> NIDM constants mappings
dataset_description = {
    "BIDSVersion" : Constants.NIDM_PROJECT_IDENTIFIER,
    "Name" : Constants.NIDM_PROJECT_NAME,
    "Procedure" : Constants.NIDM_PROJECT_DESCRIPTION,
    "License" : Constants.NIDM_PROJECT_LICENSE,
    "ReferencesAndLinks" : Constants.NIDM_PROJECT_REFERENCES,
    "Authors" : Constants.NIDM_AUTHOR
}

#BIDS Participants file -> NIDM constants mappings
participants = {
    "participant_id" : Constants.NIDM_SUBJECTID
    #"sex" : Constants.NIDM_GENDER,
    #"age" : Constants.NIDM_AGE,
    #"gender" : Constants.NIDM_GENDER,
    #"diagnosis" : Constants.NIDM_DIAGNOSIS,
    #"handedness" : Constants.NIDM_HANDEDNESS
}
#scan metadata -> NIDM constants mappings
scans = {
    "anat" : Constants.NIDM_MRI_ANATOMIC_SCAN,
    "func" : Constants.NIDM_MRI_FUNCTION_SCAN,
    "dwi" : Constants.NIDM_MRI_DWI_SCAN,
    "bval" : Constants.NIDM_MRI_DWI_BVAL,
    "bvec" : Constants.NIDM_MRI_DWI_BVEC,
    "T1w" : Constants.NIDM_MRI_T1,
    "T2w" : Constants.NIDM_MRI_T2,
    "inplaneT2" : Constants.NIDM_MRI_T2,
    "bold" : Constants.NIDM_MRI_FLOW,
    "dti" : Constants.NIDM_MRI_DIFFUSION_TENSOR
}
#JSON file keys
json_keys = {
    ##Image terms
    "run" : Constants.NIDM_ACQUISITION_ENTITY,
    "ImageType" : Constants.DICOM["ImageType"],
    "ManufacturerModelName" : Constants.DICOM["ManufacturerModelName"],
    "ScanningSequence" : Constants.DICOM["ScanningSequence"],
    "SequenceVariant" : Constants.DICOM["SequenceVariant"],
    "ScanOptions" : Constants.DICOM["ScanOptions"],
    "MRAcquisitionType" : Constants.DICOM["MRAcquisitionType"],
    "SequenceName" : Constants.DICOM["SequenceName"],
    "RepetitionTime" : Constants.DICOM["RepetitionTime"],
    "EchoTime" : Constants.DICOM["EchoTime"],
    "InversionTime" : Constants.DICOM["InversionTime"],
    "NumberOfAverages" : Constants.DICOM["NumberOfAverages"],
    "ImagingFrequency" : Constants.DICOM["ImagingFrequency"],
    "MagneticFieldStrength" : Constants.DICOM["MagneticFieldStrength"],
    "NumberOfPhaseEncodingSteps" : Constants.DICOM["NumberOfPhaseEncodingSteps"],
    "EchoTrainLength": Constants.DICOM["EchoTrainLength"],
    "PercentSampling": Constants.DICOM["PercentSampling"],
    "PercentPhaseFieldOfView": Constants.DICOM["PercentPhaseFieldOfView"],
    "PixelBandwidth":Constants.DICOM["PixelBandwidth"],
    "AccelerationFactorPE": Constants.DICOM["AccelerationFactorPE"],
    "AccelNumReferenceLines": Constants.DICOM["AccelNumReferenceLines"],
    "TotalScanTimeSec": Constants.DICOM["TotalScanTimeSec"],
    "ReceiveCoilName": Constants.DICOM["ReceiveCoilName"],
    "DeviceSerialNumber": Constants.DICOM["DeviceSerialNumber"],
    "SoftwareVersions": Constants.DICOM["SoftwareVersions"],
    "ProtocolName": Constants.DICOM["ProtocolName"],
    "TransmitCoilName": Constants.DICOM["TransmitCoilName"],
    "AcquisitionMatrix": Constants.DICOM["AcquisitionMatrix"],
    "InPlanePhaseEncodingDirection": Constants.DICOM["InPlanePhaseEncodingDirection"],
    "FlipAngle": Constants.DICOM["FlipAngle"],
    "VariableFlipAngleFlag": Constants.DICOM["VariableFlipAngleFlag"],
    "PatientPosition": Constants.DICOM["PatientPosition"],
    "PhaseEncodingDirection": Constants.NIDM["PhaseEncodingDirection"],
    "SliceTiming": Constants.NIDM["SliceTiming"],
    "TotalReadoutTime" : Constants.DICOM["TotalReadoutTime"],
    "EffectiveEchoSpacing" : Constants.NIDM["EffectiveEchoSpacing"],
    "NumberDiscardedVolumesByScanner" : Constants.NIDM["NumberDiscardedVolumesByScanner"],
    "NumberDiscardedVolumesByUser" : Constants.NIDM["NumberDiscardedVolumesByUser"],
    "DelayTime" : Constants.NIDM["DelayTime"],
    ###Task Stuff
    "TaskName" : Constants.NIDM_MRI_FUNCTION_TASK
    # "CogAtlasID" :
    # "CogPOID" :
    # "TaskDescription" :
    # "Instructions" :
    # "TaskFullName" :
    # "TaskName" :
}
