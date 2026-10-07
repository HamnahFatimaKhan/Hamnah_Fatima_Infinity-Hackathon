"""NovaWorks Execution Desk: Meeting to Execution CRM (Streamlit edition).

Roles: ADMIN extracts projects/tasks from a transcript with AI and reviews them before saving.
MANAGER sees only their projects. AGENT sees only their tasks.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

import requests
import streamlit as st

st.set_page_config(page_title="NovaWorks Execution Desk", page_icon=":material/task_alt:", layout="wide")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev.db")
DEMO_PASSWORD = "Demo123!"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SEED_USERS = [
    ("Admin", "admin@novaworks.example", "ADMIN"),
    ("Ayesha Khan", "ayesha@novaworks.example", "MANAGER"),
    ("Bilal Ahmed", "bilal@novaworks.example", "MANAGER"),
    ("Hina Malik", "hina@novaworks.example", "MANAGER"),
    ("Ali Raza", "ali@novaworks.example", "AGENT"),
    ("Hamza Shah", "hamza@novaworks.example", "AGENT"),
    ("Sara Noor", "sara@novaworks.example", "AGENT"),
    ("Usman Tariq", "usman@novaworks.example", "AGENT"),
    ("Zain Abbas", "zain@novaworks.example", "AGENT"),
    ("Maryam Asif", "maryam@novaworks.example", "AGENT"),
]

TASK_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED"]
TASK_LABEL = {"PENDING": "To do", "IN_PROGRESS": "In progress", "COMPLETED": "Done"}
PROJECT_LABEL = {"NOT_STARTED": "Not started", "IN_PROGRESS": "In progress", "COMPLETED": "Completed"}

BENCHMARK_TRANSCRIPT = """NovaWorks Weekly Delivery Sync
Date: Wednesday, 7 October 2026
Attendees: Admin, Ayesha Khan, Bilal Ahmed, Hina Malik

Admin: Good morning, everyone. Three projects kick off from this meeting, so let's agree owners and tasks before we close. First up is UrbanCart. The client is UrbanCart Services, Ayesha Khan is the project manager, and the whole project is due on 20 October 2026.

Ayesha Khan: Understood. I'm splitting it into four tasks. Backend API Integration goes to Ali Raza. He connects the order and inventory services to the storefront API, due 15 October 2026.

Ayesha Khan: Payment Gateway Setup goes to Hamza Shah. He integrates card and wallet checkout with the payment provider, due 14 October 2026.

Ayesha Khan: Product Catalog UI goes to Sara Noor. She builds the browsing, search and filter screens, due 16 October 2026.

Ayesha Khan: QA and Load Testing goes to Usman Tariq. He runs regression and load tests before launch, due 18 October 2026.

Admin: Great. Second project is Finlytics Dashboard for the client Finlytics Ltd. Bilal Ahmed manages it, and the deadline is 30 October 2026.

Bilal Ahmed: Four tasks here as well. Data Pipeline Setup goes to Zain Abbas. He sets up the ingestion jobs that load transaction data into the warehouse, due 21 October 2026.

Bilal Ahmed: Dashboard Charts goes to Maryam Asif. She builds the revenue, cashflow and retention charts, due 25 October 2026.

Bilal Ahmed: Role-based Access goes to Ali Raza. He adds role permissions so finance staff only see their own entities, due 26 October 2026.

Bilal Ahmed: Report Export goes to Sara Noor. She adds scheduled PDF and CSV exports, due 28 October 2026.

Admin: Thanks. Last one is CareBridge Portal for CareBridge Health. Hina Malik is the project manager, and it is due on 5 November 2026.

Hina Malik: Four tasks. Patient Onboarding Flow goes to Hamza Shah. He builds the registration and consent screens, due 28 October 2026.

Hina Malik: Appointment Scheduling goes to Usman Tariq. He builds the booking calendar with clinic availability and reminders, due 30 October 2026.

Hina Malik: Security Audit goes to Zain Abbas. He reviews authentication, data encryption and audit logging, due 2 November 2026.

