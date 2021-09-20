import urllib
import re
import sys

import pytest
import rdflib

from nidm.experiment import Project, Session, AssessmentAcquisition, AssessmentObject, Acquisition, AcquisitionObject, Query
from nidm.core import Constants
from nidm.experiment.tools.rest import RestParser
from nidm.experiment.tools.tests.test_rest_statistics import BRAIN_VOL_FILES

from nidm.experiment.tools.nidm_linreg import linear_regression

import os
from os.path import join,sep
from pathlib import Path
from rdflib import Graph, util, URIRef
import json
from io import TextIOWrapper, BytesIO
import subprocess
from subprocess import PIPE
import tempfile
import click

@pytest.fixture(scope="module", autouse="True")
def setup():

    for f in ['./cmu_a.nidm.ttl', 'caltech.nidm.ttl']:
        if Path(f).is_file():
            os.remove(f)

    if not Path('./cmu_a.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl",
            "cmu_a.nidm.ttl"
        )

    if not Path('./caltech.nidm.ttl').is_file():
        urllib.request.urlretrieve (
            "https://raw.githubusercontent.com/dbkeator/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/Caltech/nidm.ttl",
            "caltech.nidm.ttl"
        )

def call_click_command(cmd, *args, **kwargs):
    """ Wrapper to call a click command

    :param cmd: click cli command function to call
    :param args: arguments to pass to the function
    :param kwargs: keywrod arguments to pass to the function
    :return: None
    """

    # Get positional arguments from args
    arg_values = {c.name: a for a, c in zip(args, cmd.params)}
    args_needed = {c.name: c for c in cmd.params
                   if c.name not in arg_values}

    # build and check opts list from kwargs
    opts = {a.name: a for a in cmd.params if isinstance(a, click.Option)}
    for name in kwargs:
        if name in opts:
            arg_values[name] = kwargs[name]
        else:
            if name in args_needed:
                arg_values[name] = kwargs[name]
                del args_needed[name]
            else:
                raise click.BadParameter(
                    "Unknown keyword argument '{}'".format(name))


    # check positional arguments list
    for arg in (a for a in cmd.params if isinstance(a, click.Argument)):
        if arg.name not in arg_values:
            raise click.BadParameter("Missing required positional"
                                     "parameter '{}'".format(arg.name))

    # build parameter lists
    opts_list = sum(
        [[o.opts[0], arg_values[n]] for n, o in opts.items()], [])
    args_list = [str(v) for n, v in arg_values.items() if n not in opts]

    # call the command
    try:
        cmd(opts_list + args_list)
    except:
        pass



def test_simple_model():


    # run linear regression tool with simple model and evaluate output
    dirname = os.path.dirname(__file__)
    linreg_dirname = join(sep+join(*(dirname.split(sep)[:-1])))


    arguments = (dict(nidm_file_list =",".join(BRAIN_VOL_FILES),
                      ml='fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400',
                      ctr=None,regularization=None,output_file="output.txt"))

    call_click_command(linear_regression,*arguments,**arguments)
   

    if os.path.exists("output.txt"):
        fp = open("output.txt", "r")
        out = fp.read()
        fp.close()
        os.remove("output.txt")



    # check if model was read correctly
    assert "fs_000008 ~ ilx_0100400 + DX_GROUP" in out

    # check correct number of observations
    assert "No. Observations:                  53" in out

    # check model coefficients
    assert "const          27.7816      4.378      6.345      0.000      18.988      36.576" in out
    assert "ilx_0100400    -0.1832      0.173     -1.061      0.294      -0.530       0.164" in out
    assert "DX_GROUP        3.4908      4.031      0.866      0.391      -4.605      11.587" in out

