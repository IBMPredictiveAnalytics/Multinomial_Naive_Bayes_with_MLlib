script_details = ("naivebayes_score.py",0.5)

# COMMON SECTION VERSION 0.7
from pyspark.context import SparkContext
from pyspark.sql.context import SQLContext
from pyspark import AccumulatorParam
from pyspark.mllib.regression import LabeledPoint
from pyspark.mllib.linalg import DenseVector
import time
import sys
import os

# DataModelAnalyzer is a scalable spark accumulator for collecting the data model metadata from a dataframe
# the data model tracks the categories (for string fields) and min/max (for numeric fields)

# DataModelTools is a class which packages up useful utilities for collecting data model information (using DataModelAnalyzer)
# and converting from DataFrames to RDD[LabelledPoint] and RDD[DenseVector] typically used in MLlib

# COMMON BEGIN
class DataModelAnalyzer(AccumulatorParam):

    def zero(self, val):
        return val

    def minNonNull(self,a,b):
        if a == None:
            return b
        if b == None:
            return a
        return min(a,b)

    def addInPlace(self, meta1, meta2):
        for (cname,ctype) in schema:
            if ctype == "string":
                meta1[cname] = list(set(meta1[cname]+meta2[cname]))
            else:
                meta1[cname] = { "max":max(meta1[cname]["max"],meta2[cname]["max"]), "min":self.minNonNull(meta1[cname]["min"],meta2[cname]["min"])}
        return meta1

    @staticmethod
    def process(row):
        val = {}
        col = 0
        for (cname,ctype) in schema:
            if ctype == 'string':
                val[cname] = [row[col]]
            else:
                val[cname] = {"min":row[col],"max":row[col]}
            col += 1
        return val

    @staticmethod
    def empty(schema):
        val = {}
        for (cname,ctype) in schema:
            if ctype == 'string':
                val[cname] = []
            else:
                val[cname] = {"min":None,"max":None}
        return val


class DataModelTools(object):

    DATA_TYPES_KEY = "____data_types____"

    def __init__(self,dm=None):
        self.dm = dm

    def computeDataModel(self,df):
        global schema
        schema = df.dtypes[:]
        global dmt_acc
        dmt_acc = sc.accumulator(DataModelAnalyzer.empty(schema), DataModelAnalyzer())

        def sum(x):
            # print(str(x))
            global dmt_acc
            def process(row):
                val = {}
                col = 0
                for (cname,ctype) in schema:
                    if ctype == 'string':
                        val[cname] = [row[col]]
                    else:
                        val[cname] = {"min":row[col],"max":row[col]}
                    col += 1
                return val
            dmt_acc += process(x)
        df.foreach(sum)
        self.dm = dmt_acc.value
        data_types = {}
        for (name,type) in schema:
            data_types[name] = type
        self.dm[DataModelTools.DATA_TYPES_KEY] = data_types
        return self.dm

    def extractLabelledPoint(self,df,target,predictors,setToFlag=None):
        return self.encode(df,target,predictors,setToFlag)

    def extractDenseVector(self,df,predictors,setToFlag=None):
        return self.encode(df,None,predictors,setToFlag)

    def encode(self,df,target,predictors,setToFlag):
        if not self.dm:
            self.computeDataModel(df)
        schema = df.dtypes[:]
        lookup = {}
        for i in range(0,len(schema)):
            lookup[schema[i][0]] = i

        target_index = -1
        if target:
            target_index = lookup[target]
        dm = self.dm

        def mapFn(row):
            pvals = []
            for predictor in predictors:
                predictor_index = lookup[predictor]
                if isinstance(dm[predictor],list):
                    try:
                        encoded_val = dm[predictor].index(row[predictor_index])
                        if setToFlag == None:
                            pvals.append(encoded_val)
                        else:
                            flags = [0.0]*len(dm[predictor])
                            flags[encoded_val]=setToFlag
                            pvals += flags
                    except ValueError:
                        if setToFlag == None:
                            pvals.append(None)
                        else:
                            pvals += [0.0]*len(dm[predictor])
                else:
                    pval = row[predictor_index]
                    # if pval == None:
                    #    pval_min = dm[predictor]["min"]
                    #    pval_max = dm[predictor]["max"]
                    #    pval=pval_min+(pval_max - pval_min)*0.5
                    pvals.append(pval)
            dv = DenseVector(pvals)
            if target_index == -1:
                return (row,dv)
            tval = row[target_index]
            if isinstance(dm[target],list): # target is categorical
                try:
                    tval = dm[target].index(tval)
                except ValueError:
                    tval = None
            return (row,LabeledPoint(tval,dv))

        return df.map(mapFn)

    def getCategoricalFeatureInfo(self,df,predictors):
        if not self.dm:
            self.computeDataModel(df)
        info = {}
        index = 0
        for predictor in predictors:
            if isinstance(self.dm[predictor],list):
                info[index] = len(self.dm[predictor])
            index += 1
        return info

    @staticmethod
    def checkTargetForModelType(dm,target,model_type):
        if model_type == "classification" and not isinstance(dm[target],list):
            raise Exception("Classification target should have string values")
        elif model_type == "regression" and isinstance(dm[target],list):
            raise Exception("Regression target should have numeric values")

    @staticmethod
    def checkPredictors(dm,predictors,df):
        schema = {}
        for (name,type) in df.dtypes:
            schema[name] = type
        for predictor in predictors:
            if predictor not in schema:
                raise Exception("Predictor %s is missing from input data"%(predictor))
            applytype = schema[predictor]
            buildtype = dm[DataModelTools.DATA_TYPES_KEY][predictor]
            if applytype != buildtype:
                raise Exception("Type for predictor %s changed, was %s at model build time, now %s"%(predictor,buildtype,applytype))

    @staticmethod
    def getFieldInformation(dm,field):
        l = []
        l.append(("Data type",dm[DataModelTools.DATA_TYPES_KEY][field]))
        if isinstance(dm[field],list):
            l.append(("Categories",",".join(dm[field])))
        else:
            l.append(("Range",",".join([str(dm[field]["min"]),str(dm[field]["max"])])))
        return l



