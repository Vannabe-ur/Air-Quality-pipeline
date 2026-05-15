from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from datetime import datetime, timedelta
import requests, json, os
import sqlalchemy
AQICN_TOKEN = os.getenv("AQICN_TOKEN")
FEEDS = [
    feed.strip()
    for feed in os.getenv("AQICN_FEEDS", "@1451").split(",")
    if feed.strip()
]

RAW_PATH   = "/opt/airflow/spark_jobs/raw_data.json"
CLEAN_PATH = "/opt/airflow/spark_jobs/clean_data.json"

def extract_air_quality(**context):
    """fetch air quality data from AQICN"""
    if not AQICN_TOKEN or AQICN_TOKEN == "your_token_here":
        raise ValueError("Set a real AQICN_TOKEN in .env before running this DAG.")

    results = []
    for feed in FEEDS:
        url = f"https://api.waqi.info/feed/{feed}/?token={AQICN_TOKEN}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "ok":
            d = data["data"]
            record = {
                "city": d.get("city", {}).get("name", feed),
                "station": d.get("city", {}).get("name", feed),
                "aqi": d.get("aqi"),
                "pm25": d.get("iaqi", {}).get("pm25", {}).get("v"),
                "pm10": d.get("iaqi", {}).get("pm10", {}).get("v"),
                "o3": d.get("iaqi", {}).get("o3", {}).get("v"),
                "no2": d.get("iaqi", {}).get("no2", {}).get("v"),
                "co": d.get("iaqi", {}).get("co", {}).get("v"),
                "dominant_pollutant": d.get("dominentpol"),
                "recorded_at": d.get("time", {}).get("iso"),
            }
            results.append(record)
        else:
            print(f"Skipping {feed}: AQICN returned {data}")

    if not results:
        raise ValueError("No air quality records were extracted. Check AQICN_TOKEN and city names.")

    output_path = "/opt/airflow/spark_jobs/raw_data.json"
    with open(output_path, "w") as f:
        json.dump(results, f)

    print(f"Extracted {len(results)} records")

# Task: load
def load_to_mysql(**context):
    if not os.path.exists(CLEAN_PATH):
        raise FileNotFoundError(
            f"Clean data not found at {CLEAN_PATH}. "
            "Did the Spark Transform task succeed?"
        )
 
    with open(CLEAN_PATH) as f:
        records = json.load(f)
 
    if not records:
        raise ValueError("Clean data file is empty — nothing to load.")
 
    # ── Build MySQL connection 
    host     = os.getenv("MYSQL_HOST",     "mysql")
    port     = os.getenv("MYSQL_PORT",     "3306")
    db       = os.getenv("MYSQL_DB",       "air_quality")
    user     = os.getenv("MYSQL_USER",     "etl_user")
    password = os.getenv("MYSQL_PASSWORD", "etl_pass")
 
    engine = sqlalchemy.create_engine(
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    )
 
    # ── Upsert: skip duplicates by (city, recorded_at) 
    insert_sql = sqlalchemy.text("""
        INSERT IGNORE INTO air_quality
            (city, station, aqi, pm25, pm10, o3, no2, co,
             aqi_category, dominant_pollutant, recorded_at)
        VALUES
            (:city, :station, :aqi, :pm25, :pm10, :o3, :no2, :co,
             :aqi_category, :dominant_pollutant, :recorded_at)
    """)
 
    loaded = 0
    skipped = 0
    with engine.begin() as conn:
        for row in records:
            result = conn.execute(insert_sql, row)
            if result.rowcount:
                loaded += 1
            else:
                skipped += 1
 
    print(f"[LOAD] Inserted {loaded} rows, skipped {skipped} duplicates → {db}.air_quality")
 
    # Clean up temp file so next run starts fresh
    os.remove(CLEAN_PATH)
    print(f"[LOAD] Removed {CLEAN_PATH}")

default_args ={
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5)
}

with DAG(
    dag_id="air_quality_etl",
    default_args=default_args,
    description="ETL pipeline for air quality data",
    schedule_interval="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["air_quality", "etl"]
) as dag:
    # extracting data
    extract = PythonOperator(
        task_id="extract_air_quality",
        python_callable=extract_air_quality,
    )

    # transform data
    transform = SparkSubmitOperator(
        task_id="transform_with_spark",
        application="/opt/airflow/spark_jobs/transform.py",
        conn_id="spark_default",
        application_args=[],
        conf={},
        env_vars={
            "MYSQL_HOST": os.getenv("MYSQL_HOST", "mysql"),
            "MYSQL_PORT": os.getenv("MYSQL_PORT", "3306"),
            "MYSQL_DB": os.getenv("MYSQL_DB", "air_quality"),
            "MYSQL_USER": os.getenv("MYSQL_USER", "etl_user"),
            "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD", "etl_pass"),
        },
        verbose=True,
        name="air-quality-transform",
        packages="mysql:mysql-connector-java:8.0.33",
    )

    # Load data
    load = PythonOperator(
        task_id="load_to_mysql",
        python_callable=load_to_mysql,
    )

    extract >> transform >>load 
