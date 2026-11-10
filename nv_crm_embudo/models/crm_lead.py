import logging
import re
from datetime import timedelta

import werkzeug.urls
from markupsafe import Markup

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

DOMINIO_PROPIO = '@nuevavision.es'

# Margen para no adelantarnos a una sincronización que aún no ha terminado
MINUTOS_MARGEN = 2
# Nesto manda un mensaje por contacto y el cliente principal llega el primero: las personas
# de contacto (que son quienes traen el email) pueden tardar. Mientras el cliente no llegue
# a esta edad se reintenta en cada pasada; después se da por revisado aunque no haya salido nada.
HORAS_REINTENTO = 24
# Tope de la consulta: un cliente más viejo que esto ya no se mira aunque quedara sin marcar
# (con HORAS_REINTENTO todos acaban marcados, esto es solo una red por si hubo una parada larga)
DIAS_VENTANA = 30

# Dirección de envío de los correos del embudo. El nombre visible es «Nueva Visión | vendedora».
PARAM_EMAIL_FROM_EMBUDO = 'nv_crm_embudo.email_from_embudo'
EMAIL_FROM_EMBUDO_POR_DEFECTO = 'marketing@nuevavision.es'
# Enlace de la posdata de la app (Google Play, con el referrer de campaña como en NestoAPI)
PARAM_URL_APP = 'nv_crm_embudo.url_app'
URL_APP_POR_DEFECTO = ('https://play.google.com/store/apps/details?id=com.nuevavision.nestotiendas'
                       '&referrer=utm_source%3Dembudo%26utm_medium%3Dcorreo%26utm_campaign%3Dembudo_leads')
# Copias del aviso «el lead ha contestado» (direcciones separadas por comas)
PARAM_CC_DIRECCION = 'nv_crm_embudo.cc_direccion'
PARAM_CC_JEFE_EQUIPO = 'nv_crm_embudo.cc_jefe_equipo'
# Equipo de ventas (crm.team) del jefe de equipo: su id o su nombre exacto
PARAM_EQUIPO_JEFE = 'nv_crm_embudo.equipo_jefe_equipo'


