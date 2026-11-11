# SOLO LECTURA. Una fila por tanda del embudo: a qué hora salió el correo 01 y qué pasó después.
# Sin datos personales. No guarda nada.
import pytz
from odoo import fields
from datetime import timedelta
madrid = pytz.timezone('Europe/Madrid')
DIAS = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
Lead = env['crm.lead'].sudo().with_context(active_test=False)
Paso = env['automation.record.step'].sudo()
primeros = Paso.search([('configuration_step_id.step_type', '=', 'mail'), ('parent_id', '=', False),
                        ('state', '=', 'done'), ('record_id.model', '=', 'crm.lead'), ('is_test', '=', False)])
Mensaje = env['mail.message'].sudo()
def respondio(lead):
    # Correo ENTRANTE en el lead: de tipo email y que no lo haya mandado la empresa
    return bool(Mensaje.search_count([('model', '=', 'crm.lead'), ('res_id', '=', lead.id), ('message_type', '=', 'email'),
                                      ('email_from', 'not ilike', 'nuevavision.es')]))
tandas = {}
for paso in primeros:
    lead = Lead.browse(paso.record_id.res_id).exists()
    if not lead or lead.name == 'PRUEBA REBOTE (borrar)':
        continue
    clave = lead.nv_bloque_embudo or ('leads del CRM, alta del %s' % pytz.utc.localize(paso.processed_on).astimezone(madrid).strftime('%d/%m'))
    tandas.setdefault(clave, []).append((paso, lead))
print('%-28s %-14s %5s %5s %5s %7s %7s %5s %5s %5s %5s' % (
    'tanda', 'envío (Madrid)', 'env.', 'reb.', 'entr.', 'abr.72h', 'abr.tot', 'clic', 'resp.', 'baja', 'gan.'))
for clave, filas in sorted(tandas.items(), key=lambda kv: min(p.processed_on for p, _l in kv[1])):
    salida = min(p.processed_on for p, _l in filas)
    local = pytz.utc.localize(salida).astimezone(madrid)
    reb = sum(1 for p, l in filas if p.mail_status == 'bounce' or l.message_bounce > 0)
    abre = [p for p, _l in filas if p.mail_opened_on]
    abre72 = [p for p in abre if p.mail_opened_on <= p.processed_on + timedelta(hours=72)]
    medido = '' if fields.Datetime.now() >= salida + timedelta(hours=72) else '*'
    print('%-28s %-14s %5d %5d %5d %6d%s %7d %5d %5d %5d %5d' % (
        clave[:28], '%s %s' % (DIAS[local.weekday()], local.strftime('%d/%m %H:%M')), len(filas), reb, len(filas) - reb,
        len(abre72), medido or ' ', len(abre), sum(1 for p, _l in filas if p.mail_clicked_on),
        sum(1 for p, l in filas if p.mail_status == 'reply' or respondio(l)), sum(1 for _p, l in filas if l.is_blacklisted),
        sum(1 for _p, l in filas if l.stage_id.is_won)))
print('* = aún no han pasado 72 horas desde el envío; la cifra puede subir')
env.cr.rollback()