Hina Malik: Staff Training Docs goes to Maryam Asif. She writes the guides and walkthrough videos for clinic staff, due 3 November 2026.

Admin: Perfect. Three projects, twelve tasks, all owners confirmed. Thanks, everyone."""


def _t(title, desc, agent, deadline):
    return {"title": title, "description": desc, "agentEmail": f"{agent}@novaworks.example", "deadline": deadline}


# Used only when no API key is configured and the benchmark transcript is submitted unchanged.
BENCHMARK_RESULT = [
    {"name": "UrbanCart", "client": "UrbanCart Services", "managerEmail": "ayesha@novaworks.example", "deadline": "2026-10-20",
     "tasks": [
         _t("Backend API Integration", "Connect the order and inventory services to the storefront API.", "ali", "2026-10-15"),
         _t("Payment Gateway Setup", "Integrate card and wallet checkout with the payment provider.", "hamza", "2026-10-14"),
         _t("Product Catalog UI", "Build the browsing, search and filter screens.", "sara", "2026-10-16"),
         _t("QA and Load Testing", "Run regression and load tests before launch.", "usman", "2026-10-18"),
     ]},
    {"name": "Finlytics Dashboard", "client": "Finlytics Ltd", "managerEmail": "bilal@novaworks.example", "deadline": "2026-10-30",
     "tasks": [
         _t("Data Pipeline Setup", "Set up the ingestion jobs that load transaction data into the warehouse.", "zain", "2026-10-21"),
         _t("Dashboard Charts", "Build the revenue, cashflow and retention charts.", "maryam", "2026-10-25"),
         _t("Role-based Access", "Add role permissions so finance staff only see their own entities.", "ali", "2026-10-26"),
         _t("Report Export", "Add scheduled PDF and CSV exports.", "sara", "2026-10-28"),
     ]},
    {"name": "CareBridge Portal", "client": "CareBridge Health", "managerEmail": "hina@novaworks.example", "deadline": "2026-11-05",
     "tasks": [
         _t("Patient Onboarding Flow", "Build the registration and consent screens.", "hamza", "2026-10-28"),
         _t("Appointment Scheduling", "Build the booking calendar with clinic availability and reminders.", "usman", "2026-10-30"),
         _t("Security Audit", "Review authentication, data encryption and audit logging.", "zain", "2026-11-02"),
         _t("Staff Training Docs", "Write the guides and walkthrough videos for clinic staff.", "maryam", "2026-11-03"),
     ]},
]

# --------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN','MANAGER','AGENT'))
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, client TEXT NOT NULL,
  manager_id TEXT NOT NULL REFERENCES users(id), deadline TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'NOT_STARTED' CHECK (status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL, description TEXT NOT NULL,
  assigned_agent_id TEXT NOT NULL REFERENCES users(id), manager_id TEXT NOT NULL REFERENCES users(id),
  deadline TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','IN_PROGRESS','COMPLETED')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def new_id(prefix="c"):
    return prefix + secrets.token_hex(10)


def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${digest}"


def verify_pw(password, stored):
    salt = stored.split("$", 1)[0]
    return hmac.compare_digest(hash_pw(password, salt), stored)


@st.cache_resource
def init_db():
    """Create tables and seed the 10 demo users. Safe to run repeatedly (no duplicates)."""
    with db() as c:
        c.executescript(SCHEMA)
        for name, email, role in SEED_USERS:
            row = c.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                c.execute("UPDATE users SET name = ?, role = ? WHERE email = ?", (name, role, email))
            else:
                c.execute(
                    "INSERT INTO users (id, name, email, password, role) VALUES (?,?,?,?,?)",
                    (new_id("u"), name, email, hash_pw(DEMO_PASSWORD), role),
                )
    return True


def get_user_by_email(email):
    with db() as c:
        r = c.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(r) if r else None


def get_user(uid):
    with db() as c:
        r = c.execute("SELECT id, name, email, role FROM users WHERE id = ?", (uid,)).fetchone()
        return dict(r) if r else None


def people(role):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id, name, email FROM users WHERE role = ? ORDER BY name", (role,))]


def fetch_projects(user):
    """Admin: all. Manager: only their own. Agent: none."""
    if user["role"] == "AGENT":
        return []
    with db() as c:
        q = "SELECT p.*, m.name AS manager_name FROM projects p JOIN users m ON m.id = p.manager_id"
        args = ()
        if user["role"] == "MANAGER":
            q += " WHERE p.manager_id = ?"
            args = (user["id"],)
        q += " ORDER BY p.deadline, p.created_at"
        projects = [dict(r) for r in c.execute(q, args)]
        for p in projects:
            p["tasks"] = [
                dict(r)
                for r in c.execute(
                    "SELECT t.*, a.name AS agent_name FROM tasks t JOIN users a ON a.id = t.assigned_agent_id "
                    "WHERE t.project_id = ? ORDER BY t.deadline, t.created_at",
                    (p["id"],),
                )
            ]
    return projects


def fetch_tasks(user):
    """Agent: only assigned to them. Manager: only inside their projects. Admin: all."""
    q = (
        "SELECT t.*, a.name AS agent_name, p.name AS project_name, p.client AS project_client "
        "FROM tasks t JOIN users a ON a.id = t.assigned_agent_id JOIN projects p ON p.id = t.project_id"
    )
    args = ()
    if user["role"] == "AGENT":
        q += " WHERE t.assigned_agent_id = ?"
        args = (user["id"],)
    elif user["role"] == "MANAGER":
        q += " WHERE p.manager_id = ?"
        args = (user["id"],)
    q += " ORDER BY t.deadline, t.created_at"
    with db() as c:
        return [dict(r) for r in c.execute(q, args)]


def stats():
    with db() as c:
        return (
            c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
            c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        )


def set_task_status(user, task_id, status):
    if status not in TASK_STATUSES:
        return False, "Invalid status."
    with db() as c:
        t = c.execute(
            "SELECT t.id, t.project_id, t.assigned_agent_id, p.manager_id FROM tasks t "
            "JOIN projects p ON p.id = t.project_id WHERE t.id = ?",
            (task_id,),
        ).fetchone()
        if not t:
            return False, "Task not found."
        allowed = (
            user["role"] == "ADMIN"
            or (user["role"] == "MANAGER" and t["manager_id"] == user["id"])
            or (user["role"] == "AGENT" and t["assigned_agent_id"] == user["id"])
        )
        if not allowed:
            return False, "Your role cannot change this task."
        c.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        statuses = [r[0] for r in c.execute("SELECT status FROM tasks WHERE project_id = ?", (t["project_id"],))]
        if statuses and all(s == "COMPLETED" for s in statuses):
            pstatus = "COMPLETED"
        elif any(s != "PENDING" for s in statuses):
            pstatus = "IN_PROGRESS"
        else:
            pstatus = "NOT_STARTED"
        c.execute("UPDATE projects SET status = ? WHERE id = ?", (pstatus, t["project_id"]))
    return True, ""


def insert_projects(projects):
    """Transactional save: either every project and task is written, or none."""
    with db() as c:
        mgrs = {r["email"]: r["id"] for r in c.execute("SELECT id, email FROM users WHERE role = 'MANAGER'")}
        agts = {r["email"]: r["id"] for r in c.execute("SELECT id, email FROM users WHERE role = 'AGENT'")}
        n_tasks = 0
        for p in projects:
            mid = mgrs[p["managerEmail"]]
            pid = new_id("p")
            c.execute(
                "INSERT INTO projects (id, name, client, manager_id, deadline, status) VALUES (?,?,?,?,?, 'NOT_STARTED')",
                (pid, p["name"], p["client"], mid, p["deadline"]),
            )
            for t in p["tasks"]:
                c.execute(
                    "INSERT INTO tasks (id, project_id, title, description, assigned_agent_id, manager_id, deadline, status) "
                    "VALUES (?,?,?,?,?,?,?, 'PENDING')",
                    (new_id("t"), pid, t["title"], t["description"], agts[t["agentEmail"]], mid, t["deadline"]),
                )
                n_tasks += 1
    return len(projects), n_tasks


def reset_demo_data():
    with db() as c:
        t = c.execute("DELETE FROM tasks").rowcount
        p = c.execute("DELETE FROM projects").rowcount
    return p, t


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------

def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d") == s
    except (ValueError, TypeError):
        return False


def check_project(p, manager_emails, agent_emails):
    """Returns flags where True means the field is invalid."""
    blank = lambda s: not (s or "").strip()
    return {
        "name": blank(p["name"]),
        "client": blank(p["client"]),
        "manager": p["managerEmail"] not in manager_emails,
        "deadline": not valid_date(p["deadline"]),
        "no_tasks": len(p["tasks"]) == 0,
        "tasks": [
            {
                "title": blank(t["title"]),
                "description": blank(t["description"]),
                "agent": t["agentEmail"] not in agent_emails,
                "deadline": not valid_date(t["deadline"]),
            }
            for t in p["tasks"]
        ],
    }


def count_issues(flags):
    n = sum(bool(flags[k]) for k in ("name", "client", "manager", "deadline", "no_tasks"))
    for t in flags["tasks"]:
        n += sum(bool(v) for v in t.values())
    return n


# --------------------------------------------------------------------------------------
# AI extraction (OpenRouter)
# --------------------------------------------------------------------------------------

class ExtractionError(Exception):
    pass


def get_secret(name, default=""):
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def build_system_prompt(roster):
    lines = "\n".join(f"- {p['name']} <{p['email']}> ({p['role']})" for p in roster)
    return f"""You convert meeting transcripts into structured project plans for NovaWorks.

