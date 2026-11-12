"""Ritmo automático del embudo de reactivación.

Dos piezas:

- El motivo de cada rebote (dirección inexistente, temporal, política o spam), que Odoo no
  guarda de fábrica y es la señal de alarma para no subir el volumen.
- Una recomendación diaria (subir / mantener / bajar / parar) sobre los últimos 7 días, que
  NestoAPI lee por /nv/embudo/recomendacion y aplica al tamaño del bloque diario. Odoo no
  escribe nada en Nesto.
"""
import logging
import re
from datetime import timedelta

from odoo import api, fields, models

from .reactivacion import PARAM_POR_DIA

_logger = logging.getLogger(__name__)

# Tamaños del bloque diario. Por encima de 100 hace falta otra vía de envío (decisión de Carlos).
ESCALONES = [50, 75, 100]
TECHOS = {50: 75, 75: 100, 100: 150}
DIAS_VENTANA = 7
TANDAS_MINIMAS = 5
PARAM_CLAVE = 'nv_crm_embudo.clave_recomendacion'

MOTIVOS_REBOTE = [
    ('inexistente', 'La dirección no existe'),
    ('temporal', 'Buzón lleno o fallo temporal'),
    ('politica', 'Rechazado por política o spam'),
    ('otro', 'Otro motivo'),
]
_CODIGO = re.compile(r'\b([245])\.(\d{1,3})\.(\d{1,3})\b')
_SPAM = re.compile(r'spam|blocked|block list|blocklist|blacklist|reputation|policy|unsolicited|junk|'
                   r'not authenticated|dmarc|spf|dkim|rejected due to|banned', re.I)
_INEXISTENTE = re.compile(r'user unknown|unknown user|does not exist|doesn\'t exist|no such user|no such recipient|'
                          r'mailbox not found|recipient not found|address not found|invalid recipient|'
                          r'recipientnotfound|couldn\'t be found|wasn\'t found|no mailbox|mailbox unavailable|'
                          r'account (?:is )?disabled|account that you tried to reach', re.I)


def clasificar_rebote(texto):
    """(motivo, código) de un aviso de no entregado, a partir de su texto completo.

    Manda el código de estado (RFC 3463). Las palabras solo deciden cuando no hay código,
    o para reconocer una dirección inexistente que el servidor ha devuelto como 5.7.x: el
    aviso incluye las cabeceras del correo original (spf, dkim...) y buscar «spam» en todo
    el texto daría falsos positivos.
    """
    texto = texto or ''
    estado = re.search(r'^Status:\s*([245]\.\d{1,3}\.\d{1,3})', texto, re.M | re.I)
    suelto = _CODIGO.search(texto)
    codigo = estado.group(1) if estado else (suelto.group(0) if suelto else '')
    if not codigo:
        if _INEXISTENTE.search(texto):
            return 'inexistente', ''
        return ('politica' if _SPAM.search(texto) else 'otro'), ''
    clase, tema = codigo.split('.')[:2]
    if clase == '4':
        return 'temporal', codigo
    if tema in ('1', '4') or (tema == '7' and _INEXISTENTE.search(texto)):
        return 'inexistente', codigo
    if tema == '7':
        return 'politica', codigo
    if tema in ('2', '3'):
        return 'temporal', codigo
    return 'otro', codigo


