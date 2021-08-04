"""My thought: Don't ask the user which method to use to decide cluster number. Pick the version that has the smallest
number of clusters. There are so many versions that it's not going to help the user to decide. Also, each method of clustering
has different methods to determine the optimal number of clusters, so it's not generalizable."""
import os
import tempfile
import pandas as pd
import csv
from nidm.experiment.Query import GetProjectsUUID
import click
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
import numpy as np
import matplotlib.pyplot as plt
from itertools import cycle
from sklearn.cluster import AffinityPropagation
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn import preprocessing
from sklearn.metrics import davies_bouldin_score
from sklearn.metrics import calinski_harabaz_score
from sklearn.mixture import GaussianMixture
from sklearn.cluster import AgglomerativeClustering
from sklearn import metrics

@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("--var","-variables", required=True,
                 help="This parameter is for the variables the user would like to complete the k-means algorithm on.\nThe way this looks in the command is pynidm cluster -nl MTdemog_aseg_v2.ttl -v \"fs_003343,age*sex,sex,age,group,age*group,bmi\" -max 10 -min 2")
@click.option("--cluster_num_maximum", "-max", required=True,
              help="The maxiumum number of clusters to try. The algorithm will go from min to this number to determine the optimal number of clusters. By default, it is the length of the dataset.")
@click.option("--cluster_num_minimum", "-min", required=True,
              help="The minimum number of clusters to try. The algorithm will go from here to the maximum to determine the optimal number of clusters. By default, it is 2.")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (TXT) to store results of the linear regression, contrast, and regularization")

def cluster(nidm_file_list, output_file, var, cluster_num_minimum, cluster_num_maximum):
    """
            This function provides a tool to complete k-means clustering on NIDM data.
            """
    global v  # Needed to do this because the code only used the parameters in the first method, meaning I had to move it all to method 1.
    v = var.strip()  # used in data_aggregation, kmenas(), spaces stripped from left and right
    global o  # used in dataparsing()
    o = output_file
    global n  # used in data_aggregation()
    n = nidm_file_list
    global min
    if cluster_num_minimum:
        min = int(cluster_num_minimum)
    else:
        min = 2
    global max
    if cluster_num_maximum:
        max = int(cluster_num_maximum)
    else:
        max = None


    data_aggregation()
    dataparsing()
    k_means()
    gmm()
    affinity_propagation()
    agglomerative_clustering()

