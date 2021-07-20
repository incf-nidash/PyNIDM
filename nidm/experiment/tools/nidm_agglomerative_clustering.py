import os
import tempfile
import pandas as pd
import csv
from patsy.highlevel import dmatrices
from nidm.experiment.Query import GetProjectsUUID
import click
from nidm.experiment.tools.click_base import cli
from nidm.experiment.tools.rest import RestParser
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import AgglomerativeClustering
import scipy.cluster.hierarchy as sch
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.cluster import AffinityPropagation
from sklearn import metrics
from sklearn import preprocessing

@cli.command()
@click.option("--nidm_file_list", "-nl", required=True,
              help="A comma separated list of NIDM files with full path")
@click.option("-variables", required=False,
                 help="This parameter is for the variables the user would like to complete the k-means algorithm on.\nThe way this looks in the command is python3 nidm_kmeans.py -nl MTdemog_aseg_v2.ttl -v \"fs_003343,age*sex,sex,age,group,age*group,bmi\"")
@click.option("--output_file", "-o", required=False,
              help="Optional output file (TXT) to store results of the linear regression, contrast, and regularization")
def full_ac(nidm_file_list, output_file, variables):
    global v  # Needed to do this because the code only used the parameters in the first method, meaning I had to move it all to method 1.
    v = variables.strip()  # used in data_aggregation, linreg(), spaces stripped from left and right
    global o  # used in dataparsing()
    o = output_file
    global n  # used in data_aggregation()
    n = nidm_file_list
    data_aggregation()
    dataparsing()
    ac()


def data_aggregation():  # all data from all the files is collected
    """    This function provides query support for NIDM graphs.   """
    # query result list
    results = []
    # if there is a CDE file list, seed the CDE cache
    if v:  # ex: fs_00343 ~ age + sex + group
        print("***********************************************************************************************************")
        command = "python nidm_kmeans.py -nl " + n + " -variables \"" + v + "\" "

        print("Your command was: " + command)
        if (o is not None):
            f = open(o, "w")
            f.write("Your command was " + command)
            f.close()
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
            full_model_variable_list=[]
            global model_list
            model_list = v.split(",")
            for i in range(len(model_list)):  # here, we remove any leading or trailing spaces
                model_list[i] = model_list[i].strip()
            global vars  # used in dataparsing()
            vars = ""
            for i in range(len(model_list) - 1, -1, -1):
                full_model_variable_list.append(model_list[i])  # will be used in the regularization, but we need the full list
                if "*" in model_list[i]:  # removing the star term from the columns we're about to pull from data
                    model_list.pop(i)
                else:
                    vars = vars + model_list[i] + ","
            vars = vars[0:len(vars) - 1]
            uri = "/projects/" + project[0].toPython().split("/")[-1] + "?fields=" + vars
            # get fields output from each file and concatenate
            df_list_holder[count].append(pd.DataFrame(restParser.run([nidm_file], uri)))
            df = pd.concat(df_list_holder[count])
            with tempfile.NamedTemporaryFile(delete=False) as temp:  # turns the dataframe into a temporary csv
                df.to_csv(temp.name + '.csv')
                temp.close()
            data = list(csv.reader(open(temp.name + '.csv')))  # makes the csv a 2D list to make it easier to call the contents of certain cells
            numcols = (len(data) - 1) // (len(model_list))  # Finds the number of columns in the original dataframe
            global condensed_data  # also used in linreg()
            condensed_data_holder[count] = [[0] * (len(model_list))]  # makes an array 1 row by the number of necessary columns
            for i in range(numcols):  # makes the 2D array big enough to store all of the necessary values in the edited dataset
                condensed_data_holder[count].append([0] * (len(model_list)))
            for i in range(len(model_list)):  # stores the independent variable names in the first row
                condensed_data_holder[count][0][i] = model_list[i]
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
                        split_url = condensed_data_holder[count][0][i].split("/")
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
                        elif data[j][aboutcolumn] == split_url[
                            len(split_url) - 1]:  # this is in case the uri only works by querying the part after the last backslash
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
            for j in range(len(temp_list[0]) - 1, 0,-1):  # if the software appends a column with 0 as the heading, it removes this null column
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
            for i in range(len(vars)):
                if " " in vars[i]:
                    vars[i] = vars[i].replace(" ", "_")
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
        os.system("pynidm query --help")
        exit(1)

def dataparsing(): #The data is changed to a format that is usable by the linear regression method
    global condensed_data
    condensed_data = []
    for i in range(0, len(file_list)):
        condensed_data = condensed_data + condensed_data_holder[i]
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
def ac():
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
    #global y
    #Unsure on how to procede here with interacting variables, since I'm sure dmatrices won't work

    scaler = MinMaxScaler()

    for i in range(len(model_list)):
        scaler.fit(df_final[[model_list[i]]])
        df_final[[model_list[i]]] = scaler.transform(df_final[[model_list[i]]])

    X = df_final[model_list] #going to need to find out how to do the correct number of clusters
    dendrogram = sch.dendrogram(sch.linkage(X, method='ward'))
    model = AgglomerativeClustering(n_clusters=5, affinity='euclidean', linkage='ward')
    model.fit(X)
    labels = model.labels_

    plt.scatter(X[labels == 0, 0], X[labels == 0, 1], s=50, marker='o', color='red')
    plt.scatter(X[labels == 1, 0], X[labels == 1, 1], s=50, marker='o', color='blue')
    plt.scatter(X[labels == 2, 0], X[labels == 2, 1], s=50, marker='o', color='green')
    plt.scatter(X[labels == 3, 0], X[labels == 3, 1], s=50, marker='o', color='purple')
    plt.scatter(X[labels == 4, 0], X[labels == 4, 1], s=50, marker='o', color='orange')
    plt.show()

    
    if (o is not None):
        f = open(o, "a")
        f.close()
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
    full_ac()
