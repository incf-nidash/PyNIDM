"""This program provides a tool to complete a linear regression on nidm files"""

import csv
import os
from statistics import mean
import sys
import tempfile
import warnings
import click
import numpy as np
import pandas as pd
from patsy.contrasts import ContrastMatrix, Diff, Helmert, Sum, Treatment
from patsy.highlevel import dmatrices
from sklearn import preprocessing
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.model_selection import cross_val_score
import statsmodels.api as sm
from statsmodels.formula.api import ols
from nidm.experiment.Query import GetProjectsUUID
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
from .utils import Reporter

MAX_ALPHA = 700


# Defining the parameters of the commands.
@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma separated list of NIDM files with full path",
)
@click.option(
    "--ctr",
    "-contrast",
    required=False,
    help="This parameter will show differences in relationship by group (e.g. -contrast age*sex,group). It can be one variable, interacting variables, or multiple",
)
@click.option(
    "--ml",
    "-model",
    required=True,
    help='This parameter will return the results of the linear regression from all nidm files supplied\nThe way this looks in the command is python3 nidm_linreg.py -nl MTdemog_aseg_v2.ttl -model "fs_003343 = age*sex + sex + age + group + age*group + bmi" -contrast group -r L1',
)
@click.option(
    "--output_file",
    "-o",
    required=False,
    help="Optional output file (TXT) to store results of the linear regression, contrast, and regularization",
)
@click.option(
    "--regularization",
    "-r",
    required=False,
    help="This parameter will return the results of the linear regression with L1 or L2 regularization depending on the type specified, and the weight with the maximum likelihood solution",
)
def linear_regression(nidm_file_list, output_file, ml, ctr, regularization):
    """
    This function provides a tool to complete a linear regression on NIDM data with optional contrast and regularization.
    """

    # NOTE: Every time I make a global variable, it is because I need it in at least one other method.
    global c  # used in linreg(), contrasting()
    c = ctr  # Storing all important parameters in global variables so they can be accessed in other methods
    global m  # Needed to do this because the code only used the parameters in the first method, meaning I had to move it all to method 1.
    m = (
        ml.strip()
    )  # used in data_aggregation, linreg(), spaces stripped from left and right
    with Reporter(output_file) as reporter:
        global n  # used in data_aggregation()
        n = nidm_file_list
        global r
        r = regularization
        data_aggregation(reporter)  # collects data
        dataparsing(reporter)  # converts it to proper format
        linreg(reporter)  # performs linear regression
        contrasting(reporter)  # performs contrast
        regularizing(reporter)  # performs regularization


