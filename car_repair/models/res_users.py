from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    car_repair_role_ids = fields.Many2many(
        'res.groups', string='Car Repair Roles',
        compute='_compute_car_repair_role_ids',
        inverse='_inverse_car_repair_role_ids',
        domain=lambda self: [('category_id', '=', self._car_repair_category().id)],
        help='Roles of the car repair workshop. Roles are cumulative: ticking '
             'Service Manager also grants the Head Technician and Technician '
             'rights, so those boxes tick themselves once saved.')

    @api.model
    def _car_repair_category(self):
        return self.env.ref('car_repair.module_category_car_repair')

    @api.model
    def _car_repair_roles(self):
        return self.env['res.groups'].search(
            [('category_id', '=', self._car_repair_category().id)])

    @api.depends('groups_id')
    def _compute_car_repair_role_ids(self):
        roles = self._car_repair_roles()
        for user in self:
            user.car_repair_role_ids = user.groups_id & roles

    def _inverse_car_repair_role_ids(self):
        roles = self._car_repair_roles()
        for user in self:
            user.groups_id = (user.groups_id - roles) | user.car_repair_role_ids
