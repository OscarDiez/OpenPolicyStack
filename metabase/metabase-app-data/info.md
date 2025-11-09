This folder should contain database about metabase user and config

generated : 'When a user creates dashboards, asks questions, or saves any data in Metabase, it gets stored in PostgreSQL, which is the internal database for Metabase. Specifically, Metabase stores these user-created objects (dashboards, questions, etc.) as records in the PostgreSQL database.

Here's how it works:
User interaction (creating a dashboard, saving a question, etc.) happens in the Metabase UI (the website).

The data (dashboards, reports, saved questions) is saved to the Metabase internal database (PostgreSQL in this case) and not in the original data sources (like your SQLite DB).

When you query a data source (e.g., SQLite) and save the query as a question, Metabase stores the query logic, metadata, and results in PostgreSQL.

Dashboards are stored as a collection of references to the questions (or data visualizations) that have been saved, also in PostgreSQL.'