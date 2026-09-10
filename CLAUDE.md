# Safecurecs DSR — Project Context

## Full Project Specification (v1.0)

### Project Overview

Project Name: SafecurecsCommunication_DSR
Company: Safecurecs Communication (Fire & Safety Solutions)
Project Type: Production Web Application

The company already has a complete ERP system. This application is **NOT** an ERP — it is
**only** for managing Daily Service Reports (DSR). Used daily by real employees and office
staff. Primary objective: digitize the Daily Service Report process with a simple, fast,
secure, professional web application.

### Objectives

- Employees submit DSR online
- Admins review submitted reports
- Admins approve or reject reports
- Maintain complete report history
- Generate professional reports
- Export reports to PDF and Excel
- Works on desktop, tablet and mobile
- Lightweight; avoid unnecessary complexity
- Employee should complete one DSR in 3-5 minutes

### Out of scope (do not build)

Attendance, Leave Management, Payroll, Inventory, Quotation Management, CRM, Purchase,
Sales, Complaint Ticket System, AMC Management, Billing, Finance, Customer Portal, Mobile
Application, Google Maps API Integration, or any feature unrelated to DSR.

### User roles (only two)

1. **Admin** (office users): manage employees, view all DSR, search, filter, review,
   approve, reject, export reports, view dashboard.
2. **Employee** (field/sales engineers): login, create DSR, save draft, submit DSR, view
   own reports, edit rejected reports, update own profile.

Employees must **never** access another employee's reports.

### Tech stack (spec baseline)

- Backend: Python, Django (latest stable), MySQL.
- Frontend: Django Templates, HTML5, Bootstrap 5, CSS, Vanilla JavaScript.
- No React. No Vue. No Angular.

### Project principles

Simple, Professional, Responsive, Production Ready, Secure, Maintainable, Scalable,
Reusable. Follow Django Best Practices. Use Class Based Views wherever suitable. Never
duplicate code. Never generate unnecessary modules.

### Authentication

Login with Employee ID OR Email + Password. Role-based authentication. Secure password
hashing. CSRF protection. Session authentication. Users can change password. No Email OTP.
No SMS OTP.

### Project workflow

Employee Login → Employee Dashboard → Create New DSR → Fill DSR → Upload Project Photos →
Save Draft OR Submit → Admin Review → Approve OR Reject. If Approved: report becomes
final. If Rejected: employee edits the same report and resubmits.

### DSR status (only these four)

Draft, Submitted, Approved, Rejected.

### DSR form structure

- **Section 1 — General Information:** Auto Generated DSR Number, Visit Date, Employee
  Name, Status, Purpose of Visit (Installation, Service, Inspection, AMC, Meeting, Survey,
  Other).
- **Section 2 — Client Details:** Client Name, Company Name, Contact Person, Contact
  Number, Email (optional).
- **Section 3 — Project Details:** Project Name, Project Address, Google Maps Link (store
  URL/coordinates only, NO Maps API), Project Type (Residential, Commercial, Industrial,
  Hospital, School/College, Hotel, Office, Factory, Warehouse, Government, Other), Building
  Size (Small, Medium, Large), Built-up Area (free text, e.g. "2500 Sq.ft"), Project Stage
  (New Construction, Under Construction, Existing Building, Renovation), Project Photos
  (multiple images).
- **Section 4 — Visit Information:** Work Done, Remarks, Next Follow-up Date (optional).
- **Section 5 — Attachments:** multiple uploads; supported types JPG, JPEG, PNG, PDF; max
  upload size configurable.
- **Section 6 — Buttons:** Save Draft, Submit.

### Admin review

Admin can: open DSR, view complete report, view uploaded images, open Google Maps link,
view attachments, write admin remarks, Approve, Reject, Send back for correction.

### Reports

- Employee: "My Reports" with status filter, date filter, search.
- Admin: "All Reports" with filters by Employee, Client, Project Type, Status, Date;
  search; Export PDF; Export Excel.

### Employee profile

- Editable: Profile Photo, Email, Mobile Number.
- Read-only: Employee ID, Name, Department, Designation, Role.

### Database design

Normalized. Proper Foreign Keys. Separate attachment model. `created_at`/`updated_at`
timestamps. Auto-generate DSR numbers. Store approval information inside DSR.

### File uploads

Multiple files. JPG, JPEG, PNG, PDF. Store securely. Validate uploaded files.

### User interface

