from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, to_timestamp, lower, trim
import os

spark = SparkSession.builder \
    .appName("AirQualityETL") \
    .config("spark.jars.packages", "mysql:mysql-connector-java:8.0.33") \
    .getOrCreate()

# Transform-----
df = spark.read.json("/opt/airflow/spark_jobs/raw_data.json")

df_clean = df \
    .withColumn("city", lower(trim(col("city")))) \
    .withColumn("station", trim(col("station"))) \
    .withColumn("recorded_at", to_timestamp(col("recorded_at"))) \
    .withColumn("aqi", col("aqi").cast("integer")) \
    .withColumn("pm25", col("pm25").cast("float")) \
    .withColumn("pm10", col("pm10").cast("float")) \
    .withColumn("o3",   col("o3").cast("float")) \
    .withColumn("no2",  col("no2").cast("float")) \
    .withColumn("co",   col("co").cast("float")) \
    .withColumn("aqi_category",
                when(col("aqi") <= 50, "Good")
                .when(col("aqi") <= 100, "Moderate")
                .when(col("aqi") <= 150, "Unhealthy for Sensitive Groups")
                .when(col("aqi") <= 200, "Unhealthy")
                .when(col("aqi") <= 300, "Very Unhealthy")
                .otherwise("Hazardous")
                ) \
                .dropDuplicates(["city", "recorded_at"]) \
                .filter(col("aqi").isNotNull())

# Load -----
MYSQL_URL = f"jdbc:mysql://{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"

df_clean.write \
    .format("jdbc") \
    .option("url", MYSQL_URL) \
    .option("dbtable", "air_quality") \
    .option("user", os.getenv("MYSQL_USER")) \
    .option("password", os.getenv("MYSQL_PASSWORD")) \
    .option("driver", "com.mysql.cj.jdbc.Driver") \
    .mode("append") \
    .save()

print(f"LOADED {df_clean.count()} records to MySQL")
spark.stop()
