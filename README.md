# Safecurecs DSR

A Daily Service Report (DSR) web application for Safecurecs Communication (Fire & Safety
Solutions). Digitizes the paper DSR process: field employees create/submit reports from
their phones, office admins review, approve, reject, or send them back for correction, and
export filtered report data to Excel/PDF. This is **not** an ERP — it only manages DSRs;
the company's existing ERP handles everything else.

## Tech stack

- **Backend**: Python, Django 6, MySQL
- **Frontend**: Django Templates, Bootstrap 5, vanilla JavaScript (no SPA framework)
- **Exports**: openpyxl (Excel), xhtml2pdf (PDF)
- **Auth**: custom user model, login via Employee ID or email

## Local setup

1. **Clone the repo and create a virtual environment**
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS/Linux
   ```

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Create your `.env` file** from the template and fill in real values
   ```
   copy .env.example .env        # Windows
   cp .env.example .env          # macOS/Linux
   ```
   At minimum, set a real `SECRET_KEY` and your local MySQL credentials
   (`DB_USER`/`DB_PASSWORD`). The other defaults in `.env.example` work as-is for local
   development.

4. **Create the MySQL database** (name must match `DB_NAME` in your `.env`, default
   `safecurecs_dsr_db`)
   ```sql
   CREATE DATABASE safecurecs_dsr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

5. **Run migrations**
   ```
   python manage.py migrate
   ```

6. **Create an admin account** — either Django's built-in command:
   ```
   python manage.py createsuperuser
   ```
   or, to create a regular employee account from the CLI:
   ```
   python manage.py create_employee EMP001 employee@example.com First Last --department "Field Ops" --designation Engineer
   ```

7. **Run the development server**
   ```
   python manage.py runserver
   ```
   Visit `http://127.0.0.1:8000/`.

## Running tests

```
python manage.py test
```

Runs the full suite (accounts + dsr apps). No network access or external services are
required — MySQL must be running and reachable per your `.env`, since Django creates a
throwaway test database (`test_<DB_NAME>`) for the run and drops it afterward.

## Project structure

- `accounts/` — custom user model, authentication, profile, dashboards
- `dsr/` — DSR reports, attachments, admin review workflow, exports
- `templates/` — Django templates (Bootstrap 5, mobile-first for employee-facing pages)
- `static/` — CSS, vanilla JS, favicon

See `CLAUDE.md` for the full project specification, architectural decisions, and
deployment notes.
