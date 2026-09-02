#!/usr/bin/env bash
# One commit per build step, so the history shows how the module was built.
set -euo pipefail
cd "$(dirname "$0")/.."

git init -q -b main 2>/dev/null || true

commit() {
    local message="$1"; shift
    git add -- "$@"
    git commit -q -m "$message"
    printf '%s  %s\n' "$(git rev-parse --short HEAD)" "$message"
}

commit "Add module scaffold for car_repair" \
    .gitignore car_repair/__init__.py car_repair/__manifest__.py

commit "Add the four workshop roles" \
    car_repair/security/car_repair_groups.xml

commit "Add checklist master data with its views and menu" \
    car_repair/models/__init__.py \
    car_repair/models/car_repair_checklist.py \
    car_repair/views/car_repair_checklist_views.xml \
    car_repair/data/car_repair_data.xml

commit "Add the car repair order with its cars and checklist lines" \
    car_repair/models/car_repair_order.py \
    car_repair/views/car_repair_order_views.xml \
    car_repair/data/ir_sequence_data.xml

commit "Add the car diagnosis, its results and the assignment wizard" \
    car_repair/models/car_diagnosis.py \
    car_repair/views/car_diagnosis_views.xml \
    car_repair/wizard/

commit "Add the work order with accumulated time logs" \
    car_repair/models/car_repair_workorder.py \
    car_repair/views/car_repair_workorder_views.xml

commit "Enforce the roles with access rights and record rules" \
    car_repair/security/ir.model.access.csv \
    car_repair/security/car_repair_security.xml

commit "Chain diagnosis to quotation, work order and invoice" \
    car_repair/models/sale_order.py \
    car_repair/models/account_move.py \
    car_repair/views/sale_order_views.xml

commit "Add the menus of the application" \
    car_repair/views/car_repair_menus.xml

commit "Add the printable workshop documents" \
    car_repair/report/

commit "Add demo data for a ready to click flow" \
    car_repair/demo/

commit "Add the flow and security tests" \
    car_repair/tests/

commit "Add report and view smoke checks" \
    tools/

commit "Document the flow, the roles and the assumptions" \
    README.md

git add -A
if ! git diff --cached --quiet; then
    git commit -q -m "Add remaining module files"
    printf '%s  %s\n' "$(git rev-parse --short HEAD)" "Add remaining module files"
fi

echo '---'
git --no-pager log --oneline
