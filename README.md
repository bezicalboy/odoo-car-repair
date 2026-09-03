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

Requires a running Odoo 18.0 Community and PostgreSQL.

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

4. Give each internal user one role under Settings, Users, the "Car Repair"
   section. The database administrator receives Director Commercial on install.

Dependencies, all standard Odoo modules: `mail`, `fleet`, `sale_management`,
`account`. They are installed automatically as dependencies. PDF reports need
`wkhtmltopdf`, which the official Odoo Windows installer already bundles. No
Python packages beyond Odoo's own are required.

### Windows

The installer keeps the configuration at
`C:\Program Files\Odoo 18.0.<build>\server\odoo.conf` and runs Odoo as the
service `odoo-server-18.0`. Editing that file and starting the service both
need an elevated (Administrator) shell:

    Stop-Service odoo-server-18.0
    cd "C:\Program Files\Odoo 18.0.<build>"
    .\python\python.exe server\odoo-bin -c "server\odoo.conf" -d <database> -i car_repair --stop-after-init
    Start-Service odoo-server-18.0

Stop the service first: the running server holds the database, and two
processes updating the module registry at once can corrupt the install. Let the
command finish and return the prompt before starting the service again —
closing the window mid-install leaves modules stuck in state `to install`.

If a module is stuck in `to install`, Apps shows "Cancel Install" instead of
"Activate". A plain service restart does not clear it, because the queue is
only processed by a loader running in update mode. Re-run the `-i` command
above (do not click Cancel Install, which discards the queue).

Installing `car_repair` also installs its dependencies, so the first run
processes more modules than just this one and takes several minutes.

## Roles (FR-1)

Cumulative roles: every role includes the rights of the one above it.

| Model                 | Technician        | Head Technician | Service Manager | Director Commercial |
|-----------------------|-------------------|-----------------|-----------------|---------------------|
| Checklist             | read              | read            | read/write/create | full              |
| Car Repair Order      | read              | read            | read/write/create | full              |
| Car Diagnosis         | read              | read/write      | read/write/create | full              |
| Diagnostic Result     | **own** r/w/create| full            | full            | full                |
| Work Order            | read/write **own**| full            | full            | full                |

Access is enforced by `security/ir.model.access.csv` (what a role may do) and
`security/car_repair_security.xml` (which records it may touch) — not by Python
checks in the business methods. The technician restriction is a record rule on
`car.repair.workorder` plus its two child models, so a technician cannot reach a
colleague's work order through its lines or time logs either.

Record rules of different groups are combined with OR. The rule that grants the
Head Technician access to every work order is therefore required: without it,
the "own work orders only" domain of the Technician group would also apply to
the roles above, since the roles are cumulative.

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

Print menu of the Car Repair Order: Car Label, Car Receipt, Car Checklist.
Print menu of the Car Diagnosis: Car Diagnostic Request, Car Diagnostic Result.
Print menu of the Work Order: Car Work Order.
The native invoice report shows the car and license plate of each line.

## Tests

    odoo-bin -c odoo.conf -d <database> -u car_repair --test-enable --test-tags=/car_repair --stop-after-init

16 tests: the full flow (`tests/test_car_repair_flow.py`) and the role
enforcement (`tests/test_car_repair_security.py`), including the pause/resume
accumulation of hours, the invoice quantity following those hours, and the
technician who can fill his own diagnostic result but not a colleague's.

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
  order writes the hours on the first service line of the sales order, which
  makes it invoiceable. A work order therefore bills one labour line.
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
  reports its hours on one service line; marked in the code where the split
  would go.
- Spare part stock moves. Parts appear on the quotation and the invoice, but no
  `stock` reservation or delivery is created (the module does not depend on
  `stock`).
- Portal or website access for the client. The flow is back office only.
- Custom CSS or a custom kanban design: out of scope for this assessment.
