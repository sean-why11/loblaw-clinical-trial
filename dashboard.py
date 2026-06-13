from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

root = Path(__file__).resolve().parent
db_path = root / "cell-count.db"
population_order = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

@st.cache_data
def load_frequency_data() -> pd.DataFrame:
    query = """
    SELECT
        samples.sample_id AS sample,
        subjects.subject_id,
        subjects.project,
        subjects.indication,
        subjects.gender,
        samples.treatment,
        samples.sample_type,
        samples.response,
        samples.time_from_treatment_start,
        populations.population_name AS population,
        counts.cell_count AS count
    FROM cell_counts AS counts
    INNER JOIN samples
        ON samples.sample_id = counts.sample_id
    INNER JOIN subjects
        ON subjects.subject_id = samples.subject_id
    INNER JOIN cell_populations AS populations
        ON populations.population_id = counts.population_id;
    """
    with sqlite3.connect(db_path) as connection:
        data = pd.read_sql_query(query, connection)

    data["total_count"] = data.groupby("sample")["count"].transform("sum")
    data["percentage"] = 100 * data["count"] / data["total_count"]
    return data

st.set_page_config(page_title="Loblaw Bio Immune Cell Dashboard", layout="wide")
st.title("Loblaw Bio Immune Cell Dashboard")

if not db_path.exists():
    st.error("Database not found. Run `python load_data.py` or `make pipeline` first.")
    st.stop()

frequency_df = load_frequency_data()

with st.sidebar:
    st.header("Filters")
    indications = st.multiselect(
        "Indication",
        sorted(frequency_df["indication"].unique()),
        default=sorted(frequency_df["indication"].unique()),
    )
    treatments = st.multiselect(
        "Treatment",
        sorted(frequency_df["treatment"].unique()),
        default=sorted(frequency_df["treatment"].unique()),
    )
    sample_types = st.multiselect(
        "Sample type",
        sorted(frequency_df["sample_type"].unique()),
        default=sorted(frequency_df["sample_type"].unique()),
    )
    responses = st.multiselect(
        "Response",
        sorted(frequency_df["response"].dropna().unique()),
        default=sorted(frequency_df["response"].dropna().unique()),
    )

filtered_df = frequency_df[
    frequency_df["indication"].isin(indications)
    & frequency_df["treatment"].isin(treatments)
    & frequency_df["sample_type"].isin(sample_types)
    & frequency_df["response"].isin(responses)
].copy()

sample_count = filtered_df["sample"].nunique()
subject_count = filtered_df["subject_id"].nunique()

metric_cols = st.columns(3)
metric_cols[0].metric("Samples", f"{sample_count:,}")
metric_cols[1].metric("Subjects", f"{subject_count:,}")
metric_cols[2].metric("Rows", f"{len(filtered_df):,}")

st.subheader("Relative Frequency Summary")
summary_df = (
    filtered_df.groupby(["population", "response"], as_index=False)["percentage"]
    .agg(["count", "mean", "median"])
    .reset_index()
    .sort_values(["population", "response"])
)
st.dataframe(summary_df, use_container_width=True)

st.subheader("Population Frequencies")
chart_df = filtered_df.copy()
chart_df["population"] = pd.Categorical(
    chart_df["population"], categories=population_order, ordered=True
)
st.bar_chart(
    chart_df.groupby(["population", "response"])["percentage"]
    .mean()
    .unstack("response")
    .sort_index()
)

st.subheader("Sample-Level Frequency Table")
display_columns = [
    "sample",
    "total_count",
    "population",
    "count",
    "percentage",
    "indication",
    "treatment",
    "sample_type",
    "response",
    "gender",
    "time_from_treatment_start",
]
st.dataframe(
    filtered_df[display_columns].sort_values(["sample", "population"]),
    use_container_width=True,
    hide_index=True,
)