def data_aggregation(reporter):  # all data from all the files is collected
    """
    This function provides query support for NIDM graphs.
    """
    # if there is a CDE file list, seed the CDE cache
    if m:  # ex: fs_00343 ~ age + sex + group
        print("*" * 107)
        command = "pynidm linear-regression -nl " + n + ' -model "' + m + '" '
        if c:
            command += '-contrast "' + c + '" '
        if r:
            command += "-r " + r + " "
        reporter.print("Your command was:", command)
        verbosity = 0
        restParser = RestParser(verbosity_level=int(verbosity))
        restParser.setOutputFormat(RestParser.OBJECT_FORMAT)
        global df_list  # used in dataparsing()
        df_list = []
        # set up uri to do fields query for each nidm file
        global file_list
        file_list = n.split(",")
        df_list_holder = {}
        for i in range(len(file_list)):
            df_list_holder[i] = []
        df_holder = {}
        for i in range(len(file_list)):
            df_holder[i] = []
        global condensed_data_holder
        condensed_data_holder = {}
        for i in range(len(file_list)):
            condensed_data_holder[i] = []

        count = 0
        not_found_count = 0
        for nidm_file in file_list:
            # get project UUID
            project = GetProjectsUUID([nidm_file])
            # split the model into its constituent variables
            global full_model_variable_list
            # below, we edit the model so it splits by +,~, or =. However, to help it out in catching everything
            # we replaced ~ and = with a + so that we can still use split. Regex wasn't working.
            plus_replace = m
            if "~" in m:
                plus_replace = m.replace("~", "+")
            elif "=" in m:
                plus_replace = m.replace("=", "+")
            elif "," in m:
                plus_replace = m.replace(",", "+")
            model_list = [v.strip() for v in plus_replace.split("+")]
            full_model_variable_list = []
            # set the dependent variable to the one dependent variable in the model
            global dep_var  # used in dataparsing(), linreg(), and contrasting()
            dep_var = model_list[0]
            # join the independent variables into a comma-separated list to make it easier to call from the uri
            global ind_vars  # used in dataparsing()
            ind_vars = ""
            for i in range(len(model_list) - 1, 0, -1):
                full_model_variable_list.append(
                    model_list[i]
                )  # will be used in the regularization, but we need the full list
                if (
                    "*" in model_list[i]
                ):  # removing the star term from the columns we're about to pull from data
                    model_list.pop(i)
                elif model_list[i] == dep_var:
                    model_list.pop(i)
                    reporter.print(
                        "\n\nAn independent variable cannot be the same as the dependent variable. This prevents the model from running accurately."
                    )
                    reporter.print(
                        'Please try a different model removing "'
                        + dep_var
                        + '" from either the right or the left side of the equation.\n\n'
                    )
                    sys.exit(1)
                else:
                    ind_vars = ind_vars + model_list[i] + ","
            ind_vars = ind_vars[0 : len(ind_vars) - 1]
            uri = (
                "/projects/"
                + project[0].toPython().split("/")[-1]
                + "?fields="
                + ind_vars
                + ","
                + dep_var
            )
            # get fields output from each file and concatenate
            df_list_holder[count].append(pd.DataFrame(restParser.run([nidm_file], uri)))
            # global dep_var
            df = pd.concat(df_list_holder[count])
            with tempfile.NamedTemporaryFile(
                delete=False
            ) as temp:  # turns the dataframe into a temporary csv
                df.to_csv(temp.name + ".csv")
                temp.close()
            with open(temp.name + ".csv", encoding="utf-8") as fp:
                data = list(
                    csv.reader(fp)
                )  # makes the csv a 2D list to make it easier to call the contents of certain cells

            global independentvariables  # used in linreg
            independentvariables = ind_vars.split(
                ","
            )  # makes a list of the independent variables
            numcols = (len(data) - 1) // (
                len(independentvariables) + 1
            )  # Finds the number of columns in the original dataframe
            condensed_data_holder[count] = [
                [0] * (len(independentvariables) + 1)
            ]  # makes an array 1 row by the number of necessary columns
            for _ in range(
                numcols
            ):  # makes the 2D array big enough to store all of the necessary values in the edited dataset
                condensed_data_holder[count].append(
                    [0] * (len(independentvariables) + 1)
                )
            for i, v in enumerate(independentvariables):
                # stores the independent variable names in the first row
                condensed_data_holder[count][0][i] = v
            condensed_data_holder[count][0][-1] = str(
                dep_var
            )  # stores the dependent variable name in the first row
            numrows = 1  # begins at the first row to add data
            fieldcolumn = (
                0  # the column the variable name is in in the original dataset
            )
            valuecolumn = 0  # the column the value is in in the original dataset
            datacolumn = 0  # if it is identified by the dataElement name instead of the field's name
            not_found_list = []
            for i in range(len(data[0])):
                if (
                    data[0][i] == "sourceVariable"
                ):  # finds the column where the variable names are
                    fieldcolumn = i
                elif (
                    data[0][i] == "source_variable"
                ):  # finds the column where the variable names are
                    fieldcolumn = i
                elif data[0][i] == "isAbout":
                    aboutcolumn = i
                elif data[0][i] == "label":
                    namecolumn = i  # finds the column where the variable names are
                elif data[0][i] == "value":
                    valuecolumn = i  # finds the column where the values are
                elif (
                    data[0][i] == "dataElement"
                ):  # finds the column where the data element is if necessary
                    datacolumn = i
            for i in range(
                len(condensed_data_holder[count][0])
            ):  # starts iterating through the dataset, looking for the name in that
                for j in range(
                    1, len(data)
                ):  # column, so it can append the values under the proper variables
                    try:
                        split_url = condensed_data_holder[count][0][i].split("/")
                        for k, fmv in enumerate(full_model_variable_list):
                            if "/" in fmv:
                                full_model_variable_list[k] = split_url[-1]
                        if (
                            data[j][fieldcolumn] == condensed_data_holder[count][0][i]
                        ):  # in the dataframe, the name is in column 3
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn
                            ]  # in the dataframe, the value is in column 2
                            numrows = (
                                numrows + 1
                            )  # moves on to the next row to add the proper values
                        elif data[j][aboutcolumn] == condensed_data_holder[count][0][i]:
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn
                            ]  # in the dataframe, the value is in column 2
                            numrows = (
                                numrows + 1
                            )  # moves on to the next row to add the proper values
                        elif (
                            data[j][aboutcolumn] == split_url[len(split_url) - 1]
                        ):  # this is in case the uri only works by querying the part after the last backslash
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn
                            ]  # in the dataframe, the value is in column 2
                            numrows = (
                                numrows + 1
                            )  # moves on to the next row to add the proper values
                        elif (
                            condensed_data_holder[count][0][i] in data[j][aboutcolumn]
                        ):  # this is in case the uri only works by querying the part after the last backslash
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn
                            ]  # in the dataframe, the value is in column 2
                            numrows = (
                                numrows + 1
                            )  # moves on to the next row to add the proper values
                        elif (
                            data[j][namecolumn] == condensed_data_holder[count][0][i]
                        ):  # in the dataframe, the name is in column 12
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn
                            ]  # in the dataframe, the value is in column 2
                            numrows = (
                                numrows + 1
                            )  # moves on to the next row to add the proper values
                        elif (
                            condensed_data_holder[count][0][i] == data[j][datacolumn]
                        ):  # in the dataframe, the name is in column 9
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn
                            ]  # in the dataframe, the value is in column 2
                            numrows = (
                                numrows + 1
                            )  # moves on to the next row to add the proper values
                    except IndexError:
                        numrows = numrows + 1
                numrows = 1  # resets to the first row for the next variable
            temp_list = condensed_data_holder[count]
            for j in range(
                len(temp_list[0]) - 1, 0, -1
            ):  # if the software appends a column with 0 as the heading, it removes this null column
                if temp_list[0][j] == "0" or temp_list[0][j] == "NaN":
                    for row in condensed_data_holder[count]:
                        row.pop(j)
            rowsize = len(condensed_data_holder[count][0])
            count1 = 0
            for i in range(0, rowsize):
                for row in condensed_data_holder[count]:
                    if row[i] == 0 or row[i] == "NaN" or row[i] == "0":
                        count1 = count1 + 1
                if count1 > len(condensed_data_holder[count]) - 2:
                    not_found_list.append(condensed_data_holder[count][0][i])
                count1 = 0
            for i, cdh in enumerate(condensed_data_holder[count][0]):
                condensed_data_holder[count][0][i] = cdh.replace(" ", "_")
            independentvariables = [
                v.split("/")[-1].replace(" ", "_") for v in independentvariables
            ]
            dep_var = dep_var.replace(" ", "_")
            count += 1
            if len(not_found_list) > 0:
                print("*" * 107)
                print()
                reporter.print("Your model was", m)
                reporter.print()
                reporter.print(
                    "The following variables were not found in "
                    + nidm_file
                    + ". The model cannot run because this will skew the data. Try checking your spelling or use nidm_query.py to see other possible variables."
                )
                for i, nf in enumerate(not_found_list):
                    reporter.print(f"{i+1}. {nf}")
                not_found_list.clear()
                not_found_count += 1
                print()
        if not_found_count > 0:
            sys.exit(1)

    else:
        print("ERROR: No query parameter provided.  See help:")
        print()
        os.system("pynidm linreg --help")
        sys.exit(1)


