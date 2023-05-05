from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Optional
import prov.model as pm
import pytest
from nidm.core import Constants
from nidm.experiment import (
    Acquisition,
    AssessmentAcquisition,
    AssessmentObject,
    Project,
    Query,
    Session,
)
from nidm.experiment.CDE import download_cde_files
import nidm.experiment.Navigate


@dataclass
class ProjectData:
    files: list[str]
    cmu_test_project_uuid: str


@pytest.fixture(scope="module", autouse="True")
def abide(brain_vol_files) -> ProjectData:
    files = [f for f in brain_vol_files if Path(f).name == "cmu_a.nidm.ttl"]
    assert files
    projects = Query.GetProjectsUUID(files)
    cmu_test_project_uuid: Optional[str] = None
    for p in projects:
        proj_info = nidm.experiment.Navigate.GetProjectAttributes(files, p)
        if (
            "dctypes:title" in proj_info
            and proj_info["dctypes:title"] == "ABIDE - CMU_a"
        ):
            cmu_test_project_uuid = p
            break
    assert cmu_test_project_uuid is not None
    return ProjectData(files, cmu_test_project_uuid)


def test_GetProjectMetadata(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    project = Project(uuid="_123456", attributes=kwargs)

    # save a turtle file
    with open(tmp_path / "test_gpm.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseIII",
        Constants.NIDM_PROJECT_IDENTIFIER: 1200,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation2",
    }
    project = Project(uuid="_654321", attributes=kwargs)

    # save a turtle file
    with open(tmp_path / "test2_gpm.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    # WIP test = Query.GetProjectMetadata(["test.ttl", "test2.ttl"])

    # assert URIRef(Constants.NIDM + "_654321") in test
    # assert URIRef(Constants.NIDM + "_123456") in test
    # assert URIRef(Constants.NIDM_PROJECT_IDENTIFIER + "1200") in test
    # assert URIRef(Constants.NIDM_PROJECT_IDENTIFIER + "9610") in test
    # assert URIRef((Constants.NIDM_PROJECT_NAME + "FBIRN_PhaseII")) in test
    # assert URIRef((Constants.NIDM_PROJECT_NAME + "FBIRN_PhaseIII")) in test
    # assert URIRef((Constants.NIDM_PROJECT_DESCRIPTION + "Test investigation")) in test
    # assert URIRef((Constants.NIDM_PROJECT_DESCRIPTION + "Test investigation2")) in test


def test_GetProjects(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    project = Project(uuid="_123456", attributes=kwargs)

    # save a turtle file
    with open(tmp_path / "test_gp.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    project_list = Query.GetProjectsUUID([str(tmp_path / "test_gp.ttl")])

    assert Constants.NIIRI + "_123456" in [str(x) for x in project_list]


def test_GetParticipantIDs(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    project = Project(uuid="_123456", attributes=kwargs)
    session = Session(uuid="_13579", project=project)
    acq = Acquisition(uuid="_15793", session=session)
    acq2 = Acquisition(uuid="_15795", session=session)

    person = acq.add_person(attributes={Constants.NIDM_SUBJECTID: "9999"})
    acq.add_qualified_association(person=person, role=Constants.NIDM_PARTICIPANT)

    person2 = acq2.add_person(attributes={Constants.NIDM_SUBJECTID: "8888"})
    acq2.add_qualified_association(person=person2, role=Constants.NIDM_PARTICIPANT)

    # save a turtle file
    with open(tmp_path / "test_3.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    participant_list = Query.GetParticipantIDs([str(tmp_path / "test_3.ttl")])

    assert participant_list["ID"].str.contains("9999").any()
    assert participant_list["ID"].str.contains("8888").any()


def test_GetProjectInstruments(tmp_path: Path) -> None:
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
    }
    proj_uuid = "_123456gpi"
    project = Project(uuid=proj_uuid, attributes=kwargs)

    session = Session(project)
    acq = AssessmentAcquisition(session)

    kwargs = {
        pm.PROV_TYPE: pm.QualifiedName(
            pm.Namespace("nidm", Constants.NIDM), "NorthAmericanAdultReadingTest"
        )
    }
    AssessmentObject(acq, attributes=kwargs)

    acq2 = AssessmentAcquisition(session)

    kwargs = {
        pm.PROV_TYPE: pm.QualifiedName(
            pm.Namespace("nidm", Constants.NIDM), "PositiveAndNegativeSyndromeScale"
        )
    }
    AssessmentObject(acq2, attributes=kwargs)

    # save a turtle file
    with open(tmp_path / "test_gpi.ttl", "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())

    assessment_list = Query.GetProjectInstruments(
        [str(tmp_path / "test_gpi.ttl")], proj_uuid
    )

    assert Constants.NIDM + "NorthAmericanAdultReadingTest" in [
        str(x) for x in assessment_list["assessment_type"].to_list()
    ]
    assert Constants.NIDM + "PositiveAndNegativeSyndromeScale" in [
        str(x) for x in assessment_list["assessment_type"].to_list()
    ]


"""
The test data file could/should have the following project meta data. Taken from
https://raw.githubusercontent.com/incf-nidash/nidm/master/nidm/nidm-experiment/terms/nidm-experiment.owl

  - description
  - fileName
  - license
  - source
  - title
  - hadNumericalValue ???
  - BathSolution ???
  - CellType
  - ChannelNumber
  - ElectrodeImpedance
  - GroupLabel
  - HollowElectrodeSolution
  - hadImageContrastType
  - hadImageUsageType
  - NumberOfChannels
  - AppliedFilter
  - SolutionFlowSpeed
  - RecordingLocation

Returns the

"""


def saveTestFile(file_name, data):
    project = Project(uuid="_123_" + file_name, attributes=data)

    return saveProject(file_name, project)


def saveProject(file_name, project):
    # save a turtle file
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(project.serializeTurtle())
    return f"nidm:_123_{file_name}"


def makeProjectTestFile(filename):
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "FBIRN_PhaseII",  # this is the "title"
        Constants.NIDM_PROJECT_IDENTIFIER: 9610,
        Constants.NIDM_PROJECT_DESCRIPTION: "Test investigation",
        Constants.NIDM_FILENAME: "testfile.ttl",
        Constants.NIDM_PROJECT_LICENSE: "MIT Licence",
        Constants.NIDM_PROJECT_SOURCE: "Educational Source",
        Constants.NIDM_HAD_NUMERICAL_VALUE: "numval???",
        Constants.NIDM_BATH_SOLUTION: "bath",
        Constants.NIDM_CELL_TYPE: "ctype",
        Constants.NIDM_CHANNEL_NUMBER: "5",
        Constants.NIDM_ELECTRODE_IMPEDANCE: ".01",
        Constants.NIDM_GROUP_LABEL: "group 123",
        Constants.NIDM_HOLLOW_ELECTRODE_SOLUTION: "water",
        Constants.NIDM_HAD_IMAGE_CONTRACT_TYPE: "off",
        Constants.NIDM_HAD_IMAGE_USAGE_TYPE: "abcd",
        Constants.NIDM_NUBMER_OF_CHANNELS: "11",
        Constants.NIDM_APPLIED_FILTER: "on",
        Constants.NIDM_SOLUTION_FLOW_SPEED: "2.8",
        Constants.NIDM_RECORDING_LOCATION: "lab",
    }
    return saveTestFile(filename, kwargs)


def makeProjectTestFile2(filename):
    kwargs = {
        Constants.NIDM_PROJECT_NAME: "TEST B",  # this is the "title"
        Constants.NIDM_PROJECT_IDENTIFIER: 1234,
        Constants.NIDM_PROJECT_DESCRIPTION: "More Scans",
        Constants.NIDM_FILENAME: "testfile2.ttl",
        Constants.NIDM_PROJECT_LICENSE: "Creative Commons",
        Constants.NIDM_PROJECT_SOURCE: "Other",
        Constants.NIDM_HAD_NUMERICAL_VALUE: "numval???",
        Constants.NIDM_BATH_SOLUTION: "bath",
        Constants.NIDM_CELL_TYPE: "ctype",
        Constants.NIDM_CHANNEL_NUMBER: "5",
        Constants.NIDM_ELECTRODE_IMPEDANCE: ".01",
        Constants.NIDM_GROUP_LABEL: "group 123",
        Constants.NIDM_HOLLOW_ELECTRODE_SOLUTION: "water",
        Constants.NIDM_HAD_IMAGE_CONTRACT_TYPE: "off",
        Constants.NIDM_HAD_IMAGE_USAGE_TYPE: "abcd",
        Constants.NIDM_NUBMER_OF_CHANNELS: "11",
        Constants.NIDM_APPLIED_FILTER: "on",
        Constants.NIDM_SOLUTION_FLOW_SPEED: "2.8",
        Constants.NIDM_RECORDING_LOCATION: "lab",
    }
    project = Project(uuid="_123_" + filename, attributes=kwargs)
    s1 = Session(project)

    a1 = AssessmentAcquisition(session=s1)
    # = s1.add_acquisition("a1", attributes={"http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#Age" : 22})

    p1 = a1.add_person(
        "p1", attributes={Constants.NIDM_GIVEN_NAME: "George", Constants.NIDM_AGE: 22}
    )
    a1.add_qualified_association(person=p1, role=Constants.NIDM_PARTICIPANT)

    return saveProject(filename, project)


def test_GetProjectsMetadata(abide: ProjectData, tmp_path: Path) -> None:
    p1 = makeProjectTestFile(str(tmp_path / "testfile.ttl"))
    p2 = makeProjectTestFile2(str(tmp_path / "testfile2.ttl"))
    files = [
        str(tmp_path / "testfile.ttl"),
        str(tmp_path / "testfile2.ttl"),
        *abide.files,
    ]

    parsed = Query.GetProjectsMetadata(files)

    # assert parsed['projects'][p1][str(Constants.NIDM_PROJECT_DESCRIPTION)] == "Test investigation"
    # assert parsed['projects'][p2][str(Constants.NIDM_PROJECT_DESCRIPTION)] == "More Scans"

    # we shouldn't have the computed metadata in this result
    # assert parsed['projects'][p1].get (Query.matchPrefix(str(Constants.NIDM_NUMBER_OF_SUBJECTS)), -1) == -1

    # find the project ID from the CMU file
    p3 = None
    for project_id in parsed["projects"]:
        if project_id not in (p1, p2):
            if (
                parsed["projects"][project_id][str(Constants.NIDM_PROJECT_NAME)]
                == "ABIDE - CMU_a"
            ):
                p3 = project_id
                break
    assert p3 is not None


def test_prefix_helpers():
    assert (
        Query.expandNIDMAbbreviation("ndar:src_subject_id")
        == "https://ndar.nih.gov/api/datadictionary/v2/dataelement/src_subject_id"
    )

    assert Query.matchPrefix("http://purl.org/nidash/nidm#abc") == "nidm:abc"
    assert Query.matchPrefix("http://www.w3.org/ns/prov#123") == "prov:123"
    assert Query.matchPrefix("http://purl.org/nidash/fsl#xyz") == "fsl:xyz"
    assert Query.matchPrefix("http://purl.org/nidash/fsl#xyz", short=True) == "fsl"


def test_getProjectAcquisitionObjects(abide: ProjectData) -> None:
    files = abide.files

    project_list = Query.GetProjectsUUID(files)
    project_uuid = str(project_list[0])
    objects = Query.getProjectAcquisitionObjects(files, project_uuid)

    assert isinstance(objects, list)


def test_GetProjectAttributes(abide: ProjectData) -> None:
    files = abide.files

    project_uuid = abide.cmu_test_project_uuid
    project_attributes = nidm.experiment.Navigate.GetProjectAttributes(
        files, project_uuid
    )
    assert ("prov:Location" in project_attributes) or ("Location" in project_attributes)
    assert ("dctypes:title" in project_attributes) or ("title" in project_attributes)
    assert (
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in project_attributes
    ) or ("type" in project_attributes)
    assert "AcquisitionModality" in project_attributes
    assert "ImageContrastType" in project_attributes
    assert "Task" in project_attributes
    assert "ImageUsageType" in project_attributes


def test_download_cde_files():
    cde_dir = download_cde_files()
    assert cde_dir == tempfile.gettempdir()
    fcount = 0
    for url in Constants.CDE_FILE_LOCATIONS:
        fname = url.split("/")[-1]
        assert Path(cde_dir, fname).is_file()
        fcount += 1
    assert fcount > 0


@pytest.mark.skip(
    reason="We don't have an easily accessible file for this test so skipping it until better test samples are available."
)
def test_custom_data_types():
    SPECIAL_TEST_FILES = ["/opt/project/ttl/MTdemog_aseg.ttl"]

    valuetype1 = Query.getDataTypeInfo(
        Query.OpenGraph(SPECIAL_TEST_FILES[0]), "no-real-value"
    )
    assert valuetype1 is False

    valuetype2 = Query.getDataTypeInfo(
        Query.OpenGraph(SPECIAL_TEST_FILES[0]), Constants.NIIRI["age_e3hrcc"]
    )
    assert str(valuetype2["label"]) == "age"
    assert str(valuetype2["description"]) == "Age of participant at scan"
    assert str(valuetype2["isAbout"]) == str(Constants.NIIRI["24d78sq"])

    valuetype3 = Query.getDataTypeInfo(
        Query.OpenGraph(SPECIAL_TEST_FILES[0]), "age_e3hrcc"
    )
    assert str(valuetype3["label"]) == "age"
    assert str(valuetype3["description"]) == "Age of participant at scan"
    assert str(valuetype3["isAbout"]) == str(Constants.NIIRI["24d78sq"])
