from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    car_line_id = fields.Many2one('car.repair.order.line', string='Car')
    car_model_id = fields.Many2one(
        related='car_line_id.model_id', string='Model #', store=True)
    car_license_plate = fields.Char(
        related='car_line_id.license_plate', string='License Plate', store=True)