def dataparsing(
    reporter,
):  # The data is changed to a format that is usable by the linear regression method
    global condensed_data
    condensed_data = []
    for i in range(0, len(file_list)):
        condensed_data = condensed_data + condensed_data_holder[i]
    for i in range(len(condensed_data[0])):
        if (
            "/" in condensed_data[0][i]
        ):  # change any URLs to just the last part so contrasting works.
            split = condensed_data[0][i].split("/")
            condensed_data[0][i] = split[len(split) - 1]

    # In this section, if there are less than 20 points, the model will be
    # inaccurate and there are too few variables for regularization.  That
    # means that we warn the user that such errors can occur and ask them if
    # they want to proceed.  The answer is stored in answer. If the user
    # responds with N, it exits the code after writing the error to the output
    # file (if there is one).  If the user says Y instead, the code runs, but
    # stops before doing the regularization.
    global answer
    answer = "?"
    if (len(condensed_data) - 1) < 20:
        print(
            "\nYour data set has less than 20 points, which means the model calculated may not be accurate due to a lack of data. "
        )
        print("This means you cannot regularize the data either.")
        warnings.filterwarnings("ignore")
        answer = input("Continue anyways? Y or N: ")
        reporter.print_file("Your model was", m)
        reporter.print_file(
            "\n\nThere was a lack of data (<20 points) in your model, which may result in inaccuracies. In addition, a regularization cannot and will not be performed.\n"
        )
    if "n" in answer.lower():
        print("\nModel halted.")
        reporter.print_file("Your model was", m)
        reporter.print_file(
            "Due to a lack of data (<20 points), you stopped the model because the results may have been inaccurate."
        )
        sys.exit(1)
    x = pd.read_csv(
        opencsv(condensed_data)
    )  # changes the dataframe to a csv to make it easier to work with
    x.head()  # prints what the csv looks like
    x.dtypes  # checks data format
    obj_df = x.select_dtypes  # puts all the variables in a dataset
    x.shape  # says number of rows and columns in form of tuple
    x.describe()  # says dataset statistics
    obj_df = x.select_dtypes(
        include=["object"]
    ).copy()  # takes everything that is an object (not float or int) and puts it in a new dataset
    obj_df.head()  # prints the new dataset
    int_df = x.select_dtypes(
        include=["int64"]
    ).copy()  # takes everything that is an int and puts it in a new dataset
    float_df = x.select_dtypes(
        include=["float64"]
    ).copy()  # takes everything that is a float and puts it in a new dataset
    df_int_float = pd.concat([float_df, int_df], axis=1)
    variables = []  # starts a list that will store all variables that are not numbers
    for i in range(1, len(condensed_data)):  # goes through each variable
        for j in range(len(condensed_data[0])):  # in the 2D array
            try:  # if the value of the field can be turned into a float (is numerical)
                float(condensed_data[i][j])  # this means it's a number
            except ValueError:  # if it can't be (is a string)
                if (
                    condensed_data[0][j] not in variables
                ):  # adds the variable name to the list if it isn't there already
                    variables.append(condensed_data[0][j])
    le = (
        preprocessing.LabelEncoder()
    )  # anything involving le shows the encoding of categorical variables
    for v in variables:
        le.fit(obj_df[v].astype(str))
    obj_df_trf = obj_df.astype(str).apply(
        le.fit_transform
    )  # transforms the categorical variables into numbers.
    global df_final  # also used in linreg()
    if not obj_df_trf.empty:
        df_final = pd.concat(
            [df_int_float, obj_df_trf], axis=1
        )  # join_axes=[df_int_float.index])
    else:
        df_final = df_int_float
    reporter.print(df_final.to_string(header=True, index=True))
    reporter.print("\n\n" + ("*" * 107))
    reporter.print("\n\nModel Results: ")