def data_aggregation():  # all data from all the files is collected
    """    This function provides query support for NIDM graphs.   """
    # query result list
    results = []
    # if there is a CDE file list, seed the CDE cache
    if v:  #ex: age,sex,DX_GROUP
        print("***********************************************************************************************************")
        command = "pynidm cluster -nl " + n + " -variables \"" + v + "\" " + "-min " + str(min) + " -max " + str(max)

        print("Your command was: " + command)
        if (o is not None):
            f = open(o, "w")
            f.write("Your command was " + command)
            f.close()
        verbosity=0
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
            var_list = v.split(",")
            for i in range(len(var_list)):  # here, we remove any leading or trailing spaces
                var_list[i] = var_list[i].strip()
            # set the dependent variable to the one dependent variable in the model
            global vars  # used in dataparsing()
            vars = ""
            for i in range(len(var_list) - 1, -1, -1):
                if not "*" in var_list[i]:  # removing the star term from the columns we're about to pull from data
                    vars = vars + var_list[i] + ","
                else:
                    print("Interacting variables are not present in clustering models. They will be removed.")
            vars = vars[0:len(vars) - 1]
            uri = "/projects/" + project[0].toPython().split("/")[-1] + "?fields=" + vars
            # get fields output from each file and concatenate
            df_list_holder[count].append(pd.DataFrame(restParser.run([nidm_file], uri)))
            # global dep_var
            df = pd.concat(df_list_holder[count])
            with tempfile.NamedTemporaryFile(delete=False) as temp:  # turns the dataframe into a temporary csv
                df.to_csv(temp.name + '.csv')
                temp.close()
            data = list(csv.reader(open(
                temp.name + '.csv')))  # makes the csv a 2D list to make it easier to call the contents of certain cells

            var_list = vars.split(",")  # makes a list of the independent variables
            numcols = (len(data) - 1) // (
                    len(var_list))  # Finds the number of columns in the original dataframe
            global condensed_data  # also used in linreg()
            condensed_data_holder[count] = [
                [0] * (len(var_list))]  # makes an array 1 row by the number of necessary columns
            for i in range(
                    numcols):  # makes the 2D array big enough to store all of the necessary values in the edited dataset
                condensed_data_holder[count].append([0] * (len(var_list)))
            for m in range(0, len(var_list)):
                end_url = var_list[m].split("/")
                if "/" in var_list[m]:
                    var_list[m] = end_url[len(end_url) - 1]
            for i in range(len(var_list)):  # stores the independent variable names in the first row
                condensed_data_holder[count][0][i] = var_list[i]
            numrows = 1  # begins at the first row to add data
            fieldcolumn = 0  # the column the variable name is in in the original dataset
            valuecolumn = 0  # the column the value is in in the original dataset
            datacolumn = 0  # if it is identified by the dataElement name instead of the field's name
            not_found_list = []
            for i in range(len(data[0])):
                if data[0][i] == 'sourceVariable':  # finds the column where the variable names are
                    fieldcolumn = i
                elif data[0][i] == 'source_variable':  # finds the column where the variable names are
                    fieldcolumn = i
                elif data[0][i] == 'isAbout':
                    aboutcolumn = i
                elif data[0][i] == 'label':
                    namecolumn = i  # finds the column where the variable names are
                elif data[0][i] == 'value':
                    valuecolumn = i  # finds the column where the values are
                elif data[0][i] == 'dataElement':  # finds the column where the data element is if necessary
                    datacolumn = i
            for i in range(
                    len(condensed_data_holder[count][
                            0])):  # starts iterating through the dataset, looking for the name in that
                for j in range(1, len(data)):  # column, so it can append the values under the proper variables
                    try:
                        if data[j][fieldcolumn] == condensed_data_holder[count][0][
                            i]:  # in the dataframe, the name is in column 3
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn]  # in the dataframe, the value is in column 2
                            numrows = numrows + 1  # moves on to the next row to add the proper values
                        elif data[j][aboutcolumn] == condensed_data_holder[count][0][
                            i]:
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn]  # in the dataframe, the value is in column 2
                            numrows = numrows + 1  # moves on to the next row to add the proper values
                        elif condensed_data_holder[count][0][
                            i] in data[j][
                            aboutcolumn]:  # this is in case the uri only works by querying the part after the last backslash
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn]  # in the dataframe, the value is in column 2
                            numrows = numrows + 1  # moves on to the next row to add the proper values
                        elif data[j][namecolumn] == condensed_data_holder[count][0][
                            i]:  # in the dataframe, the name is in column 12
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn]  # in the dataframe, the value is in column 2
                            numrows = numrows + 1  # moves on to the next row to add the proper values
                        elif condensed_data_holder[count][0][i] == data[j][
                            datacolumn]:  # in the dataframe, the name is in column 9
                            condensed_data_holder[count][numrows][i] = data[j][
                                valuecolumn]  # in the dataframe, the value is in column 2
                            numrows = numrows + 1  # moves on to the next row to add the proper values
                    except IndexError:
                        numrows = numrows + 1
                numrows = 1  # resets to the first row for the next variable
            temp_list = condensed_data_holder[count]
            for j in range(len(temp_list[0]) - 1, 0,
                           -1):  # if the software appends a column with 0 as the heading, it removes this null column
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
            for i in range(len(condensed_data_holder[count][0])):
                if " " in condensed_data_holder[count][0][i]:
                    condensed_data_holder[count][0][i] = condensed_data_holder[count][0][i].replace(" ", "_")
            for i in range(len(var_list)):
                if "/" in var_list[i]:
                    splitted = var_list[i].split("/")
                    var_list[i] = splitted[len(splitted) - 1]
                if " " in var_list[i]:
                    var_list[i] = var_list[i].replace(" ", "_")
            count = count + 1
            if len(not_found_list) > 0:
                print(
                    "***********************************************************************************************************")
                print()
                print("Your variables were " + v)
                print()
                print(
                    "The following variables were not found in " + nidm_file + ". The model cannot run because this will skew the data. Try checking your spelling or use nidm_query.py to see other possible variables.")
                if (o is not None):
                    f = open(o, "a")
                    f.write("Your variables were " + v)
                    f.write(
                        "The following variables were not found in " + nidm_file + ". The model cannot run because this will skew the data. Try checking your spelling or use nidm_query.py to see other possible variables.")
                    f.close()
                for i in range(0, len(not_found_list)):
                    print(str(i + 1) + ". " + not_found_list[i])
                    if (o is not None):
                        f = open(o, "a")
                        f.write(str(i + 1) + ". " + not_found_list[i])
                        f.close()
                for j in range(len(not_found_list) - 1, 0, -1):
                    not_found_list.pop(j)
                not_found_count = not_found_count + 1
                print()
        if not_found_count > 0:
            exit(1)


    else:
        print("ERROR: No query parameter provided.  See help:")
        print()
        os.system("pynidm k-means --help")
        exit(1)

