from odoo import _, fields, models


class CarDiagnosisAssign(models.TransientModel):
    """Wizard used by the Head Technician to assign a technician to a diagnosis."""
    _name = 'car.diagnosis.assign'
    _description = 'Assign To Technician'

    diagnosis_id = fields.Many2one('car.diagnosis', required=True, readonly=True)
    technician_id = fields.Many2one(
        'res.users', string='Technician', required=True,
        domain="[('share', '=', False)]")

    def action_assign(self):
        self.ensure_one()
        self.diagnosis_id.technician_id = self.technician_id
        self.diagnosis_id._message_log(
            body=_('Diagnosis assigned to %s.', self.technician_id.display_name))
        self.diagnosis_id.workorder_ids.filtered(
            lambda w: w.state == 'draft').technician_id = self.technician_id
        return {'type': 'ir.actions.act_window_close'}
