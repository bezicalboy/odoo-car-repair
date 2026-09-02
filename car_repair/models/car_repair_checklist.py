from odoo import fields, models


class CarRepairChecklist(models.Model):
    """Master data of the inspection items that can be added to a repair order."""
    _name = 'car.repair.checklist'
    _description = 'Car Repair Checklist Item'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Checklist Name', required=True)
    description = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A checklist item with this name already exists.'),
    ]
