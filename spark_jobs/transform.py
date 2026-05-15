from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, to_timestamp, lower, trim
import json, os

RAW_PATH   = "/opt/airflow/spark_jobs/raw_data.json"
CLEAN_PATH = "/opt/airflow/spark_jobs/clean_data.json"

spark = SparkSession.builder \
    .appName("AirQualityTransform") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# ── Read 
print(f"[TRANSFORM] Reading raw data from {RAW_PATH}")
df = spark.read.option("multiLine", True).json(RAW_PATH)
print(f"[TRANSFORM] Raw record count: {df.count()}")

# ── Clean & enrich 
df_clean = (
    df
    .withColumn("city",    lower(trim(col("city"))))
    .withColumn("station", trim(col("station")))
    .withColumn("recorded_at", to_timestamp(col("recorded_at")))
    .withColumn("aqi",  col("aqi").cast("integer"))
    .withColumn("pm25", col("pm25").cast("float"))
    .withColumn("pm10", col("pm10").cast("float"))
    .withColumn("o3",   col("o3").cast("float"))
    .withColumn("no2",  col("no2").cast("float"))
    .withColumn("co",   col("co").cast("float"))
    # Derive AQI category from the numeric AQI value
    .withColumn(
        "aqi_category",
        when(col("aqi") <= 50,  "Good")
        .when(col("aqi") <= 100, "Moderate")
        .when(col("aqi") <= 150, "Unhealthy for Sensitive Groups")
        .when(col("aqi") <= 200, "Unhealthy")
        .when(col("aqi") <= 300, "Very Unhealthy")
        .otherwise("Hazardous")
    )
    # Drop rows with no AQI or duplicate (city + time) combinations
    .filter(col("aqi").isNotNull())
    .dropDuplicates(["city", "recorded_at"])
    # Keep only the columns the Load task expects
    .select(
        "city", "station", "aqi", "pm25", "pm10",
        "o3", "no2", "co", "aqi_category",
        "dominant_pollutant", "recorded_at",
    )
)

clean_count = df_clean.count()
print(f"[TRANSFORM] Clean record count: {clean_count}")

# ── Write clean JSON for the Load task
# Collect is safe here — we're dealing with a small number of station feeds.
# For large-scale pipelines, write to parquet instead and adjust load_to_mysql.
records = [
    {
        k: (str(v) if v is not None else None)
        for k, v in row.asDict().items()
    }
    for row in df_clean.collect()
]

with open(CLEAN_PATH, "w") as f:
    json.dump(records, f, default=str)

print(f"[TRANSFORM] Wrote {len(records)} clean records → {CLEAN_PATH}")
spark.stop()