def linreg(reporter):  # actual linear regression
    print("Model Results: ")
    # printing the corrected model_string
    model_string = []
    model_string.append(dep_var)
    model_string.append(" ~ ")
    for fmv in full_model_variable_list:
        model_string.append(fmv)
        model_string.append(" + ")
    model_string.pop(-1)
    global full_model
    full_model = "".join(model_string)
    print(full_model)  # prints model
    print()
    print("*" * 107)
    print()
    index = 0
    global levels  # also used in contrasting()
    levels = []
    for i in range(len(condensed_data[0])):
        if c == condensed_data[0][i]:
            index = i
    for i in range(1, len(condensed_data)):
        if condensed_data[i][index] not in levels:
            levels.append(condensed_data[i][index])
    levels = list(range(len(levels)))

    # Beginning of the linear regression
    global X
    global y
    if "*" in m:
        # correcting the format of the model string
        model_string = []
        model_string.append(dep_var)
        model_string.append(" ~ ")
        for fmv in full_model_variable_list:
            model_string.append(fmv)
            model_string.append(" + ")
        model_string.pop(-1)
        for i, mdl in enumerate(model_string):
            if "*" in mdl:
                replacement = mdl.split("*")
                model_string[i] = replacement[0] + ":" + replacement[1]
            # makes sure the model is in the right format.
        string = "".join(model_string)
        y, X = dmatrices(string, df_final)
    else:
        X = df_final[
            independentvariables
        ]  # gets the modified values of the independent variables
        y = df_final[dep_var]  # gets the modified values of the dependent variable
    if not c:
        # The linear regression
        regressor = LinearRegression()
        regressor.fit(X, y)
        # Data about the linear regression, starting without contrast
        X2 = sm.add_constant(X)
        statistics = sm.OLS(y, X2)
        finalstats = statistics.fit()
        # concatenate data frames
        reporter.print_file(full_model)
        reporter.print_file("\n" + ("*" * 85) + "\n")
        reporter.print(finalstats.summary())
        return finalstats


