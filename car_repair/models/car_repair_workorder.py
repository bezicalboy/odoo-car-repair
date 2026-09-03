from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class CarRepairWorkorder(models.Model):
    """Execution of the job on the shop floor, created when a quotation is confirmed."""
    _name = 'car.repair.workorder'
    _description = 'Car Repair Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    subject = fields.Char(string='Work Order', required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('paused', 'Paused'),
            ('pending', 'Pending'),
            ('finished', 'Finished'),
            ('cancel', 'Cancelled'),
        ],
        default='draft', required=True, copy=False, tracking=True,
        help='Gives the status of the work order.')
    technician_id = fields.Many2one(
        'res.users', string='Technician', tracking=True, index=True,
        domain="[('share', '=', False)]",
        help='Technician responsible for this work order. A technician only sees his own.')
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', readonly=True, ondelete='cascade', index=True)
    diagnosis_id = fields.Many2one('car.diagnosis', string='Diagnosis', readonly=True)
    repair_order_id = fields.Many2one(
        'car.repair.order', string='Repair Order', readonly=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    priority = fields.Selection(
        selection=[('0', 'Normal'), ('1', 'High'), ('2', 'Very High')], default='0')

    date = fields.Date(default=fields.Date.context_today)
    date_start = fields.Datetime(string='Scheduled Date', tracking=True)
    date_end = fields.Datetime(string='Planned End Date', tracking=True)
    line_ids = fields.One2many(
        'car.repair.workorder.line', 'workorder_id', string='Work Order Lines')
    time_ids = fields.One2many(
        'car.repair.workorder.time', 'workorder_id', string='Time Logs', readonly=True)
    hours = fields.Float(
        string='Number of Hours', compute='_compute_hours', store=True,
        help='Total hours spent on this work order, computed from the time logs.')
    note = fields.Html(string='Work Note')

    @api.depends('time_ids.duration')
    def _compute_hours(self):
        for workorder in self:
            workorder.hours = sum(workorder.time_ids.mapped('duration'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'car.repair.workorder') or _('New')
        return super().create(vals_list)

    def _set_repair_order_state(self, state):
        self.ensure_one()
        if self.repair_order_id and self.repair_order_id.state != state:
            self.repair_order_id.sudo().state = state

    def action_start(self):
        for workorder in self:
            if workorder.state != 'draft':
                raise UserError(_('Only a draft work order can be started.'))
            workorder.state = 'in_progress'
            if not workorder.date_start:
                workorder.date_start = fields.Datetime.now()
            workorder._open_time_log()
            workorder._set_repair_order_state('work_in_progress')

    def action_pause(self):
        for workorder in self:
            if workorder.state != 'in_progress':
                raise UserError(_('Only a running work order can be paused.'))
            workorder._close_time_log()
            workorder.state = 'paused'

    def action_pending(self):
        for workorder in self:
            if workorder.state != 'in_progress':
                raise UserError(_('Only a running work order can be set to pending.'))
            workorder._close_time_log()
            workorder.state = 'pending'

    def action_resume(self):
        for workorder in self:
            if workorder.state not in ('paused', 'pending'):
                raise UserError(_('Only a paused or pending work order can be resumed.'))
            workorder.state = 'in_progress'
            workorder._open_time_log()

    def action_finish(self):
        for workorder in self:
            if workorder.state not in ('in_progress', 'paused', 'pending'):
                raise UserError(_('This work order cannot be finished from its current state.'))
            workorder._close_time_log()
            workorder.state = 'finished'
            workorder.date_end = fields.Datetime.now()
            workorder._update_sale_order_delivered_qty()
            workorder._set_repair_order_state('done')

    def action_cancel(self):
        for workorder in self:
            if workorder.state == 'finished':
                raise UserError(_('A finished work order cannot be cancelled.'))
            workorder._close_time_log()
            workorder.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'

    def _open_time_log(self):
        """Start a new time log. Pause/resume cycles therefore add up."""
        self.ensure_one()
        self.env['car.repair.workorder.time'].create({
            'workorder_id': self.id,
            'user_id': self.env.uid,
            'date_start': fields.Datetime.now(),
        })

    def _close_time_log(self):
        self.ensure_one()
        open_logs = self.time_ids.filtered(lambda log: not log.date_end)
        open_logs.write({'date_end': fields.Datetime.now()})

    def _labour_product(self):
        return self.env.ref(
            'car_repair.product_car_repair_labour').product_variant_id

    def _update_sale_order_delivered_qty(self):
        """Report what the workshop handed over so the sales order is invoiceable."""
        self.ensure_one()
        order = self.sale_order_id.sudo()
        if not order:
            return
        lines = order.order_line.filtered(lambda line: not line.display_type)
        service_lines = lines.filtered(lambda line: line.product_id.type == 'service')
        if self.hours and not service_lines:
            service_lines = self.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': self._labour_product().id,
                'product_uom_qty': self.hours,
            })
            lines |= service_lines
        if self.hours and service_lines:
            service_lines[0].qty_delivered = self.hours
        for line in lines - service_lines[:1]:
            if line.qty_delivered_method == 'manual':
                line.qty_delivered = line.product_uom_qty

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'finished':
            raise UserError(_('Finish the work order before invoicing it.'))
        if not self.sale_order_id:
            raise UserError(_('This work order is not linked to a sales order.'))
        self._update_sale_order_delivered_qty()
        if not self.sale_order_id.sudo().order_line.filtered('qty_to_invoice'):
            raise UserError(_(
                'Everything on sales order %s is already invoiced.',
                self.sale_order_id.name))
        invoices = self.sale_order_id._create_invoices()
        if not invoices:
            raise AccessError(_(
                'You are not allowed to create the invoice of this work order.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': invoices[:1].id,
            'view_mode': 'form',
        }

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }

    def action_view_diagnosis(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Diagnosis'),
            'res_model': 'car.diagnosis',
            'res_id': self.diagnosis_id.id,
            'view_mode': 'form',
        }

    def action_view_repair_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Order'),
            'res_model': 'car.repair.order',
            'res_id': self.repair_order_id.id,
            'view_mode': 'form',
        }


class CarRepairWorkorderLine(models.Model):
    """Job to perform on one car of the work order."""
    _name = 'car.repair.workorder.line'
    _description = 'Car Repair Work Order Line'

    workorder_id = fields.Many2one(
        'car.repair.workorder', required=True, ondelete='cascade', index=True)
    car_line_id = fields.Many2one('car.repair.order.line', string='Car')
    vehicle_id = fields.Many2one(
        related='car_line_id.vehicle_id', string='Vehicle', store=True)
    product_id = fields.Many2one('product.product', string='Spare Part / Service')
    description = fields.Char()
    quantity = fields.Float(default=1.0)
    is_done = fields.Boolean(string='Done')


class CarRepairWorkorderTime(models.Model):
    """One start/stop interval of a work order, so pause/resume accumulates."""
    _name = 'car.repair.workorder.time'
    _description = 'Car Repair Work Order Time Log'
    _order = 'date_start desc'

    workorder_id = fields.Many2one(
        'car.repair.workorder', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='Technician', required=True)
    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime()
    duration = fields.Float(
        string='Hours', compute='_compute_duration', store=True, aggregator='sum')

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for log in self:
            if log.date_start and log.date_end:
                delta = log.date_end - log.date_start
                log.duration = delta.total_seconds() / 3600.0
            else:
                log.duration = 0.0