def dataparsing(): #The data is changed to a format that is usable by the linear regression method
    global condensed_data
    condensed_data = []
    for i in range(0, len(file_list)):
        condensed_data = condensed_data + condensed_data_holder[i]
    global max
    if not (max == None):
        if len(condensed_data[0]) <= max:
            print("\nThe maximum number of clusters specified is greater than the amount of data present.")
            print("The algorithm cannot run with this, so the cluster number range will be reduced to 1 less than the length of the dataset.")
            max = len(condensed_data) - 1
            print("The cluster range value is now: " + str(max))
    else:
        max = len(condensed_data) - 1
    x = pd.read_csv(opencsv(condensed_data))  # changes the dataframe to a csv to make it easier to work with
    x.head()  # prints what the csv looks like
    x.dtypes  # checks data format
    obj_df = x.select_dtypes  # puts all the variables in a dataset
    x.shape  # says number of rows and columns in form of tuple
    x.describe()  # says dataset statistics
    obj_df = x.select_dtypes(
        include=['object']).copy()  # takes everything that is an object (not float or int) and puts it in a new dataset
    obj_df.head()  # prints the new dataset
    int_df = x.select_dtypes(include=['int64']).copy()  # takes everything that is an int and puts it in a new dataset
    float_df = x.select_dtypes(
        include=['float64']).copy()  # takes everything that is a float and puts it in a new dataset
    df_int_float = pd.concat([float_df, int_df], axis=1)
    stringvars = []  # starts a list that will store all variables that are not numbers
    for i in range(1, len(condensed_data)):  # goes through each variable
        for j in range(len(condensed_data[0])):  # in the 2D array
            try:  # if the value of the field can be turned into a float (is numerical)
                float(condensed_data[i][j])  # this means it's a number
            except ValueError:  # if it can't be (is a string)
                if condensed_data[0][
                    j] not in stringvars:  # adds the variable name to the list if it isn't there already
                    stringvars.append(condensed_data[0][j])
    le = preprocessing.LabelEncoder()  # anything involving le shows the encoding of categorical variables
    for i in range(len(stringvars)):
        le.fit(obj_df[stringvars[i]].astype(str))
    obj_df_trf = obj_df.astype(str).apply(le.fit_transform)  # transforms the categorical variables into numbers.
    global df_final  # also used in linreg()
    if not obj_df_trf.empty:
        df_final = pd.concat([df_int_float, obj_df_trf], axis=1)  # join_axes=[df_int_float.index])
    else:
        df_final = df_int_float
    df_final.head()  # shows the final dataset with all the encoding
    print(df_final)  # prints the final dataset
    print()
    print("***********************************************************************************************************")
    print()
    if (o is not None):
        f = open(o, "a")
        f.write(df_final.to_string(header=True, index=True))
        f.write(
            "\n\n***********************************************************************************************************")
        f.write("\n\nModel Results: ")
        f.close()
    index = 0
    global levels  # also used in contrasting()
    levels = []
    for i in range(1, len(condensed_data)):
        if condensed_data[i][index] not in levels:
            levels.append(condensed_data[i][index])
    for i in range(len(levels)):
        levels[i] = i

    # Beginning of the linear regression
    global X
    # global y
    # Unsure on how to procede here with interacting variables, since I'm sure dmatrices won't work

    """scaler = MinMaxScaler()

    for i in range(len(model_list)):
        scaler.fit(df_final[[model_list[i]]])
        df_final[[model_list[i]]] = scaler.transform(df_final[[model_list[i]]])"""
    X = df_final[var_list]