def contrasting(reporter):
    global c
    global full_model_variable_list
    if c:
        # to account for multiple contrast variables
        contrastvars = []
        if "," in c:
            contrastvars = c.split(",")
        contrastvars = [
            v.strip().replace(" ", "_").split("/")[-1] for v in contrastvars
        ]
        c = c.split("/")[-1]  # to account for URLs
        ind_vars_no_contrast_var = ""
        index = 1
        full_model_variable_list = [
            v.split("/")[-1].replace(" ", "_") for v in full_model_variable_list
        ]
        for var in full_model_variable_list:
            if var != c and var not in contrastvars:
                if index == 1:
                    ind_vars_no_contrast_var = var
                    index += 1
                else:
                    ind_vars_no_contrast_var += " + " + var
        if len(contrastvars) > 0:
            contraststring = " + ".join(contrastvars)
        else:
            if " " in c:
                c = c.replace(" ", "_")
            contraststring = c
        # With contrast (treatment coding)
        reporter.print_file("\n" + full_model)
        reporter.print_file("\n\n" + ("*" * 107))
        reporter.print(
            "\n\nTreatment (Dummy) Coding: Dummy coding compares each level of the categorical variable to a base reference level. The base reference level is the value of the intercept."
        )
        Treatment(reference=0).code_without_intercept(levels)
        mod = ols(
            dep_var
            + " ~ "
            + ind_vars_no_contrast_var
            + " + C("
            + contraststring
            + ", Treatment)",
            data=df_final,
        )
        res = mod.fit()
        reporter.print("With contrast (treatment coding)")
        reporter.print(res.summary())

        # Defining the Simple class
        def _name_levels(prefix, levels):
            return [f"[{prefix}{level}]" for level in levels]

        class Simple:
            def _simple_contrast(self, levels):
                nlevels = len(levels)
                contr = -1.0 / nlevels * np.ones((nlevels, nlevels - 1))
                contr[1:][np.diag_indices(nlevels - 1)] = (nlevels - 1.0) / nlevels
                return contr

            def code_with_intercept(self, levels):
                c = np.column_stack(
                    (np.ones(len(levels)), self._simple_contrast(levels))
                )
                return ContrastMatrix(c, _name_levels("Simp.", levels))

            def code_without_intercept(self, levels):
                c = self._simple_contrast(levels)
                return ContrastMatrix(c, _name_levels("Simp.", levels[:-1]))

        Simple().code_without_intercept(levels)
        mod = ols(
            dep_var
            + " ~ "
            + ind_vars_no_contrast_var
            + " + C("
            + contraststring
            + ", Simple)",
            data=df_final,
        )
        res = mod.fit()
        reporter.print(
            "\n\nSimple Coding: Like Treatment Coding, Simple Coding compares each level to a fixed reference level. However, with simple coding, the intercept is the grand mean of all the levels of the factors."
        )
        reporter.print(res.summary())

        # With contrast (sum/deviation coding)
        Sum().code_without_intercept(levels)
        mod = ols(
            dep_var
            + " ~ "
            + ind_vars_no_contrast_var
            + " + C("
            + contraststring
            + ", Sum)",
            data=df_final,
        )
        res = mod.fit()
        reporter.print(
            "\n\nSum (Deviation) Coding: Sum coding compares the mean of the dependent variable for a given level to the overall mean of the dependent variable over all the levels."
        )
        reporter.print(res.summary())

        # With contrast (backward difference coding)
        Diff().code_without_intercept(levels)
        mod = ols(
            dep_var
            + " ~ "
            + ind_vars_no_contrast_var
            + " + C("
            + contraststring
            + ", Diff)",
            data=df_final,
        )
        res = mod.fit()
        reporter.print(
            "\n\nBackward Difference Coding: In backward difference coding, the mean of the dependent variable for a level is compared with the mean of the dependent variable for the prior level."
        )
        reporter.print(res.summary())

        # With contrast (Helmert coding)
        Helmert().code_without_intercept(levels)
        mod = ols(
            dep_var
            + " ~ "
            + ind_vars_no_contrast_var
            + " + C("
            + contraststring
            + ", Helmert)",
            data=df_final,
        )
        res = mod.fit()
        reporter.print(
            "\n\nHelmert Coding: Our version of Helmert coding is sometimes referred to as Reverse Helmert Coding. The mean of the dependent variable for a level is compared to the mean of the dependent variable over all previous levels. Hence, the name ‘reverse’ being sometimes applied to differentiate from forward Helmert coding."
        )
        reporter.print(res.summary())


