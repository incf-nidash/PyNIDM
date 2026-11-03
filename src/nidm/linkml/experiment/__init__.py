"""
nidm.linkml.experiment — RDFLib + LinkML implementation of NIDM-Experiment.

Mirrors the public API of the legacy ``nidm.experiment`` package
(Project, Session, Acquisition, AcquisitionObject, MRAcquisition,
MRObject, PETAcquisition, PETObject, AssessmentAcquisition,
AssessmentObject, DemographicsObject, DataElement, PersonalDataElement,
Derivative, DerivativeObject) but built on ``rdflib.Graph`` directly,
backed by Pydantic dataclasses generated from ``nidm_schema.yaml``.

Wrappers are landing incrementally — re-exports below grow as each
class is ported.
"""
from . import navigate, query  # noqa: F401 -- submodule re-export shims
from .acquisition import Acquisition
from .acquisition_object import AcquisitionObject
from .assessment_acquisition import AssessmentAcquisition
from .assessment_object import AssessmentObject
from .association import Association
from .collection import Collection
from .core import Core, getUUID
from .data_element import DataElement
from .demographics_object import DemographicsObject
from .derivative import Derivative
from .derivative_object import DerivativeObject
from .export_activity import ExportActivity
from .linkml_node import LinkMLBackedNode
from .mr_acquisition import MRAcquisition
from .mr_object import MRObject
from .person import Person
from .personal_data_element import PersonalDataElement
from .pet_acquisition import PETAcquisition
from .pet_object import PETObject
from .project import Project
from .session import Session
from .software_agent import SoftwareAgent

__all__ = [
    "add_segmentation_derivative",
    "Acquisition",
    "AcquisitionObject",
    "AssessmentAcquisition",
    "AssessmentObject",
    "Association",
    "Collection",
    "Core",
    "DataElement",
    "DemographicsObject",
    "Derivative",
    "DerivativeObject",
    "ExportActivity",
    "getUUID",
    "LinkMLBackedNode",
    "MRAcquisition",
    "MRObject",
    "Person",
    "PersonalDataElement",
    "PETAcquisition",
    "PETObject",
    "Project",
    "Session",
    "SoftwareAgent",
]


def __getattr__(name):  # noqa: D401 -- PEP 562 lazy attribute
    """Lazily expose ``add_segmentation_derivative`` without importing the
    derivatives module (and its ``pandas`` / tools dependencies) at package
    import time.  Keeps ``import nidm.linkml.experiment`` lightweight while
    still allowing ``from nidm.linkml.experiment import
    add_segmentation_derivative``."""
    if name == "add_segmentation_derivative":
        from .derivatives import add_segmentation_derivative

        return add_segmentation_derivative
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
