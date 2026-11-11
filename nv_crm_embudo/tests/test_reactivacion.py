"""Bloques de reactivación: clientes de Nesto que entran en el embudo una sola vez."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import datetime as datetime_seguro, safe_eval

from odoo.addons.nv_crm_embudo.models.reactivacion import (
    EXCLUSION_BOLETIN, EXCLUSION_REBOTES, PARAM_POR_DIA, PARAM_USUARIO_SIN_RESPONSABLE, SIN_ESPERA_BLOQUES, _con_clausulas, _sin_espera_para_bloques)

BLOQUE = 'NV-2026-11-01'
DOMINIO_GENERAL = ("[('type', '=', 'opportunity'), ('active', '=', True), ('stage_id.is_won', '=', False), "
                   "('email_from', '!=', False), ('create_date', '<=', (datetime.datetime.now() - "
                   "datetime.timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S'))]")


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestReactivacion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env['crm.lead']
        cls.Partner = cls.env['res.partner'].with_context(skip_sync=True)
        cls.alberto = cls.env['res.users'].with_context(skip_sync=True, no_reset_password=True).create(
            {'name': 'Jefe Equipo', 'login': 'jefe@ejemplo.test', 'email': 'jefe@ejemplo.test'})
        cls.env['ir.config_parameter'].sudo().set_param('nv_crm_embudo.cc_direccion', 'direccion@ejemplo.test')
        cls.env['ir.config_parameter'].sudo().set_param(PARAM_POR_DIA, '25')
        cls.env['ir.config_parameter'].sudo().set_param(PARAM_USUARIO_SIN_RESPONSABLE, '')

    def _cliente(self, numero, emails=('uno',), bloque=BLOQUE, responsable='tienda@ejemplo.test',
                 tipo='TiendaOnline', boletin=None, **vals):
        cliente = self.Partner.create(dict({
            'name': 'CENTRO %s' % numero, 'cliente_externo': numero, 'contacto_externo': '0',
            'is_company': True, 'vendedor_nesto': 'NV', 'estado_nesto': '0', 'bloque_embudo': bloque,
            'responsable_embudo_email': responsable, 'responsable_embudo_tipo': tipo,
        }, **vals))
        for i, nombre in enumerate(emails, start=1):
            self.Partner.create({
                'name': 'ANA %s' % nombre.upper(), 'parent_id': cliente.id, 'type': 'contact',
                'email': '%s.%s@ejemplo.test' % (nombre, numero.lower()),
                'cliente_externo': numero, 'contacto_externo': '0', 'persona_contacto_externa': str(i),
                'enviar_boletin': boletin,
            })
        self._reposar()
        return cliente

    def _reposar(self):
        """Como si Nesto hubiera dejado de mandar mensajes de estos clientes hace una hora."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE res_partner SET write_date = (now() at time zone 'utc') - interval '1 hour' "
                            "WHERE cliente_externo IS NOT NULL")
        self.env.invalidate_all()

    def _leads(self, cliente):
        return self.Lead.with_context(active_test=False).search([('partner_id', 'child_of', cliente.id)])

    # ---------------------------------------------------------- entrada

    def test_entra_en_silencio_con_la_persona_y_el_responsable(self):
        cliente = self._cliente('R0001', fecha_ultimo_pedido=date(2023, 2, 1))
        correos_antes = self.env['mail.mail'].sudo().search_count([])
        self.Lead._nv_poblar_embudo_bloques()
        lead = self._leads(cliente)
        self.assertEqual(len(lead), 1)
        self.assertEqual(lead.email_from, 'uno.r0001@ejemplo.test')
        self.assertEqual(lead.nv_nombre_saludo(), 'Ana')
        self.assertEqual(lead.campaign_id.name, 'REACTIVACION-NV')
        self.assertEqual(lead.nv_bloque_embudo, BLOQUE)
        self.assertEqual(lead.nv_responsable_embudo_email, 'tienda@ejemplo.test')
        self.assertEqual(lead.nv_ultimo_pedido_al_entrar, date(2023, 2, 1))
        # Silencio: sin vendedor, sin equipo, sin correos y sin ganarse por el pedido antiguo
        self.assertFalse(lead.user_id)
        self.assertFalse(lead.team_id)
        self.assertFalse(lead.stage_id.is_won)
        self.assertFalse(lead.nv_ya_compra())
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), correos_antes)
        self.assertEqual(cliente.nv_embudo_bloque, BLOQUE)
        self.assertEqual(cliente.nv_embudo_resultado, 'oportunidad')

    def test_una_sola_vez_aunque_llegue_en_otro_bloque(self):
        cliente = self._cliente('R0002')
        self.Lead._nv_poblar_embudo_bloques()
        cliente.bloque_embudo = 'NV-2027-01-09'
        self._reposar()
        self.Lead._nv_poblar_embudo_bloques()
        self.assertEqual(len(self._leads(cliente)), 1)
        self.assertEqual(cliente.nv_embudo_bloque, BLOQUE)

    def test_correo_que_ya_tiene_un_lead_no_entra(self):
        self.Lead.create({'name': 'Lead antiguo', 'type': 'opportunity',
                          'email_from': 'uno.r0003@ejemplo.test', 'active': False})
        cliente = self._cliente('R0003')
        self.Lead._nv_poblar_embudo_bloques()
        self.assertFalse(self._leads(cliente))
        self.assertEqual(cliente.nv_embudo_resultado, 'repetido')

    def test_bajas_de_boletin_y_lista_negra(self):
        baja_nesto = self._cliente('R0004', boletin='no')
        lista_negra = self._cliente('R0005')
        self.env['mail.blacklist'].sudo().create({'email': 'uno.r0005@ejemplo.test'})
        mixto = self._cliente('R0006', emails=('uno', 'dos'))
        mixto.child_ids.filtered(lambda p: p.persona_contacto_externa == '1').enviar_boletin = 'no'
        sin_correo = self._cliente('R0007', emails=())
        self._reposar()
        self.Lead._nv_poblar_embudo_bloques()
        self.assertEqual(baja_nesto.nv_embudo_resultado, 'baja')
        self.assertEqual(lista_negra.nv_embudo_resultado, 'baja')
        self.assertEqual(sin_correo.nv_embudo_resultado, 'sin_correo')
        self.assertEqual(self._leads(mixto).email_from, 'dos.r0006@ejemplo.test')

    def test_cupo_diario(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_POR_DIA, '2')
        clientes = [self._cliente('R001%s' % i) for i in range(3)]
        self.Lead._nv_poblar_embudo_bloques()
        self.Lead._nv_poblar_embudo_bloques()
        self.assertEqual([len(self._leads(c)) for c in clientes], [1, 1, 0])
        # El tercero no queda marcado: entrará mañana
        self.assertFalse(clientes[2].nv_embudo_bloque)

    def test_espera_a_que_nesto_termine_de_mandar_el_cliente(self):
        cliente = self._cliente('R0020')
        cliente.child_ids[:1].comment = 'acaba de llegar'  # write_date de ahora
        self.env.flush_all()
        self.Lead._nv_poblar_embudo_bloques()
        self.assertFalse(self._leads(cliente))
        self.assertFalse(cliente.nv_embudo_bloque)

    def test_cliente_sin_bloque_no_entra(self):
        cliente = self._cliente('R0021', bloque=False)
        self.Lead._nv_poblar_embudo_bloques()
        self.assertFalse(self._leads(cliente))

    def test_persona_con_el_correo_como_nombre_no_se_saluda_por_el_correo(self):
        cliente = self._cliente('R0022')
        cliente.child_ids.name = 'uno.r0022@ejemplo.test'
        self._reposar()
        self.Lead._nv_poblar_embudo_bloques()
        self.assertEqual(self._leads(cliente).nv_nombre_saludo(), '')

    # ------------------------------------------------------------ avisos

    def test_pedido_nuevo_gana_y_avisa_al_responsable(self):
        cliente = self._cliente('R0030', fecha_ultimo_pedido=date(2023, 2, 1),
                                fecha_primer_pedido=date(2019, 5, 5),
                                responsable='jefe@ejemplo.test', tipo='EquipoAlberto')
        self.Lead._nv_poblar_embudo_bloques()
        lead = self._leads(cliente)
        # La misma fecha republicada no mueve nada
        cliente.fecha_ultimo_pedido = date(2023, 2, 1)
        self.assertFalse(lead.stage_id.is_won)
        cliente.fecha_ultimo_pedido = date(2026, 11, 20)
        self.assertTrue(lead.stage_id.is_won)
        self.assertTrue(lead.nv_ya_compra())
        self.assertEqual(lead.user_id, self.alberto)
        aviso = self.env['mail.mail'].sudo().search([('subject', 'like', 'Ha hecho un pedido')], order='id desc', limit=1)
        self.assertEqual(aviso.email_to, 'jefe@ejemplo.test')
        self.assertEqual(aviso.email_cc, 'direccion@ejemplo.test')

    def test_primer_pedido_de_quien_no_habia_comprado_nunca(self):
        cliente = self._cliente('R0031')
        self.Lead._nv_poblar_embudo_bloques()
        lead = self._leads(cliente)
        self.assertFalse(lead.nv_ultimo_pedido_al_entrar)
        cliente.write({'fecha_primer_pedido': date(2026, 12, 1), 'fecha_ultimo_pedido': date(2026, 12, 1)})
        self.assertTrue(lead.stage_id.is_won)
        aviso = self.env['mail.mail'].sudo().search([('subject', 'like', 'Ha hecho un pedido')], order='id desc', limit=1)
        self.assertEqual(aviso.email_to, 'tienda@ejemplo.test')

    def test_respuesta_avisa_al_responsable_sin_usuario(self):
        cliente = self._cliente('R0032')
        self.Lead._nv_poblar_embudo_bloques()
        lead = self._leads(cliente)
        lead.nv_avisar_respuesta()
        aviso = self.env['mail.mail'].sudo().search([('model', '=', 'crm.lead'), ('res_id', '=', lead.id)],
                                                    order='id desc', limit=1)
        self.assertEqual(aviso.email_to, 'tienda@ejemplo.test')
        self.assertEqual(aviso.email_cc, 'direccion@ejemplo.test')
        self.assertFalse(lead.user_id)

    def test_respuesta_de_tienda_online_deja_la_oportunidad_al_usuario_del_parametro(self):
        suplente = self.env['res.users'].with_context(skip_sync=True, no_reset_password=True).create(
            {'name': 'Suplente Tienda', 'login': 'suplente@ejemplo.test', 'email': 'suplente@ejemplo.test'})
        self.env['ir.config_parameter'].sudo().set_param(PARAM_USUARIO_SIN_RESPONSABLE, 'suplente@ejemplo.test')
        cliente = self._cliente('R0036')
        self.Lead._nv_poblar_embudo_bloques()
        lead = self._leads(cliente)
        self.assertFalse(lead.user_id, 'la entrada sigue siendo silenciosa: sin vendedor')
        lead.nv_avisar_respuesta()
        self.assertEqual(lead.user_id, suplente)
        aviso = self.env['mail.mail'].sudo().search([('model', '=', 'crm.lead'), ('res_id', '=', lead.id)],
                                                    order='id desc', limit=1)
        self.assertEqual(aviso.email_to, 'tienda@ejemplo.test')
        self.assertEqual(aviso.email_cc, 'direccion@ejemplo.test')

    def test_el_cupo_por_defecto_es_cincuenta(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_POR_DIA, '')
        self.assertEqual(self.Lead._nv_reactivacion_por_dia(), 50)

    def test_respuesta_asigna_al_responsable_con_usuario(self):
        cliente = self._cliente('R0033', responsable='jefe@ejemplo.test', tipo='EquipoAlberto')
        self.Lead._nv_poblar_embudo_bloques()
        lead = self._leads(cliente)
        correos_antes = self.env['mail.mail'].sudo().search_count([])
        # Llega la respuesta del cliente: se asigna ya, para que la tarea del embudo tenga dueño
        lead.message_update({'email_from': lead.email_from, 'body': 'Me interesa', 'subject': 'Re: hola'})
        self.assertEqual(lead.user_id, self.alberto)
        # Sin el «te han asignado» de Odoo: el aviso es el nuestro
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), correos_antes)
        lead.nv_avisar_respuesta()
        aviso = self.env['mail.mail'].sudo().search([('model', '=', 'crm.lead'), ('res_id', '=', lead.id)],
                                                    order='id desc', limit=1)
        self.assertEqual(aviso.email_to, 'jefe@ejemplo.test')
        self.assertEqual(aviso.email_cc, 'direccion@ejemplo.test')

    def test_resumen_por_bloque(self):
        self._cliente('R0040')
        self._cliente('R0041', emails=())
        self.Lead._nv_poblar_embudo_bloques()
        fila = next(f for f in self.Lead.nv_resumen_bloques() if f['bloque'] == BLOQUE)
        self.assertEqual((fila['oportunidades'], fila['sin_correo'], fila['pendientes']), (1, 1, 0))

    # ----------------------------------------------------------- dominio

    def test_dominio_sin_espera_para_los_bloques(self):
        nuevo = _sin_espera_para_bloques(_con_clausulas(DOMINIO_GENERAL, EXCLUSION_BOLETIN))
        self.assertIn(SIN_ESPERA_BLOQUES + "('create_date', '<='", nuevo)
        self.assertIn('datetime.timedelta(days=15)', nuevo)
        self.assertEqual(_sin_espera_para_bloques(_con_clausulas(nuevo, EXCLUSION_BOLETIN)), nuevo)

        cliente = self._cliente('R0050')
        baja = self._cliente('R0051')
        self.Lead._nv_poblar_embudo_bloques()
        # La baja de boletín llega de Nesto después de entrar
        baja.child_ids.enviar_boletin = 'no'
        reciente = self.Lead.create({'name': 'Lead de hoy', 'type': 'opportunity', 'email_from': 'hoy@ejemplo.test'})
        leads = self._leads(cliente) | self._leads(baja) | reciente
        entran = self.Lead.search(safe_eval(nuevo, {'datetime': datetime_seguro}) + [('id', 'in', leads.ids)])
        self.assertEqual(entran, self._leads(cliente))

    def test_un_lead_con_rebote_no_recibe_los_correos_siguientes(self):
        paso = "[('active', '=', True), ('is_blacklisted', '=', False)]"
        nuevo = _con_clausulas(paso, EXCLUSION_REBOTES)
        self.assertEqual(_con_clausulas(nuevo, EXCLUSION_REBOTES), nuevo, 'Repetirlo no añade nada')
        bien = self.Lead.create({'name': 'Llega', 'type': 'opportunity', 'email_from': 'llega@ejemplo.test'})
        rebota = self.Lead.create({'name': 'Rebota', 'type': 'opportunity', 'email_from': 'rebota@ejemplo.test'})
        rebota.message_bounce = 1
        leads = bien | rebota
        self.assertEqual(self.Lead.search(safe_eval(nuevo) + [('id', 'in', leads.ids)]), bien)
        # Si esa dirección vuelve a escribir, Odoo pone el contador a cero y vuelve a entrar
        rebota.message_bounce = 0
        self.assertEqual(self.Lead.search(safe_eval(nuevo) + [('id', 'in', leads.ids)]), leads)

    def test_la_migracion_toca_solo_los_correos_con_dominio_propio(self):
        if 'automation.configuration' not in self.env:
            self.skipTest('automation_oca no está instalado')
        Config = self.env['automation.configuration'].sudo().with_context(active_test=False)
        config = Config.search([('name', '=', 'Embudo de conversión')], limit=1)
        if not config:
            self.skipTest('No hay embudo general en esta base')
        self.Lead._nv_excluir_rebotados_del_embudo()
        self.Lead._nv_excluir_rebotados_del_embudo()
        for paso in config.automation_step_ids:
            propio = not paso.apply_parent_domain and paso.step_type == 'mail'
            self.assertEqual((paso.domain or '').count("('message_bounce', '=', 0)"), 1 if propio else 0, paso.name)

