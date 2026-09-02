from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CarRepairOrder(models.Model):
    """Entry document of the workshop: client, cars, checklist and repair notes."""
    _name = 'car.repair.order'
    _description = 'Car Repair Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_receipt desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    subject = fields.Char(required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('in_diagnosis', 'In Diagnosis'),
            ('quotation_sent', 'Quotation Sent'),
            ('quotation_approved', 'Quotation Approved'),
            ('work_in_progress', 'Work In Progress'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        default='received', required=True, copy=False, tracking=True,
        help='Gives the status of the car repair order.')
    user_id = fields.Many2one(
        'res.users', string='Assigned to', tracking=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]")
    priority = fields.Selection(
        selection=[('0', 'Normal'), ('1', 'High'), ('2', 'Very High')],
        default='0')
    date_receipt = fields.Date(
        string='Date of Receipt', default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    # Client details
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True)
    contact_name = fields.Char()
    # Kept read-only related: the workshop document must not silently rewrite
    # the customer record. Workshop specific contact data goes in contact_number.
    phone = fields.Char(related='partner_id.phone', readonly=True)
    mobile = fields.Char(related='partner_id.mobile', readonly=True)
    email = fields.Char(related='partner_id.email', readonly=True)
    contact_number = fields.Char()

    car_line_ids = fields.One2many(
        'car.repair.order.line', 'repair_order_id', string='Car Details', copy=True)
    checklist_line_ids = fields.One2many(
        'car.repair.order.checklist', 'repair_order_id',
        string='Repair Checklist', copy=True)
    note = fields.Html(string='Repair Note')

    diagnosis_ids = fields.One2many(
        'car.diagnosis', 'repair_order_id', string='Diagnosis')
    diagnosis_count = fields.Integer(compute='_compute_counts')
    workorder_ids = fields.One2many(
        'car.repair.workorder', 'repair_order_id', string='Work Orders')
    workorder_count = fields.Integer(compute='_compute_counts')
    sale_order_ids = fields.One2many(
        'sale.order', 'car_repair_order_id', string='Quotations')
    sale_order_count = fields.Integer(compute='_compute_counts')

    @api.depends('diagnosis_ids', 'workorder_ids', 'sale_order_ids')
    def _compute_counts(self):
        diagnosis_data = self.env['car.diagnosis']._read_group(
            [('repair_order_id', 'in', self.ids)],
            groupby=['repair_order_id'], aggregates=['__count'])
        diagnosis_map = {order.id: count for order, count in diagnosis_data}
        workorder_data = self.env['car.repair.workorder']._read_group(
            [('repair_order_id', 'in', self.ids)],
            groupby=['repair_order_id'], aggregates=['__count'])
        workorder_map = {order.id: count for order, count in workorder_data}
        sale_data = self.env['sale.order'].sudo()._read_group(
            [('car_repair_order_id', 'in', self.ids)],
            groupby=['car_repair_order_id'], aggregates=['__count'])
        sale_map = {order.id: count for order, count in sale_data}
        for order in self:
            order.diagnosis_count = diagnosis_map.get(order.id, 0)
            order.workorder_count = workorder_map.get(order.id, 0)
            order.sale_order_count = sale_map.get(order.id, 0)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for order in self:
            if order.partner_id:
                order.contact_name = order.partner_id.name
                order.contact_number = order.partner_id.phone

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('car.repair.order') or _('New')
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_started(self):
        for order in self:
            if order.state not in ('received', 'cancel'):
                raise UserError(_(
                    'Repair order %s is already in progress, it cannot be deleted.',
                    order.name))

    def action_create_diagnosis(self):
        """Create one diagnosis holding the cars of this repair order."""
        self.ensure_one()
        if not self.car_line_ids:
            raise UserError(_('Add at least one car before creating a diagnosis.'))
        diagnosis = self.env['car.diagnosis'].create({
            'repair_order_id': self.id,
            'subject': self.subject,
            'car_line_ids': [(6, 0, self.car_line_ids.ids)],
        })
        self.car_line_ids.state = 'in_diagnosis'
        if self.state == 'received':
            self.state = 'in_diagnosis'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Car Diagnosis'),
            'res_model': 'car.diagnosis',
            'res_id': diagnosis.id,
            'view_mode': 'form',
        }

    def action_view_diagnosis(self):
        self.ensure_one()
        return self._action_open_related('car.diagnosis', self.diagnosis_ids, _('Car Diagnosis'))

    def action_view_workorder(self):
        self.ensure_one()
        return self._action_open_related(
            'car.repair.workorder', self.workorder_ids, _('Work Orders'))

    def action_view_sale_order(self):
        self.ensure_one()
        return self._action_open_related('sale.order', self.sale_order_ids, _('Quotations'))

    def _action_open_related(self, model, records, name):
        action = {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': [('id', 'in', records.ids)],
        }
        if len(records) == 1:
            action.update(view_mode='form', res_id=records.id)
        return action


class CarRepairOrderLine(models.Model):
    """One car handed over to the workshop, with its service conditions."""
    _name = 'car.repair.order.line'
    _description = 'Car Repair Order Line'

    repair_order_id = fields.Many2one(
        'car.repair.order', required=True, ondelete='cascade', index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Car', required=True)
    license_plate = fields.Char(related='vehicle_id.license_plate', readonly=True)
    model_id = fields.Many2one('fleet.vehicle.model', related='vehicle_id.model_id', readonly=True)
    vin_sn = fields.Char(
        string='Chassis Number', related='vehicle_id.vin_sn', readonly=True)
    fuel_type = fields.Selection(related='vehicle_id.fuel_type', readonly=True)
    odometer = fields.Float(related='vehicle_id.odometer', readonly=True)
    under_guarantee = fields.Boolean(string='Under Guarantee?')
    guarantee_type = fields.Selection(
        selection=[('paid', 'Paid'), ('free', 'Free')], default='paid')
    nature_of_service = fields.Char()
    service_details = fields.Text()
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('in_diagnosis', 'In Diagnosis'), ('done', 'Done')],
        default='draft', required=True)
    partner_id = fields.Many2one(related='repair_order_id.partner_id', store=True)

    def _display_name_car(self):
        self.ensure_one()
        return self.vehicle_id.display_name


class CarRepairOrderChecklist(models.Model):
    """Checklist item picked from the master data and checked on a repair order."""
    _name = 'car.repair.order.checklist'
    _description = 'Car Repair Order Checklist Line'

    repair_order_id = fields.Many2one(
        'car.repair.order', required=True, ondelete='cascade', index=True)
    checklist_id = fields.Many2one(
        'car.repair.checklist', string='Checklist Name', required=True)
    is_done = fields.Boolean(string='Checked')
    note = fields.Char()

    _sql_constraints = [
        ('checklist_uniq', 'unique(repair_order_id, checklist_id)',
         'This checklist item is already on the repair order.'),
    ]
