from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CarDiagnosis(models.Model):
    """Damage assessment of the cars of a repair order, done by a technician."""
    _name = 'car.diagnosis'
    _description = 'Car Diagnosis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    subject = fields.Char(required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('complete', 'Complete'),
            ('cancel', 'Cancelled'),
        ],
        default='draft', required=True, copy=False, tracking=True)
    repair_order_id = fields.Many2one(
        'car.repair.order', string='Repair Order', required=True,
        ondelete='cascade', index=True, tracking=True)
    technician_id = fields.Many2one(
        'res.users', string='Technician', tracking=True,
        domain="[('share', '=', False)]",
        help='Technician in charge of filling the diagnostic result.')
    partner_id = fields.Many2one(related='repair_order_id.partner_id', store=True, string='Client')
    contact_name = fields.Char(related='repair_order_id.contact_name')
    phone = fields.Char(related='repair_order_id.phone')
    mobile = fields.Char(related='repair_order_id.mobile')
    email = fields.Char(related='repair_order_id.email')
    contact_number = fields.Char(related='repair_order_id.contact_number')
    priority = fields.Selection(related='repair_order_id.priority', readonly=False)
    date_receipt = fields.Date(related='repair_order_id.date_receipt')
    company_id = fields.Many2one(related='repair_order_id.company_id', store=True)

    car_line_ids = fields.Many2many(
        'car.repair.order.line', string='Car Details',
        domain="[('repair_order_id', '=', repair_order_id)]")
    result_ids = fields.One2many(
        'car.diagnosis.result', 'diagnosis_id', string='Diagnostic Result')
    result_count = fields.Integer(compute='_compute_result_count')
    note = fields.Html(string='Diagnosis Note')

    sale_order_ids = fields.One2many('sale.order', 'car_diagnosis_id', string='Quotations')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count')
    workorder_ids = fields.One2many(
        'car.repair.workorder', 'diagnosis_id', string='Work Orders')

    @api.depends('result_ids')
    def _compute_result_count(self):
        for diagnosis in self:
            diagnosis.result_count = len(diagnosis.result_ids)

    @api.depends('sale_order_ids')
    def _compute_sale_order_count(self):
        data = self.env['sale.order'].sudo()._read_group(
            [('car_diagnosis_id', 'in', self.ids)],
            groupby=['car_diagnosis_id'], aggregates=['__count'])
        counts = {diagnosis.id: count for diagnosis, count in data}
        for diagnosis in self:
            diagnosis.sale_order_count = counts.get(diagnosis.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('car.diagnosis') or _('New')
        return super().create(vals_list)

    def action_assign_technician(self):
        """Open the assignment wizard (used by the Head Technician)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign To Technician'),
            'res_model': 'car.diagnosis.assign',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_diagnosis_id': self.id},
        }

    def action_enter_results(self):
        """Move to In Progress and show the diagnostic result lines."""
        self.ensure_one()
        if not self.technician_id:
            raise UserError(_('Assign a technician before entering the results.'))
        if self.state == 'draft':
            self.state = 'in_progress'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Car Diagnostic Result'),
            'res_model': 'car.diagnosis',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('car_repair.view_car_diagnosis_result_form').id, 'form')],
            'target': 'new',
        }

    def action_complete(self):
        for diagnosis in self:
            if not diagnosis.result_ids:
                raise UserError(_(
                    'Fill the diagnostic result of %s before completing it.', diagnosis.name))
            diagnosis.state = 'complete'
            diagnosis.car_line_ids.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'

    def action_create_quotation(self):
        """Create a native quotation out of the diagnostic result lines."""
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_('Complete the diagnosis before creating a quotation.'))
        if not self.result_ids:
            raise UserError(_('There is no diagnostic result to quote.'))
        order = self.env['sale.order'].create(self._prepare_sale_order_values())
        self.repair_order_id.state = 'quotation_sent'
        if self.state == 'in_progress':
            self.action_complete()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation'),
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
        }

    def _prepare_sale_order_values(self):
        self.ensure_one()
        return {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'car_repair_order_id': self.repair_order_id.id,
            'car_diagnosis_id': self.id,
            'order_line': [
                (0, 0, line._prepare_sale_order_line_values())
                for line in self.result_ids
            ],
        }

    def action_view_sale_order(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Quotations'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
        }
        if len(self.sale_order_ids) == 1:
            action.update(view_mode='form', res_id=self.sale_order_ids.id)
        return action

    def action_view_repair_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Order'),
            'res_model': 'car.repair.order',
            'res_id': self.repair_order_id.id,
            'view_mode': 'form',
        }


class CarDiagnosisResult(models.Model):
    """One finding of the diagnosis: spare part or labour needed on a car."""
    _name = 'car.diagnosis.result'
    _description = 'Car Diagnostic Result'

    diagnosis_id = fields.Many2one(
        'car.diagnosis', required=True, ondelete='cascade', index=True)
    car_line_id = fields.Many2one(
        'car.repair.order.line', string='Car', required=True,
        domain="[('id', 'in', parent.car_line_ids)]")
    vehicle_id = fields.Many2one(
        related='car_line_id.vehicle_id', string='Vehicle', store=True)
    vin_sn = fields.Char(related='car_line_id.vin_sn', string='Serial Number')
    product_id = fields.Many2one(
        'product.product', string='Spare Part', required=True,
        domain="[('sale_ok', '=', True)]")
    code = fields.Char(string='Code')
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price')
    recommendation = fields.Char(string='Repair Recommendation')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.code = line.product_id.default_code
                line.price_unit = line.product_id.lst_price

    def _prepare_sale_order_line_values(self):
        self.ensure_one()
        values = {
            'product_id': self.product_id.id,
            'product_uom_qty': self.quantity,
            'car_line_id': self.car_line_id.id,
        }
        if self.price_unit:
            values['price_unit'] = self.price_unit
        if self.recommendation:
            values['name'] = '%s - %s' % (self.product_id.display_name, self.recommendation)
        return values
