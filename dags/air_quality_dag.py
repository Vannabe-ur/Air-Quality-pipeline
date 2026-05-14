from airflow import DAG 
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from datetime import datetime,  timedelta
import requests, json, os

AQICN_TOKEN = os.getenv("AQICN_TOKEN")
FEEDS = [
    feed.strip()
    for feed in os.getenv("AQICN_FEEDS", "@1451").split(",")
    if feed.strip()
]

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

    extract >> transform # extract then transform (which also loads)