def k_means():
    global X

    """scaler = MinMaxScaler()

    for i in range(len(model_list)):
        scaler.fit(df_final[[model_list[i]]])
        df_final[[model_list[i]]] = scaler.transform(df_final[[model_list[i]]])"""
    X = df_final[var_list]

    cluster_list = []
    print("\n\nK-Means: Elbow Method")
    sse = []
    for i in range(min,max):
        km = KMeans(n_clusters=i, init='k-means++', max_iter=300, n_init=10, random_state=0)
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
    #the way I am doing the elbow method is as follows:
    #the different sse values form a curve like an L (like an exponential decay)
    #The elbow is the point furthest from a line connecting max and min
    #So I am calculating the distance, and the maximum distance from point to curve shows the optimal point
    #AKA the number of clusters
    dist = []
    for n in range(0,len(sse)):
        norm = np.linalg.norm
        p3 = np.array([n,sse[n]])
        dist.append(np.abs(norm(np.cross(p2-p1, p1-p3)))/norm(p2-p1))
    max_dist = dist[0]
    optimal_cluster = 2
    for x in range(1,len(dist)):
        if dist[x]>=max_dist:
            max_dist = dist[x]
            optimal_cluster = x+2
    cluster_list.append(optimal_cluster)
    print("Optimal number of clusters by elbow method for k-means: " + str(optimal_cluster)) #the optimal number of clusters for elbow method

    print("\n\n K-Means: Silhouette Score\n")
    ss = []
    for i in range(min,max):
        km = KMeans(n_clusters=i, init='k-means++', max_iter=300, n_init=10, random_state=0)
        cluster_labels = km.fit_predict(X)
        silhouette_avg = silhouette_score(X, cluster_labels)
        ss.append(silhouette_avg)
    optimal_i = 0
    distance_to_one = abs(1 - ss[0])
    for i in range(0, len(ss)):
        if abs(1 - ss[i]) <= distance_to_one:
            optimal_i = i
            distance_to_one = abs(1 - ss[i])
    n_clusters = optimal_i + 2
    cluster_list.append(n_clusters)
    print("\nOptimal number of clusters for K-Means by Silhouette Score: " + str(n_clusters)) #the optimal number of clusters


    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning) #it is a function for 0.24 but says it is depracated in 0.23
    print("\n\nK-Means: Calinski-Harabasz Index\n")
    pca = PCA(n_components=2)
    impca = pca.fit_transform(X)
    scores = []

    centers = list(range(min,max))
    for center in centers:
        km = KMeans(n_clusters=center, init='k-means++', max_iter=300, n_init=10, random_state=0).fit(impca)
        score = calinski_harabaz_score(impca,km.labels_)
        scores.append(score)
    optimal_i = 0
    max_score = scores[0]

    for i in range(1, len(scores)):
        if scores[i] >= max_score:
            optimal_i = i
            max_score = scores[i]
    n_clusters = optimal_i + 2
    cluster_list.append(n_clusters)
    print("Optimal number of clusters for K-Means by Calinski-Harabaz Index: " + str(n_clusters)) #the optimal number of clusters


    print("\n\nK-Means: Davies-Bouldin Index\n")
    scores = []

    centers = list(range(min,max))
    for center in centers:
        km = KMeans(n_clusters=center, init='k-means++', max_iter=300, n_init=10, random_state=0)
        model = km.fit_predict(X)
        score = davies_bouldin_score(X, model)
        scores.append(score)
    optimal_i = 0
    min_score = scores[0]

    for i in range(1,len(scores)):
        if scores[i]<=min_score:
            optimal_i = i
            min_score = scores[i]
    n_clusters = optimal_i + 2
    cluster_list.append(n_clusters)
    print("Optimal number of clusters for K-Means by Davies-Bouldin Index: " + str(n_clusters)) #the optimal number of clusters

    method_list = ['Elbow Method','Silhouette Score','Calinski-Harabasz Index','Davies-Bouldin Index']
    min_num_clusters = cluster_list[0]
    index = 0
    for i in range(1,len(cluster_list)):
        if cluster_list[i]<=min_num_clusters:
            min_num_clusters = cluster_list[i]
            index = i

    print("The minimum number of clusters is " + str(min_num_clusters) + " produced by " + method_list[index])

    km = KMeans(n_clusters=min_num_clusters, init='k-means++', max_iter=300, n_init=10, random_state=0)
    labels = km.fit(X).predict(X)
    ax = None or plt.gca()
    X = df_final[var_list].to_numpy()
    ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap='viridis', zorder=2)
    ax.axis('equal')
    plt.show()