def decidir(actual, previa, escalon):
    """La recomendación a partir de las cifras de la ventana actual y de la anterior.

    `actual` y `previa` son diccionarios con tandas, enviados, entregados, rebotes,
    rebotes_politica, fallos_envio, bajas y aperturas (`previa` puede venir vacía).
    Devuelve (recomendación, escalón recomendado, motivo).
    """
    def tasa(cifras, arriba, abajo):
        return (cifras.get(arriba, 0) / cifras[abajo]) if cifras.get(abajo) else 0.0

    posicion = ESCALONES.index(escalon)
    anterior = ESCALONES[max(posicion - 1, 0)]
    rebote, rebote_previo = tasa(actual, 'rebotes', 'enviados'), tasa(previa, 'rebotes', 'enviados')
    if not actual.get('enviados'):
        return 'mantener', escalon, 'Sin envíos en los últimos %s días' % DIAS_VENTANA
    if actual.get('rebotes_politica', 0) >= max(3, 0.05 * actual['enviados']):
        return 'parar', escalon, '%s rebotes por política o spam' % actual['rebotes_politica']
    if actual.get('fallos_envio', 0) >= 0.10 * actual['enviados']:
        return 'parar', escalon, '%s correos no han podido salir' % actual['fallos_envio']
    problemas = []
    if actual.get('rebotes_politica'):
        problemas.append('%s rebote(s) por política o spam' % actual['rebotes_politica'])
    if actual.get('fallos_envio'):
        problemas.append('%s correo(s) no han podido salir' % actual['fallos_envio'])
    if rebote > 0.25:
        problemas.append('rebote del %d %%' % round(rebote * 100))
    if problemas:
        if anterior < escalon:
            return 'bajar', anterior, '; '.join(problemas)
        return 'mantener', escalon, '; '.join(problemas) + ' (ya en el escalón mínimo)'
    if posicion == len(ESCALONES) - 1:
        return 'mantener', escalon, 'Escalón máximo por esta vía de envío'
    if actual.get('tandas', 0) < TANDAS_MINIMAS or actual.get('escalones', 1) > 1:
        return 'mantener', escalon, 'Datos insuficientes: %s tanda(s) en este escalón' % actual.get('tandas', 0)
    frenos = []
    if previa.get('enviados') and rebote > rebote_previo + 0.02:
        frenos.append('el rebote sube del %d %% al %d %%' % (round(rebote_previo * 100), round(rebote * 100)))
    if tasa(actual, 'bajas', 'entregados') >= 0.01:
        frenos.append('bajas del %.1f %%' % (tasa(actual, 'bajas', 'entregados') * 100))
    apertura, apertura_previa = tasa(actual, 'aperturas', 'entregados'), tasa(previa, 'aperturas', 'entregados')
    if previa.get('entregados') and apertura_previa and apertura < apertura_previa * 2 / 3:
        frenos.append('las aperturas caen del %d %% al %d %%' % (round(apertura_previa * 100), round(apertura * 100)))
    if frenos:
        return 'mantener', escalon, '; '.join(frenos)
    return 'subir', ESCALONES[posicion + 1], 'Semana limpia: rebote del %d %%, sin fallos ni rechazos' % round(rebote * 100)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _routing_handle_bounce(self, email_message, message_dict):
        resultado = super()._routing_handle_bounce(email_message, message_dict)
        try:
            Lead = self.env['crm.lead'].sudo().with_context(active_test=False)
            mensaje = message_dict.get('bounced_message')
            leads = Lead
            if mensaje and mensaje.model == 'crm.lead' and mensaje.res_id:
                leads = Lead.browse(mensaje.res_id).exists()
            if not leads and message_dict.get('bounced_email'):
                # Hay avisos (los de Google, por ejemplo) que no traen el identificador del correo
                # original: Odoo anota el rebote en las oportunidades con esa dirección, pero no
                # sabe cuál lo provocó. El motivo se guarda en esas mismas oportunidades.
                leads = Lead.search([('email_normalized', '=', message_dict['bounced_email'])])
            if leads:
                motivo, codigo = clasificar_rebote(email_message.as_string())
                leads.write({'nv_rebote_motivo': motivo, 'nv_rebote_codigo': codigo or False,
                             'nv_rebote_fecha': fields.Datetime.now()})
        except Exception:
            _logger.exception('No se ha podido clasificar un rebote; el rebote sí queda anotado')
        return resultado


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    nv_rebote_motivo = fields.Selection(MOTIVOS_REBOTE, string='Motivo del rebote', readonly=True, copy=False)
    nv_rebote_codigo = fields.Char(string='Código del rebote', readonly=True, copy=False)
    nv_rebote_fecha = fields.Datetime(string='Fecha del rebote', readonly=True, copy=False)