def test_model_with_contrasts():
    # run linear regression tool with simple model and evaluate output

    arguments = (dict(nidm_file_list=",".join(BRAIN_VOL_FILES),
                      ml='fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400',
                      ctr="DX_GROUP", regularization=None, output_file="output.txt"))

    call_click_command(linear_regression, *arguments, **arguments)


    if os.path.exists('output.txt'):
        fp = open('output.txt', "r")
        out = fp.read()
        fp.close()
        os.remove('output.txt')

    # print(out)

    # check if model was read correctly
    assert "fs_000008 ~ ilx_0100400 + DX_GROUP" in out

    # check correct number of observations
    assert "No. Observations:                  53" in out

    # check model coefficients for different codings
    assert "C(DX_GROUP, Treatment)[T.1]     0.7307      4.209      0.174      0.863      -7.727       9.189" in out
    assert "C(DX_GROUP, Treatment)[T.2]    32.7462     15.984      2.049      0.046       0.625      64.868" in out
    assert "C(DX_GROUP, Simple)[Simp.0]     0.7307      4.209      0.174      0.863      -7.727       9.189" in out
    assert "C(DX_GROUP, Simple)[Simp.1]    32.7462     15.984      2.049      0.046       0.625      64.868" in out
    assert "C(DX_GROUP, Sum)[S.0]   -11.1590      5.713     -1.953      0.057     -22.639       0.321" in out
    assert "C(DX_GROUP, Sum)[S.1]   -10.4283      5.631     -1.852      0.070     -21.743       0.887" in out
    assert "C(DX_GROUP, Diff)[D.0]     0.7307      4.209      0.174      0.863      -7.727       9.189" in out
    assert "C(DX_GROUP, Diff)[D.1]    32.0155     15.896      2.014      0.050       0.070      63.961" in out
    assert "C(DX_GROUP, Helmert)[H.1]     0.3653      2.104      0.174      0.863      -3.864       4.594" in out
    assert "C(DX_GROUP, Helmert)[H.2]    10.7936      5.267      2.049      0.046       0.209      21.378" in out

@pytest.mark.skip(reason="regularization weights seem to be different depending on the platform")
def test_model_with_contrasts_reg_L1():


    arguments = (dict(nidm_file_list=",".join(BRAIN_VOL_FILES),
                      ml='fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400',
                      ctr="DX_GROUP", regularization="L1", output_file="output.txt"))

    call_click_command(linear_regression, *arguments, **arguments)

    if os.path.exists('output.txt'):
        fp = open('output.txt', "r")
        out = fp.read()
        fp.close()
        os.remove('output.txt')

    print(out)

    # check if model was read correctly
    assert "fs_000008 ~ ilx_0100400 + DX_GROUP" in out

    # check correct number of observations
    assert "No. Observations:                  53" in out

    # check lasso regression
    assert "Alpha with maximum likelihood (range: 1 to 700) = 43.000000" in out
    assert "Current Model Score = 0.000000" in out
    assert "ilx_0100400 	 -0.000000" in out
    assert "DX_GROUP 	 0.000000" in out
    assert "Intercept: 26.000000" in out

@pytest.mark.skip(reason="regularization weights seem to be different depending on the platform")
def test_model_with_contrasts_reg_L2():

    arguments = (dict(nidm_file_list=",".join(BRAIN_VOL_FILES),
                      ml='fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400',
                      ctr="DX_GROUP", regularization="L2", output_file="output.txt"))

    call_click_command(linear_regression, *arguments, **arguments)

    if os.path.exists('output.txt'):
        fp = open('output.txt', "r")
        out = fp.read()
        fp.close()
        os.remove('output.txt')

    # print(out)

    # check if model was read correctly
    assert "fs_000008 ~ ilx_0100400 + DX_GROUP" in out

    # check correct number of observations
    assert "No. Observations:                  53" in out

    # check lasso regression
    assert "Alpha with maximum likelihood (range: 1 to 700) = 699.000000" in out
    assert "Current Model Score = 0.017618" in out
    assert "ilx_0100400 	 -0.148397" in out
    assert "DX_GROUP 	 0.071356" in out
    assert "Intercept: 28.951297" in out