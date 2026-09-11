from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    can_edit_readings = fields.Boolean(
        string='Puede modificar lectura anterior',
        default=False,
    )

    def _set_water_home_action(self):
        action = self.env.ref(
            'water_meter_reading.action_water_period',
            raise_if_not_found=False,
        )
        if not action:
            return
        water_group = self.env.ref(
            'water_meter_reading.group_water_user',
            raise_if_not_found=False,
        )
        if not water_group:
            return
        users = self.filtered(lambda user: water_group in user.all_group_ids)
        users.filtered(lambda user: user.action_id != action).sudo().write({
            'action_id': action.id,
        })

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._set_water_home_action()
        return users

    def write(self, vals):
        result = super().write(vals)
        if 'group_ids' in vals:
            self._set_water_home_action()
        return result