def gmm():
    global X
    cluster_list = []
    print("\n\nGMM: Silhouette Score")
    ss = []

    for i in range(min,max):
        model = GaussianMixture(n_components=i, init_params='kmeans')
        cluster_labels = model.fit_predict(X)
        silhouette_avg = silhouette_score(X, cluster_labels)
        ss.append(silhouette_avg)
    optimal_i = 0
    distance_to_one = abs(1-ss[0])
    for i in range(0,len(ss)):
        if abs(1-ss[i]) <= distance_to_one:
            optimal_i = i
            distance_to_one = abs(1-ss[i])

    n_clusters = optimal_i + 2
    cluster_list.append(n_clusters)
    print("\nOptimal number of clusters for GMM by Silhouette Score: " + str(n_clusters)) #optimal number of clusters

    print("\n\nGMM: AIC\n")
    aic = []
    for i in range(min,max):
        model = GaussianMixture(n_components=i, init_params='kmeans')
        model.fit(X)
        aic.append(model.bic(X))
    min_aic = aic[0]
    min_i = 0
    for i in range(1, len(aic)):
        if aic[i] <= min_aic:
            min_aic = aic[i]
            min_i = i
    n_clusters = min_i +2
    cluster_list.append(n_clusters)
    print("Optimal number of clusters for GMM by AIC: " + str(n_clusters)) #optimal number of clusters, minimizing aic

    print("\n\nGMM: BIC\n")
    bic = []
    for i in range(min,max):
        model = GaussianMixture(n_components=i, init_params='kmeans')
        model.fit(X)
        bic.append(model.bic(X))
    min_bic = bic[0]
    min_i = 0
    for i in range(1, len(bic)):
        if bic[i] <= min_bic:
            min_bic = bic[i]
            min_i = i
    n_clusters = min_i + 2
    cluster_list.append(n_clusters)
    print("Optimal number of clusters for GMM by BIC: " + str(n_clusters)) #optimal number of clusters

    method_list = ["Silhouette Score","AIC","BIC"]
    min_num_clusters = cluster_list[0]
    index = 0
    for i in range(1, len(cluster_list)):
        if cluster_list[i] <= min_num_clusters:
            min_num_clusters = cluster_list[i]
            index = i

    print("The minimum number of clusters is " + str(min_num_clusters) + " produced by " + method_list[index])

    gmm = GaussianMixture(n_components=min_num_clusters).fit(X)
    labels = gmm.fit(X).predict(X)
    ax = None or plt.gca()
    X = df_final[var_list].to_numpy()
    ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap='viridis', zorder=2)
    ax.axis('equal')
    plt.show()

def affinity_propagation():
    global X
    print("\n\nAffinity Propagation")
    af = AffinityPropagation(preference=-50).fit(X)
    cluster_centers_indices = af.cluster_centers_indices_
    labels = af.labels_
    n_clusters = len(cluster_centers_indices)
    plt.close('all')
    plt.figure(1)
    plt.clf()

    colors = cycle('bgrcmykbgrcmykbgrcmykbgrcmyk')

    for k, col in zip(range(n_clusters), colors):
        class_members = labels == k
        cluster_center = X[cluster_centers_indices[k]]
        plt.plot(X[class_members, 0], X[class_members, 1], col + '.')
        plt.plot(cluster_center[0], cluster_center[1], 'o',
                 markerfacecolor=col, markeredgecolor='k',
                 markersize=14)

        for x in X[class_members]:
            plt.plot([cluster_center[0], x[0]],
                     [cluster_center[1], x[1]], col)

    plt.title('Estimated number of clusters: % d' % n_clusters)
    plt.show()

    if (o is not None):
        f = open(o, "a")
        f.close()

