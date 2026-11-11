# SOLO LECTURA. Export detallado del embudo: una fila por oportunidad y correo enviado.
# Sin nombres, correos ni teléfonos: el cliente va por su número de Nesto.
# Uso (root):
#   su -s /bin/bash odoo -c "/usr/bin/odoo shell -c /etc/odoo/odoo.conf -d odoo_nv --no-http --log-level=warn < /tmp/exportar_envios_embudo.py"
# (el usuario odoo no lee /root: copiar antes el guion a /tmp con permisos 644)
# Deja el fichero en /tmp/envios_embudo_AAAAMMDD_HHMM.csv (separador ;, UTF-8) y no guarda nada en Odoo.
import csv
import re
import pytz
from odoo import fields

MADRID = pytz.timezone('Europe/Madrid')
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
COLUMNAS = ['cliente_nesto', 'bloque', 'puerta', 'oportunidad_id', 'correo', 'envio_fecha', 'envio_hora', 'dia_semana',
            'estado', 'rebote', 'apertura', 'apertura_fecha_hora', 'minutos_hasta_apertura', 'clic', 'clic_fecha_hora',
            'respuesta', 'respuesta_fecha_hora', 'baja', 'rebotes_oportunidad', 'ganada']


def local(momento):
    return pytz.utc.localize(momento).astimezone(MADRID) if momento else None


def texto(momento):
    return local(momento).strftime('%Y-%m-%d %H:%M') if momento else ''


def filas_de_envios(env):
    Lead = env['crm.lead'].sudo().with_context(active_test=False)
    pasos = env['automation.record.step'].sudo().search(
        [('configuration_step_id.step_type', '=', 'mail'), ('state', '=', 'done'),
         ('record_id.model', '=', 'crm.lead'), ('is_test', '=', False)], order='processed_on, id')
    filas = []
    for paso in pasos:
        lead = Lead.browse(paso.record_id.res_id).exists()
        if not lead or (lead.name or '').startswith('PRUEBA REBOTE'):
            continue
        numero = re.search(r'Correo (\d+)', paso.configuration_step_id.name or '')
        envio = local(paso.processed_on)
        respuesta = paso.mail_replied_on if 'mail_replied_on' in paso._fields else False
        abierto = paso.mail_opened_on
        filas.append({
            'cliente_nesto': lead.partner_id.commercial_partner_id.cliente_externo or '',
            'bloque': lead.nv_bloque_embudo or '',
            'puerta': lead.campaign_id.name or '',
            'oportunidad_id': lead.id,
            'correo': numero.group(1) if numero else (paso.configuration_step_id.name or ''),
            'envio_fecha': envio.strftime('%Y-%m-%d') if envio else '',
            'envio_hora': envio.strftime('%H:%M') if envio else '',
            'dia_semana': DIAS[envio.weekday()] if envio else '',
            'estado': paso.mail_status or '',
            'rebote': 1 if paso.mail_status == 'bounce' else 0,
            'apertura': 1 if abierto else 0,
            'apertura_fecha_hora': texto(abierto),
            'minutos_hasta_apertura': int((abierto - paso.processed_on).total_seconds() // 60) if abierto and paso.processed_on else '',
            'clic': 1 if paso.mail_clicked_on else 0,
            'clic_fecha_hora': texto(paso.mail_clicked_on),
            'respuesta': 1 if (respuesta or paso.mail_status == 'reply') else 0,
            'respuesta_fecha_hora': texto(respuesta),
            'baja': 1 if lead.is_blacklisted else 0,
            'rebotes_oportunidad': lead.message_bounce,
            'ganada': 1 if lead.stage_id.is_won else 0,
        })
    return filas


if __name__ == '__main__' or 'env' in globals():
    filas = filas_de_envios(env)  # noqa: F821 (env lo pone la consola de Odoo)
    destino = '/tmp/envios_embudo_%s.csv' % local(fields.Datetime.now()).strftime('%Y%m%d_%H%M')
    with open(destino, 'w', newline='', encoding='utf-8') as fichero:
        escritor = csv.DictWriter(fichero, fieldnames=COLUMNAS, delimiter=';')
        escritor.writeheader()
        escritor.writerows(filas)
    env.cr.rollback()  # noqa: F821
    print('Escrito %s: %d filas' % (destino, len(filas)))
    resumen = {}
    for f in filas:
        clave = (f['bloque'] or 'leads del CRM', f['correo'], f['envio_fecha'])
        r = resumen.setdefault(clave, [0, 0, 0, 0])
        r[0] += 1; r[1] += f['rebote']; r[2] += f['apertura']; r[3] += f['clic']
    for (bloque, correo, dia), (n, reb, abre, clic) in sorted(resumen.items(), key=lambda kv: kv[0][2]):
        print('  %s · correo %s · %s: %d enviados, %d rebotes, %d aperturas, %d clics' % (bloque, correo, dia, n, reb, abre, clic))
