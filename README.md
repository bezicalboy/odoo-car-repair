# Car Repair & Automotive Service — Odoo 18 Community

Custom addon that manages a car repair workshop, from the moment a client drops a
car off until the invoice is issued.

Built for Odoo 18.0 Community. Module technical name: `car_repair`.

## The flow

    Car Repair Order  ──>  Car Diagnosis  ──>  Quotation (sale.order)  ──>  Work Order  ──>  Invoice (account.move)
    (client + cars)        (parts needed)      (native Odoo sales)          (hours spent)     (native Odoo accounting)

1. The Service Manager creates a Car Repair Order: client, one or more cars,
   and the checklist items to inspect.
2. `Create Diagnosis` opens a Car Diagnosis holding the cars of that order.
3. The Head Technician assigns a technician (wizard), the technician fills the
   Diagnostic Result lines: which spare part or labour each car needs.
4. `Create Quotation` builds a native `sale.order` out of those result lines.
5. Confirming the quotation creates the Work Order automatically.
6. The technician runs Start / Pause / Resume / Pending / Finish. Every
   start-stop interval is stored, so the hours add up over several sessions.
7. Finishing the work order reports the hours on the sales order service line,
   and `Create Invoice` produces the native customer invoice.

## Install

Requires a running Odoo 18.0 Community and PostgreSQL. Windows users can skip to
[Install on Windows](#install-on-windows), which repeats these steps with the
paths and commands of the official installer.

### Linux, macOS, Docker

1. Clone the repository somewhere outside the Odoo installation directory:

       git clone https://github.com/bezicalboy/odoo-car-repair /opt/odoo/custom-addons/odoo-car-repair

2. Add the clone directory to `addons_path` in your Odoo configuration file,
   comma separated:

       addons_path = /opt/odoo/addons,/opt/odoo/custom-addons/odoo-car-repair

   Point `addons_path` at the directory that *contains* `car_repair`, which is
   the repository root — not at `car_repair` itself. Odoo only scans the direct
   children of each `addons_path` entry for a `__manifest__.py`, so a path one
   level too deep or one level too shallow makes the module invisible in Apps.

3. Restart Odoo, then install from the command line:

       odoo-bin -c odoo.conf -d <database> -i car_repair --stop-after-init

   or from the interface: enable developer mode, then Apps, Update Apps List,
   search "Car Repair", Activate.

   To pick up a later version of the addon, use `-u car_repair` instead of
   `-i car_repair`: `-i` does nothing once the module is installed.

4. Give each internal user their roles under Settings, Users, Access Rights, in
   the "Car Repair" section. The roles are checkboxes, so one user can hold
   several positions. Ticking a higher role also grants the lower ones. The
   database administrator receives Director Commercial on install.

Dependencies, all standard Odoo modules: `mail`, `fleet`, `sale_management`,
`account`. They are installed automatically as dependencies. PDF reports need
`wkhtmltopdf`, which the official Odoo Windows installer already bundles. No
Python packages beyond Odoo's own are required.

## Install on Windows

Tested on the official `odoo_18.0.<build>.exe` installer, which puts Odoo in
`C:\Program Files\Odoo 18.0.<build>`, bundles its own Python and PostgreSQL, and
runs the server as the Windows service `odoo-server-18.0`.

Substitute your real build number for `<build>` and your database name for
`<database>` throughout.

### Step 1 — clone the repository outside the Odoo folder

Anything under `C:\Program Files` needs administrator rights to write, so keep
the clone somewhere else. A short path without spaces is easiest:

    git clone https://github.com/bezicalboy/odoo-car-repair C:\odoo-addons

That directory now holds `C:\odoo-addons\car_repair\__manifest__.py`.

### Step 2 — add the clone to addons_path

Open `C:\Program Files\Odoo 18.0.<build>\server\odoo.conf` in a text editor
started as administrator (Notepad, right-click, Run as administrator), and append
the clone directory to the existing `addons_path`, comma separated:

    addons_path = C:\Program Files\Odoo 18.0.<build>\server\odoo\addons,C:\odoo-addons

Point `addons_path` at the directory that *contains* `car_repair`, so
`C:\odoo-addons` — not `C:\odoo-addons\car_repair`. Odoo scans only the direct
children of each entry for a `__manifest__.py`.

Keep a copy of the file first; the installer does not back it up.

### Step 3 — install the module from an elevated PowerShell

Open the Start menu, type `PowerShell`, right-click *Windows PowerShell* and
choose **Run as administrator**. The window title must read
"Administrator: Windows PowerShell". Then, in order:

    Stop-Service odoo-server-18.0
    cd "C:\Program Files\Odoo 18.0.<build>"
    .\python\python.exe server\odoo-bin -c "server\odoo.conf" -d <database> -i car_repair --stop-after-init
    Start-Service odoo-server-18.0

Stop the service first: the running server holds the database, and two processes
updating the module registry at once can corrupt the install. Wait for the third
command to finish and return the prompt before starting the service again —
closing the window mid-install leaves modules stuck in state `to install`.

Installing `car_repair` also installs `sale_management`, `account`, `fleet` and
their own dependencies, so the first run processes dozens of modules and takes
several minutes. Lines such as
`Unmet dependencies: hr / mass_mailing / survey` are harmless: those modules are
unrelated and stay uninstalled.

### Step 4 — assign the roles

Open <http://localhost:8069>, then Settings, Users and Companies, Users. Open a
user, go to the Access Rights tab and tick the roles in the **Car Repair**
section. They are checkboxes, so one user can hold several positions, and ticking
a higher role also grants the lower ones. The database administrator receives
Director Commercial during installation.

### Updating to a later version of the addon

Pull the new code, then run the same sequence with `-u` instead of `-i`. On an
installed module `-i` does nothing:

    git -C C:\odoo-addons pull
    Stop-Service odoo-server-18.0
    cd "C:\Program Files\Odoo 18.0.<build>"
    .\python\python.exe server\odoo-bin -c "server\odoo.conf" -d <database> -u car_repair --stop-after-init
    Start-Service odoo-server-18.0

### Windows troubleshooting

**`PermissionError: [Errno 13] Permission denied` on `sessions\filestore\...`**
The PowerShell window is not elevated. The installer keeps `data_dir` under
`C:\Program Files`, where a normal user has read-only rights, so writing the menu
icon fails. The database is left untouched, but the service stays stopped: rerun
the command from an elevated window, then start the service.

**The module does not appear in Apps.**
`addons_path` points one level too deep or too shallow. It must name the
directory that contains `car_repair`. After fixing it, restart the service and
use Apps, Update Apps List (developer mode must be on).

**Apps shows "Cancel Install" instead of "Activate".**
The module is queued in state `to install` from an interrupted run. A plain
service restart does not clear it, because the queue is only processed by a
loader running in update mode. Rerun the step 3 command — do not click Cancel
Install, which discards the queue.

**`ERROR: couldn't create the logfile directory.`**
Harmless. Odoo falls back to logging on standard output, which is what you are
reading in the window.

**`odoo-bin` is not recognised.**
Run it through the bundled interpreter as shown above
(`.\python\python.exe server\odoo-bin`); the installer does not put Odoo on
`PATH`.

## Roles (FR-1)

Cumulative roles: every role includes the rights of the one above it.

| Model                 | Technician        | Head Technician | Service Manager | Director Commercial |
|-----------------------|-------------------|-----------------|-----------------|---------------------|
| Checklist             | read              | read            | read/write/create | full              |
| Car Repair Order      | read              | read            | read/write/create | full              |
| Car Diagnosis         | read              | read/write      | read/write/create | full              |
| Diagnostic Result     | **own** r/w/create| full            | full            | full                |
| Work Order            | read/write **own**| full            | full            | full                |

The roles are assigned as checkboxes on the user form (Settings, Users, Access
Rights, section "Car Repair"), so a single user can hold several positions at
once. Odoo renders a group category either as a single-choice selection field —
which it does here, because the roles imply each other — or as checkboxes hidden
behind developer mode. Neither is usable for a workshop administrator, so the
field `car_repair_role_ids` exposes the same four groups as a plain checkbox
list. It reads and writes `groups_id`, therefore implied groups still apply:
ticking Service Manager also grants Head Technician and Technician.

Access is enforced by `security/ir.model.access.csv` (what a role may do) and
`security/car_repair_security.xml` (which records it may touch) — not by Python
checks in the business methods. The technician restriction is a record rule on
`car.repair.workorder` plus its two child models, so a technician cannot reach a
colleague's work order through its lines or time logs either.

Record rules of different groups are combined with OR. The rule that grants the
Head Technician access to every work order is therefore required: without it,
the "own work orders only" domain of the Technician group would also apply to
the roles above, since the roles are cumulative.

The `groups=` attributes on buttons and menus only hide user interface elements;
they are a convenience, not the enforcement. Every restriction that matters is
verified again by the access rights and record rules when the ORM is called.

Because the roles are genuinely restrictive, the documents move their own status
instead of expecting the acting user to have write access on a parent document:

- `car.repair.order.line.state` is computed from the state of its diagnoses, so
  a Head Technician completing a diagnosis does not need write access on the
  repair order lines.
- `car.repair.order.state` is moved by the work order through one narrow
  `sudo()` call, so a Technician finishing his own work order does not need
  write access on the repair order itself.

FR-4 asks for a Technician who is read only on the Diagnosis but who still fills
his own Diagnostic Result. Those are two models, so the rights differ: read only
on `car.diagnosis`, read/write/create on `car.diagnosis.result` limited by a
record rule to the diagnoses assigned to him. That is why `Enter Results` opens
the result list on its own model (menu Car Repair, Diagnostic Results) instead of
writing through the one2many of the diagnosis form, which the read-only right on
the parent would refuse.

## Cars

Cars are `fleet.vehicle` records from the standard Fleet module, so license
plate, model, chassis number and fuel type are not duplicated. Add cars under
Car Repair, Configuration, Cars.

## Reports (FR-7)

Every report has a button in the header of the form it belongs to, so printing is
one click and does not require opening the cog Print dropdown. The reports are
also bound to that dropdown, so both paths work.

| Form             | Header buttons                                  |
|------------------|-------------------------------------------------|
| Car Repair Order | Print Receipt, Print Label, Print Checklist     |
| Car Diagnosis    | Print Request, Print Result                     |
| Work Order       | Print Work Order                                |

Print Checklist and Print Result appear once the document has lines to print.
The native invoice report shows the car and license plate of each line.

## Tests

    odoo-bin -c odoo.conf -d <database> -u car_repair --test-enable --test-tags=/car_repair --stop-after-init

20 tests: the full flow (`tests/test_car_repair_flow.py`) and the role
enforcement (`tests/test_car_repair_security.py`), including the pause/resume
accumulation of hours, the invoice quantity following those hours, the technician
who can fill his own diagnostic result but not a colleague's, the role checkboxes
on the user form, a user holding several roles at once, and the print buttons
being present in the form headers.

Two extra checks render every report and load every view and menu, which the
unit tests do not cover:

    odoo-bin shell -c odoo.conf -d <database> --no-http < tools/check_reports.py
    odoo-bin shell -c odoo.conf -d <database> --no-http < tools/check_views.py

Install with demo data (`-i car_repair` without `--without-demo`) to get two
example repair orders, cars and checklist items.

## Assumptions

- **Cars are fleet vehicles.** The test screenshots show brand, model, license
  plate and chassis number, which is exactly `fleet.vehicle`. A repair order
  line points at a vehicle and shows those values read-only.
- **One diagnosis per repair order, several cars per diagnosis.** `Create
  Diagnosis` puts every car of the order on one diagnosis; the button can be
  used again for a second round.
- **Work order states.** The screenshots of the source module show two different
  status bars (one with Pending, one without). Implemented state machine:
  `draft -> in progress -> paused / pending -> in progress -> finished`, plus
  `cancelled` from any state except finished. Buttons are shown per state.
- **Hours are stored as intervals**, not as one start/stop pair, otherwise a
  second pause would overwrite the first period. `car.repair.workorder.time`
  holds one row per interval and `hours` is their sum.
- **Labour is invoiced from the hours.** The product `Car Repair Labour (Hour)`
  is a service with invoicing policy "Delivered quantities". Finishing the work
  order writes the hours on the service line of the sales order, and adds that
  line when the quotation has none, so a parts-only quotation stays invoiceable.
  A work order therefore bills one labour line.
- **Finishing a work order means the parts were fitted.** Without the `stock`
  module nothing ever marks a spare part as delivered, so a quotation of parts
  with the "Delivered quantities" policy would have nothing to invoice.
  `Finish` therefore reports the ordered quantity as delivered on every line
  whose delivery is tracked manually. With `stock` installed, the delivery
  orders take that over and this code leaves those lines alone.
- **Native sales and accounting.** Quotations are `sale.order`, invoices are
  `account.move`. No copy of either model; only the car reference columns were
  added.
- **Client contact fields are read-only** on the repair order when they come
  from the client record (phone, mobile, email), so the workshop document cannot
  silently rewrite the customer file. `Contact Name` and `Contact Number` are
  free workshop fields.
- **Deletion guards** use `@api.ondelete(at_uninstall=False)`: a repair order
  can only be deleted while it is still Received or Cancelled.

## Not implemented

- Splitting labour hours across several sales order lines. One work order
  reports its hours on one service line.
- Spare part stock moves. Parts appear on the quotation and the invoice, but no
  `stock` reservation or delivery is created (the module does not depend on
  `stock`).
- Portal or website access for the client. The flow is back office only.
- Email. The module sends none: the only mail call is an internal chatter note
  logged by the assignment wizard. The `mail` dependency is there for
  `mail.thread` and `mail.activity.mixin`, which the assessment requires for the
  activity log, not for notifications.
- Custom CSS or a custom kanban design: out of scope for this assessment.

## Known upstream issue: Send & Print on an invoice

On this Odoo 18.0 Community build, the invoice **Send & Print** button fails
with:

    AttributeError: 'account.move.line' object has no attribute 'deferred_start_date'

This is a bug in the standard `account_edi_ubl_cii` module, not in this addon.
`account_edi_ubl_cii/models/account_edi_cii.py` reads
`account.move.line.deferred_start_date` while building the Factur-X XML that
Odoo always embeds in the invoice PDF, and that field is declared by
`account_accountant`, which is an Enterprise module. The same traceback appears
on a plain invoice created without this addon, and `account_edi_ubl_cii` arrives
through `auto_install` via `sale_edi_ubl`, so it is present in every database
where Sales is installed.

Use the **Print** button, which renders the invoice PDF normally, including the
car and license plate columns this addon adds. Uninstalling the EDI modules is
not a fix: `auto_install` reinstates them on the next module update. The
Indonesian e-invoicing modules (`l10n_id_efaktur`, `l10n_id_efaktur_coretax`)
depend on `l10n_id` only and are unaffected.