Return ONLY one JSON object, with no commentary and no markdown, in exactly this shape:
{{
  "projects": [
    {{
      "name": "short project name",
      "client": "client organisation name",
      "managerEmail": "email from the roster",
      "deadline": "YYYY-MM-DD",
      "tasks": [
        {{"title": "short task title", "description": "one or two sentences describing the work",
          "agentEmail": "email from the roster", "deadline": "YYYY-MM-DD"}}
      ]
    }}
  ]
}}

Rules:
1. One entry per distinct project discussed. One task for every task assigned in the meeting. Do not invent, merge or drop tasks.
2. managerEmail and agentEmail must be copied exactly from the roster, matched to the person by name.
3. If a person cannot be matched to the roster, use an empty string "" instead of guessing.
4. All dates must be YYYY-MM-DD. Resolve relative dates using the meeting date in the transcript. If the year is missing, use the meeting year.
5. If a value is not stated in the transcript, use an empty string "".
6. The project name is the short product name (for example "UrbanCart"); the client is the organisation named as the client.

Roster of people who can be assigned:
{lines}"""


def _s(v):
    return "" if v is None else str(v).strip()


def normalize(raw):
    projects = raw.get("projects") if isinstance(raw, dict) else None
    if not isinstance(projects, list):
        raise ExtractionError("The AI response did not contain a projects list. Try again.")
    out = []
    for p in projects:
        p = p if isinstance(p, dict) else {}
        tasks = p.get("tasks") if isinstance(p.get("tasks"), list) else []
        out.append({
            "name": _s(p.get("name")),
            "client": _s(p.get("client")),
            "managerEmail": _s(p.get("managerEmail")).lower(),
            "deadline": _s(p.get("deadline")),
            "tasks": [
                {
                    "title": _s(t.get("title")),
                    "description": _s(t.get("description")),
                    "agentEmail": _s(t.get("agentEmail")).lower(),
                    "deadline": _s(t.get("deadline")),
                }
                for t in tasks if isinstance(t, dict)
            ],
        })
    return out


def parse_json_loose(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        a, b = cleaned.find("{"), cleaned.rfind("}")
        if a != -1 and b > a:
            try:
                return json.loads(cleaned[a:b + 1])
            except json.JSONDecodeError:
                pass
    raise ExtractionError("The AI returned text that is not valid JSON. Try again.")


def extract_from_transcript(transcript):
    key = get_secret("OPENROUTER_API_KEY")
    if not key:
        if transcript.strip() == BENCHMARK_TRANSCRIPT.strip():
            return json.loads(json.dumps(BENCHMARK_RESULT)), "offline-benchmark"
        raise ExtractionError(
            "OPENROUTER_API_KEY is not set. Add it in Secrets to extract from your own transcripts."
        )
    roster = [{**u, "role": "MANAGER"} for u in people("MANAGER")] + [{**u, "role": "AGENT"} for u in people("AGENT")]
    model = get_secret("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    try:
        res = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "NovaWorks Meeting to Execution"},
            json={
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": build_system_prompt(roster)},
                    {"role": "user", "content": f"Transcript:\n\n{transcript}"},
                ],
            },
            timeout=90,
        )
    except requests.RequestException:
        raise ExtractionError("Could not reach the AI provider. Check the connection and try again.")
    if res.status_code != 200:
        raise ExtractionError(f"The AI provider returned {res.status_code}. {res.text[:200]}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        raise ExtractionError("The AI provider returned an unexpected response. Try again.")
    return normalize(parse_json_loose(content)), "openrouter"


# --------------------------------------------------------------------------------------
# UI helpers
# --------------------------------------------------------------------------------------

def flash(kind, message):
    st.session_state["flash"] = (kind, message)


def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        {"error": st.error, "success": st.success, "info": st.info}[f[0]](f[1])


def due_text(deadline, done):
    try:
        due = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return f":red[Invalid date {deadline}]"
    pretty = due.strftime("%d %b %Y")
    if done:
        return f":green[Finished, was due {pretty}]"
    diff = (due - date.today()).days
    if diff < 0:
        return f":red[Overdue by {-diff} day{'s' if diff != -1 else ''}, {pretty}]"
    if diff == 0:
        return f":orange[Due today, {pretty}]"
    if diff <= 3:
        return f":orange[Due in {diff} day{'s' if diff != 1 else ''}, {pretty}]"
    return f"Due {pretty}"


def project_badge(status):
    color = {"COMPLETED": "green", "IN_PROGRESS": "orange", "NOT_STARTED": "gray"}[status]
    return f":{color}-badge[{PROJECT_LABEL[status]}]"


def on_status_change(task_id, key):
    user = current_user()
    ok, msg = set_task_status(user, task_id, st.session_state[key])
    if not ok:
        flash("error", msg)


def status_control(task, ctx):
    key = f"{ctx}_status_{task['id']}"
    st.session_state[key] = task["status"]  # always mirror the database
    st.radio(
        "Status", TASK_STATUSES, key=key, horizontal=True, label_visibility="collapsed",
        format_func=lambda s: TASK_LABEL[s], on_change=on_status_change, args=(task["id"], key),
    )


def current_user():
    uid = st.session_state.get("uid")
    return get_user(uid) if uid else None


def login(email, password):
    u = get_user_by_email(email or "")
    if u and verify_pw(password or "", u["password"]):
        st.session_state["uid"] = u["id"]
        st.session_state.pop("draft", None)
    else:
        flash("error", "Email or password is incorrect.")


def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


# --------------------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------------------

def login_screen():
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown("# NovaWorks Execution Desk")
        st.markdown("### Meeting notes in. Assigned work out.")
        st.write("Paste a transcript, check what the AI found, and publish projects and tasks to the right managers and agents in one step.")
        st.caption("Infinity Hack '26 demo build")
    with right:
        show_flash()
        st.subheader("Sign in")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                login(email, password)
                st.rerun()
        st.subheader("Demo quick login")
        st.caption("One click signs in with the demo password.")
        quick = [
            ("Login as Admin", "admin@novaworks.example"),
            ("Login as Manager Ayesha", "ayesha@novaworks.example"),
            ("Login as Agent Ali", "ali@novaworks.example"),
            ("Login as Agent Hamza", "hamza@novaworks.example"),
        ]
        cols = st.columns(2)
        for i, (label, email) in enumerate(quick):
            cols[i % 2].button(label, key=f"quick_{i}", use_container_width=True, on_click=login, args=(email, DEMO_PASSWORD))


def sidebar(user):
    with st.sidebar:
        st.markdown("### NovaWorks Execution Desk")
        st.write(f"**{user['name']}**")
        st.caption({"ADMIN": "Admin", "MANAGER": "Project manager", "AGENT": "Agent"}[user["role"]])
        st.button("Sign out", on_click=logout, use_container_width=True)


def project_card(p, ctx, editable):
    with st.container(border=True):
        top, badge = st.columns([3, 2])
        top.markdown(f"#### {p['name']}")
        top.caption(f"Client: {p['client']}. Manager: {p['manager_name']}.")
        badge.markdown(f"{project_badge(p['status'])} &nbsp; {due_text(p['deadline'], p['status'] == 'COMPLETED')}")
        total = len(p["tasks"])
        done = sum(t["status"] == "COMPLETED" for t in p["tasks"])
        st.progress(done / total if total else 0.0, text=f"{done} of {total} tasks done")
        if editable:
            for t in p["tasks"]:
                c1, c2 = st.columns([3, 3])
                c1.markdown(f"**{t['title']}**")
                c1.caption(f"{t['agent_name']}  \n{due_text(t['deadline'], t['status'] == 'COMPLETED')}")
                with c2:
                    status_control(t, ctx)
                st.divider()


def admin_screen(user):
    st.title("Admin workspace")
    st.caption("Turn a meeting transcript into projects and tasks, and watch delivery across the company.")

    head, reset_col = st.columns([4, 1])
    with reset_col.popover("Reset projects & tasks", use_container_width=True):
        st.warning("This deletes every project and task. The 10 demo users stay.")
        if st.button("Yes, delete projects and tasks", type="primary"):
            p, t = reset_demo_data()
            st.session_state.pop("draft", None)
            flash("success", f"Removed {p} projects and {t} tasks.")
            st.rerun()

    show_flash()
    view = st.radio("View", ["Overview", "Create from transcript"], horizontal=True, key="admin_view", label_visibility="collapsed")

    if view == "Overview":
        n_projects, n_tasks, n_users = stats()
        a, b, c = st.columns(3)
        a.metric("Projects", n_projects)
        b.metric("Tasks", n_tasks)
        c.metric("Users", n_users)
        projects = fetch_projects(user)
        if not projects:
            st.info("No projects yet. Open \"Create from transcript\" to add the first ones.")
        for p in projects:
            project_card(p, "admin", editable=False)
    else:
        create_screen()


def collect_draft(d, mgr, agt):
    """Read the current (possibly edited) values of the review form back into project dicts."""
    did, out = d["id"], []
    for i, p in enumerate(d["projects"]):
        mname = st.session_state.get(f"d{did}_p{i}_mgr", mgr["rev"].get(p["managerEmail"], mgr["ph"]))
        proj = {
            "name": st.session_state.get(f"d{did}_p{i}_name", p["name"]),
            "client": st.session_state.get(f"d{did}_p{i}_client", p["client"]),
            "managerEmail": mgr["map"].get(mname, ""),
            "deadline": st.session_state.get(f"d{did}_p{i}_deadline", p["deadline"]).strip(),
            "tasks": [],
        }
        for j, t in enumerate(p["tasks"]):
            aname = st.session_state.get(f"d{did}_p{i}_t{j}_agent", agt["rev"].get(t["agentEmail"], agt["ph"]))
            proj["tasks"].append({
                "title": st.session_state.get(f"d{did}_p{i}_t{j}_title", t["title"]),
                "description": st.session_state.get(f"d{did}_p{i}_t{j}_desc", t["description"]),
                "agentEmail": agt["map"].get(aname, ""),
                "deadline": st.session_state.get(f"d{did}_p{i}_t{j}_deadline", t["deadline"]).strip(),
            })
        out.append(proj)
    return out


def dropdown_model(users, placeholder):
    return {"ph": placeholder, "map": {u["name"]: u["email"] for u in users}, "rev": {u["email"]: u["name"] for u in users},
            "options": [placeholder] + [u["name"] for u in users]}


def save_draft():
    d = st.session_state.get("draft")
    if not d:
        return
    mgr = dropdown_model(people("MANAGER"), "Select a manager")
    agt = dropdown_model(people("AGENT"), "Select an agent")
    projects = collect_draft(d, mgr, agt)
    issues = sum(count_issues(check_project(p, set(mgr["map"].values()), set(agt["map"].values()))) for p in projects)
    if issues:
        flash("error", f"{issues} field(s) are still invalid. Fix the red fields and save again.")
        return
    try:
        n_p, n_t = insert_projects(projects)
    except Exception as e:  # noqa: BLE001
        flash("error", f"Nothing was saved. {e}")
        return
    st.session_state.pop("draft", None)
    st.session_state["transcript"] = ""
    st.session_state["admin_view"] = "Overview"
    flash("success", f"Saved {n_p} projects and {n_t} tasks.")


def create_screen():
    d = st.session_state.get("draft")
    if not d:
        st.subheader("Meeting transcript")
        st.button("Load Benchmark Transcript", on_click=lambda: st.session_state.update(transcript=BENCHMARK_TRANSCRIPT))
        transcript = st.text_area("Paste the transcript", key="transcript", height=320, label_visibility="collapsed",
                                  placeholder="Paste a meeting transcript here...")
        if st.button("Extract projects and tasks", type="primary", disabled=len(transcript.strip()) < 40):
            try:
                with st.spinner("Reading the transcript..."):
                    projects, source = extract_from_transcript(transcript)
                st.session_state["draft_counter"] = st.session_state.get("draft_counter", 0) + 1
                st.session_state["draft"] = {"id": st.session_state["draft_counter"], "projects": projects, "source": source}
                st.rerun()
            except ExtractionError as e:
                st.error(str(e))
        return

    # ---- Review & validation screen ----
    did = d["id"]
    mgr = dropdown_model(people("MANAGER"), "Select a manager")
    agt = dropdown_model(people("AGENT"), "Select an agent")
    current = collect_draft(d, mgr, agt)
    flags = [check_project(p, set(mgr["map"].values()), set(agt["map"].values())) for p in current]
    issues = sum(count_issues(f) for f in flags)
    n_tasks = sum(len(p["tasks"]) for p in current)

    bad_keys = []
    def mark(bad, key):
        if bad:
            bad_keys.append(key)
        return bad

    def lab(text, bad, hint=""):
        return f":red[{text} (needs fixing{': ' + hint if hint else ''})]" if bad else text

    with st.container(border=True):
        a, b, c, e = st.columns([3, 1.4, 1, 1.4])
        a.markdown("#### Review before saving")
        src = " Built-in benchmark result (no API key set)." if d["source"] == "offline-benchmark" else ""
        a.caption(f"{len(current)} projects and {n_tasks} tasks found.{src}")
        (b.markdown(f":red-badge[{issues} to fix]") if issues else b.markdown(":green-badge[All checks passed]"))
        c.button("Discard", on_click=lambda: st.session_state.pop("draft", None), use_container_width=True)
        e.button("Save to database", type="primary", disabled=issues > 0 or not current, on_click=save_draft, use_container_width=True)
    if issues:
        st.error("Saving is blocked until every red field is resolved. Use the dropdowns to choose the right person or correct the value.")

    show_flash()

    for i, p in enumerate(d["projects"]):
        f, cur = flags[i], current[i]
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1.5])
            k = f"d{did}_p{i}"
            c1.text_input(lab("Project", mark(f["name"], f"{k}_name")), value=p["name"], key=f"{k}_name")
            c2.text_input(lab("Client", mark(f["client"], f"{k}_client")), value=p["client"], key=f"{k}_client")
            ai_m = f"AI said {p['managerEmail']!r}" if p["managerEmail"] else "AI left this blank"
            c3.selectbox(lab("Manager", mark(f["manager"], f"{k}_mgr"), ai_m), mgr["options"],
                         index=mgr["options"].index(mgr["rev"].get(p["managerEmail"], mgr["ph"])), key=f"{k}_mgr")
            c4.text_input(lab("Deadline (YYYY-MM-DD)", mark(f["deadline"], f"{k}_deadline")), value=p["deadline"], key=f"{k}_deadline")
            if f["no_tasks"]:
                st.error("This project has no tasks.")
            for j, t in enumerate(p["tasks"]):
                tf = f["tasks"][j]
                kt = f"{k}_t{j}"
                with st.container(border=True):
                    t1, t2, t3 = st.columns([3, 2, 1.5])
                    t1.text_input(lab("Task", mark(tf["title"], f"{kt}_title")), value=t["title"], key=f"{kt}_title")
                    ai_a = f"AI said {t['agentEmail']!r}" if t["agentEmail"] else "AI left this blank"
                    t2.selectbox(lab("Assigned agent", mark(tf["agent"], f"{kt}_agent"), ai_a), agt["options"],
                                 index=agt["options"].index(agt["rev"].get(t["agentEmail"], agt["ph"])), key=f"{kt}_agent")
                    t3.text_input(lab("Deadline (YYYY-MM-DD)", mark(tf["deadline"], f"{kt}_deadline")), value=t["deadline"], key=f"{kt}_deadline")
                    st.text_area(lab("Description", mark(tf["description"], f"{kt}_desc")), value=t["description"], key=f"{kt}_desc", height=70)

    if bad_keys:
        sel = ",".join(
            f'.st-key-{k} [data-baseweb="input"],.st-key-{k} [data-baseweb="select"]>div,.st-key-{k} [data-baseweb="textarea"]'
            for k in bad_keys
        )
        st.markdown(f"<style>{sel}{{border:2px solid #c4342b !important;background:#fbe6e4 !important;}}</style>", unsafe_allow_html=True)


def manager_screen(user):
    st.title("Your projects")
    st.caption("Track delivery and update task status for the projects you manage.")
    show_flash()
    projects = fetch_projects(user)
    if not projects:
        st.info("No projects assigned to you yet. They appear here once an admin creates them from a meeting transcript.")
    for p in projects:
        project_card(p, "mgr", editable=True)


def agent_screen(user):
    tasks = fetch_tasks(user)
    open_n = sum(t["status"] != "COMPLETED" for t in tasks)
    st.title("My tasks")
    st.caption(f"{open_n} open, {len(tasks) - open_n} done.")
    show_flash()
    flt = st.radio("Filter", ["Open", "Done", "All"], horizontal=True, label_visibility="collapsed")
    shown = [t for t in tasks if flt == "All" or (flt == "Done") == (t["status"] == "COMPLETED")]
    if not shown:
        st.info("Nothing assigned to you yet." if not tasks else "No tasks in this view. Switch the filter to see others.")
    cols = st.columns(2)
    for i, t in enumerate(shown):
        with cols[i % 2].container(border=True):
            st.markdown(f":blue-badge[{t['project_name']}] &nbsp; {due_text(t['deadline'], t['status'] == 'COMPLETED')}")
            st.markdown(f"**{t['title']}**")
            st.caption(t["description"])
            status_control(t, "agent")
            if t["status"] != "COMPLETED":
                st.button("Mark done", key=f"done_{t['id']}", type="primary",
                          on_click=lambda tid=t["id"]: set_task_status(current_user(), tid, "COMPLETED"))


def main():
    init_db()
    user = current_user()
    if not user:
        login_screen()
        return
    sidebar(user)
    {"ADMIN": admin_screen, "MANAGER": manager_screen, "AGENT": agent_screen}[user["role"]](user)


main()
