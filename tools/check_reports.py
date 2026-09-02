"""Render every report of car_repair once, to catch QWeb template errors."""
import sys

from odoo import fields

REPORTS = [
    ('car_repair.action_report_car_label', 'car.repair.order'),
    ('car_repair.action_report_car_receipt', 'car.repair.order'),
    ('car_repair.action_report_car_checklist', 'car.repair.order'),
    ('car_repair.action_report_car_diagnosis_request', 'car.diagnosis'),
    ('car_repair.action_report_car_diagnosis_result', 'car.diagnosis'),
    ('car_repair.action_report_car_workorder', 'car.repair.workorder'),
    ('account.account_invoices', 'account.move'),
]


def main(env):
    failures = []

    # Build one full flow so every report has a record with content.
    partner = env['res.partner'].create({'name': 'Report Client'})
    brand = env['fleet.vehicle.model.brand'].create({'name': 'Reportcar'})
    model = env['fleet.vehicle.model'].create({'name': 'R1', 'brand_id': brand.id})
    vehicle = env['fleet.vehicle'].create({
        'model_id': model.id, 'license_plate': '1-RPT-001', 'vin_sn': 'VINRPT01',
    })
    labour = env.ref('car_repair.product_car_repair_labour').product_variant_id
    order = env['car.repair.order'].create({
        'subject': 'Report flow',
        'partner_id': partner.id,
        'contact_name': 'Report Contact',
        'contact_number': '0800-1234',
        'car_line_ids': [(0, 0, {
            'vehicle_id': vehicle.id,
            'under_guarantee': True,
            'nature_of_service': 'Full service',
            'service_details': 'Check everything',
        })],
        'checklist_line_ids': [(0, 0, {
            'checklist_id': env.ref('car_repair.checklist_battery').id,
            'is_done': True,
        })],
    })
    order.action_create_diagnosis()
    diagnosis = order.diagnosis_ids
    diagnosis.write({
        'state': 'in_progress',
        'technician_id': env.uid,
        'note': '<p>Battery dead</p>',
        'result_ids': [(0, 0, {
            'car_line_id': order.car_line_ids.id,
            'product_id': labour.id,
            'code': 'BAT-01',
            'quantity': 2.0,
            'recommendation': 'Replace the battery',
        })],
    })
    diagnosis.action_create_quotation()
    sale_order = diagnosis.sale_order_ids
    sale_order.action_confirm()
    workorder = sale_order.car_workorder_ids
    workorder.action_start()
    # Backdate the open time log so the finished work order has billable hours.
    workorder.time_ids.date_start = fields.Datetime.subtract(
        fields.Datetime.now(), hours=2)
    workorder.action_finish()
    invoice = env['account.move'].browse(workorder.action_create_invoice()['res_id'])

    records = {
        'car.repair.order': order,
        'car.diagnosis': diagnosis,
        'car.repair.workorder': workorder,
        'account.move': invoice,
    }

    for xmlid, model_name in REPORTS:
        record = records[model_name]
        try:
            html, _dummy = env['ir.actions.report']._render_qweb_html(xmlid, record.ids)
            size = len(html)
            assert size > 500, 'suspiciously short output: %s bytes' % size
            print('OK   %-50s %6d bytes' % (xmlid, size))
        except Exception as error:  # noqa: BLE001 - report every failure, not the first
            failures.append((xmlid, error))
            print('FAIL %-50s %s: %s' % (xmlid, type(error).__name__, error))

    print('---')
    print('invoice line qty: %s (work order hours: %s)' % (
        invoice.invoice_line_ids.filtered(lambda l: l.product_id == labour).quantity,
        workorder.hours))
    print('%d ok, %d failed' % (len(REPORTS) - len(failures), len(failures)))
    if failures:
        sys.exit(1)


main(env)  # noqa: F821 - provided by odoo shell