def agglomerative_clustering(): #Fowlkes-Mallows and Adjusted Rand Score are not possible since we don't have existing labels we're training on.
    global X
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning) #it is a function for 0.24 but says it is depracated in 0.23
    print("\n\nAgglomerative Clustering: Calinski-Harabasz Index\n")
    pca = PCA(n_components=2)
    impca = pca.fit_transform(X)

    comp_cluster_list = []
    avg_cluster_list = []
    ward_cluster_list = []

    agg_comp_scores = []
    agg_avg_scores = []
    agg_ward_scores = []

    centers = list(range(min,max))
    for center in centers:
        agg_comp = AgglomerativeClustering(linkage='complete', n_clusters=center)
        labels_comp = agg_comp.labels_
        agg_comp_scores.append(metrics.calinski_harabasz_score(X, labels_comp))

        agg_ward = AgglomerativeClustering(linkage='ward', n_clusters=center)
        labels_ward = agg_ward.labels_
        agg_ward_scores.append(metrics.calinski_harabasz_score(X, labels_ward))

        agg_avg = AgglomerativeClustering(linkage='average', n_clusters=center)
        labels_avg = agg_avg.labels_
        agg_avg_scores.append(metrics.calinski_harabasz_score(X, labels_avg))

    optimal_comp_i = 0
    max_score = agg_comp_scores[0]

    for i in range(1, len(agg_comp_scores)):
        if agg_comp_scores[i] >= max_score:
            optimal_comp_i = i
            max_score = agg_comp_scores[i]
    n_comp_clusters = optimal_comp_i + 2
    comp_cluster_list.append(n_comp_clusters)
    print("Optimal number of clusters for agglomerative complete clustering by Calinski-Harabasz Index: " + str(n_comp_clusters)) #the optimal number of clusters


    optimal_ward_i = 0
    max_score = agg_ward_scores[0]

    for i in range(1, len(agg_ward_scores)):
        if agg_ward_scores[i] >= max_score:
            optimal_ward_i = i
            max_score = agg_ward_scores[i]
    n_ward_clusters = optimal_ward_i + 2
    ward_cluster_list.append(n_ward_clusters)
    print("Optimal number of clusters for agglomerative ward clustering by Calinski-Harabasz Index: " + str(
            n_ward_clusters))  # the optimal number of clusters

    optimal_avg_i = 0
    max_score = agg_avg_scores[0]

    for i in range(1, len(agg_avg_scores)):
        if agg_avg_scores[i] >= max_score:
            optimal_avg_i = i
            max_score = agg_avg_scores[i]
    n_avg_clusters = optimal_avg_i + 2
    avg_cluster_list.append(n_avg_clusters)
    print("Optimal number of clusters for agglomerative average clustering by Calinski-Harabasz Index: " + str(
            n_avg_clusters))  # the optimal number of clusters


    print("\n\nAgglomerative Clustering: Silhoette Score\n")
    pca = PCA(n_components=2)
    impca = pca.fit_transform(X)

    agg_comp_scores = []
    agg_avg_scores = []
    agg_ward_scores = []

    centers = list(range(min,max))
    for center in centers:
        agg_comp = AgglomerativeClustering(linkage='complete', n_clusters=center)
        labels_comp = agg_comp.labels_
        agg_comp_scores.append(metrics.calinski_harabasz_score(X, labels_comp))

        agg_ward = AgglomerativeClustering(linkage='ward', n_clusters=center)
        labels_ward = agg_ward.labels_
        agg_ward_scores.append(metrics.calinski_harabasz_score(X, labels_ward))

        agg_avg = AgglomerativeClustering(linkage='average', n_clusters=center)
        labels_avg = agg_avg.labels_
        agg_avg_scores.append(metrics.calinski_harabasz_score(X, labels_avg))

    optimal_comp_i = 0

    distance_to_one = abs(1 - agg_comp_scores[0])
    for i in range(0, len(agg_comp_scores)):
        if abs(1 - agg_comp_scores[i]) <= distance_to_one:
            optimal_comp_i = i
            distance_to_one = abs(1 - agg_comp_scores[i])
    n_comp_clusters = optimal_comp_i + 2
    comp_cluster_list.append(n_comp_clusters)
    print("Optimal number of clusters for agglomerative complete clustering by Silhouette Score: " + str(n_comp_clusters)) #the optimal number of clusters

    optimal_ward_i = 0

    distance_to_one = abs(1 - agg_ward_scores[0])
    for i in range(0, len(agg_ward_scores)):
        if abs(1 - agg_ward_scores[i]) <= distance_to_one:
            optimal_ward_i = i
            distance_to_one = abs(1 - agg_ward_scores[i])
    n_ward_clusters = optimal_ward_i + 2
    ward_cluster_list.append(n_ward_clusters)
    print("Optimal number of clusters for agglomerative ward clustering by Silhouette Score: " + str(
            n_ward_clusters))  # the optimal number of clusters

    optimal_avg_i = 0

    distance_to_one = abs(1 - agg_avg_scores[0])
    for i in range(0, len(agg_avg_scores)):
        if abs(1 - agg_avg_scores[i]) <= distance_to_one:
            optimal_avg_i = i
            distance_to_one = abs(1 - agg_avg_scores[i])
    n_avg_clusters = optimal_avg_i + 2
    avg_cluster_list.append(n_avg_clusters)
    print("Optimal number of clusters for agglomerative average clustering: " + str(
            n_avg_clusters))  # the optimal number of clusters

    method_list = ['Calinski-Harabasz Index', 'Silhouette Score']
    min_num_comp_clusters = comp_cluster_list[0]
    index = 0
    for i in range(1, len(comp_cluster_list)):
        if comp_cluster_list[i] <= min_num_comp_clusters:
            min_num_comp_clusters = comp_cluster_list[i]
            index = i

    print("The minimum number of clusters for agglomerative complete clustering is " + str(min_num_comp_clusters) + " produced by " + method_list[index])
    agg_comp = AgglomerativeClustering(linkage='complete', n_clusters=min_num_comp_clusters)
    as_comp = agg_comp.fit_predict(X)
    plt.scatter(X[:, 0], X[:, 1], c=as_comp, s=10)

    min_num_ward_clusters = ward_cluster_list[0]
    index = 0
    for i in range(1, len(ward_cluster_list)):
        if ward_cluster_list[i] <= min_num_ward_clusters:
            min_num_ward_clusters = ward_cluster_list[i]
            index = i

    print("The minimum number of clusters for agglomerative ward clustering is " + str(
        min_num_ward_clusters) + " produced by " + method_list[index])
    agg_ward = AgglomerativeClustering(linkage='ward', n_clusters=min_num_ward_clusters)
    as_ward = agg_ward.fit_predict(X)
    plt.scatter(X[:, 0], X[:, 1], c=as_ward, s=10)

    min_num_avg_clusters = avg_cluster_list[0]
    index = 0
    for i in range(1, len(avg_cluster_list)):
        if avg_cluster_list[i] <= min_num_avg_clusters:
            min_num_avg_clusters = avg_cluster_list[i]
            index = i

    print("The minimum number of clusters for agglomerative average clustering is " + str(
        min_num_avg_clusters) + " produced by " + method_list[index])
    agg_avg = AgglomerativeClustering(linkage='average', n_clusters=min_num_avg_clusters)
    as_avg = agg_avg.fit_predict(X)
    plt.scatter(X[:, 0], X[:, 1], c=as_avg, s=10)


def opencsv(data):
    """saves a list of lists as a csv and opens"""
    import tempfile
    import os
    import csv
    handle, fn = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(handle,"w", encoding='utf8',errors='surrogateescape',newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    return fn

# it can be used calling the script `python nidm_query.py -nl ... -q ..
if __name__ == "__main__":
    cluster()