class NvEmbudoRecomendacion(models.Model):
    _name = 'nv.embudo.recomendacion'
    _description = 'Recomendación diaria de ritmo del embudo de reactivación'
    _order = 'calculado_el desc, id desc'
    _rec_name = 'calculado_el'

    calculado_el = fields.Datetime(required=True, readonly=True)
    ventana_desde = fields.Datetime(readonly=True)
    ventana_hasta = fields.Datetime(readonly=True)
    escalon_actual = fields.Integer(readonly=True)
    recomendacion = fields.Selection(
        [('subir', 'Subir'), ('mantener', 'Mantener'), ('bajar', 'Bajar'), ('parar', 'Parar')], readonly=True)
    escalon_recomendado = fields.Integer(readonly=True)
    techo = fields.Integer(string='Techo de Odoo', readonly=True)
    tandas = fields.Integer(readonly=True)
    enviados = fields.Integer(readonly=True)
    entregados = fields.Integer(readonly=True)
    rebotes = fields.Integer(readonly=True)
    rebotes_politica = fields.Integer(readonly=True)
    rebotes_sin_clasificar = fields.Integer(readonly=True)
    fallos_envio = fields.Integer(readonly=True)
    bajas = fields.Integer(readonly=True)
    aperturas = fields.Integer(readonly=True)
    respuestas = fields.Integer(readonly=True)
    motivo = fields.Char(readonly=True)

    @api.model
    def _nv_cifras(self, desde, hasta):
        """Cifras de los correos 01 de los bloques enviados en [desde, hasta)."""
        cifras = dict.fromkeys(('tandas', 'enviados', 'entregados', 'rebotes', 'rebotes_politica',
                                'rebotes_sin_clasificar', 'fallos_envio', 'bajas', 'aperturas', 'respuestas'), 0)
        cifras.update(escalon=ESCALONES[0], escalones=1)
        if 'automation.record.step' not in self.env:
            return cifras
        pasos = self.env['automation.record.step'].sudo().search([
            ('configuration_step_id.step_type', '=', 'mail'), ('parent_id', '=', False), ('state', '=', 'done'),
            ('record_id.model', '=', 'crm.lead'), ('is_test', '=', False),
            ('processed_on', '>=', desde), ('processed_on', '<', hasta)])
        Lead = self.env['crm.lead'].sudo().with_context(active_test=False)
        por_bloque = {}
        for paso in pasos:
            lead = Lead.browse(paso.record_id.res_id).exists()
            if not lead or not lead.nv_bloque_embudo:
                continue
            por_bloque[lead.nv_bloque_embudo] = por_bloque.get(lead.nv_bloque_embudo, 0) + 1
            rebotado = paso.mail_status == 'bounce' or lead.message_bounce > 0
            cifras['enviados'] += 1
            cifras['rebotes'] += 1 if rebotado else 0
            cifras['rebotes_politica'] += 1 if rebotado and lead.nv_rebote_motivo == 'politica' else 0
            cifras['rebotes_sin_clasificar'] += 1 if rebotado and not lead.nv_rebote_motivo else 0
            cifras['aperturas'] += 1 if paso.mail_opened_on else 0
            cifras['respuestas'] += 1 if paso.mail_status == 'reply' else 0
            cifras['bajas'] += 1 if lead.is_blacklisted else 0
        cifras['entregados'] = cifras['enviados'] - cifras['rebotes']
        cifras['tandas'] = len(por_bloque)
        if por_bloque:
            def escalon_de(tamano):
                return max([e for e in ESCALONES if e <= tamano] or [ESCALONES[0]])
            escalones = {escalon_de(n) for n in por_bloque.values()}
            cifras.update(escalon=max(escalones), escalones=len(escalones))
        remitente = self.env['crm.lead']._nv_param('nv_crm_embudo.email_from_embudo') or 'marketing@nuevavision.es'
        cifras['fallos_envio'] = self.env['mail.mail'].sudo().search_count([
            ('state', '=', 'exception'), ('model', '=', 'crm.lead'), ('email_from', 'ilike', remitente),
            ('create_date', '>=', desde), ('create_date', '<', hasta)])
        return cifras

    @api.model
    def _nv_calcular(self, ahora=None):
        """Calcula y guarda la recomendación del día, y ajusta el techo diario de Odoo."""
        ahora = ahora or fields.Datetime.now()
        desde = ahora - timedelta(days=DIAS_VENTANA)
        actual = self._nv_cifras(desde, ahora)
        previa = self._nv_cifras(desde - timedelta(days=DIAS_VENTANA), desde)
        recomendacion, recomendado, motivo = decidir(actual, previa, actual['escalon'])
        techo = TECHOS[recomendado]
        if recomendacion != 'parar':
            self.env['ir.config_parameter'].sudo().set_param(PARAM_POR_DIA, str(techo))
        fila = self.sudo().create({
            'calculado_el': ahora, 'ventana_desde': desde, 'ventana_hasta': ahora,
            'escalon_actual': actual['escalon'], 'recomendacion': recomendacion,
            'escalon_recomendado': recomendado, 'techo': techo, 'motivo': motivo,
            **{k: actual[k] for k in ('tandas', 'enviados', 'entregados', 'rebotes', 'rebotes_politica',
                                      'rebotes_sin_clasificar', 'fallos_envio', 'bajas', 'aperturas', 'respuestas')},
        })
        _logger.info('Ritmo del embudo: %s (escalón %s -> %s, techo %s). %s',
                     recomendacion, actual['escalon'], recomendado, techo, motivo)
        return fila

    def nv_json(self):
        self.ensure_one()

        def iso(momento):
            return momento.strftime('%Y-%m-%dT%H:%M:%SZ') if momento else None
        return {
            'calculadoEl': iso(self.calculado_el), 'ventanaDesde': iso(self.ventana_desde),
            'ventanaHasta': iso(self.ventana_hasta), 'escalonActual': self.escalon_actual,
            'recomendacion': self.recomendacion, 'escalonRecomendado': self.escalon_recomendado,
            'techoOdoo': self.techo, 'tandas': self.tandas, 'enviados': self.enviados,
            'entregados': self.entregados, 'rebotes': self.rebotes, 'rebotesPorPolitica': self.rebotes_politica,
            'rebotesSinClasificar': self.rebotes_sin_clasificar, 'fallosEnvio': self.fallos_envio,
            'bajas': self.bajas, 'aperturas': self.aperturas, 'respuestas': self.respuestas,
            'motivo': self.motivo or '',
        }
