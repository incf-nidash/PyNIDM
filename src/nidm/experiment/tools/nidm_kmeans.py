import csv
import os
import sys
import tempfile
import warnings
import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn import preprocessing
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    calinski_harabaz_score,
    davies_bouldin_score,
    silhouette_score,
)
from nidm.experiment.Query import GetProjectsUUID
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
from .utils import Reporter


@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma separated list of NIDM files with full path",
)
@click.option(
    "--var",
    "-variables",
    required=True,
    help='This parameter is for the variables the user would like to complete the k-means algorithm on.\nThe way this looks in the command is python3 nidm_kmeans.py -nl MTdemog_aseg_v2.ttl -v "fs_003343,age*sex,sex,age,group,age*group,bmi"',
)
@click.option(
    "--k_range",
    "-k",
    required=True,
    help="The maximum number of clusters to try. The algorithm will go from 2 to this number to determine the optimal number of clusters.",
)
@click.option(
    "--optimal_cluster_method",
    "-m",
    required=True,
    help="The criterion used to select the optimal partitioning (either Gap Statistic, Elbow Method, Silhouette Coefficient, Calinski-Harabasz Index, or Davies_Bouldin Index).",
)
@click.option(
    "--output_file",
    "-o",
    required=False,
    help="Optional output file (TXT) to store results of the linear regression, contrast, and regularization",
)
def k_means(nidm_file_list, output_file, var, k_range, optimal_cluster_method):
    """
    This function provides a tool to complete k-means clustering on NIDM data.
    """
    global v  # Needed to do this because the code only used the parameters in the first method, meaning I had to move it all to method 1.
    v = (
        var.strip()
    )  # used in data_aggregation, kmenas(), spaces stripped from left and right
    with Reporter(output_file) as reporter:
        global n  # used in data_aggregation()
        n = nidm_file_list
        global k_num
        k_num = int(k_range)
        global cm
        cm = optimal_cluster_method
        data_aggregation(reporter)
        dataparsing(reporter)
        cluster_number()


def data_aggregation(reporter):  # all data from all the files is collected
    """This function provides query support for NIDM graphs."""
    # if there is a CDE file list, seed the CDE cache
    if v:  # ex: age,sex,DX_GROUP
        print("*" * 107)
        command = (
            "pynidm k-means -nl "
            + n
            + ' -variables "'
            + v
            + '" '
            + "-k "
            + str(k_num)
            + " -m "
            + cm
        )

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
            global var_list
            # below, we edit the model so it splits by +,~, or =. However, to help it out in catching everything
            # we replaced ~ and = with a + so that we can still use split. Regex wasn't working.
            var_list = [vv.strip() for vv in v.split(",")]
            # set the dependent variable to the one dependent variable in the model
            global variables  # used in dataparsing()
            variables = ""
            for vr in reversed(var_list):
                if (
                    "*" not in vr
                ):  # removing the star term from the columns we're about to pull from data
                    variables += vr + ","
                else:
                    print(
                        "Interacting variables are not present in clustering models. They will be removed."
                    )
            variables = variables[:-1]
            uri = (
                "/projects/"
                + project[0].toPython().split("/")[-1]
                + "?fields="
                + variables
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

            var_list = variables.split(",")  # makes a list of the independent variables
            numcols = (len(data) - 1) // (
                len(var_list)
            )  # Finds the number of columns in the original dataframe
            condensed_data_holder[count] = [
                [0] * (len(var_list))
            ]  # makes an array 1 row by the number of necessary columns
            for _ in range(
                numcols
            ):  # makes the 2D array big enough to store all of the necessary values in the edited dataset
                condensed_data_holder[count].append([0] * (len(var_list)))
            var_list = [vr.split("/")[-1] for vr in var_list]
            for i, vr in enumerate(var_list):
                # stores the independent variable names in the first row
                condensed_data_holder[count][0][i] = vr
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
                if " " in cdh:
                    condensed_data_holder[count][0][i] = cdh.replace(" ", "_")
            var_list = [vr.split("/")[-1].replace(" ", "_") for vr in var_list]
            count += 1
            if len(not_found_list) > 0:
                print("*" * 107)
                print()
                reporter.print("Your variables were", v)
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
        os.system("pynidm k-means --help")
        sys.exit(1)


