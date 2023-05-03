from dataclasses import dataclass
import urllib.request
import pytest
from nidm.experiment.tools.rest import RestParser

BRAIN_VOL_FILES = ["cmu_a.nidm.ttl", "caltech.nidm.ttl"]
OPENNEURO_FILES = [
    "ds000002.nidm.ttl",
    "ds000003.nidm.ttl",
    "ds000011.nidm.ttl",
    "ds000017.nidm.ttl",
    "ds000101.nidm.ttl",
    "ds000108.nidm.ttl",
    "ds000113.nidm.ttl",
    "ds000114.nidm.ttl",
    "ds000120.nidm.ttl",
    "ds000122.nidm.ttl",
    "ds000138.nidm.ttl",
    "ds000171.nidm.ttl",
    "ds000208.nidm.ttl",
    "ds000214.nidm.ttl",
    "ds000222.nidm.ttl",
    "ds000224.nidm.ttl",
    "ds000238.nidm.ttl",
    "ds000246.nidm.ttl",
    "ds001021.nidm.ttl",
    "ds001178.nidm.ttl",
    "ds001232.nidm.ttl",
    "ds001241.nidm.ttl",
]

# OPENNEURO_FILES = ['ds000001.nidm.ttl',
#                    'ds000003.nidm.ttl']
#


@dataclass
class Setup:
    brain_vol_files: list[str]
    openneuro_files: list[str]


@pytest.fixture(scope="module")
def setup(tmp_path_factory: pytest.TempPathFactory) -> Setup:
    tmp_path = tmp_path_factory.mktemp("setup")
    for fname in OPENNEURO_FILES:
        dataset = fname.split(".")[0]
        urllib.request.urlretrieve(
            f"https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/openneuro/{dataset}/nidm.ttl",
            tmp_path / fname,
        )

    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
        tmp_path / "cmu_a.nidm.ttl",
    )

    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/Caltech/nidm.ttl",
        tmp_path / "caltech.nidm.ttl",
    )

    return Setup(
        brain_vol_files=[str(tmp_path / fname) for fname in BRAIN_VOL_FILES],
        openneuro_files=[str(tmp_path / fname) for fname in OPENNEURO_FILES],
    )


def test_dataelement_list(setup: Setup) -> None:
    rest_parser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    result = rest_parser.run(setup.openneuro_files, "/dataelements")

    assert type(result) == dict
    assert "data_elements" in result
    assert "uuid" in result["data_elements"]
    assert "label" in result["data_elements"]
    assert "data_type_info" in result["data_elements"]

    assert len(result["data_elements"]["label"]) != 0
    assert len(result["data_elements"]["label"]) == len(result["data_elements"]["uuid"])
    assert len(result["data_elements"]["label"]) == len(
        result["data_elements"]["data_type_info"]
    )

    for label in result["data_elements"]["label"]:
        assert label in [
            str(x["label"]) for x in result["data_elements"]["data_type_info"]
        ]

    for uuid in result["data_elements"]["uuid"]:
        assert uuid in [
            str(x["dataElementURI"]) for x in result["data_elements"]["data_type_info"]
        ]

    # now check for derivatives
    result = rest_parser.run(setup.brain_vol_files, "/dataelements")
    assert type(result) == dict
    assert (
        "Left-WM-hypointensities Volume_mm3 (mm^3)" in result["data_elements"]["label"]
    )


def test_dataelement_details(setup: Setup) -> None:
    rest_parser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    # result = rest_parser.run(setup.openneuro_files, '/dataelements')
    #
    # dti = rest_parser.run(setup.openneuro_files, '/dataelements/{}'.format(result["data_elements"]["label"][0]))
    #
    # assert "label" in dti
    # assert "description" in dti
    # assert "isAbout" in dti
    # assert "inProjects" in dti
    #
    # # make sure the text formatter doesn't fail horribly
    # rest_parser.setOutputFormat(RestParser.CLI_FORMAT)
    # txt = rest_parser.run(setup.openneuro_files, '/dataelements/{}'.format(result["data_elements"]["label"][0]))
    #

    dti = rest_parser.run(
        setup.openneuro_files, "/dataelements/Left-WM-hypointensities Volume_mm3 (mm^3)"
    )
    print(dti)


def test_dataelement_details_in_projects_field(setup: Setup) -> None:
    rest_parser = RestParser(output_format=RestParser.OBJECT_FORMAT)
    # result = rest_parser.run(setup.openneuro_files, '/dataelements')
    # dti = rest_parser.run(setup.openneuro_files, '/dataelements/{}'.format(result["data_elements"]["label"][0]))
    # assert len(dti['inProjects']) >= 1

    # find a data element that we are using for at least one subject
    data_element_label = "Right-non-WM-hypointensities normMax (MR)"
    dti = rest_parser.run(setup.brain_vol_files, f"/dataelements/{data_element_label}")
    assert len(dti["inProjects"]) >= 1
