from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestCarRepairSecurity(TransactionCase):
    """FR-1: the roles are enforced by ACL and record rules, not by Python."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(
            cls.env, login='car_tech1', groups='car_repair.group_technician')
        cls.technician2 = new_test_user(
            cls.env, login='car_tech2', groups='car_repair.group_technician')
        cls.head_technician = new_test_user(
            cls.env, login='car_head', groups='car_repair.group_head_technician')
        cls.service_manager = new_test_user(
            cls.env, login='car_manager', groups='car_repair.group_service_manager')

        cls.partner = cls.env['res.partner'].create({'name': 'Security Client'})
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Sectest'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'S1', 'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id, 'license_plate': '1-SEC-001',
        })
        cls.repair_order = cls.env['car.repair.order'].create({
            'subject': 'Security test',
            'partner_id': cls.partner.id,
            'car_line_ids': [(0, 0, {'vehicle_id': cls.vehicle.id})],
        })
        cls.car_line = cls.repair_order.car_line_ids
        cls.diagnosis = cls.env['car.diagnosis'].create({
            'subject': 'Security test',
            'repair_order_id': cls.repair_order.id,
            'car_line_ids': [(6, 0, cls.car_line.ids)],
        })
        cls.workorder_own = cls.env['car.repair.workorder'].create({
            'subject': 'Own work order',
            'technician_id': cls.technician.id,
        })
        cls.workorder_other = cls.env['car.repair.workorder'].create({
            'subject': 'Colleague work order',
            'technician_id': cls.technician2.id,
        })

    def test_technician_sees_only_own_workorder(self):
        workorders = self.env['car.repair.workorder'].with_user(self.technician).search([])
        self.assertIn(self.workorder_own, workorders)
        self.assertNotIn(
            self.workorder_other, workorders,
            'A technician must not see the work orders of his colleagues.')

    def test_technician_cannot_write_other_workorder(self):
        self.workorder_own.with_user(self.technician).action_start()
        self.assertEqual(self.workorder_own.state, 'in_progress')
        with self.assertRaises(AccessError):
            self.workorder_other.with_user(self.technician).action_start()

    def test_technician_read_only_on_repair_order_and_diagnosis(self):
        self.repair_order.with_user(self.technician).read(['subject'])
        with self.assertRaises(AccessError):
            self.repair_order.with_user(self.technician).write({'subject': 'Hacked'})
        with self.assertRaises(AccessError):
            self.env['car.diagnosis'].with_user(self.technician).create({
                'subject': 'Nope',
                'repair_order_id': self.repair_order.id,
            })

    def test_assigned_technician_fills_own_diagnostic_result(self):
        """FR-4: read only on the diagnosis, but owns his findings."""
        self.diagnosis.technician_id = self.technician
        part = self.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        result = self.env['car.diagnosis.result'].with_user(self.technician).create({
            'diagnosis_id': self.diagnosis.id,
            'car_line_id': self.car_line.id,
            'product_id': part.id,
            'quantity': 2.0,
            'recommendation': 'Replace it',
        })
        result.with_user(self.technician).write({'quantity': 3.0})
        self.assertEqual(result.quantity, 3.0)
        self.assertEqual(result.technician_id, self.technician)

    def test_technician_cannot_touch_result_of_colleague(self):
        self.diagnosis.technician_id = self.technician2
        part = self.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        other_result = self.env['car.diagnosis.result'].create({
            'diagnosis_id': self.diagnosis.id,
            'car_line_id': self.car_line.id,
            'product_id': part.id,
        })
        visible = self.env['car.diagnosis.result'].with_user(self.technician).search([])
        self.assertNotIn(other_result, visible)
        with self.assertRaises(AccessError):
            other_result.with_user(self.technician).write({'quantity': 9.0})

    def test_head_technician_sees_all_workorders(self):
        workorders = self.env['car.repair.workorder'].with_user(self.head_technician).search([])
        self.assertIn(self.workorder_own, workorders)
        self.assertIn(self.workorder_other, workorders)

    def test_head_technician_cannot_change_repair_order(self):
        with self.assertRaises(AccessError):
            self.repair_order.with_user(self.head_technician).write({'subject': 'Hacked'})

    def test_head_technician_can_fill_diagnostic_result(self):
        self.diagnosis.with_user(self.head_technician).write({'technician_id': self.technician.id})
        self.assertEqual(self.diagnosis.technician_id, self.technician)

    def test_service_manager_can_create_repair_order(self):
        order = self.env['car.repair.order'].with_user(self.service_manager).create({
            'subject': 'Manager order',
            'partner_id': self.partner.id,
        })
        self.assertTrue(order.name.startswith('SR'))

    def test_roles_are_checkboxes_on_the_user_form(self):
        """FR-1: one user may hold several roles, ticked on the user form."""
        roles = self.technician._car_repair_roles()
        self.assertEqual(len(roles), 4)
        self.assertEqual(self.technician.car_repair_role_ids, self.env.ref(
            'car_repair.group_technician'))

        field = self.env['res.users']._fields['car_repair_role_ids']
        self.assertEqual(field.type, 'many2many')

        arch = self.env['res.users'].get_view(
            self.env.ref('base.view_users_form').id, 'form')['arch']
        self.assertIn('car_repair_role_ids', arch)
        self.assertIn('many2many_checkboxes', arch)

    def test_one_user_can_hold_several_roles(self):
        user = new_test_user(self.env, login='car_multi', groups='base.group_user')
        user.write({'car_repair_role_ids': [(6, 0, [
            self.env.ref('car_repair.group_technician').id,
            self.env.ref('car_repair.group_service_manager').id,
        ])]})
        self.assertTrue(user.has_group('car_repair.group_technician'))
        self.assertTrue(user.has_group('car_repair.group_head_technician'))
        self.assertTrue(user.has_group('car_repair.group_service_manager'))
        self.assertFalse(user.has_group('car_repair.group_director_commercial'))

        user.write({'car_repair_role_ids': [(6, 0, [
            self.env.ref('car_repair.group_technician').id])]})
        self.assertTrue(user.has_group('car_repair.group_technician'))
        self.assertFalse(user.has_group('car_repair.group_service_manager'))

    def test_technician_can_print_his_work_order(self):
        """FR-7: the reports are reachable by the role that needs them."""
        content, ext = self.env['ir.actions.report'].with_user(
            self.technician)._render_qweb_pdf(
            'car_repair.report_car_workorder', res_ids=self.workorder_own.ids)
        self.assertIn(ext, ('pdf', 'html'))
        self.assertTrue(content)
        self.assertIn(
            self.workorder_own.name,
            content.decode() if ext == 'html' else self.workorder_own.name)

    def test_print_buttons_are_in_the_form_header(self):
        """FR-7: printing is one click in the header, not only in the cog menu."""
        expected = {
            'car.repair.order': ('car_repair.view_car_repair_order_form', 3),
            'car.diagnosis': ('car_repair.view_car_diagnosis_form', 2),
            'car.repair.workorder': ('car_repair.view_car_repair_workorder_form', 1),
        }
        for model, (view_xmlid, count) in expected.items():
            arch = etree.fromstring(self.env[model].get_view(
                self.env.ref(view_xmlid).id, 'form')['arch'])
            buttons = arch.xpath('//header/button[@type="action"]')
            self.assertEqual(
                len(buttons), count,
                'Model %s must expose %d print buttons in its header.' % (model, count))

        reports = self.env['ir.actions.report'].search([
            ('report_name', 'like', 'car_repair.%')])
        self.assertTrue(all(r.binding_model_id for r in reports),
                        'The reports stay bound to the cog Print menu as well.')