Modern, minimal, professional. Bootstrap 5. White background, blue primary theme.
Responsive sidebar, navbar, tables, cards. Mobile-first. Avoid unnecessary animations.

**MOBILE-FIRST PRIORITY (Critical):**
Employees will use this application PRIMARILY ON MOBILE PHONES in the field. Desktop is
secondary for employees; admins use desktop. Every employee-facing screen must be
designed phone-first:
- Large touch-friendly inputs and buttons (min 44px touch targets), adequate spacing.
- DSR form: single-column layout on mobile, clearly separated sections (stacked cards or
  accordion), minimal typing — prefer dropdowns/date pickers over free text where the
  spec allows.
- File/photo upload must work smoothly from the phone camera and gallery (input
  accept="image/*,.pdf" with capture support for photos).
- Lists/tables (My Reports) must render as stacked cards on small screens, not
  horizontally-scrolling tables.
- Sticky/easily reachable Save Draft and Submit buttons on the DSR form on mobile.
- Fast page loads — no heavy assets. Test all employee pages at 360px-414px viewport
  widths.
- Employee should still complete one DSR in 3-5 minutes ON A PHONE.

### Security

Role-based authorization. Login required. Object-level permissions — employees only
access their own reports. CSRF protection. Password hashing. Secure sessions. Validate
uploaded files.

### Code quality

Clean, readable, modular code. Django Best Practices. No hardcoded values. Reuse
components. Keep business logic separate. Production-ready code.

### Development process

Never build the entire project at once. Develop in phases. Each phase: 1) Analyze existing
project, 2) Explain implementation plan, 3) Implement only requested scope, 4) Run tests,
5) Explain files created/modified, 6) Stop and wait. Never continue automatically.

### Project goal

A professional, secure, responsive, easy-to-use Online DSR system deployable for
Safecurecs Communication daily operations, without replacing the existing ERP.

---

## Phase 1 Implementation Notes (completed)

### Tech stack (as actually installed)

- Python 3.13, Django 6.0 (installed in `venv/`)
- MySQL (`safecurecs_dsr_db`), via `mysqlclient`
- `python-decouple` for `.env`-based configuration
- Bootstrap 5 (CDN) for UI
- Pillow for image field support (`profile_photo`)

### Apps

- `accounts` — custom user model, auth backend, admin config. Owns all identity/auth
  concerns.
- `dsr` — registered, intentionally empty. Report models/views (per the DSR form
  structure above) arrive in a later phase.

### Custom user model (`accounts.User`)

- Extends `AbstractBaseUser` + `PermissionsMixin` (not `AbstractUser`) — chosen because
  login is by `employee_id` **or** `email`, not a `username`; avoids carrying an unused
  `username` column/semantics.
- `USERNAME_FIELD = 'employee_id'`; `email` unique and required.
- Fields: `employee_id`, `email`, `first_name`, `last_name`, `mobile_number`, `department`,
  `designation`, `profile_photo`, `role` (`ADMIN`/`EMPLOYEE` — matches the two spec roles),
  `is_active`, `is_staff`, `date_joined`, `created_at`, `updated_at`.
- `accounts.backends.EmployeeIdOrEmailBackend` (in `AUTHENTICATION_BACKENDS`, ahead of the
  default `ModelBackend`) allows authenticating with either identifier against the same
  password field, per the spec's "Employee ID OR Email + Password" login requirement.
  Email lookup is case-insensitive.
- `accounts.models.UserManager` implements `create_user` / `create_superuser`.

### Conventions established

- Secrets/config live in `.env` (see `.env.example` for the required keys); never hardcode
  `SECRET_KEY` or DB credentials in `settings.py`.
- Templates: single `templates/` dir at project root, `base.html` provides navbar +
  collapsible sidebar (placeholder links: Dashboard, My Reports, New DSR, Profile) + Django
  messages block. Sidebar link targets are `#` until the relevant phase builds those pages.
- Static assets: `static/css/style.css`, `static/js/main.js`, wired via `STATICFILES_DIRS`.
- Media uploads go to `MEDIA_ROOT` (`media/`). **Superseded in Phase 8**: only
  `profile_photos/` is directly served even in `DEBUG`; `dsr_attachments/` is deliberately
  unmapped and only reachable via the authenticated `dsr:attachment_download` view — see
  the Phase 8 notes and Deployment section below.

### Phase 1 file manifest

