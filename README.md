# Air-Quality-pipeline

### Workflow
```
[Air Quality API]
       ↓  (Extract)
  Airflow DAG
       ↓  (Transform)
  Apache Spark (PySpark)
       ↓  (Load)
    MySQL DB
       ↓  (Visualize)
  Streamlit Dashboard
```
---
### Project Structure
```
air_quality_etl/
├── docker-compose.yml          ← Spins up all services
├── dags/
│   └── air_quality_dag.py      ← Airflow DAG definition
├── spark_jobs/
│   └── transform.py            ← PySpark transformation script
├── scripts/
│   └── init_db.sql             ← MySQL table creation
├── streamlit_app/
│   └── app.py            ← Streamlit dashboard
├── requirements.txt
└── .env                        ← API keys, DB credentials
```
---
### Step-by-Step
#### Step 1: Install and setup Docker
Docker will run Airflow, Spark, and MySQL as isolated containers so nothing conflicts with your local system.
```
# Docker Desktop (includes Docker Compose)
# Download from: https://www.docker.com/products/docker-desktop/

# Verify installation
docker --version
docker compose version
```

#### Step 2: Get an Air Quality API key
Here in this project we used AQICN(free key).
Air quality data gives us real-world measurements: PM2.5, PM10, CO, NO2, O3 — all timestamped by city/station.
```
# AQICN - get a free token at:
# https://aqicn.org/data-platform/token/
# Save your token, you'll put it in .env
```

c
```
mkdir air_quality_etl && cd air_quality_etl
mkdir -p dags spark_jobs scripts streamlit_app
```
In **.env** file (Storing Secrete Key).
Keeping secrets in .env (not in code) is best practice — never commit API keys to Git.
Sample:
```
AQICN_TOKEN=your_token_here
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=etl_user
MYSQL_PASSWORD=etl_pass
MYSQL_DB=air_quality
```
#### Step 4: Create `docker-compose.yml`
This is the heart of the setup. It defines all your services.
**Why each service?**
- `postgres` → Airflow stores its own metadata (DAG runs, task logs) here
- `mysql` → YOUR data lives here (air quality readings)
- `airflow-webserver` → The browser UI at localhost:8080
- `airflow-scheduler` → Watches the clock and triggers DAG runs
- `spark-master/worker` → Distributed compute engine for transformation

#### Step 5: MySQL Table Schema
Create `scripts/init_db.sql`
This table is created automatically when MySQL starts. Each row = one air quality reading from one station at one time.

#### Step 6: Airflow DAG (Extract step)
Create `dags/air_quality_dag.py`for processing:
- `@hourly` schedule means Airflow auto-runs this every hour
- `PythonOperator` runs plain Python (the API call)
- `SparkSubmitOperator` submits a job to your Spark cluster
- `>>` defines the dependency chain (task order)

#### Step 6: PySpark Transform + Load
Create `spark_jobs/transform.py`
**Why Spark here?**
- Spark handles data cleaning in a distributed, fault-tolerant way
- It can scale to millions of rows (not just 5 cities — imagine 5000)
- JDBC connector writes directly to MySQL

#### Step 8: Streamlit App
Create `streamlit_app/dashboard.py` 
For interactive virtulization, testing the workflow whether it could process exact same data with the real website.

#### Step 9: Launch Everything
Using these commands:
```
# 1. Start all services
docker compose up -d

# 2. Wait ~60 seconds for Airflow to initialize, then open:
#    Airflow UI  → http://localhost:8080  (admin / admin)
#    Spark UI    → http://localhost:8081

# 3. In Airflow UI:
#    - Find DAG "air_quality_etl"
#    - Toggle it ON
#    - Click "Trigger DAG" to run immediately

# 4. Run Streamlit (on your local machine, not Docker)
pip install streamlit plotly sqlalchemy pymysql python-dotenv
cd streamlit_app
streamlit run app.py #or
python -m streamlit run app.py

# Opens at http://localhost:8501
```

#### Step 10: Verify data in MySQL
```
# Connect to MySQL inside Docker
docker exec -it air_quality_etl-mysql-1 mysql -u etl_user -petl_pass air_quality

# Run SQL
SELECT city, aqi, aqi_category, recorded_at FROM air_quality_readings LIMIT 10;
```


