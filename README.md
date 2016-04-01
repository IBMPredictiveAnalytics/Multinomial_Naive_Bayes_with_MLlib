# Multinomial Naïve Bayes  with MLlib
Naive Bayes is a probabilistic classification algorithm with an assumption of conditional independence between every pair of features.  The multinomial Naïve Bayes algorithm implemented in MLlib and used for this extension performs very well in the task of document classification or spam filtering.  For this extension, predictors should represent a frequency of a given feature.  An example of this would be using a term document matrix where a cell in the matrix would represent the frequency of a given word in a given document.

Learn more about this implementation [from the MLlib Documentation][4]

![Stream](https://raw.githubusercontent.com/IBMPredictiveAnalytics/Multinomial_Naive_Bayes_with_MLlib/master/screenshots/stream.png)


---
Requirements
----
-	SPSS Modeler v18.0 or later
- [Python 2.7 Anaconda Distribution](https://www.continuum.io/downloads)

More information here: [IBM Predictive Extensions][2]

---
Installation Instructions
----

#### Initial one-time set-up for PySpark Extensions

If using v18.0 of SPSS Modeler, navigate to the options.cfg file (Windows default path: C:\Program Files\IBM\SPSS\Modeler\18.0\config).  Open this file in a text editor and paste the following text at the bottom of the document:

  eas_pyspark_python_path, "*C:/Users/IBM_ADMIN/Anaconda/python.exe*"

  -   The italicized path should be replaced with the path to your python.exe from your Anaconda installation.

#### Extension Hub Installation
  1. Go to the Extension menu in Modeler and click "Extension Hub"
  2.	In the search bar, type the name of this extension and press enter
  3. Check the box next to "Get extension" and click OK at the bottom of the screen
  4. The extension will install and a pop-up will show what palette it was installed to

#### Manual Installation
  1.	[Save the .mpe file][3] to your computer
  2.	In Modeler, click the Extensions menu, then click Install Local Extension Bundle
  3.	Navigate to where the .mpe was saved and click open
  4.	The extension will install and a pop-up will show what palette it was installed


---
License
----

[Apache 2.0][1]

---
Contributors
----
- Nial McCarrol - ([www.mccaroll.net](http://www.mccarroll.net/))
- Greg Filla ([gdfilla](https://twitter.com/gdfilla))


[1]: http://www.apache.org/licenses/LICENSE-2.0.html
[2]:https://developer.ibm.com/predictiveanalytics/downloads
[3]:https://github.com/IBMPredictiveAnalytics/Multinomial_Naive_Bayes_with_MLlib/releases/download/1.0.0/MultinomialNaiveBayeswithMLlib.mpe
[4]:https://spark.apache.org/docs/1.5.2/mllib-naive-bayes.html