Project scaffold:
- `manage.py`, `safecurecs_dsr/{__init__,asgi,wsgi}.py` — Django project entrypoints (generated)
- `safecurecs_dsr/settings.py` — env-driven settings (decouple), MySQL config, custom user model wiring, static/media paths
- `safecurecs_dsr/urls.py` — admin, home smoke-test route, media serving in DEBUG
- `accounts/`, `dsr/` — two apps created; `dsr` left empty per scope

Config/secrets:
- `.env` — real local values (SECRET_KEY, DEBUG, DB creds)
- `.env.example` — template with blank/placeholder values for git
- `.gitignore` — venv, `.env`, `__pycache__`, media, sqlite, IDE junk
- `requirements.txt` — pinned from installed packages (Django 6.0.6, mysqlclient 2.2.8, Pillow 12.3.0, python-decouple 3.8)

Custom user model (`accounts/`):
- `accounts/models.py` — `User` (AbstractBaseUser+PermissionsMixin) + `UserManager` with `create_user`/`create_superuser`
- `accounts/backends.py` — `EmployeeIdOrEmailBackend` for dual-identifier login
- `accounts/admin.py` — `UserAdmin` registration with list display/filters/fieldsets
- `accounts/migrations/0001_initial.py` — generated migration
- `accounts/tests.py` — 8 tests: manager creation, superuser validation, login via employee_id/email (incl. case-insensitivity, wrong password, unknown user)

Templates/static:
- `templates/base.html` — navbar + collapsible sidebar + messages block, Bootstrap 5 CDN
- `templates/home.html` — smoke-test page extending base
- `static/css/style.css` — white/blue theme, responsive sidebar collapse
- `static/js/main.js` — sidebar toggle behavior

Not touched: `dsr/models.py`, `dsr/admin.py`, `dsr/views.py`, `dsr/tests.py` — left as
Django defaults, no DSR models per Phase 1 scope.

Superuser created: `admin001` / `admin@safecurecs.com` (password set at creation time,
change it after first login).

---

## Phased development status

Phases 1-8 shipped as v1.0. Phase 9 followed afterward as a standalone addition. Each
phase was scoped narrowly, implemented only after an approved plan, and stopped for
review before the next began, per the spec's Development Process section.

- **Phase 1 (done):** Project scaffold, custom user model + auth backend + admin, base
  template/theme. See notes above.
- **Phase 2 (done):** Login/logout views (`accounts.views.SafecurecsLoginView`, dual
  identifier via the existing `EmployeeIdOrEmailBackend`), role-based post-login redirect
  (`accounts.utils.get_dashboard_url`), `AdminRequiredMixin`/`EmployeeRequiredMixin`
  (`accounts/mixins.py`), profile view/edit (photo, email, mobile only — rest read-only,
  enforced via `ProfileUpdateForm.Meta.fields`), change-password view. Placeholder
  dashboards and sidebar wiring for New DSR/My Reports/All Reports.
- **Phase 3 (done):** `dsr.models.DSR` and `DSRAttachment`. Race-safe daily DSR-number
  generation (`DSRDailySequence` + `select_for_update()`, with a bounded retry on MySQL
  deadlock — see `dsr/utils.py`). Status state machine on the model itself
  (`submit`/`approve`/`reject`/`send_back`, `ALLOWED_TRANSITIONS`, `can_edit(user)`).
  Attachment content validation (`dsr/validators.py`) — extension allowlist, size cap, and
  real content sniffing (Pillow for images, `%PDF` magic bytes for PDFs) so a renamed file
  can't bypass the allowlist.
- **Phase 4 (done):** Employee DSR create/edit form (`dsr.forms.DSRForm`, mode-aware
  validation: `draft` vs `submit`), file uploads (Project Photos vs Attachments mapped onto
  `DSRAttachment.category`), DSR detail view, "My Reports" list with filters
  (`DSRFilterForm`) and mobile-card/desktop-table responsive pattern. Ownership convention
  established and used everywhere since: **cross-user access → 404; own-but-blocked
  (wrong status) → redirect with a message**, not a bare 404.
- **Phase 5 (done):** Admin "All Reports" (`AdminDSRFilterForm`, extending the employee
  filter form) and the review page/actions (approve/reject/send-back), all routed through
  one view with the action selected by submit-button name, reusing the Phase 3 transition
  methods rather than reimplementing the rules. `send_back()`/`approve()` gained
  remarks-handling in this phase (still living in the model, not the view).
