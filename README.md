# NovaWorks Execution Desk
### Meeting to Execution CRM: turn a meeting transcript into assigned work in one click

**The Infinity Hack '26: AI Project Manager Challenge**

Team: `PickA Bite` | Members: `Noor ul Ain Zahid, Hamnah Fatima Khan, Zulaikha Arshad, Fariha Imran ` | Live demo: `https://37uesvnghpuluaqntjnw22.streamlit.app/`

---

## Try it now (demo logins)

Open the live demo and click a quick-login button on the login page, or type an email and the password below.

**Password for every account: `Demo123!`**

| Role | Name | Email |
| --- | --- | --- |
| **Admin** | Admin | `admin@novaworks.example` |
| **Manager** | Ayesha Khan | `ayesha@novaworks.example` |
| **Manager** | Bilal Ahmed | `bilal@novaworks.example` |
| **Manager** | Hina Malik | `hina@novaworks.example` |
| **Agent** | Ali Raza | `ali@novaworks.example` |
| **Agent** | Hamza Shah | `hamza@novaworks.example` |
| **Agent** | Sara Noor | `sara@novaworks.example` |
| **Agent** | Usman Tariq | `usman@novaworks.example` |
| **Agent** | Zain Abbas | `zain@novaworks.example` |
| **Agent** | Maryam Asif | `maryam@novaworks.example` |

**Quick start:** log in as **Admin**, open **Create from transcript**, click **Load Benchmark Transcript**, then **Extract**. You should get **3 projects and 12 tasks**.

---

## The problem
Decisions made in meetings (who does what, by when) get lost. Someone has to retype them into a tracker, names get mistyped, and owners and deadlines slip.

## Our solution
1. The **Admin** pastes a meeting transcript.
2. An **AI model** extracts projects, tasks, owners and deadlines.
3. A **review screen** checks every name and date against the real user database. Problems turn **red** and **saving is blocked** until a human fixes them.
4. One click saves everything in a **single all-or-nothing transaction**.
5. **Managers** and **agents** instantly see their own projects and tasks and update progress.

> **AI proposes, a human confirms.** Unchecked AI output never reaches the database.

## Who sees what

| Role | Projects | Tasks | Extras |
| --- | --- | --- | --- |
| Admin | All | All | Stats, AI extraction, reset demo data |
| Manager | Only their own | Only inside those projects | Update task status |
| Agent | None | Only tasks assigned to them | Update their own task status |

These rules are enforced on the server, not just hidden in the interface.

## Features
- One-click demo login
- AI extraction from a transcript (OpenRouter, structured JSON)
- Review screen with red highlights, "AI said..." hints and dropdown fixes
- Transactional save
- Manager project cards with a progress bar (one block per task)
- Agent task dashboard with deadline indicators (overdue, due soon) and **Mark done**
- Project status updates automatically from its tasks
- **Reset projects and tasks** button for clean demos (users are kept)
- Built-in benchmark result so the official transcript works even without an API key

## How the AI step works
The server sends the transcript plus the real list of managers and agents to OpenRouter and asks for JSON only. Dates must be `YYYY-MM-DD`, emails must be copied from the roster, and unknown people are left blank rather than guessed. The response is cleaned and checked.

```json
{
  "projects": [{
    "name": "UrbanCart",
    "client": "UrbanCart Services",
    "managerEmail": "ayesha@novaworks.example",
    "deadline": "2026-10-20",
    "tasks": [{
      "title": "Backend API Integration",
      "description": "Connect the order and inventory services to the storefront API.",
      "agentEmail": "ali@novaworks.example",
      "deadline": "2026-10-15"
    }]
  }]
}
```

**Checks before saving:** manager and agent emails must exist with the right role, dates must be real, and names, titles and descriptions cannot be empty. The server repeats these checks on save.

## Tech stack
| | Streamlit version | Next.js version |
| --- | --- | --- |
| Language | Python | TypeScript |
| UI | Streamlit | Next.js + Tailwind CSS |
| Database | SQLite | SQLite via Prisma |
| Login | Session + hashed passwords | HTTP-only JWT cookie |
| AI | OpenRouter | OpenRouter |
| Free hosting | Streamlit Community Cloud | Vercel + Neon Postgres |

---

## Setup

### 1. Get an OpenRouter API key
1. Sign up at **https://openrouter.ai**.
2. Open **Keys**, click **Create Key**, and copy it (starts with `sk-or-`).
3. Add a few dollars of credit. The default model, `openai/gpt-4o-mini`, is very cheap.

Never put the key in code or a public repo. No key? The unchanged benchmark transcript still works with a built-in result.

### 2a. Run the Streamlit version
Needs Python 3.10+.

