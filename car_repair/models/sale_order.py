from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    car_repair_order_id = fields.Many2one(
        'car.repair.order', string='Repair Order', readonly=True, index='btree_not_null')
    car_diagnosis_id = fields.Many2one(
        'car.diagnosis', string='Car Diagnosis', readonly=True, index='btree_not_null')
    car_workorder_ids = fields.One2many(
        'car.repair.workorder', 'sale_order_id', string='Work Orders')
    car_workorder_count = fields.Integer(compute='_compute_car_workorder_count')

    @api.depends('car_workorder_ids')
    def _compute_car_workorder_count(self):
        data = self.env['car.repair.workorder']._read_group(
            [('sale_order_id', 'in', self.ids)],
            groupby=['sale_order_id'], aggregates=['__count'])
        counts = {order.id: count for order, count in data}
        for order in self:
            order.car_workorder_count = counts.get(order.id, 0)

    def action_confirm(self):
        """A confirmed car repair quotation automatically gets its work order."""
        res = super().action_confirm()
        for order in self.filtered(lambda o: o.car_repair_order_id and not o.car_workorder_ids):
            order._create_car_workorder()
        return res

    def _create_car_workorder(self):
        self.ensure_one()
        diagnosis = self.car_diagnosis_id
        workorder = self.env['car.repair.workorder'].create({
            'subject': self.car_repair_order_id.subject or self.name,
            'sale_order_id': self.id,
            'diagnosis_id': diagnosis.id,
            'repair_order_id': self.car_repair_order_id.id,
            'partner_id': self.partner_id.id,
            'technician_id': diagnosis.technician_id.id,
            'line_ids': [
                (0, 0, {
                    'car_line_id': line.car_line_id.id,
                    'product_id': line.product_id.id,
                    'description': line.name,
                    'quantity': line.product_uom_qty,
                })
                for line in self.order_line.filtered(lambda l: not l.display_type)
            ],
        })
        self.car_repair_order_id.state = 'work_in_progress'
        return workorder

    def action_view_car_workorder(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Work Orders'),
            'res_model': 'car.repair.workorder',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
        }
        if len(self.car_workorder_ids) == 1:
            action.update(view_mode='form', res_id=self.car_workorder_ids.id)
        return action

    def action_view_car_repair_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Order'),
            'res_model': 'car.repair.order',
            'res_id': self.car_repair_order_id.id,
            'view_mode': 'form',
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    car_line_id = fields.Many2one('car.repair.order.line', string='Car')
    car_model_id = fields.Many2one(
        related='car_line_id.model_id', string='Model #', store=True)
    car_license_plate = fields.Char(
        related='car_line_id.license_plate', string='License Plate', store=True)

    def _prepare_invoice_line(self, **optional_values):
        values = super()._prepare_invoice_line(**optional_values)
        if self.car_line_id:
            values['car_line_id'] = self.car_line_id.id
        return values
