# Notebooks

Notebooks explain and visualize results; reusable transformations stay in `src/smartgrid`.

`01_eda.ipynb` is the executed observed-only analysis of the existing processed
Parquets. It calls reusable functions in `smartgrid.features.behaviour`; it does
not rerun ingestion, fit models or materialize windows. The inferred academic
calendar is labelled **PROVISIONAL** pending the supervisor's actual calendar.

On the VM, with the project venv on PATH, PYTHONPATH pointing to the project
`src/`, and Jupyter/cache/temp directories inside the project, execute headlessly:

```sh
jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb
```

Findings and complete aggregate tables are under `reports/EDA.md` and
`reports/eda_*.csv`; all figures are `reports/figures/*.png` at 150 dpi.
Synthetic-only tests are in `tests/test_behaviour.py`.
