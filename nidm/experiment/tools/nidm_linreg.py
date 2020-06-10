import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import OneHotEncoder
from sklearn import metrics
#Before calling this code, make sure to call this: pynidm query -nl MTdemog_aseg_v2.ttl -gf age,sex,fs_003343 -o data.csv
#data.csv is the name of the file you will use here.
dataset = pd.read_csv(input("Enter CSV dataset: "))
dataset.shape() #says number of rows and columns in form of tuple
dataset.describe() #says dataset statistics
dataset.columns()
#might be dataset.columns
dataset.isna().sum()
dataset.head()
if dataset.isnull().any(): #if there are empty spaces in dataset
    dataset = dataset.fillna(method='ffill')
FIELD1 = input('Enter independent variable 1: ')
FIELD2 = input('Enter independent variable 2: ')

FIELD3 = input('Enter dependent variable: ')

field1 = ""
field2 = ""
field3 = ""
filename = input("Name of original .ttl file: ")
with open(filename , 'r') as f:
    lines = f.readlines()
for i in range(len(lines)):
    if FIELD1 in lines[i]:
        for j in range(i,i+8):
            element = field1 + lines[j]
    elif FIELD2 in lines[i]:
        for j in range(i,i+8):
            element = field2 + lines[j]
    elif FIELD3 in lines[i]:
        for j in range(i,i+8):
            element = field3 + lines[j]
if "nidm:valueType xsd:complex" in field1 and "nidm:levels" in field1:
    ohe = OneHotEncoder(sparse=False)
    ohe.fit_transform(dataset[[FIELD1]])
    ohe.categories_()
if "nidm:valueType xsd:complex" in field2 and "nidm:levels" in field2:
    ohe = OneHotEncoder(sparse=False)
    ohe.fit_transform(dataset[[FIELD2]])
    ohe.categories_()
if "nidm:valueType xsd:complex" in field3 and "nidm:levels" in field3:
    ohe = OneHotEncoder(sparse=False)
    ohe.fit_transform(dataset[[FIELD3]])
    ohe.categories_()

X = dataset[[FIELD1, FIELD2]].values
y = dataset[FIELD3].values

#below code puts 80% of data into training set and 20% to the test set
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

#training
regressor = LinearRegression()
regressor.fit(X_train, y_train)

#to see coefficients
coeff_df = pd.DataFrame(regressor.coef_, X.columns, columns = ['Coefficient'])
coeff_df

#prediction
y_pred = regressor.predict(X_test)

#to check the accuracy
df = pd.DataFrame({'Actual': y_test, 'Predicted': y_pred})
df1 = df.head(25)
# Plotting actual versus predicted
df1.plot(kind='bar',figsize=(10,8))
plt.grid(which='major', linestyle='-', linewidth='0.5', color='green')
plt.grid(which='minor', linestyle=':', linewidth='0.5', color='black')
plt.show()

#evaluating performance of the algorithm using MAE, RMSE, RMSE
print('Mean Absolute Error:', metrics.mean_absolute_error(y_test, y_pred))
print('Mean Squared Error:', metrics.mean_squared_error(y_test, y_pred))
print('Root Mean Squared Error:', np.sqrt(metrics.mean_squared_error(y_test, y_pred)))