- **Phase 6 (done):** Employee and admin dashboards — stat cards computed via conditional
  aggregation (`Count(..., filter=Q(...))`) in one or two queries rather than N separate
  counts, capped recent/pending lists. Found and fixed during this phase: MySQL's
  `CONVERT_TZ` silently returns NULL here because the server's timezone tables aren't
  loaded (`mysql.time_zone_name` is empty) — any `__date` lookup on a `DateTimeField` under
  a non-UTC `TIME_ZONE` is affected. Fixed by comparing tz-aware `gte`/`lt` datetime ranges
  instead of `__date`, which needs no server-side timezone data. Worth remembering if this
  ever recurs elsewhere.
- **Phase 7 (done):** Admin-only exports — Excel (`openpyxl`) and PDF (`xhtml2pdf`, chosen
  over WeasyPrint after WeasyPrint failed to import at runtime on this Windows machine:
  `OSError: cannot load library 'libgobject-2.0-0'` — WeasyPrint needs GTK/Pango native
  libraries not installed here). Filtering logic for the list view and both list-level
  exports lives in exactly one place: `dsr.mixins.AdminDSRFilterMixin`. Single-DSR PDF is
  the one deliberate exception to "exports are admin-only": an employee may download their
  own report's PDF, but only once it's `APPROVED` (own-but-wrong-status still follows the
  established redirect-with-message convention, not a 404).
- **Phase 8 (done):** Security hardening, protected media, error pages, and deployment
  readiness — see below.
- **Phase 9 (done):** Admin Employee Management page — brings the sidebar "Employees"
  link (placeholder since Phase 1) to life. See below.

## Phase 8 notes (security, media protection, deployment readiness)

### Security settings

