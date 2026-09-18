# Publish this project to GitHub

The project repository is [Moundirhzr2/aquawatch](https://github.com/Moundirhzr2/aquawatch). The instructions below also describe how to publish your own copy.

Before publishing, inspect `git status` and the files to be included. `.env`, databases, caches, virtual environments and dbt build output are ignored. Keep the Power BI `DataFolder` parameter generic in committed source; configure your own path locally when using Desktop.

Create an empty GitHub repository named `aquawatch`, then follow GitHub's instructions for adding your own remote. Do not use a fabricated username or an unrelated repository. A suitable description is:

> Explainable water-consumption and billing investigations: Python, PostgreSQL, dbt, FastAPI and Power BI. Synthetic data, tested pipelines and an auditable case workflow.

Suggested topics: `data-engineering`, `data-analytics`, `python`, `postgresql`, `dbt`, `fastapi`, `powerbi`, `data-quality`, `portfolio-project`.

Pin the repository to your profile. Keep the dashboard screenshot near the top of the README and link the project from your CV and portfolio. After the first push, inspect the Actions results and resolve any environment-specific failures before adding a CI badge.

The Power BI source passed schema checks and native model refresh/DAX validation. PBIP opening, Desktop refresh and all three populated pages are confirmed by user screenshots. The updated formatting on all three pages is also confirmed, including exact card totals and readable table headers. The user manually confirmed that Billing review district selections update the linked visuals. Do not claim an implemented cloud deployment, real business savings or a company affiliation.