def dataparsing(
    reporter,
):  # The data is changed to a format that is usable by the linear regression method
    global condensed_data
    condensed_data = []
    for i in range(0, len(file_list)):
        condensed_data += condensed_data_holder[i]
    global k_num
    if len(condensed_data[0]) <= k_num:
        print(
            "\nThe maximum number of clusters specified is greater than the amount of data present."
        )
        print(
            "The algorithm cannot run with this, so k_num will be reduced to 1 less than the length of the dataset."
        )
        k_num = len(condensed_data) - 1
        print("The k_num value is now:", k_num)
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
    stringvars = []  # starts a list that will store all variables that are not numbers
    for i in range(1, len(condensed_data)):  # goes through each variable
        for j in range(len(condensed_data[0])):  # in the 2D array
            try:  # if the value of the field can be turned into a float (is numerical)
                float(condensed_data[i][j])  # this means it's a number
            except ValueError:  # if it can't be (is a string)
                if (
                    condensed_data[0][j] not in stringvars
                ):  # adds the variable name to the list if it isn't there already
                    stringvars.append(condensed_data[0][j])
    le = (
        preprocessing.LabelEncoder()
    )  # anything involving le shows the encoding of categorical variables
    for sv in stringvars:
        le.fit(obj_df[sv].astype(str))
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
    reporter.print("\n" + ("*" * 107))
    reporter.print("\nModel Results: ")


