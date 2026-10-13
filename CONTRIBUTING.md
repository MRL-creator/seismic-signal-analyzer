# Contributing

Use Python 3.10 or newer and a project-local virtual environment. Install with
`python -m pip install -e ".[dev]" build ruff`, then run:

```sh
python -m ruff check --select E9,F63,F7,F82 .
python -m pytest -q
python -m build
```

Tests use bundled or synthetic data and mocked network responses. The Streamlit
smoke check renders the default example without a browser or external service.
Keep new scientific checks deterministic and document units and assumptions.

GitHub Actions runs the checks on each push and pull request, on Linux with
Python 3.10, 3.12, and 3.14, and Windows with Python 3.12. A separate job audits
the currently resolved runtime dependencies with `pip-audit`. The lint gate
checks syntax and definite Python errors; it does not claim full style or
static type coverage. Action versions are pinned to reviewed commit SHAs.

For UI changes, also run `streamlit run app.py` and inspect the actual
application. Do not commit credentials, local environments, or real private
datasets. Explain the change and its verification in the pull request.

