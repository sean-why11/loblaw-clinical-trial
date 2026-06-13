from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import mannwhitneyu


root = Path(__file__).resolve().parent
db_path = root / "cell-count.db"
output_dir = root / "outputs"
population_order = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]
response_order = ["Responder", "Non-responder"]


def benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    p_values = pd.Series(p_values, dtype="float64")
    sorted_p_values = p_values.sort_values()
    ranks = range(1, len(sorted_p_values) + 1)
    adjusted = sorted_p_values * len(sorted_p_values) / pd.Series(
        ranks, index=sorted_p_values.index
    )
    adjusted = adjusted.iloc[::-1].cummin().iloc[::-1]
    return adjusted.reindex(p_values.index).clip(upper=1.0)


def run_loader() -> None:
    subprocess.run([sys.executable, "load_data.py"], cwd=root, check=True)


def read_raw_counts() -> pd.DataFrame:
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
        return pd.read_sql_query(query, connection)


def calculate_frequencies(raw_df: pd.DataFrame) -> pd.DataFrame:
    frequency_df = raw_df.copy()
    frequency_df["total_count"] = frequency_df.groupby("sample")["count"].transform("sum")
    frequency_df["percentage"] = (
        100 * frequency_df["count"] / frequency_df["total_count"]
    ).round(4)
    return frequency_df[
        [
            "sample",
            "subject_id",
            "project",
            "indication",
            "gender",
            "treatment",
            "sample_type",
            "response",
            "time_from_treatment_start",
            "total_count",
            "population",
            "count",
            "percentage",
        ]
    ]


def part_3_analysis(frequency_df: pd.DataFrame) -> pd.DataFrame:
    analysis_df = frequency_df[
        (frequency_df["indication"].str.lower() == "melanoma")
        & (frequency_df["treatment"].str.lower() == "miraclib")
        & (frequency_df["sample_type"].str.upper() == "PBMC")
        & (frequency_df["response"].isin(["yes", "no"]))
    ].copy()
    analysis_df["response_group"] = analysis_df["response"].map(
        {"yes": "Responder", "no": "Non-responder"}
    )
    analysis_df.to_csv(output_dir / "part3_analysis_cohort.csv", index=False)

    results = []
    for population in population_order:
        responder_values = analysis_df.loc[
            (analysis_df["population"] == population)
            & (analysis_df["response_group"] == "Responder"),
            "percentage",
        ]
        non_responder_values = analysis_df.loc[
            (analysis_df["population"] == population)
            & (analysis_df["response_group"] == "Non-responder"),
            "percentage",
        ]
        test = mannwhitneyu(
            responder_values,
            non_responder_values,
            alternative="two-sided",
        )
        results.append(
            {
                "population": population,
                "responder_n": responder_values.size,
                "non_responder_n": non_responder_values.size,
                "responder_median_pct": responder_values.median(),
                "non_responder_median_pct": non_responder_values.median(),
                "median_difference_pct": responder_values.median()
                - non_responder_values.median(),
                "mann_whitney_u": test.statistic,
                "p_value": test.pvalue,
            }
        )

    stats_df = pd.DataFrame(results)
    stats_df["fdr_adjusted_p_value"] = benjamini_hochberg(stats_df["p_value"])
    stats_df["nominally_significant_p_0_05"] = stats_df["p_value"] < 0.05
    stats_df["significant_at_fdr_0_05"] = stats_df["fdr_adjusted_p_value"] < 0.05
    stats_df.sort_values("fdr_adjusted_p_value").to_csv(
        output_dir / "part3_population_statistics.csv", index=False
    )

    fig, axes = plt.subplots(1, len(population_order), figsize=(18, 5), sharey=True)
    for ax, population in zip(axes, population_order):
        plot_data = [
            analysis_df.loc[
                (analysis_df["population"] == population)
                & (analysis_df["response_group"] == response_group),
                "percentage",
            ]
            for response_group in response_order
        ]
        ax.boxplot(plot_data, showmeans=True)
        ax.set_xticks(range(1, len(response_order) + 1), response_order)
        ax.set_title(population)
        ax.tick_params(axis="x", rotation=30)
    axes[0].set_ylabel("Relative frequency (%)")
    fig.suptitle("PBMC Melanoma Miraclib Samples: Responders vs Non-responders")
    fig.tight_layout()
    fig.savefig(output_dir / "part3_response_boxplots.png", dpi=150)
    plt.close(fig)

    return stats_df


def part_4_analysis(frequency_df: pd.DataFrame) -> None:
    baseline_df = frequency_df[
        (frequency_df["indication"].str.lower() == "melanoma")
        & (frequency_df["sample_type"].str.upper() == "PBMC")
        & (frequency_df["treatment"].str.lower() == "miraclib")
        & (frequency_df["time_from_treatment_start"] == 0)
        & (frequency_df["population"] == "b_cell")
    ].copy()

    baseline_df.to_csv(output_dir / "part4_baseline_subset.csv", index=False)

    baseline_df.groupby("project", as_index=False)["sample"].nunique().rename(
        columns={"sample": "sample_count"}
    ).sort_values("project").to_csv(
        output_dir / "part4_samples_by_project.csv", index=False
    )

    baseline_df.groupby("response", as_index=False)["subject_id"].nunique().rename(
        columns={"subject_id": "subject_count"}
    ).sort_values("response").to_csv(
        output_dir / "part4_subjects_by_response.csv", index=False
    )

    baseline_df.groupby("gender", as_index=False)["subject_id"].nunique().rename(
        columns={"subject_id": "subject_count"}
    ).sort_values("gender").to_csv(
        output_dir / "part4_subjects_by_gender.csv", index=False
    )

    average = round(
        baseline_df[
            (baseline_df["gender"].str.upper() == "M")
            & (baseline_df["response"].str.lower() == "yes")
        ]["count"].mean(),
        2,
    )
    pd.DataFrame(
        [
            {
                "subset": "melanoma male responders, PBMC, miraclib, baseline",
                "population": "b_cell",
                "average_count": average,
            }
        ]
    ).to_csv(output_dir / "part4_average_b_cells_male_responders.csv", index=False)


def main() -> None:
    output_dir.mkdir(exist_ok=True)
    run_loader()

    raw_df = read_raw_counts()
    frequency_df = calculate_frequencies(raw_df)
    frequency_df.to_csv(output_dir / "part2_cell_frequencies.csv", index=False)

    part_3_analysis(frequency_df)
    part_4_analysis(frequency_df)

    print(f"Pipeline complete. Outputs written to {output_dir}.")


if __name__ == "__main__":
    main()
