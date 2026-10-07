# NovaWorks Execution Desk (Streamlit)

Meeting transcript in, assigned projects and tasks out. Admin extracts with AI and reviews before saving; managers and agents see only their own work.

## Run locally
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add OPENROUTER_API_KEY
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this folder to a public GitHub repo (`app.py` and `requirements.txt` at the root).
2. Go to share.streamlit.io, sign in with GitHub, click **Create app**, pick the repo, branch `main`, main file `app.py`.
3. Open **Advanced settings > Secrets** and paste:
   ```
   OPENROUTER_API_KEY = "sk-or-..."
   OPENROUTER_MODEL = "openai/gpt-4o-mini"
   ```
4. Click **Deploy**.

## Demo accounts
Password `Demo123!` for all: admin@, ayesha@, bilal@, hina@, ali@, hamza@, sara@, usman@, zain@, maryam@ `novaworks.example`.

## Notes
- Data is stored in `dev.db` (SQLite). On Community Cloud it resets when the app restarts or sleeps; the 10 users are re-seeded automatically. Use a hosted database for persistence.
- Without an API key, the unchanged benchmark transcript still returns 3 projects / 12 tasks from a built-in result.
