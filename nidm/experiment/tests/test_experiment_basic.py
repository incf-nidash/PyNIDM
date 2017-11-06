import os,sys
import pytest, pdb

from nidm.experiment import Project,Session,Acquisition,AcquisitionObject
from nidm.core import Constants

def test_1(tmpdir):
    tmpdir.chdir()

    project = Project()

    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())


def test_2(tmpdir):
    tmpdir.chdir()

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(attributes=kwargs)

    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())


def test_sessions_1(tmpdir):
    tmpdir.chdir()

    project = Project()
    assert project.sessions == []

    session1 = Session(project)
    project.add_sessions(session1)
    assert session1.label == project.sessions[0].label

    session2 = Session(project)
    project.add_sessions(session2)
    assert len(project.sessions) == 2
    assert session2.label == project.sessions[1].label


def test_sessions_2(tmpdir):
    tmpdir.chdir()

    project = Project()
    assert project.sessions == []

    session1 = Session(project)
    assert project.sessions[0].label == session1.label


def test_sessions_3(tmpdir):
    tmpdir.chdir()

    project1 = Project()
    project2 = Project()

    session1 = Session(project1)
    session2 = Session(project2)

    project1.add_sessions(session1)
    project1.add_sessions(session2)

    assert len(project1.sessions) == 2
    assert session2.label == project1.sessions[1].label
    assert session1.label == project1.sessions[0].label