All new settings are env-driven via `python-decouple` with safe local-dev defaults
(`False`/`0`), following the same pattern already used for `DEBUG`/`MAX_*_SIZE_MB`:
`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
`SECURE_HSTS_SECONDS` (+ `INCLUDE_SUBDOMAINS`/`PRELOAD`). Always-on regardless of
environment: `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`,
`SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS='DENY'`, `SECURE_REFERRER_POLICY`.

**`CSRF_COOKIE_HTTPONLY=True`** — safe here because nothing in this codebase reads the
`csrftoken` cookie from JS (every form uses the `{% csrf_token %}` hidden input, no
AJAX/fetch anywhere). **If AJAX that reads that cookie is ever introduced, this must be
revisited (set back to `False`)**, or the CSRF token must be sourced another way (e.g. a
meta tag).

**Session policy**: `SESSION_COOKIE_AGE` defaults to 10 hours (`36000`, env-driven), with
`SESSION_SAVE_EVERY_REQUEST=True` so the window rolls forward on activity — an active
field worker's session keeps extending rather than expiring on a fixed clock from login
time. `SESSION_EXPIRE_AT_BROWSER_CLOSE=False` deliberately: mobile browsers often keep
cookies alive across app-switch/lock-screen without a "real" close, so tying expiry to
browser-close is unreliable there; the explicit `COOKIE_AGE` is more predictable.

**`manage.py check --deploy`** currently reports 5 warnings in local dev
(`SECURE_HSTS_SECONDS` unset, `SECURE_SSL_REDIRECT` not True, `SESSION_COOKIE_SECURE` not
True, `CSRF_COOKIE_SECURE` not True, `DEBUG=True`). All five are **intentional and
expected** here (there's no SSL in local dev) and are resolved simply by setting the
corresponding production `.env` values — verified directly: running `check --deploy` with
`SECURE_SSL_REDIRECT=True SESSION_COOKIE_SECURE=True CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000 SECURE_HSTS_INCLUDE_SUBDOMAINS=True SECURE_HSTS_PRELOAD=True
DEBUG=False` produces a clean "no issues" result.

### Protected DSR attachments

Uploaded DSR attachments (`dsr_attachments/`) contain private client data and must never
be served directly by the web server — only through the authenticated
`dsr.views.DSRAttachmentDownloadView` (`GET /dsr/attachment/<pk>/download/`), which checks
owner-or-admin before streaming the file via `FileResponse`. This is enforced even in local
dev: the `if settings.DEBUG: urlpatterns += static(...)` helper in
`safecurecs_dsr/urls.py` now maps **only** `MEDIA_URL + 'profile_photos/'`, not the whole
`MEDIA_ROOT` — a raw guessed `/media/dsr_attachments/...` URL 404s even locally, so the
protection is real and test-covered, not just "the UI happens not to link there."

**Profile photos remain on direct `/media/` serving** (`profile_photos/` only) — accepted
tradeoff, not an oversight: they're low-sensitivity (a person's own photo, already visible
to anyone who's met them) and are needed in the navbar avatar on every single page, so
routing them through an authenticated view would add a DB-backed request to every page
load for no real security benefit.

**For the production web server config** (nginx/IIS): serve `/media/profile_photos/`
directly; do **not** add a location/alias serving `/media/dsr_attachments/` — that
directory must only ever be reached through Django (the `dsr:attachment_download` view).
X-Accel-Redirect (nginx) / X-Sendfile (IIS/Apache) would let the web server handle the
actual byte-streaming after Django's permission check, which is more efficient than
Django holding the request open via `FileResponse` for large files — **not implemented,
left as optional future work**; `FileResponse` is fine at this app's current scale.

### Error pages

`templates/403.html`, `404.html`, `500.html` (template root — required location for
Django's default error handlers) extend `templates/base_error.html`, a minimal layout that
does **not** depend on `base.html`'s context processors — this matters most for
`500.html`, which Django renders with **no context at all** (confirmed from
`django.views.defaults.server_error`'s source — it calls `template.render()` with no
context or request). The single action link on all three (`{% url 'home' %}`) needs no
request-based branching to "respect login state": `home` is the existing
`IndexRedirectView`, which already redirects anonymous → login / authenticated → their own
dashboard.

Tested by calling Django's actual `django.views.defaults.page_not_found` /
`permission_denied` / `server_error` functions directly via `RequestFactory`
(`accounts.tests.ErrorPageTests`) — the same code path Django uses when `DEBUG=False` in
production, without needing a real broken URL. Additionally verified manually: ran
`DEBUG=False manage.py runserver` and requested a genuinely nonexistent URL — confirmed
the custom 404 template rendered (not Django's DEBUG technical-404 page), and confirmed
`manage.py collectstatic --noinput` completes cleanly (134 files, including the favicon).

### Operational additions

- `accounts.management.commands.create_employee` — thin CLI wrapper over
  `UserManager.create_user` (`employee_id email first_name last_name [--department]
  [--designation] [--password]`, prompts securely via `getpass` if `--password` omitted).
  Django admin remains the primary way to onboard employees; this is a convenience for
  scripted/bulk setup.
- `LOGGING`: console + `RotatingFileHandler` (`logs/`, gitignored, 5MB × 5 backups,
  auto-created on startup via `Path.mkdir`). Level is env-driven (`DJANGO_LOG_LEVEL`,
  default `INFO`) — set `WARNING` in production to cut routine noise. DSR status
  transitions (`submit`/`approve`/`reject`/`send_back`) log at `INFO` with the
  `dsr_number` and the acting user's `employee_id`, directly inside the transition methods
  on the model (not in views), consistent with "business logic stays out of views."
- Django admin site header/title set to "Safecurecs DSR Administration"
  (`safecurecs_dsr/urls.py`).
- Sitewide double-submit prevention: one global `submit` event listener in
  `static/js/main.js` disables all submit buttons in the submitted form (spinner on the
  one actually clicked). Listens on `submit`, not `click`, so it only fires after any
  `onclick="return confirm(...)"` guard (attachment delete, review actions) has been
  accepted — a cancelled confirm never reaches it.
- Favicon: a solid blue square with "S", generated locally via Pillow (already a
  dependency — no new package) at `static/img/favicon.png`.
- Mobile audit at 360px: no browser/screenshot tool is available in this environment, so
  this was a structural/CSS audit (fixed widths, breakpoint usage, table/grid overflow
  risk), not an actual rendered visual check — stating that limitation plainly. One real
  issue found and fixed: the navbar's user-name span had no width constraint, so a long
  name could push the navbar wider than a 360px viewport; fixed by hiding the name below
  the `sm` breakpoint (`d-none d-sm-inline`), keeping just the avatar dropdown trigger on
  the smallest screens. No other structural overflow risks were found by this method.

## Phase 9 notes (admin employee management)

Adds four admin-only views under `/employees/` (`accounts.views.EmployeeListView`,
`EmployeeCreateView`, `EmployeeUpdateView`, `EmployeeResetPasswordView`), all gated by the
existing `AdminRequiredMixin` — no new access-control machinery. No `User` model changes.

- **List** (`employee_list.html`): search (employee_id/name/email), `is_active` and
  `department` filters, 20/page pagination — mirrors the responsive
  filter-card/mobile-cards/desktop-table/pagination pattern already established in
  `dsr/admin_dsr_list.html`.
- **Add** (`EmployeeCreateForm`): always creates an `EMPLOYEE` — the form has no
  `role`/`is_staff`/`is_superuser` fields, and `save()` calls
  `User.objects.create_user(...)` directly (never `create_superuser`), so injected POST
  data for those keys has no effect. Password validated against
  `AUTH_PASSWORD_VALIDATORS` via a `_post_clean()` override mirroring
  `django.contrib.auth.forms.UserCreationForm` (runs after the instance is populated, so
  `UserAttributeSimilarityValidator` compares against the entered employee_id/email/name).
- **Edit** (`EmployeeEditForm`): `employee_id` and `role` are absent from the form (shown
  read-only in the template) — unchangeable regardless of injected POST data. Includes an
  `is_active` checkbox; deactivating blocks login immediately (the existing
  `EmployeeIdOrEmailBackend`, via inherited `user_can_authenticate()`, already refuses
  inactive users — no auth code changed for this).
- **Reset password**: a separate POST-only view (`EmployeeResetPasswordView`), not merged
  into the edit `UpdateView` — `SetPasswordForm(user, data)`'s constructor takes a
  positional `user`, which doesn't fit `UpdateView.get_form_kwargs()` (passes
  `instance=`). Reuses Django's own `SetPasswordForm` as-is (wrapped in
  `StyledSetPasswordForm` for Bootstrap classes only) rather than reimplementing it.
- **No delete** — deactivation via the edit form's `is_active` checkbox is the only way to
  disable an account, per spec.
- **Admin accounts are unreachable from every `/employees/` URL**: `EmployeeListView`,
  `EmployeeUpdateView`, and `EmployeeResetPasswordView` all scope their queryset to
  `role=User.Role.EMPLOYEE`, so an admin's own pk on the edit or reset-password URL
  returns 404 (not a redirect) — consistent with this project's established
  cross-user/cross-role access convention.
- Tests: `accounts/tests.py` — `EmployeeManagementAccessTests`,
  `EmployeeListViewTests`, `EmployeeCreateViewTests`, `EmployeeUpdateViewTests`,
  `EmployeeResetPasswordViewTests`. Cover role-gating on all four URLs, list
  search/filter/pagination, the role/is_staff/is_superuser tampering case on Add, duplicate
  employee_id/email field errors, weak-password rejection, real login after creation,
  employee_id/role tamper-resistance on Edit, deactivate/reactivate login effects, and
  admin-pk-404 on both Edit and Reset Password.

## Deployment

### Environment variables

| Variable | Local dev | Production |
|---|---|---|
| `SECRET_KEY` | any string | long random value, kept secret |
| `DEBUG` | `True` | `False` |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | your real domain(s) |
| `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` | local MySQL | production MySQL |
| `MAX_PROFILE_PHOTO_SIZE_MB` / `MAX_DSR_ATTACHMENT_SIZE_MB` | `2` / `5` | same, or tune |
| `SECURE_SSL_REDIRECT` | `False` | `True` |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | `False` | `True` |
| `SECURE_HSTS_SECONDS` | `0` | e.g. `31536000` (1 year), once HTTPS is confirmed working |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` | `False` | `True` (with care) |
| `SESSION_COOKIE_AGE` | `36000` (10h) | tune to policy |
| `DJANGO_LOG_LEVEL` | `INFO` | `WARNING` |

### Checklist

1. Set all production env vars above (never commit `.env`; `.env.example` documents every key).
2. `pip install -r requirements.txt` into a fresh venv.
3. `python manage.py migrate`.
4. `python manage.py collectstatic --noinput` (serve `STATIC_ROOT` via the web server or a CDN).
5. `python manage.py createsuperuser` (or `create_employee` for regular employees).
6. Media serving rule (see Phase 8 notes above): web server serves `/media/profile_photos/`
   directly; `/media/dsr_attachments/` must **not** be exposed — only reachable through
   Django's `dsr:attachment_download` view.
7. Run behind a real WSGI server — **gunicorn** or **waitress** — fronted by **nginx** (or
   **IIS** if staying on Windows), terminating TLS and reverse-proxying to the app server.
   This is a brief pointer, not a full deployment guide.
8. Backups: MySQL logical dump (`mysqldump`) on a schedule, plus the `media/` folder
   (specifically `dsr_attachments/` and `profile_photos/` — these aren't in the database).