def cluster_number():
    index = 0
    global levels  # also used in contrasting()
    levels = []
    for i in range(1, len(condensed_data)):
        if condensed_data[i][index] not in levels:
            levels.append(condensed_data[i][index])
    levels = list(range(len(levels)))

    # Beginning of the linear regression
    global X
    # global y
    # Unsure on how to proceed here with interacting variables, since I'm sure dmatrices won't work

    # scaler = MinMaxScaler()
    #
    # for i in range(len(model_list)):
    #     scaler.fit(df_final[[model_list[i]]])
    #     df_final[[model_list[i]]] = scaler.transform(df_final[[model_list[i]]])
    X = df_final[var_list]
    if "ga" in cm.lower():
        print("\n\nGap Statistic")
        gaps = np.zeros((len(range(2, int(k_num)))))
        global resulting_df
        resulting_df = pd.DataFrame({"clusterCount": [], "gap": []})
        global gap_index, k
        for gap_index, k in enumerate(range(2, int(k_num))):
            dispersion_results = np.zeros(3)  # make three random datasets
            for i in range(3):
                random_reference = np.random.random_sample(size=df_final.shape)
                km = KMeans(k)
                km.fit(random_reference)
                dispersion_results[i] = km.inertia_
            km = KMeans(k)
            km.fit(df_final)

            original_sse = km.inertia_
            global gap
            gap = np.log(np.mean(dispersion_results)) - np.log(original_sse)

            gaps[gap_index] = gap
        max_gap = gaps[0]
        optimal_i = 0
        for i in range(1, len(gaps)):
            if gaps[i] > max_gap:
                optimal_i = i
                max_gap = gaps[i]
        optimal_cluster = optimal_i + 2
        print(
            "Optimal number of clusters: " + str(optimal_cluster)
        )  # the optimal number of clusters for gap statistic
        km = KMeans(
            n_clusters=optimal_cluster,
            init="k-means++",
            max_iter=300,
            n_init=10,
            random_state=0,
        )
        labels = km.fit(X).predict(X)
        ax = None or plt.gca()
        X = df_final[var_list].to_numpy()
        ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap="viridis", zorder=2)
        ax.axis("equal")
        plt.show()

    if "el" in cm.lower():
        print("\n\nElbow Method")
        sse = []
        for i in range(2, int(k_num)):
            km = KMeans(
                n_clusters=i, init="k-means++", max_iter=300, n_init=10, random_state=0
            )
            model = km.fit(X)
            sse.append(km.inertia_)
        min_sse = sse[0]
        max_sse = sse[0]
        max_i = 0
        min_i = 0
        for i in range(1, len(sse)):
            if sse[i] >= max_sse:
                max_sse = sse[i]
                max_i = i
            elif sse[i] <= min_sse:
                min_sse = sse[i]
                min_i = i
        p1 = np.array([min_i, sse[min_i]])
        p2 = np.array([max_i, sse[max_i]])
        # the way I am doing the elbow method is as follows:
        # the different sse values form a curve like an L (like an exponential decay)
        # The elbow is the point furthest from a line connecting max and min
        # So I am calculating the distance, and the maximum distance from point to curve shows the optimal point
        # AKA the number of clusters
        dist = []
        for n, s in enumerate(sse):
            norm = np.linalg.norm
            p3 = np.array([n, s])
            dist.append(np.abs(norm(np.cross(p2 - p1, p1 - p3))) / norm(p2 - p1))
        max_dist = dist[0]
        optimal_cluster = 2
        for x in range(1, len(dist)):
            if dist[x] >= max_dist:
                max_dist = dist[x]
                optimal_cluster = x + 2
        print(
            "Optimal number of clusters: " + str(optimal_cluster)
        )  # the optimal number of clusters for elbow method
        km = KMeans(
            n_clusters=optimal_cluster,
            init="k-means++",
            max_iter=300,
            n_init=10,
            random_state=0,
        )
        labels = km.fit(X).predict(X)
        ax = None or plt.gca()
        X = df_final[var_list].to_numpy()
        ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap="viridis", zorder=2)
        ax.axis("equal")
        plt.show()

    if "si" in cm.lower():
        print("Silhouette Score\n")
        ss = []
        for i in range(2, int(k_num)):
            km = KMeans(
                n_clusters=i, init="k-means++", max_iter=300, n_init=10, random_state=0
            )
            cluster_labels = km.fit_predict(X)
            silhouette_avg = silhouette_score(X, cluster_labels)
            ss.append(silhouette_avg)
        optimal_i = 0
        distance_to_one = abs(1 - ss[0])
        for i, s in enumerate(ss):
            if abs(1 - s) <= distance_to_one:
                optimal_i = i
                distance_to_one = abs(1 - s)
        n_clusters = optimal_i + 2
        print(
            "Optimal number of clusters: " + str(n_clusters)
        )  # the optimal number of clusters
        km = KMeans(
            n_clusters=n_clusters,
            init="k-means++",
            max_iter=300,
            n_init=10,
            random_state=0,
        )
        labels = km.fit(X).predict(X)
        ax = None or plt.gca()
        X = df_final[var_list].to_numpy()
        ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap="viridis", zorder=2)
        ax.axis("equal")
        plt.show()

    if "ca" in cm.lower():
        warnings.filterwarnings(
            "ignore", category=FutureWarning
        )  # it is a function for 0.24 but says it is deprecated in 0.23
        print("Calinski-Harabasz Index\n")
        pca = PCA(n_components=2)
        impca = pca.fit_transform(X)
        scores = []

        centers = list(range(2, int(k_num)))
        for center in centers:
            km = KMeans(
                n_clusters=center,
                init="k-means++",
                max_iter=300,
                n_init=10,
                random_state=0,
            ).fit(impca)
            score = calinski_harabaz_score(impca, km.labels_)
            scores.append(score)
        optimal_i = 0
        max_score = scores[0]

        for i in range(1, len(scores)):
            if scores[i] >= max_score:
                optimal_i = i
                max_score = scores[i]
        n_clusters = optimal_i + 2
        print(
            "Optimal number of clusters: " + str(n_clusters)
        )  # the optimal number of clusters
        km = KMeans(
            n_clusters=n_clusters,
            init="k-means++",
            max_iter=300,
            n_init=10,
            random_state=0,
        )
        labels = km.fit(X).predict(X)
        ax = None or plt.gca()
        X = df_final[var_list].to_numpy()
        ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap="viridis", zorder=2)
        ax.axis("equal")
        plt.show()

    if "da" in cm.lower():
        print("Davies-Bouldin Index\n")
        scores = []

        centers = list(range(2, int(k_num)))
        for center in centers:
            km = KMeans(
                n_clusters=center,
                init="k-means++",
                max_iter=300,
                n_init=10,
                random_state=0,
            )
            model = km.fit_predict(X)
            score = davies_bouldin_score(X, model)
            scores.append(score)
        optimal_i = 0
        min_score = scores[0]

        for i in range(1, len(scores)):
            if scores[i] <= min_score:
                optimal_i = i
                min_score = scores[i]
        n_clusters = optimal_i + 2
        print(
            "Optimal number of clusters: " + str(n_clusters)
        )  # the optimal number of clusters
        km = KMeans(
            n_clusters=n_clusters,
            init="k-means++",
            max_iter=300,
            n_init=10,
            random_state=0,
        )
        labels = km.fit(X).predict(X)
        ax = None or plt.gca()
        X = df_final[var_list].to_numpy()
        ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap="viridis", zorder=2)
        ax.axis("equal")
        plt.show()

    if "de" in cm.lower():
        print("Dendrogram")
        # ask for help: how does one do a dendrogram, also without graphing?


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
    k_means()
