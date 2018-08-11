import click
from click.testing import CliRunner
import subprocess
import pytest

from ..nidm_query import query

def test_query_failing():
    runner = CliRunner()
    res = runner.invoke(query)
    assert res.exit_code != 0
    assert "Missing option" in res.output

# TODO: adding tests that are passing
