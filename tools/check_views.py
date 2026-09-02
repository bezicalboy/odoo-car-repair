"""Load every view and every action of car_repair, as the web client would."""
import sys

MODELS = [
    ('car.repair.checklist', ['list', 'form']),
    ('car.repair.order', ['list', 'form', 'kanban', 'search']),
    ('car.diagnosis', ['list', 'form', 'search']),
    ('car.repair.workorder', ['list', 'form', 'kanban', 'search']),
    ('car.diagnosis.assign', ['form']),
    ('sale.order', ['form']),
]


def main(env):
    failures = []

    for model_name, view_types in MODELS:
        for view_type in view_types:
            try:
                env[model_name].get_views([(None, view_type)])
                print('OK   view  %-28s %s' % (model_name, view_type))
            except Exception as error:  # noqa: BLE001
                failures.append((model_name, view_type, error))
                print('FAIL view  %-28s %s -> %s: %s' % (
                    model_name, view_type, '', type(error).__name__, error))

    # Every menu must point at an action that opens without crashing.
    menus = env['ir.ui.menu'].search([]).filtered(
        lambda menu: menu.action and menu.get_external_id().get(menu.id, '').startswith('car_repair.'))
    for menu in menus:
        action = menu.action
        try:
            if action._name == 'ir.actions.act_window':
                env[action.res_model].get_views(
                    [(None, mode) for mode in action.view_mode.split(',')])
            print('OK   menu  %-28s %s' % (menu.complete_name, action.display_name))
        except Exception as error:  # noqa: BLE001
            failures.append((menu.complete_name, 'menu', error))
            print('FAIL menu  %-28s %s: %s' % (
                menu.complete_name, type(error).__name__, error))

    print('---')
    print('%d menus checked, %d failures' % (len(menus), len(failures)))
    if failures:
        sys.exit(1)


main(env)  # noqa: F821 - provided by odoo shell