```bash
cd nova-streamlit
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # Windows: copy
```
Edit `.streamlit/secrets.toml`:
```toml
OPENROUTER_API_KEY = "sk-or-your-key"
OPENROUTER_MODEL = "openai/gpt-4o-mini"
```
```bash
streamlit run app.py
```


### 2b. Run the Next.js version
Needs Node.js 20+.

```bash
cd ai-crm
npm install
cp .env.example .env          # Windows: copy
```
Edit `.env`:
```env
DATABASE_URL="file:./dev.db"
AUTH_SECRET="any-long-random-string-32-characters-or-more"
OPENROUTER_API_KEY="sk-or-your-key"
OPENROUTER_MODEL="openai/gpt-4o-mini"
```
```bash
npx prisma generate
npx prisma db push
npx prisma db seed
npm run dev
```
Open streamlit deployed app: https://37uesvnghpuluaqntjnw22.streamlit.app/  

The seed command is safe to repeat; it never duplicates users.

---

## Deploy for free

**Streamlit Community Cloud**
1. Push the `nova-streamlit` files to GitHub (`app.py` and `requirements.txt` at the top level).
2. Go to **share.streamlit.io**, sign in, click **Create app**, pick the repo, and set the main file to `app.py`.
3. In **Advanced settings, Secrets**, paste your `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`.
4. Click **Deploy**.

On the free tier the database resets when the app restarts. The 10 users return automatically, but saved projects do not, so **run the benchmark again just before presenting**.

**Vercel + Neon (Next.js)**
1. Create a free Postgres database at **neon.tech** and copy its connection string.
2. In `prisma/schema.prisma`, change `provider = "sqlite"` to `"postgresql"`, set `DATABASE_URL` to the Neon string, then run `npx prisma db push` and `npx prisma db seed`.
3. In `package.json`, set `"postinstall": "prisma generate"` and `"build": "prisma generate && next build"`.
4. Push to GitHub, import the repo at **vercel.com**, and add `DATABASE_URL`, `AUTH_SECRET`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` and `COOKIE_SECURE=true`.
5. Click **Deploy**.

---

## 3-minute demo script
1. **Login as Admin.** Open **Create from transcript**, click **Load Benchmark Transcript**, then **Extract**.
2. Show **3 projects and 12 tasks** (UrbanCart: Ayesha Khan, due 20 October 2026, 4 tasks).
3. Set one dropdown to "Select...". It turns **red** and **Save is disabled**. Fix it, then **Save to database**.
4. **Login as Ayesha:** she sees only UrbanCart. Change a task status and watch the progress bar.
5. **Login as Ali:** he sees only his tasks. Click **Mark done**.
6. Back as **Admin**, show the updated progress. Use **Reset projects and tasks** before the next run.

**Pitch:** *"We turn meetings into assigned, tracked work in one click, and a human always confirms before anything is saved."*
## Some Images



<img width="1915" height="761" alt="Screenshot 2026-10-07 124720" src="https://github.com/user-attachments/assets/8fbaaece-41fb-4e30-9178-2505e0e9575b" />

<img width="1918" height="763" alt="Screenshot 2026-10-07 124701" src="https://github.com/user-attachments/assets/3c14a048-b621-4157-976d-cd913c0bf73b" />

<img width="1918" height="867" alt="Screenshot 2026-10-07 124528" src="https://github.com/user-attachments/assets/a684dfbb-29ed-4968-9ca4-c05c96e39ab9" />

<img width="1917" height="866" alt="Screenshot 2026-10-07 123903" src="https://github.com/user-attachments/assets/5eb83dc3-93b1-4c2f-9d2c-3271d7ec8e2f" />

## Troubleshooting
| Problem | Fix |
| --- | --- |
| "OPENROUTER_API_KEY is not set" | Add the key to `secrets.toml`, `.env` or hosting secrets, then restart |
| AI error 401 or 403 | Key is wrong or out of credit. Check openrouter.ai |
| Model error | Use `openai/gpt-4o-mini`, or check the model name on openrouter.ai/models |
| Wrong number of tasks | Run the extraction again, or fix it on the review screen |
| Cannot log in | Password is `Demo123!`. Restart the app to re-seed users |
| Data disappeared on Streamlit Cloud | Free-tier restart. Run the benchmark again |

## Limitations
- AI can make mistakes, which is why the review screen exists.
- Demo-grade security (shared demo password). A real version needs password changes, rate limiting and SSO.
- Reads pasted text only; audio transcription is not included yet.

## Future ideas
Audio upload and transcription, drag-and-drop kanban board, task comments and activity log, AI risk flags (overloaded agents, clashing deadlines), email or Slack notifications, and workload charts.

---

## Team:
- Noor ul Ain Zahid
- Hamnah Fatima Khan
- Fariha Imran
- Zulaikha Arshad