class ModelBuildReporter(object):

    def __init__(self,sc):
        self.sc = sc
        self.start_time = time.time()
        self.indent = 0

    def report(self,training_record_count,partition_count,predictors,datamodel,target=None,model_type=None,settings=[]):
        end_time = time.time()
        items = []
        if model_type:
            items.append(("Model Type",model_type))
        items += settings
        items.append(("Environment","",[("Spark Version",self.sc.version),("Spark User",self.sc.sparkUser()),("Python",sys.version.replace(os.linesep,"")),("Script",str(script_details))]))
        training_details = [("Records",training_record_count),("Partitions",partition_count),("Elapsed Time (sec)",int(end_time-self.start_time))]
        try:
            applicationId = sc.applicationId
            training_details.append(("Application Id",applicationId))
        except:
            pass
        items.append(("Training Details","",training_details))

        if target:
            items.append(("Target Field",target,DataModelTools.getFieldInformation(datamodel,target)))
        if predictors:
            predictor_list = []
            for predictor in predictors:
                predictor_list.append((predictor,"",DataModelTools.getFieldInformation(datamodel,predictor)))
            items.append(("Predictors",len(predictors),predictor_list))

        s = ""
        s += "Training Summary"+os.linesep
        s += os.linesep
        s += self.format(items)
        s += os.linesep+os.linesep
        return s

    def format(self,items):
        s = ""
        if items:
            keylen = 0
            for item in items:
                key = item[0]
                if len(key) > keylen:
                    keylen = len(key)
            for item in items:
                key = item[0]
                val = item[1]
                s += "    "*self.indent + (key + ":").ljust(keylen+2," ") + str(val) + os.linesep
                if len(item) == 3:
                    self.indent += 1
                    s += self.format(item[2])
                    self.indent -= 1
        return s

# COMMON END

import sys
import os
import json
from pyspark.sql.types import StructField, StructType, StringType, DoubleType

ascontext=None
try:
    import spss.pyspark.runtime
    ascontext = spss.pyspark.runtime.getContext()
    sc = ascontext.getSparkContext()
    sqlCtx = ascontext.getSparkSQLContext()
    df = ascontext.getSparkInputData()
    target = '%%target_field%%'
    schema = ascontext.getSparkInputSchema()
except:
    sc = SparkContext('local')
    sqlCtx = SQLContext(sc)
    # get an input dataframe with sample data by looking in working directory for file DRUG1N.json
    wd = os.getcwd()
    df = sqlCtx.load("file://"+wd+"/DRUG1N.json","json").repartition(4)
    schema = df.schema
    modelpath_base = "/tmp/model1234"
    modelpath = "file://"+modelpath_base+"/model"
    metadatapath = modelpath_base+"/metadata"
    model_metadata = json.loads(open(metadatapath,"r").read())
    target = model_metadata["target"]


prediction_field = "$T-" + target
prediction_type = StringType()

output_schema = StructType(schema.fields + [StructField(prediction_field, prediction_type, nullable=True)])

if ascontext:
    if ascontext.isComputeDataModelOnly():
        ascontext.setSparkOutputSchema(output_schema)
        sys.exit(0)
    else:
        modelpath = ascontext.getModelContentToPath("model")
        model_metadata = json.loads(ascontext.getModelContentToString("model.metadata"))

# create a DataModelTools to handle data model and data conversions
datamodel = model_metadata["datamodel"]
dmt = DataModelTools(datamodel)
predictors = model_metadata["predictors"]
DataModelTools.checkPredictors(datamodel,predictors,df)

from pyspark.mllib.classification import NaiveBayesModel
model = NaiveBayesModel.load(sc, modelpath);

# to score the model, we need an RDD of DenseVector (the numeric encoded values of the predictors), use DataModelTools to do this
dv = dmt.extractDenseVector(df,predictors).map(lambda x:x[1])

# scoring generates an RDD of predictions (but not the original features)
predictions = model.predict(dv)

# now we need to zip together the original rows from the DataFrame and the RDD of predictions
# we end up with an RDD containing the list of values from the original dataframe plus the predicted class, converted from the encoded number to the original string
def rowToList(row):
        result = []
        for idx in range(0, len(row)):
            result.append(row[idx])
        return result

mapFn = lambda (x,y):rowToList(x)+[datamodel[target][int(y)]]

rdd2 = df.rdd.zip(predictions).map(mapFn)

# finally convert the RDD containing the list of values for the resulting rows, back to a dataframe
outdf = sqlCtx.createDataFrame(rdd2,output_schema)

if ascontext:
    ascontext.setSparkOutputData(outdf)
else:
    print(outdf.take(10))



