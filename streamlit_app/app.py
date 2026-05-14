import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlalchemy
import streamlit as st


st.set_page_config(page_title="Air Quality Monitoring System", layout="wide")

# Industrial color palette
AQI_COLORS = {
    "Good": "#00a65a",
    "Moderate": "#f39c12",
    "Unhealthy for Sensitive Groups": "#f09300",
    "Unhealthy": "#dd4b39",
    "Very Unhealthy": "#8e44ad",
    "Hazardous": "#7f1d1d",
}

# Technical thresholds
AQI_THRESHOLDS = {
    "Good": (0, 50),
    "Moderate": (51, 100),
    "Unhealthy for Sensitive Groups": (101, 150),
    "Unhealthy": (151, 200),
    "Very Unhealthy": (201, 300),
    "Hazardous": (301, 500),
}

POLLUTANTS = ["pm25", "pm10", "o3", "no2", "co"]
POLLUTANT_LABELS = {
    "pm25": "PM2.5 (\u00b5g/m³)",
    "pm10": "PM10 (\u00b5g/m³)",
    "o3": "Ozone (ppb)",
    "no2": "NO₂ (ppb)",
    "co": "CO (ppm)",
}

POLLUTANT_NAMES = {
    "pm25": "Particulate Matter 2.5",
    "pm10": "Particulate Matter 10",
    "o3": "Ozone",
    "no2": "Nitrogen Dioxide",
    "co": "Carbon Monoxide",
}


def display_name(value):
    if pd.isna(value):
        return "Unknown"
    text = str(value)
    text = text.replace("??", "").replace("  ", " ").strip()
    return text.title() if text else "Unknown"


def load_env_file():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def mysql_config():
    load_env_file()
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3307")

    if host == "mysql":
        host = "localhost"
        port = os.getenv("MYSQL_HOST_PORT", "3307")

    return {
        "host": host,
        "port": port,
        "user": os.getenv("MYSQL_USER", "etl_user"),
        "password": os.getenv("MYSQL_PASSWORD", "etl_pass"),
        "database": os.getenv("MYSQL_DB", "air_quality"),
    }


