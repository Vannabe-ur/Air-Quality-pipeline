CREATE TABLE IF NOT EXISTS air_quality (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city VARCHAR(100),
    station VARCHAR(200),
    aqi INT,
    pm25 FLOAT,
    pm10 FLOAT,
    o3 FLOAT,
    no2 FLOAT,
    co FLOAT,
    aqi_category VARCHAR(50),
    dominant_pollutant VARCHAR(50),
    recorded_at DATETIME,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
