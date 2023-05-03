from __future__ import annotations
from pathlib import Path
import click
from click.testing import CliRunner
import pytest
from nidm.experiment.tools.nidm_linreg import linear_regression


def call_click_command(cmd, *args, **kwargs):
    """Wrapper to call a click command

    :param cmd: click cli command function to call
    :param args: arguments to pass to the function
    :param kwargs: keyword arguments to pass to the function
    :return: None
    """

    # Get positional arguments from args
    arg_values = {c.name: a for a, c in zip(args, cmd.params)}
    args_needed = {c.name: c for c in cmd.params if c.name not in arg_values}

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
                raise click.BadParameter("Unknown keyword argument '{}'".format(name))

    # check positional arguments list
    for arg in (a for a in cmd.params if isinstance(a, click.Argument)):
        if arg.name not in arg_values:
            raise click.BadParameter(
                "Missing required positional parameter '{}'".format(arg.name)
            )

    # build parameter lists
    opts_list = sum([[o.opts[0], arg_values[n]] for n, o in opts.items()], [])
    args_list = [str(v) for n, v in arg_values.items() if n not in opts]

    # call the command
    CliRunner().invoke(cmd, opts_list + args_list)


def test_simple_model(brain_vol_files: list[str], tmp_path: Path) -> None:
    arguments = dict(
        nidm_file_list=",".join(brain_vol_files),
        ml="fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400",
        ctr=None,
        regularization=None,
        output_file=str(tmp_path / "output.txt"),
    )

    call_click_command(linear_regression, *arguments, **arguments)

    out = (tmp_path / "output.txt").read_text()

    # check if model was read correctly
    assert "fs_000008 ~ ilx_0100400 + DX_GROUP" in out

    # check correct number of observations
    assert "No. Observations:                  53" in out

    # check model coefficients
    assert (
        "const          27.7816      4.378      6.345      0.000      18.988      36.576"
        in out
    )
    assert (
        "ilx_0100400    -0.1832      0.173     -1.061      0.294      -0.530       0.164"
        in out
    )
    assert (
        "DX_GROUP        3.4908      4.031      0.866      0.391      -4.605      11.587"
        in out
    )


def test_model_with_contrasts(brain_vol_files: list[str], tmp_path: Path) -> None:
    # run linear regression tool with simple model and evaluate output

    arguments = dict(
        nidm_file_list=",".join(brain_vol_files),
        ml="fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400",
        ctr="DX_GROUP",
        regularization=None,
        output_file=str(tmp_path / "output.txt"),
    )

    call_click_command(linear_regression, *arguments, **arguments)

    out = (tmp_path / "output.txt").read_text()

    # check if model was read correctly
    assert "fs_000008 ~ ilx_0100400 + DX_GROUP" in out

    # check correct number of observations
    assert "No. Observations:                  53" in out

    # check model coefficients for different codings
    assert (
        "C(DX_GROUP, Treatment)[T.1]     0.7307      4.209      0.174      0.863      -7.727       9.189"
        in out
    )
    assert (
        "C(DX_GROUP, Treatment)[T.2]    32.7462     15.984      2.049      0.046       0.625      64.868"
        in out
    )
    assert (
        "C(DX_GROUP, Simple)[Simp.0]     0.7307      4.209      0.174      0.863      -7.727       9.189"
        in out
    )
    assert (
        "C(DX_GROUP, Simple)[Simp.1]    32.7462     15.984      2.049      0.046       0.625      64.868"
        in out
    )
    assert (
        "C(DX_GROUP, Sum)[S.0]   -11.1590      5.713     -1.953      0.057     -22.639       0.321"
        in out
    )
    assert (
        "C(DX_GROUP, Sum)[S.1]   -10.4283      5.631     -1.852      0.070     -21.743       0.887"
        in out
    )
    assert (
        "C(DX_GROUP, Diff)[D.0]     0.7307      4.209      0.174      0.863      -7.727       9.189"
        in out
    )
    assert (
        "C(DX_GROUP, Diff)[D.1]    32.0155     15.896      2.014      0.050       0.070      63.961"
        in out
    )
    assert (
        "C(DX_GROUP, Helmert)[H.1]     0.3653      2.104      0.174      0.863      -3.864       4.594"
        in out
    )
    assert (
        "C(DX_GROUP, Helmert)[H.2]    10.7936      5.267      2.049      0.046       0.209      21.378"
        in out
    )


@pytest.mark.skip(
    reason="regularization weights seem to be different depending on the platform"
)
def test_model_with_contrasts_reg_L1(
    brain_vol_files: list[str], tmp_path: Path
) -> None:
    arguments = dict(
        nidm_file_list=",".join(brain_vol_files),
        ml="fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400",
        ctr="DX_GROUP",
        regularization="L1",
        output_file=str(tmp_path / "output.txt"),
    )

    call_click_command(linear_regression, *arguments, **arguments)

    out = (tmp_path / "output.txt").read_text()

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


@pytest.mark.skip(
    reason="regularization weights seem to be different depending on the platform"
)
def test_model_with_contrasts_reg_L2(
    brain_vol_files: list[str], tmp_path: Path
) -> None:
    arguments = dict(
        nidm_file_list=",".join(brain_vol_files),
        ml="fs_000008 = DX_GROUP + http://uri.interlex.org/ilx_0100400",
        ctr="DX_GROUP",
        regularization="L2",
        output_file=str(tmp_path / "output.txt"),
    )

    call_click_command(linear_regression, *arguments, **arguments)

    out = (tmp_path / "output.txt").read_text()

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
