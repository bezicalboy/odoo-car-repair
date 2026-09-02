from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCarRepairFlow(TransactionCase):
    """Repair order -> diagnosis -> quotation -> work order -> invoice."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Client'})
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Testcar'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'T1', 'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': '1-TST-001',
            'vin_sn': 'VIN000001',
        })
        cls.labour = cls.env.ref('car_repair.product_car_repair_labour').product_variant_id
        cls.checklist = cls.env.ref('car_repair.checklist_battery')

    def _new_repair_order(self):
        order = self.env['car.repair.order'].create({
            'subject': 'Battery replacement',
            'partner_id': self.partner.id,
            'car_line_ids': [(0, 0, {
                'vehicle_id': self.vehicle.id,
                'under_guarantee': True,
                'nature_of_service': 'Does not start',
            })],
            'checklist_line_ids': [(0, 0, {'checklist_id': self.checklist.id})],
        })
        return order

    def test_01_sequence_and_related_car_data(self):
        order = self._new_repair_order()
        self.assertTrue(order.name.startswith('SR'), 'The reference comes from the sequence.')
        line = order.car_line_ids
        self.assertEqual(line.license_plate, '1-TST-001')
        self.assertEqual(line.vin_sn, 'VIN000001')
        self.assertEqual(line.state, 'draft')

    def test_02_create_diagnosis(self):
        order = self._new_repair_order()
        order.action_create_diagnosis()
        diagnosis = order.diagnosis_ids
        self.assertEqual(len(diagnosis), 1)
        self.assertEqual(order.state, 'in_diagnosis')
        self.assertEqual(diagnosis.car_line_ids, order.car_line_ids)
        self.assertEqual(order.car_line_ids.state, 'in_diagnosis')
        self.assertEqual(order.diagnosis_count, 1)

    def test_03_diagnosis_requires_car(self):
        order = self.env['car.repair.order'].create({
            'subject': 'No car', 'partner_id': self.partner.id,
        })
        with self.assertRaises(UserError):
            order.action_create_diagnosis()

    def test_04_quotation_from_diagnosis(self):
        order = self._new_repair_order()
        order.action_create_diagnosis()
        diagnosis = order.diagnosis_ids
        diagnosis.technician_id = self.env.user
        with self.assertRaises(UserError):
            # No diagnostic result yet.
            diagnosis.action_create_quotation()
        diagnosis.write({
            'state': 'in_progress',
            'result_ids': [(0, 0, {
                'car_line_id': order.car_line_ids.id,
                'product_id': self.labour.id,
                'quantity': 3.0,
            })],
        })
        diagnosis.action_create_quotation()
        sale_order = diagnosis.sale_order_ids
        self.assertEqual(len(sale_order), 1)
        self.assertEqual(sale_order.partner_id, self.partner)
        self.assertEqual(sale_order.car_repair_order_id, order)
        self.assertEqual(sale_order.order_line.product_uom_qty, 3.0)
        self.assertEqual(sale_order.order_line.car_line_id, order.car_line_ids)
        self.assertEqual(order.state, 'quotation_sent')
        self.assertEqual(diagnosis.state, 'complete')

    def _confirmed_workorder(self):
        order = self._new_repair_order()
        order.action_create_diagnosis()
        diagnosis = order.diagnosis_ids
        diagnosis.write({
            'state': 'in_progress',
            'technician_id': self.env.user.id,
            'result_ids': [(0, 0, {
                'car_line_id': order.car_line_ids.id,
                'product_id': self.labour.id,
                'quantity': 3.0,
            })],
        })
        diagnosis.action_create_quotation()
        sale_order = diagnosis.sale_order_ids
        sale_order.action_confirm()
        return order, sale_order, sale_order.car_workorder_ids

    def test_05_workorder_created_on_confirm(self):
        order, sale_order, workorder = self._confirmed_workorder()
        self.assertEqual(len(workorder), 1, 'Confirming the quotation creates the work order.')
        self.assertEqual(workorder.state, 'draft')
        self.assertEqual(workorder.repair_order_id, order)
        self.assertEqual(workorder.technician_id, self.env.user)
        self.assertEqual(order.state, 'work_in_progress')
        self.assertEqual(len(workorder.line_ids), 1)

    def test_06_state_machine_and_hours(self):
        order, sale_order, workorder = self._confirmed_workorder()
        with self.assertRaises(UserError):
            workorder.action_pause()  # Not started yet.
        workorder.action_start()
        self.assertEqual(workorder.state, 'in_progress')
        self.assertEqual(len(workorder.time_ids), 1)

        # Pause then resume must accumulate, not overwrite.
        log = workorder.time_ids
        log.date_start = fields.Datetime.subtract(fields.Datetime.now(), hours=2)
        workorder.action_pause()
        self.assertEqual(workorder.state, 'paused')
        self.assertAlmostEqual(workorder.hours, 2.0, places=1)

        workorder.action_resume()
        self.assertEqual(workorder.state, 'in_progress')
        self.assertEqual(len(workorder.time_ids), 2)
        second = workorder.time_ids - log
        second.date_start = fields.Datetime.subtract(fields.Datetime.now(), hours=1)
        workorder.action_pending()
        self.assertEqual(workorder.state, 'pending')
        self.assertAlmostEqual(workorder.hours, 3.0, places=1)

        workorder.action_resume()
        workorder.action_finish()
        self.assertEqual(workorder.state, 'finished')
        self.assertTrue(workorder.date_end)
        self.assertFalse(workorder.time_ids.filtered(lambda t: not t.date_end))
        with self.assertRaises(UserError):
            workorder.action_cancel()  # A finished work order cannot be cancelled.
        self.assertEqual(order.state, 'done')

        # The hours spent are reported on the service line so it becomes invoiceable.
        service_line = sale_order.order_line.filtered(
            lambda line: line.product_id.type == 'service')
        self.assertAlmostEqual(service_line.qty_delivered, workorder.hours, places=1)

    def test_07_invoice_from_finished_workorder(self):
        order, sale_order, workorder = self._confirmed_workorder()
        with self.assertRaises(UserError):
            workorder.action_create_invoice()  # Not finished yet.
        workorder.action_start()
        workorder.time_ids.date_start = fields.Datetime.subtract(
            fields.Datetime.now(), hours=4)
        workorder.action_finish()
        self.assertAlmostEqual(workorder.hours, 4.0, places=1)
        action = workorder.action_create_invoice()
        invoice = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.partner_id, self.partner)
        invoice_line = invoice.invoice_line_ids.filtered(
            lambda line: line.product_id == self.labour)
        self.assertAlmostEqual(
            invoice_line.quantity, 4.0, places=1,
            msg='The invoice quantity follows the hours spent on the work order.')
        self.assertEqual(invoice_line.car_line_id, order.car_line_ids)
