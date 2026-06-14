# Loblaw Clinical Trial

This repository analyzes immune cell population counts from `cell-count.csv` for Loblaw Bio's clinical trial.

## Run In GitHub Codespaces

Install dependencies:

```bash
make setup
```

Run the full reproducible pipeline:

```bash
make pipeline
```

Start the interactive dashboard:

```bash
make dashboard
```

The dashboard runs on port `8501`. In GitHub Codespaces, open the forwarded port URL for port `8501`.

Local dashboard link:

```text should say something like
http://localhost:8501
```

## Pipeline Outputs

`make pipeline` performs the full analysis from start to finish:

1. Runs `load_data.py` to create `cell_counts.db`.
2. Loads all rows from `cell-count.csv` into SQLite.
3. Computes Part 2 sample-level cell population frequencies.
4. Computes Part 3 responder versus non-responder statistics and boxplots.
5. Computes Part 4 baseline subset summaries.

Generated files are written to `outputs/`:

- `part2_cell_frequencies.csv`
- `part3_analysis_cohort.csv`
- `part3_population_statistics.csv`
- `part3_response_boxplots.png`
- `part4_baseline_subset.csv`
- `part4_samples_by_project.csv`
- `part4_subjects_by_response.csv`
- `part4_subjects_by_gender.csv`
- `part4_average_b_cells_male_responders.csv`

The notebooks provide readable analysis walkthroughs:

- `initial_analysis.ipynb`: Part 2 data overview
- `statistical_analysis.ipynb`: Part 3 statistical analysis
- `data_subset_analysis.ipynb`: Part 4 data subset analysis

## Database Schema

The SQLite database is created by `load_data.py` as `cell-count.db`.

The schema is normalized into four tables:

### `subjects`

One row per biological subject.

Columns:

- `subject_id`
- `project`
- `indication`
- `age`
- `gender`

Subject-level metadata belongs here because it is shared across multiple samples from the same patient.

### `samples`

One row per biological sample.

Columns:

- `sample_id`
- `subject_id`
- `sample_type`
- `treatment`
- `response`
- `time_from_treatment_start`

Sample-level metadata belongs here because treatment time, sample type, and response are used frequently for filtering analytical cohorts.

### `cell_populations`

Lookup table for immune cell population names.

Columns:

- `population_id`
- `population_name`

This avoids hard-coding population names into every count row and allows additional populations to be added later.

### `cell_counts`

Long-format count table with one row per sample and population.

Columns:

- `sample_id`
- `population_id`
- `cell_count`

This design avoids storing immune populations as separate repeated columns. It makes population-level queries, groupings, and future additions easier.

## Schema Rationale And Scaling

The input CSV is wide: each sample has columns such as `b_cell`, `cd8_t_cell`, `cd4_t_cell`, `nk_cell`, and `monocyte`. The database stores these counts in long format instead:

```text
sample_id    population      cell_count
sample00000  b_cell          10908
sample00000  cd8_t_cell      24440
```

This scales better if there are hundreds of projects, thousands of samples, and many analytics because:

- New immune populations can be added as rows in `cell_populations`, not as new database columns.
- Filtering by project, treatment, indication, response, sample type, and timepoint is efficient through the `subjects` and `samples` tables.
- Different analyses can reuse the same raw schema and compute derived metrics, such as percentages, medians, statistical tests, and subset summaries, without changing the database.
- The `cell_counts` table remains narrow and analytics-friendly for SQL joins, pandas groupbys, and dashboard filtering.
- Indexes on sample and response-related fields help common cohort-selection queries.

The database is intentionally used for raw data management. Mathematical analysis is performed in the notebooks and `run_pipeline.py`, keeping the loader focused on reproducible ingestion.

## Code Structure

```text
cell-count.csv                 Source data
load_data.py                   Part 1 database schema and CSV loader
run_pipeline.py                Noninteractive pipeline for Parts 1-4
dashboard.py                   Streamlit dashboard
initial_analysis.ipynb         Part 2 notebook
statistical_analysis.ipynb     Part 3 notebook
data_subset_analysis.ipynb     Part 4 notebook
requirements.txt               Python dependencies
Makefile                       Grading entry points
```

`load_data.py` is deliberately small and focused: it initializes SQLite and loads raw data.

`run_pipeline.py` mirrors the notebook calculations in script form so automated graders can reproduce outputs without opening notebooks.

The notebooks are kept separate by analysis question so the work is easier to review:

- Part 2 focuses on sample-level relative frequencies.
- Part 3 focuses on responder versus non-responder statistical testing.
- Part 4 focuses on baseline subset counts and the requested B-cell average.

`dashboard.py` provides an interactive Streamlit view for filtering the cohort and inspecting relative frequency summaries.
