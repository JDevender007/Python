from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, count, current_date, when

spark = (
    SparkSession.builder
    .appName("Patient Entry System")
    .config("spark.sql.warehouse.dir", "spark-warehouse")
    .getOrCreate()
)

patients = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv("patient.csv")
)

print("\n==============================")
print("PATIENT RECORDS")
print("==============================")
patients.show(truncate=False)

print("\n==============================")
print("SCHEMA")
print("==============================")
patients.printSchema()

patients = patients.dropDuplicates()

print("\n==============================")
print("MISSING VALUES")
print("==============================")

patients.select([
    count(when(col(c).isNull(), c)).alias(c)
    for c in patients.columns
]).show()

print("Total Patients:", patients.count())

spark.sql("DROP TABLE IF EXISTS PatientDetails")

patients.write.mode("overwrite").saveAsTable("PatientDetails")

patient_table = spark.read.table("PatientDetails")

print("\n==============================")
print("PATIENT TABLE")
print("==============================")
patient_table.show(truncate=False)

print("\nPatients Older Than 40")
patient_table.filter(col("Age") > 40).show()

print("\nFemale Patients")
patient_table.filter(col("Gender") == "Female").show()

print("\nMale Patients")
patient_table.filter(col("Gender") == "Male").show()

print("\nDiabetes Patients")
patient_table.filter(col("Diagnosis") == "Diabetes").show()

print("\nFever Patients")
patient_table.filter(col("Diagnosis") == "Fever").show()

print("\nAverage Age")
patient_table.select(avg("Age").alias("Average Age")).show()

print("\nPatients by Gender")
patient_table.groupBy("Gender").count().show()

print("\nPatients by Diagnosis")
patient_table.groupBy("Diagnosis").count().show()

print("\nPatients Sorted by Age")
patient_table.orderBy(col("Age").desc()).show()

report = patient_table.withColumn("ReportDate", current_date())

print("\nPATIENT REPORT")
report.show(truncate=False)

report.createOrReplaceTempView("Patients")

print("\nPatients Above 35 Years")

spark.sql("""
SELECT PatientID,
       Name,
       Age,
       Diagnosis
FROM Patients
WHERE Age > 35
ORDER BY Age DESC
""").show()

print("\nFemale Patients")

spark.sql("""
SELECT Name,
       Diagnosis
FROM Patients
WHERE Gender='Female'
""").show()

print("\nDiagnosis Count")

spark.sql("""
SELECT Diagnosis,
       COUNT(*) AS TotalPatients
FROM Patients
GROUP BY Diagnosis
ORDER BY TotalPatients DESC
""").show()

spark.sql("DROP TABLE IF EXISTS PatientReport")

report.write.mode("overwrite").saveAsTable("PatientReport")

print("\n===================================")
print("PROJECT COMPLETED SUCCESSFULLY")
print("===================================")

spark.stop()