def _ultimos9(numero):
    digitos = re.sub(r'\D', '', numero or '')
    return digitos[-9:] if len(digitos) >= 9 else False


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ---------------------------------------------------------------- baja

    def _nv_baja_token(self):
        self.ensure_one()
        return tools.hmac(self.env(su=True), 'nv_embudo_baja', (self.id, self.email_normalized or ''))

    def nv_url_baja(self):
        """URL de baja para usar en las plantillas de correo del embudo."""
        self.ensure_one()
        return werkzeug.urls.url_join(self.get_base_url(), '/nv/baja/%s/%s' % (self.id, self._nv_baja_token()))

    # --------------------------------------------- plantillas del embudo

    def nv_nombre_saludo(self):
        """Nombre para el «Hola …» de los correos del embudo (vacío si no hay nada fiable).

        De una persona se coge solo el nombre de pila (la primera palabra, y si viene todo en
        mayúsculas, como suele llegar de Nesto, con la primera en mayúscula). Si solo hay
        empresa, va el nombre de la empresa entero: «Hola Peluquería» quedaría peor.
        """
        self.ensure_one()
        persona = self.contact_name
        if not persona and self.partner_id and not self.partner_id.is_company:
            persona = self.partner_id.name
        if persona and persona.strip():
            nombre = persona.split()[0]
            # Una persona de contacto sin nombre en Nesto llega con su correo como nombre
            if '@' in nombre:
                return ''
            return nombre.capitalize() if nombre.isupper() else nombre
        empresa = self.partner_name or (self.partner_id.name if self.partner_id else '')
        return (empresa or '').strip()

    def nv_ya_compra(self):
        """True si el cliente del lead ya ha hecho algún pedido en Nesto (FINAL B del correo).

        Mismo criterio que el avance a Ganado (#9): fecha_primer_pedido en cualquier contacto
        de la familia del cliente principal.
        """
        self.ensure_one()
        if not self.partner_id:
            return False
        if self.nv_bloque_embudo:
            # Reactivación: los pedidos de hace años no cuentan, solo uno posterior a la entrada
            return self._nv_ha_comprado_tras_entrar()
        _presupuesto, pedido = self._nv_fechas_cliente(self.partner_id.sudo().commercial_partner_id)
        return bool(pedido)

    def nv_email_from_embudo(self):
        """Remitente de los correos del embudo: «Nueva Visión | Vendedora» <dirección estable>.

        La dirección sale del parámetro del sistema nv_crm_embudo.email_from_embudo y, si no
        existe, de EMAIL_FROM_EMBUDO_POR_DEFECTO.
        """
        self.ensure_one()
        direccion = (self.env['ir.config_parameter'].sudo().get_param(PARAM_EMAIL_FROM_EMBUDO)
                     or EMAIL_FROM_EMBUDO_POR_DEFECTO).strip()
        nombre = 'Nueva Visión | %s' % self.user_id.name if self.user_id else 'Nueva Visión'
        return tools.formataddr((nombre, direccion))

    def nv_url_app(self):
        """Enlace de la posdata de la app (parámetro nv_crm_embudo.url_app)."""
        return (self.env['ir.config_parameter'].sudo().get_param(PARAM_URL_APP) or URL_APP_POR_DEFECTO).strip()

    # ------------------------------------------- aviso «el lead ha contestado»

    def _nv_param(self, clave):
        return (self.env['ir.config_parameter'].sudo().get_param(clave) or '').strip()

    def _nv_es_equipo_jefe(self):
        """True si el lead o su vendedora son del equipo del jefe de equipo.

        El equipo se configura en nv_crm_embudo.equipo_jefe_equipo (id o nombre del crm.team).
        Cuenta el equipo del lead y los equipos de los que es miembro la vendedora.
        """
        self.ensure_one()
        valor = self._nv_param(PARAM_EQUIPO_JEFE)
        if not valor:
            return False
        equipos = self.team_id | self.user_id.sudo().crm_team_ids
        if valor.isdigit():
            return int(valor) in equipos.ids
        return valor.casefold() in {nombre.casefold() for nombre in equipos.mapped('name') if nombre}

    def nv_cc_aviso_respuesta(self):
        """Copias del aviso: Dirección y, si es de su equipo, el jefe de equipo. Sin repetir a la vendedora."""
        self.ensure_one()
        direcciones = self._nv_param(PARAM_CC_DIRECCION).split(',')
        # En los bloques de reactivación el reparto ya lo ha hecho Nesto por código postal
        # (si toca al equipo del jefe, el destinatario es él): la copia es solo a Dirección.
        if not self.nv_bloque_embudo and self._nv_es_equipo_jefe():
            direcciones += self._nv_param(PARAM_CC_JEFE_EQUIPO).split(',')
        # Ni la vendedora ni el responsable del bloque: ya son los destinatarios
        vistas = {tools.email_normalize(self.user_id.email or ''),
                  tools.email_normalize(self.nv_responsable_embudo_email or '')}
        copias = []
        for direccion in (d.strip() for d in direcciones):
            normalizada = tools.email_normalize(direccion)
            if normalizada and normalizada not in vistas:
                vistas.add(normalizada)
                copias.append(direccion)
        return ', '.join(copias)

    def nv_ultima_respuesta(self):
        """Último correo que ha entrado en el lead (la respuesta del cliente), o vacío."""
        self.ensure_one()
        return self.env['mail.message'].sudo().search([
            ('model', '=', self._name), ('res_id', '=', self.id), ('message_type', '=', 'email'),
            ('author_id', '!=', self.user_id.partner_id.id or False),
        ], order='id desc', limit=1)

    def nv_avisar_respuesta(self):
        """Correo a la vendedora con copias cuando el lead contesta a un correo del embudo.

        Lo llama la acción de servidor del paso de la rama «ha contestado» de automation_oca
        (código: records.nv_avisar_respuesta()). La tarea la crea otro paso; esto es solo el aviso.
        Un lead sin vendedora con email no manda nada (queda en el log).

        Los leads de un bloque de reactivación nacen sin vendedora: el aviso va al
        responsable que mandó Nesto (por código postal) y, si tiene usuario en Odoo, se le
        pone como vendedor en este momento.
        """
        plantilla = self.env.ref('nv_crm_embudo.embudo_aviso_respuesta')
        for lead in self:
            valores = None
            if lead.nv_bloque_embudo:
                lead._nv_asignar_responsable()
                destino = lead.nv_responsable_embudo_email or lead.user_id.email
                copias = lead.nv_cc_aviso_respuesta()
                if not destino:
                    # Nesto no mandó responsable: que al menos se entere Dirección
                    destino, copias = copias, ''
                valores = {'email_to': destino, 'email_cc': copias or False}
            else:
                destino = lead.user_id.email
            if not destino:
                _logger.warning('Lead %s ha contestado al embudo pero no hay a quién avisar: sin aviso', lead.id)
                continue
            plantilla.sudo().send_mail(lead.id, force_send=False, email_values=valores)
        return True

    # ------------------------------------------- enlace con clientes de Nesto

    @api.model
    def _nv_cron_enlazar_clientes_nesto(self, limite=100):
        """Busca el lead de origen de cada cliente creado en Nesto desde la última pasada.

        Va aparte de la sincronización a propósito: si algo falla aquí, el mensaje de Nesto
        ya está guardado y no se reintenta ni acaba en la DLQ.

        Cada cliente se marca con `nv_lead_revisado` cuando se resuelve, en vez de llevar un
        marcador de «último id visto»: el cliente principal se crea antes que sus personas de
        contacto (validate_cliente_principal_exists lo exige), así que un cliente sin emails
        todavía puede tenerlos dentro de un rato y hay que volver a mirarlo. Los clientes que
        ya existían al instalar el módulo quedan marcados por el post_init_hook.
        """
        # Antes del enlace: los clientes de Meta (#43) tienen su propia oportunidad
        self._nv_crear_oportunidades_origen()
        self._nv_enlazar_clientes_nuevos(limite)
        # Después del enlace: los bloques de reactivación miran si la persona ya tiene lead
        self._nv_poblar_embudo_bloques()

    @api.model
    def _nv_enlazar_clientes_nuevos(self, limite=100):
        ahora = fields.Datetime.now()
        clientes = self.env['res.partner'].sudo().with_context(active_test=False).search([
            ('cliente_externo', '!=', False),
            ('parent_id', '=', False),
            ('nv_lead_revisado', '=', False),
            ('create_date', '>', ahora - timedelta(days=DIAS_VENTANA)),
            ('create_date', '<=', ahora - timedelta(minutes=MINUTOS_MARGEN)),
        ], order='create_date', limit=limite)
        if not clientes:
            return

        # Una sola lectura de leads por pasada, no una por cliente
        leads = self._nv_leads_abiertos()
        for cliente in clientes:
            agotado = cliente.create_date <= ahora - timedelta(hours=HORAS_REINTENTO)
            try:
                with self.env.cr.savepoint():
                    resuelto = self._nv_enlazar_cliente_nesto(cliente, leads)
            except Exception:
                _logger.exception('No se ha podido enlazar el cliente %s de Nesto con su lead',
                                  cliente.cliente_externo)
                resuelto = False
            if resuelto:
                cliente._nv_marcar_lead_revisado()
            elif agotado:
                _logger.info('Cliente %s de Nesto: sin lead de origen tras %s horas, se deja de buscar',
                             cliente.cliente_externo, HORAS_REINTENTO)
                cliente._nv_marcar_lead_revisado()

    @api.model
    def _nv_datos_contacto_cliente(self, cliente):
        familia = cliente | cliente.with_context(active_test=False).child_ids
        emails = {
            p.email_normalized for p in familia
            if p.email_normalized and not p.email_normalized.endswith(DOMINIO_PROPIO)
        }
        telefonos = {t for p in familia for t in (_ultimos9(p.phone), _ultimos9(p.mobile)) if t}
        return emails, telefonos

    @api.model
    def _nv_leads_abiertos(self):
        """Leads abiertos y sin cliente de Nesto, leídos una sola vez por pasada.

        Se leen con search_read (solo las tres columnas que hacen falta, sin recordsets) y se
        comparan en Python: el criterio son los últimos 9 dígitos del teléfono y en la base de
        datos están con espacios, prefijos y guiones, así que un LIKE sobre la columna no vale.
        """
        return self.sudo().search_read([
            # En producción no se usan leads sin convertir: los 198 registros son oportunidades
            ('type', '=', 'opportunity'),
            ('stage_id.is_won', '=', False),
            '|', ('partner_id', '=', False),
            ('partner_id.commercial_partner_id.cliente_externo', '=', False),
        ], ['email_normalized', 'phone', 'mobile'])

    @api.model
    def _nv_leads_candidatos(self, emails, telefonos, leads):
        """De los leads leídos, los de este cliente: {lead: 'email y teléfono'}."""
        candidatos = {}
        for lead in leads:
            coincide = []
            if lead['email_normalized'] and lead['email_normalized'] in emails:
                coincide.append('email')
            if {_ultimos9(lead['phone']), _ultimos9(lead['mobile'])} & telefonos:
                coincide.append('teléfono')
            if coincide:
                candidatos[self.browse(lead['id'])] = ' y '.join(coincide)
        return candidatos

    @api.model
    def _nv_enlazar_cliente_nesto(self, cliente, leads):
        """Devuelve True si el cliente queda resuelto (enlazado o pasado a la vendedora)."""
        emails, telefonos = self._nv_datos_contacto_cliente(cliente)
        if not emails and not telefonos:
            return False
        candidatos = self._nv_leads_candidatos(emails, telefonos, leads)
        if not candidatos:
            return False
        if len(candidatos) == 1:
            lead, motivo = next(iter(candidatos.items()))
            etapa = self.env.ref('nv_crm_embudo.stage_cliente_nesto', raise_if_not_found=False)
            lead._nv_enlazar_con_cliente(cliente, motivo, etapa)
            # Si el cliente ya traía fechas de compras, el lead avanza en el acto
            self._nv_avanzar_por_fechas(cliente)
            return True

        # No elegimos por la vendedora: que lo decida ella
        for lead in candidatos:
            responsable = self._nv_responsable_tarea(lead, cliente)
            if not responsable:
                _logger.warning('Lead %s del cliente %s de Nesto: sin responsable activo, no se crea la tarea',
                                lead.id, cliente.cliente_externo)
                continue
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='¿Este lead es el cliente %s de Nesto?' % cliente.cliente_externo,
                note=Markup('<p>Se ha creado en Nesto el cliente <b>%s %s</b>, que coincide con %s leads abiertos. '
                            'Enlaza el que corresponda poniéndole ese cliente.</p>')
                % (cliente.cliente_externo, cliente.name, len(candidatos)),
                user_id=responsable.id,
            )
        _logger.info('Cliente %s de Nesto: %s leads candidatos, se pide a la vendedora que elija',
                     cliente.cliente_externo, len(candidatos))
        return True

    @api.model
    def _nv_responsable_tarea(self, lead, cliente):
        """Primer usuario activo entre la vendedora del lead y la del cliente.

        En el cron `env.user` es OdooBot, así que no sirve de recambio: una tarea suya no la
        ve nadie. Si no hay vendedora activa se avisa por log y no se crea la tarea.
        """
        for usuario in (lead.user_id, cliente.user_id):
            if usuario and usuario.active:
                return usuario
        return self.env['res.users'].browse()

    def _nv_enlazar_con_cliente(self, cliente, motivo='email o teléfono', etapa=None):
        self.ensure_one()
        antes = [
            (etiqueta, self[campo]) for etiqueta, campo in (
                ('Empresa', 'partner_name'), ('Contacto', 'contact_name'), ('Email', 'email_from'),
                ('Teléfono', 'phone'), ('Móvil', 'mobile'), ('Dirección', 'street'),
                ('Población', 'city'), ('C.P.', 'zip'))
            if self[campo]
        ]
        if self.partner_id:
            antes.append(('Cliente anterior', self.partner_id.display_name))
        vals = {'partner_id': cliente.id}
        if etapa and self.stage_id.sequence < etapa.sequence:
            vals['stage_id'] = etapa.id
        # Al poner el cliente, Odoo copia al lead los datos de la ficha de Nesto (nombre, dirección...).
        # La ficha del cliente no se toca, así que no se publica nada hacia Nesto.
        self.write(vals)
        filas = Markup('').join(Markup('<li>%s: %s</li>') % (e, v) for e, v in antes)
        self.message_post(
            body=Markup('<p>Enlazado automáticamente con el cliente <b>%s</b> de Nesto (coincide por %s).</p>'
                        '<p>Datos que tenía el lead antes del enlace:</p><ul>%s</ul>')
            % (cliente.cliente_externo, motivo, filas),
            message_type='comment', subtype_xmlid='mail.mt_note',
        )
        _logger.info('Lead %s enlazado con el cliente %s de Nesto', self.id, cliente.cliente_externo)

    # ------------------------------------- avance por las fechas de compras

    @api.model
    def _nv_avanzar_por_fechas(self, clientes):
        """Mueve los leads abiertos de estos clientes según sus fechas de compras (#9, paso 2).

        Se mira el estado actual del cliente, no qué campo ha cambiado: así da igual el orden
        en que lleguen los mensajes de Nesto y volver a llamar no hace daño. Nunca se retrocede
        de etapa, y un presupuesto que se acepta (FechaPrimerPresupuesto vuelve a null en Nesto)
        no devuelve el lead a su etapa anterior.
        """
        etapa_presupuesto = self.env.ref('nv_crm_embudo.stage_presupuesto', raise_if_not_found=False)
        for cliente in clientes:
            leads = self.sudo().search([
                ('partner_id.commercial_partner_id', '=', cliente.id),
                ('stage_id.is_won', '=', False),
            ])
            # Los de un bloque de reactivación ya eran clientes: solo los mueve un pedido nuevo
            de_bloque = leads.filtered('nv_bloque_embudo')
            de_bloque._nv_avanzar_reactivacion(cliente)
            leads -= de_bloque
            if not leads:
                continue
            fecha_presupuesto, fecha_pedido = self._nv_fechas_cliente(cliente)
            if fecha_pedido:
                leads._nv_ganar_por_primer_pedido(cliente, fecha_pedido)
            elif fecha_presupuesto and etapa_presupuesto:
                leads._nv_pasar_a_presupuesto(cliente, fecha_presupuesto, etapa_presupuesto)

    @api.model
    def _nv_fechas_cliente(self, cliente):
        """Las fechas de compras del cliente, miradas en toda su familia de contactos.

        Son del cliente (Nº_Cliente), pero Nesto publica un mensaje por contacto y los campos
        no son de los que Odoo propaga entre la empresa y sus contactos: la fecha se queda en
        el contacto cuyo mensaje llegó. Vale cualquiera de la familia y, si hay varias, la más
        antigua, que es la que de verdad marca cuándo empezó.
        """
        familia = cliente | cliente.with_context(active_test=False).child_ids
        presupuestos = [p.fecha_primer_presupuesto for p in familia if p.fecha_primer_presupuesto]
        pedidos = [p.fecha_primer_pedido for p in familia if p.fecha_primer_pedido]
        return min(presupuestos, default=False), min(pedidos, default=False)

    def _nv_ganar_por_primer_pedido(self, cliente, fecha):
        """Ganado de verdad: el cliente ha hecho su primer pedido en Nesto."""
        for lead in self:
            lead.message_post(
                body=Markup('<p>Ganado automáticamente: el cliente <b>%s</b> hizo su primer pedido '
                            'en Nesto el <b>%s</b>.</p>')
                % (cliente.cliente_externo or cliente.display_name, fields.Date.to_string(fecha)),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
        self.action_set_won()
        _logger.info('Leads %s ganados por el primer pedido del cliente %s de Nesto',
                     self.ids, cliente.cliente_externo)

    def _nv_pasar_a_presupuesto(self, cliente, fecha, etapa):
        """Solo hacia delante: un lead que ya esté más avanzado se queda donde está."""
        pendientes = self.filtered(lambda lead: lead.stage_id.sequence < etapa.sequence)
        if not pendientes:
            return
        pendientes.write({'stage_id': etapa.id})
        for lead in pendientes:
            lead.message_post(
                body=Markup('<p>El cliente <b>%s</b> tiene su primer presupuesto en Nesto del '
                            '<b>%s</b>.</p>')
                % (cliente.cliente_externo or cliente.display_name, fields.Date.to_string(fecha)),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
        _logger.info('Leads %s pasados a Presupuesto por el cliente %s de Nesto',
                     pendientes.ids, cliente.cliente_externo)