def regularizing(reporter):
    # does it say L1, and has the user chosen to go ahead with running the code?
    if r in ("L1", "Lasso", "l1", "lasso") and "y" not in answer.lower():
        # Loop to compute the cross-validation scores
        max_cross_val_alpha = 1
        max_cross_val_score = (
            -1000000000.000
        )  # making it a super negative number initially
        for x in range(1, MAX_ALPHA):
            lassoModel = Lasso(alpha=x, tol=0.0925)
            lassoModel.fit(X, y)
            scores = cross_val_score(lassoModel, X, y, cv=10)
            avg_cross_val_score = mean(scores) * 100
            # figure out which setting of the regularization parameter results in the max likelihood score
            if avg_cross_val_score > max_cross_val_score:
                max_cross_val_alpha = x
                max_cross_val_score = avg_cross_val_score

        # Building and fitting the Lasso Regression Model
        lassoModelChosen = Lasso(alpha=max_cross_val_alpha, tol=0.0925)
        lassoModelChosen.fit(X, y)
        reporter.print("\nLasso regression model:")
        reporter.print(
            f"Alpha with maximum likelihood (range: 1 to {MAX_ALPHA}) = {max_cross_val_alpha}"
        )
        reporter.print(f"Current Model Score = {lassoModelChosen.score(X, y)}")
        index = 0
        reporter.print("\nCoefficients:")
        for var in full_model_variable_list:
            reporter.print(f"{var} \t {lassoModelChosen.coef_[index]}")
            index += 1
        reporter.print(f"Intercept: {lassoModelChosen.intercept_}")
        reporter.print()

    # does it say L2, and has the user chosen to go ahead with running the code?
    if r in ("L2", "Ridge", "l2", "ridge") and "y" not in answer.lower():
        # Loop to compute the different values of cross-validation scores
        max_cross_val_alpha = 1
        max_cross_val_score = (
            -1000000000.000
        )  # making it a super negative number initially
        for x in range(1, MAX_ALPHA):
            ridgeModel = Ridge(alpha=x, tol=0.0925)
            ridgeModel.fit(X, y)
            scores = cross_val_score(ridgeModel, X, y, cv=10)
            avg_cross_val_score = mean(scores) * 100
            # figure out which setting of the regularization parameter results in the max likelihood score
            if avg_cross_val_score > max_cross_val_score:
                max_cross_val_alpha = x
                max_cross_val_score = avg_cross_val_score

        # Building and fitting the Lasso Regression Model
        ridgeModelChosen = Ridge(alpha=max_cross_val_alpha, tol=0.0925)
        ridgeModelChosen.fit(X, y)
        reporter.print("\nRidge regression model:")
        reporter.print(
            f"Alpha with maximum likelihood (range: 1 to {MAX_ALPHA}) = {max_cross_val_alpha}"
        )
        reporter.print(f"Current Model Score = {ridgeModelChosen.score(X, y)}")
        index = 0
        # This numpy_conversion part was necessary because for the ridge model,
        # all the coefficients get stored in a numpy array, and the conversion
        # is necessary to get the coefficients. However, it is only needed if
        # the model has interacting variables.
        numpy_conversion = False
        for var in full_model_variable_list:
            if ("*" in var) or (":" in var):
                numpy_conversion = True
        reporter.print("\nCoefficients:")
        if numpy_conversion:
            coeff_list = ridgeModelChosen.coef_[index].tolist()
            coeff_list.pop(0)
            for var in full_model_variable_list:
                reporter.print(f"{var} \t {coeff_list[index]}")
                index += 1
            reporter.print(f"Intercept: {ridgeModelChosen.intercept_}")
            reporter.print()
        else:
            for var in full_model_variable_list:
                reporter.print(f"{var} \t {ridgeModelChosen.coef_[index]}")
                index += 1
            reporter.print(f"Intercept: {ridgeModelChosen.intercept_}")
            reporter.print()


def opencsv(data):
    """saves a list of lists as a csv and opens"""
    handle, fn = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(
        handle, "w", encoding="utf8", errors="surrogateescape", newline=""
    ) as f:
        writer = csv.writer(f)
        writer.writerows(data)
    return fn


# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    linear_regression()