@st.cache_data(ttl=120)
def load_data():
    config = mysql_config()
    engine = sqlalchemy.create_engine(
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    query = """
        SELECT city, station, aqi, pm25, pm10, o3, no2, co,
               aqi_category, dominant_pollutant, recorded_at, fetched_at
        FROM air_quality
        ORDER BY fetched_at DESC
        LIMIT 2000
    """
    return pd.read_sql(query, engine)


def prepare_data(df):
    prepared = df.copy()
    prepared["recorded_at"] = pd.to_datetime(prepared["recorded_at"], errors="coerce")
    prepared["fetched_at"] = pd.to_datetime(prepared["fetched_at"], errors="coerce")

    for column in ["aqi", *POLLUTANTS]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    prepared["city"] = prepared["city"].apply(display_name)
    prepared["station"] = prepared["station"].fillna(prepared["city"]).apply(display_name)
    prepared["aqi_category"] = prepared["aqi_category"].fillna("Unknown")
    return prepared


def get_aqi_category(aqi_value):
    for category, (low, high) in AQI_THRESHOLDS.items():
        if low <= aqi_value <= high:
            return category
    return "Hazardous"


def create_gauge_chart(value, title, min_val=0, max_val=300, threshold=100):
    """Create industrial-style gauge chart"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={"text": title, "font": {"size": 14, "color": "#7f8c8d"}},
        delta={"reference": threshold, "increasing": {"color": "#dd4b39"}},
        gauge={
            "axis": {"range": [min_val, max_val], "tickwidth": 1, "tickcolor": "#2c3e50"},
            "bar": {"color": "#2c3e50", "thickness": 0.3},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": "#d4efdf"},
                {"range": [51, 100], "color": "#fdebd0"},
                {"range": [101, 150], "color": "#fadbd8"},
                {"range": [151, 200], "color": "#f5b7b1"},
                {"range": [201, 500], "color": "#d7bde2"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 2},
                "thickness": 0.75,
                "value": threshold
            }
        }
    ))
    
    fig.update_layout(
        height=250,
        margin=dict(l=30, r=30, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#2c3e50", "size": 12}
    )
    return fig


def style_industrial_chart(fig, height=400):
    """Apply industrial styling to charts"""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f8f9fa",
        font=dict(color="#2c3e50", size=11, family="Arial, sans-serif"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#dee2e6",
            borderwidth=1
        ),
        hovermode="x unified",
        title_font=dict(size=12, color="#495057"),
    )
    fig.update_xaxes(
        showgrid=True,
        gridwidth=0.5,
        gridcolor="#e9ecef",
        title_font=dict(size=10, color="#6c757d"),
        tickfont=dict(size=10, color="#495057")
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=0.5,
        gridcolor="#e9ecef",
        title_font=dict(size=10, color="#6c757d"),
        tickfont=dict(size=10, color="#495057")
    )
    return fig


# Industrial CSS styling
st.markdown(
    """
    <style>
        /* Industrial theme variables */
        :root {
            --industrial-primary: #1a5490;
            --industrial-secondary: #2c3e50;
            --industrial-accent: #e74c3c;
            --industrial-success: #27ae60;
            --industrial-warning: #f39c12;
            --industrial-background: #ecf0f1;
            --industrial-card: #ffffff;
            --industrial-border: #bdc3c7;
            --industrial-text: #2c3e50;
            --industrial-text-light: #7f8c8d;
        }
        
        /* Main container */
        .main .block-container {
            padding: 1rem 1.5rem;
            max-width: 1600px;
            background-color: #f5f7fa;
        }
        
        /* Sidebar industrial styling */
        [data-testid="stSidebar"] {
            background-color: #2c3e50;
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdown"] {
            color: #ecf0f1;
        }
        
        [data-testid="stSidebar"] h1, 
        [data-testid="stSidebar"] h2, 
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] .stMarkdown {
            color: #ecf0f1 !important;
        }
        
        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stMultiSelect label,
        [data-testid="stSidebar"] .stSlider label {
            color: #bdc3c7 !important;
        }
        
        /* Sidebar divider */
        [data-testid="stSidebar"] hr {
            border-color: #7f8c8d;
        }
        
        /* Header styling */
        .dashboard-header {
            background: linear-gradient(135deg, #1a5490 0%, #2c3e50 100%);
            border-radius: 8px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .dashboard-header h1 {
            color: white;
            margin: 0;
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        
        .dashboard-header p {
            color: #bdc3c7;
            margin: 0.25rem 0 0 0;
            font-size: 0.8125rem;
        }
        
        /* Status indicator panel */
        .status-panel {
            background: white;
            border-left: 4px solid;
            border-radius: 4px;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        .status-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            font-weight: 600;
            color: #7f8c8d;
            letter-spacing: 0.5px;
        }
        
        .status-value {
            font-size: 1.125rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }
        
        /* KPI cards industrial */
        .kpi-card {
            background: white;
            border-radius: 6px;
            padding: 1rem;
            border: 1px solid #dee2e6;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
            transition: all 0.2s;
        }
        
        .kpi-card:hover {
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            border-color: #1a5490;
        }
        
        .kpi-label {
            font-size: 0.6875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #7f8c8d;
            margin-bottom: 0.5rem;
        }
        
        .kpi-value {
            font-size: 1.625rem;
            font-weight: 700;
            color: #2c3e50;
            line-height: 1.2;
        }
        
        .kpi-unit {
            font-size: 0.75rem;
            font-weight: 400;
            color: #95a5a6;
            margin-left: 0.25rem;
        }
        
        .kpi-trend {
            font-size: 0.6875rem;
            margin-top: 0.5rem;
            color: #7f8c8d;
        }
        
        .trend-up { color: #e74c3c; }
        .trend-down { color: #27ae60; }
        
        /* Info panel */
        .info-panel {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 0.875rem;
            margin: 1rem 0;
        }
        
        .info-title {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #6c757d;
            margin-bottom: 0.5rem;
            letter-spacing: 0.5px;
        }
        
        .info-text {
            font-size: 0.8125rem;
            color: #495057;
            line-height: 1.4;
        }
        
        /* Section headers */
        .section-header {
            margin: 1.5rem 0 1rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #dee2e6;
        }
        
        .section-header h3 {
            margin: 0;
            font-size: 1rem;
            font-weight: 600;
            color: #2c3e50;
            letter-spacing: 0.3px;
        }
        
        /* Data table styling */
        .stDataFrame {
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-size: 0.8125rem;
        }
        
        /* Button styling */
        .stButton button {
            background-color: #1a5490;
            color: white;
            border-radius: 4px;
            border: none;
            font-size: 0.8125rem;
            font-weight: 500;
        }
        
        .stButton button:hover {
            background-color: #2c3e50;
        }
        
        /* Select box styling */
        .stSelectbox [data-baseweb="select"] {
            border-radius: 4px;
        }
        
        /* Alert boxes */
        .stAlert {
            border-radius: 4px;
            border-left-width: 4px;
        }
        
        /* Divider */
        hr {
            margin: 0.75rem 0;
            border-color: #dee2e6;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .dashboard-header {
                padding: 1rem;
            }
            
            .kpi-value {
                font-size: 1.25rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Load data
df = prepare_data(load_data())

if df.empty:
    st.error("System Alert: No data available from monitoring network")
    st.stop()

# Apply filters
with st.sidebar:
    st.markdown("### MONITORING CONTROLS")
    st.markdown("---")
    
    cities = sorted(df["city"].dropna().unique())
    selected_cities = st.multiselect(
        "Monitoring Stations",
        cities,
        default=cities[:3] if len(cities) > 3 else cities,
        help="Select locations for comparative analysis"
    )
    
    categories = sorted(df["aqi_category"].dropna().unique())
    selected_categories = st.multiselect(
        "AQI Classification",
        categories,
        default=categories,
        help="Filter by air quality category"
    )
    
    pollutant = st.selectbox(
        "Primary Pollutant",
        POLLUTANTS,
        index=0,
        format_func=lambda item: POLLUTANT_NAMES[item],
        help="Select pollutant for detailed analysis"
    )
    
    max_rows = st.slider(
        "Record Display Limit",
        25, 500, 100, step=25,
        help="Maximum number of records in table view"
    )
    
    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 0.7rem; color: #95a5a6;">
        <strong>DATA PIPELINE STATUS</strong><br>
        Source: AQICN Network<br>
        ETL: Apache Airflow<br>
        Processing: Apache Spark<br>
        Storage: MySQL<br>
        Update Interval: 2 minutes
        </div>
        """,
        unsafe_allow_html=True
    )

# Filter data
filtered = df[
    df["city"].isin(selected_cities)
    & df["aqi_category"].isin(selected_categories)
].copy()

if filtered.empty:
    st.warning("No data matches current filter criteria. Please adjust monitoring controls.")
    st.stop()

# Calculate latest readings
latest = (
    filtered.sort_values("fetched_at")
    .groupby("city", as_index=False)
    .tail(1)
    .sort_values("aqi", ascending=False)
)

if latest.empty:
    st.warning("Insufficient data for analysis")
    st.stop()

latest_record = latest.iloc[0]
last_seen = filtered["fetched_at"].max()

# Calculate trends (compare current with previous)
trend_data = filtered.sort_values("fetched_at")
if len(trend_data) > 1:
    current_avg = filtered["aqi"].mean()
    previous_avg = filtered[filtered["fetched_at"] < filtered["fetched_at"].max() - pd.Timedelta(hours=1)]["aqi"].mean() if len(filtered) > 10 else current_avg
    aqi_trend = ((current_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
else:
    aqi_trend = 0

# Dashboard header
st.markdown(
    f"""
    <div class="dashboard-header">
        <h1>INDUSTRIAL AIR QUALITY MONITORING SYSTEM</h1>
        <p>Real-time surveillance | {latest['city'].nunique()} active monitoring stations | System time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Status panel
status_color = AQI_COLORS.get(latest_record["aqi_category"], "#7f8c8d")

col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1])

with col1:
    st.markdown(
        f"""
        <div class="status-panel" style="border-left-color: {status_color};">
            <div class="status-label">System Status</div>
            <div class="status-value" style="color: {status_color};">{latest_record['aqi_category'].upper()}</div>
            <div style="font-size: 0.75rem; color: #6c757d;">Latest reading from {latest_record['city']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div class="status-panel">
            <div class="status-label">Current AQI</div>
            <div class="status-value">{int(latest_record['aqi'])}</div>
            <div style="font-size: 0.75rem; color: #6c757d;">{latest_record['city']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div class="status-panel">
            <div class="status-label">Primary Pollutant</div>
            <div class="status-value">{latest_record['dominant_pollutant'].upper() if latest_record['dominant_pollutant'] else 'N/A'}</div>
            <div style="font-size: 0.75rem; color: #6c757d;">Dominant contaminant</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col4:
    st.markdown(
        f"""
        <div class="status-panel">
            <div class="status-label">Data Freshness</div>
            <div class="status-value">{last_seen.strftime('%H:%M:%S')}</div>
            <div style="font-size: 0.75rem; color: #6c757d;">{last_seen.strftime('%Y-%m-%d')}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# KPI metrics row
st.markdown('<div class="section-header"><h3>OPERATIONAL METRICS</h3></div>', unsafe_allow_html=True)

kpi_cols = st.columns(5)

with kpi_cols[0]:
    trend_symbol = "▲" if aqi_trend > 0 else "▼"
    trend_class = "trend-up" if aqi_trend > 0 else "trend-down"
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Average AQI</div>
            <div class="kpi-value">{round(filtered['aqi'].mean(), 1)}<span class="kpi-unit">AQI</span></div>
            <div class="kpi-trend"><span class="{trend_class}">{trend_symbol} {abs(aqi_trend):.1f}%</span> vs previous</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi_cols[1]:
    max_aqi_city = latest.iloc[0]['city'] if not latest.empty else "N/A"
    max_aqi = int(latest.iloc[0]['aqi']) if not latest.empty else 0
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Peak AQI</div>
            <div class="kpi-value">{max_aqi}<span class="kpi-unit">AQI</span></div>
            <div class="kpi-trend">{max_aqi_city}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi_cols[2]:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">PM2.5 Concentration</div>
            <div class="kpi-value">{round(filtered['pm25'].max(), 1)}<span class="kpi-unit">µg/m³</span></div>
            <div class="kpi-trend">Peak particulate matter</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi_cols[3]:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Network Coverage</div>
            <div class="kpi-value">{filtered['station'].nunique()}<span class="kpi-unit">stations</span></div>
            <div class="kpi-trend">{filtered['city'].nunique()} cities</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi_cols[4]:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Data Points</div>
            <div class="kpi-value">{len(filtered)}<span class="kpi-unit">records</span></div>
            <div class="kpi-trend">Current session</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Technical information panel
col_info1, col_info2, col_info3 = st.columns(3)

with col_info1:
    st.markdown(
        """
        <div class="info-panel">
            <div class="info-title">AQI THRESHOLDS</div>
            <div class="info-text">
                <strong>Good (0-50):</strong> Minimal risk<br>
                <strong>Moderate (51-100):</strong> Acceptable quality<br>
                <strong>Unhealthy (101-150):</strong> Sensitive groups impact<br>
                <strong>Hazardous (151+):</strong> Health alert
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_info2:
    st.markdown(
        """
        <div class="info-panel">
            <div class="info-title">OPERATIONAL GUIDANCE</div>
            <div class="info-text">
                • AQI > 100: Initiate mitigation protocols<br>
                • AQI > 150: Issue public advisory<br>
                • PM2.5 > 35: Enhanced filtration required<br>
                • Trend analysis: 2-hour rolling window
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_info3:
    st.markdown(
        """
        <div class="info-panel">
            <div class="info-title">SYSTEM SPECIFICATIONS</div>
            <div class="info-text">
                Resolution: Hourly readings<br>
                Calibration: EPA standards<br>
                Validation: Automated QC checks<br>
                Alert threshold: Configurable
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Charts section
st.markdown('<div class="section-header"><h3>ANALYTICAL DASHBOARD</h3></div>', unsafe_allow_html=True)

# Gauge chart for current AQI
col_gauge, col_trend = st.columns([0.8, 1.2])

with col_gauge:
    current_aqi = int(latest_record['aqi'])
    gauge_fig = create_gauge_chart(current_aqi, "Current AQI", threshold=100)
    st.plotly_chart(gauge_fig, use_container_width=True)

with col_trend:
    trend_data_viz = filtered.sort_values("fetched_at")
    if not trend_data_viz.empty:
        fig_trend = px.line(
            trend_data_viz,
            x="fetched_at",
            y="aqi",
            color="city",
            markers=True,
            labels={"fetched_at": "Timestamp (UTC)", "aqi": "Air Quality Index", "city": "Station"},
            line_shape="linear",
        )
        fig_trend.add_hrect(y0=0, y1=50, fillcolor="#00a65a", opacity=0.1, line_width=0)
        fig_trend.add_hrect(y0=51, y1=100, fillcolor="#f39c12", opacity=0.1, line_width=0)
        fig_trend.add_hrect(y0=101, y1=150, fillcolor="#f09300", opacity=0.1, line_width=0)
        fig_trend.add_hrect(y0=151, y1=500, fillcolor="#dd4b39", opacity=0.08, line_width=0)
        fig_trend.update_traces(line=dict(width=2), marker=dict(size=4))
        fig_trend.update_layout(
            title="Time Series Analysis",
            xaxis_title="",
            yaxis_title="AQI Value"
        )
        st.plotly_chart(style_industrial_chart(fig_trend, 380), use_container_width=True)

# Two column chart layout
col_left, col_right = st.columns(2)

with col_left:
    if not latest.empty:
        fig_bar = px.bar(
            latest,
            x="aqi",
            y="city",
            color="aqi_category",
            orientation="h",
            color_discrete_map=AQI_COLORS,
            labels={"aqi": "AQI Value", "city": "Monitoring Location", "aqi_category": "Classification"},
            text="aqi",
        )
        fig_bar.update_traces(
            texttemplate="%{text:.0f}",
            textposition="outside",
            marker=dict(line=dict(width=0.5, color="#dee2e6"))
        )
        fig_bar.update_layout(
            title="Current AQI by Location",
            yaxis=dict(categoryorder="total ascending"),
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        st.plotly_chart(style_industrial_chart(fig_bar, 450), use_container_width=True)

with col_right:
    # Category distribution
    category_counts = (
        filtered["aqi_category"]
        .value_counts()
        .rename_axis("category")
        .reset_index(name="readings")
    )
    
    if not category_counts.empty:
        fig_pie = px.pie(
            category_counts,
            names="category",
            values="readings",
            color="category",
            color_discrete_map=AQI_COLORS,
            hole=0.55,
        )
        fig_pie.update_traces(
            textposition="inside",
            textinfo="percent+label",
            textfont_size=11,
            marker=dict(line=dict(color="#ffffff", width=1))
        )
        fig_pie.update_layout(
            title="AQI Classification Distribution",
            showlegend=False
        )
        st.plotly_chart(style_industrial_chart(fig_pie, 450), use_container_width=True)

# Pollutant analysis section
st.markdown('<div class="section-header"><h3>POLLUTANT CONCENTRATION ANALYSIS</h3></div>', unsafe_allow_html=True)

pollutant_cols = st.columns(2)

with pollutant_cols[0]:
    city_for_pollutants = st.selectbox(
        "Select Location for Pollutant Profile",
        sorted(latest["city"].unique()),
        key="pollutant_location"
    )
    
    city_data = filtered[filtered["city"] == city_for_pollutants].sort_values("fetched_at")
    if not city_data.empty:
        latest_city = city_data.iloc[-1]
        pollutant_values = []
        for p in POLLUTANTS:
            val = latest_city[p]
            if pd.notna(val):
                pollutant_values.append({
                    "pollutant": POLLUTANT_NAMES[p],
                    "value": val,
                    "unit": POLLUTANT_LABELS[p].split("(")[-1].rstrip(")")
                })
        
        if pollutant_values:
            pollutant_df = pd.DataFrame(pollutant_values)
            fig_pollutants = px.bar(
                pollutant_df,
                x="pollutant",
                y="value",
                color="pollutant",
                labels={"pollutant": "Pollutant", "value": "Concentration"},
                text="value",
            )
            fig_pollutants.update_traces(
                texttemplate="%{text:.1f}",
                textposition="outside",
                marker=dict(line=dict(width=0))
            )
            fig_pollutants.update_layout(showlegend=False)
            st.plotly_chart(style_industrial_chart(fig_pollutants, 350), use_container_width=True)

with pollutant_cols[1]:
    # Time series for selected pollutant
    if not city_data.empty and len(city_data) > 1:
        fig_ts = px.line(
            city_data,
            x="fetched_at",
            y=pollutant,
            labels={
                "fetched_at": "Timestamp",
                pollutant: POLLUTANT_LABELS[pollutant]
            },
            title=f"{POLLUTANT_NAMES[pollutant]} Trend - {city_for_pollutants}"
        )
        fig_ts.update_traces(line=dict(width=2, color="#1a5490"))
        st.plotly_chart(style_industrial_chart(fig_ts, 350), use_container_width=True)
    else:
        st.info("Insufficient historical data for trend analysis")

# Data table
st.markdown('<div class="section-header"><h3>MONITORING DATA LOG</h3></div>', unsafe_allow_html=True)

table_data = filtered.sort_values("fetched_at", ascending=False).head(max_rows)
display_table = table_data[
    [
        "fetched_at",
        "recorded_at",
        "city",
        "station",
        "aqi",
        "aqi_category",
        pollutant,
        "dominant_pollutant",
    ]
].rename(columns={
    "fetched_at": "Ingestion Timestamp",
    "recorded_at": "Measurement Timestamp",
    "city": "Location",
    "station": "Station ID",
    "aqi": "AQI",
    "aqi_category": "Classification",
    pollutant: POLLUTANT_LABELS[pollutant],
    "dominant_pollutant": "Primary Pollutant",
})

st.dataframe(
    display_table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ingestion Timestamp": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
        "Measurement Timestamp": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
        "AQI": st.column_config.NumberColumn(format="%d"),
        "Classification": st.column_config.TextColumn(),
        "Location": st.column_config.TextColumn(),
        "Station ID": st.column_config.TextColumn(),
        "Primary Pollutant": st.column_config.TextColumn(),
    }
)

# Export option
st.markdown("---")
col_export, _ = st.columns([0.2, 0.8])
with col_export:
    csv = display_table.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="EXPORT DATA (CSV)",
        data=csv,
        file_name=f"air_quality_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )