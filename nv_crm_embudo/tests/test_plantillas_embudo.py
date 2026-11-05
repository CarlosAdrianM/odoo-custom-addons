"""Plantillas de correo del embudo de leads (correos 01-03 de Marketing).

Cada correo lleva un solo cierre: FINAL A si el lead todavía no compra, FINAL B si su cliente
ya tiene primer pedido en Nesto (mismo criterio que el avance a Ganado, #9).
"""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# (xml_id, título del FINAL A, título del FINAL B)
PLANTILLAS = [
    ('nv_crm_embudo.embudo_correo_01', 'Ordenar un caso', 'Revisar opciones'),
    ('nv_crm_embudo.embudo_correo_02', 'Elegir un activo', 'Revisar protocolos'),
    ('nv_crm_embudo.embudo_correo_03', 'Elegir aparatología', 'Aprovechar el equipo'),
]


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestPlantillasEmbudo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner'].with_context(skip_sync=True)
        cls.vendedora = cls.env['res.users'].with_context(skip_sync=True, no_reset_password=True).create({
            'name': 'Ana Vendedora', 'login': 'ana_embudo_nv', 'email': 'ana.vendedora@nuevavision.es'})

    def _lead_sin_cliente(self, **vals):
        return self.env['crm.lead'].create(dict({
            'name': 'Lead embudo', 'type': 'opportunity', 'contact_name': 'MARÍA José Pérez',
            'email_from': 'maria@ejemplo.test', 'user_id': self.vendedora.id}, **vals))

    def _lead_que_ya_compra(self):
        cliente = self.Partner.create({
            'name': 'Cliente C9001', 'cliente_externo': 'C9001', 'contacto_externo': '0',
            'is_company': True, 'fecha_primer_pedido': date(2026, 5, 4)})
        # Sin email ni teléfono propios: crm los copiaría a la ficha y nesto_sync la publicaría
        return self.env['crm.lead'].create({
            'name': 'Lead de C9001', 'type': 'opportunity', 'partner_id': cliente.id,
            'user_id': self.vendedora.id})

    def _cuerpo(self, xml_id, lead):
        plantilla = self.env.ref(xml_id)
        return str(plantilla._render_field('body_html', lead.ids)[lead.id])

    def _comprobar_comun(self, cuerpo, lead):
        self.assertIn('Ana Vendedora', cuerpo, 'Firma con el nombre de la vendedora')
        self.assertIn('/nv/baja/%s/' % lead.id, cuerpo, 'Enlace de baja firmado')
        self.assertIn('/nv_crm_embudo/static/src/img/logo-nueva-vision.png', cuerpo)
        self.assertIn(lead.get_base_url(), cuerpo, 'Imágenes con URL absoluta')
        for resto in ('[NOMBRE', 'assets/', 'FINAL A', 'FINAL B'):
            self.assertNotIn(resto, cuerpo)
        self.assertLess(len(cuerpo.encode('utf-8')), 100 * 1024)
        self.assertIn('PD:', cuerpo, 'Posdata de la app')
        self.assertIn('https://play.google.com/store/apps/details?id=com.nuevavision.nestotiendas', cuerpo)
        self.assertIn('He olvidado mi contraseña', cuerpo)
        self.assertLess(cuerpo.index('PD:'), cuerpo.index('/nv/baja/'), 'La posdata va antes del pie legal')

    # ------------------------------------------------------------- FINAL A

    def test_lead_sin_cliente_lleva_el_final_a(self):
        lead = self._lead_sin_cliente()
        self.assertFalse(lead.nv_ya_compra())
        for xml_id, final_a, final_b in PLANTILLAS:
            with self.subTest(plantilla=xml_id):
                cuerpo = self._cuerpo(xml_id, lead)
                self._comprobar_comun(cuerpo, lead)
                self.assertIn('Hola María,', cuerpo, 'Solo el nombre de pila, sin gritar')
                self.assertIn(final_a, cuerpo)
                self.assertNotIn(final_b, cuerpo)

    # ------------------------------------------------------------- FINAL B

    def test_cliente_con_primer_pedido_lleva_el_final_b(self):
        lead = self._lead_que_ya_compra()
        self.assertTrue(lead.nv_ya_compra())
        for xml_id, final_a, final_b in PLANTILLAS:
            with self.subTest(plantilla=xml_id):
                cuerpo = self._cuerpo(xml_id, lead)
                self._comprobar_comun(cuerpo, lead)
                self.assertIn(final_b, cuerpo)
                self.assertNotIn(final_a, cuerpo)

    def test_el_primer_pedido_en_una_persona_de_contacto_tambien_cuenta(self):
        cliente = self.Partner.create({
            'name': 'Cliente C9002', 'cliente_externo': 'C9002', 'contacto_externo': '0', 'is_company': True})
        self.Partner.create({
            'name': 'Contacto', 'parent_id': cliente.id, 'cliente_externo': 'C9002', 'contacto_externo': '0',
            'persona_contacto_externa': '1', 'fecha_primer_pedido': date(2026, 5, 4)})
        lead = self.env['crm.lead'].create({'name': 'Lead de C9002', 'type': 'opportunity', 'partner_id': cliente.id})
        self.assertTrue(lead.nv_ya_compra())

    def test_cliente_sin_pedido_sigue_en_el_final_a(self):
        cliente = self.Partner.create({
            'name': 'Cliente C9003', 'cliente_externo': 'C9003', 'contacto_externo': '0', 'is_company': True,
            'fecha_primer_presupuesto': date(2026, 5, 4)})
        lead = self.env['crm.lead'].create({'name': 'Lead de C9003', 'type': 'opportunity', 'partner_id': cliente.id})
        self.assertFalse(lead.nv_ya_compra(), 'Un presupuesto no es una compra')

    # ------------------------------------------------------------- saludo

    def test_nombre_del_saludo(self):
        self.assertEqual(self._lead_sin_cliente(contact_name='Lucía Gómez').nv_nombre_saludo(), 'Lucía')
        self.assertEqual(self._lead_sin_cliente(contact_name=False, partner_name='Peluquería Rosa').nv_nombre_saludo(),
                         'Peluquería Rosa', 'Sin persona, la empresa entera')
        lead = self._lead_sin_cliente(contact_name=False)
        self.assertEqual(lead.nv_nombre_saludo(), '')
        self.assertIn('Hola,', self._cuerpo(PLANTILLAS[0][0], lead), 'Sin nombre no queda «Hola ,»')

    # -------------------------------------------------- remitente y respuesta

    def test_remitente_y_responder_a(self):
        lead = self._lead_sin_cliente()
        plantilla = self.env.ref(PLANTILLAS[0][0])
        remitente = plantilla._render_field('email_from', lead.ids)[lead.id]
        self.assertIn('Nueva Visión | Ana Vendedora', remitente)
        self.assertIn('<marketing@nuevavision.es>', remitente)
        self.env['ir.config_parameter'].sudo().set_param('nv_crm_embudo.email_from_embudo', 'otra@nuevavision.es')
        self.assertIn('<otra@nuevavision.es>', lead.nv_email_from_embudo())
        self.assertFalse(plantilla.reply_to, 'Sin reply_to: responde al alias del equipo y entra en el lead')
        self.assertEqual(plantilla._render_field('email_to', lead.ids)[lead.id], 'maria@ejemplo.test')
        self.assertEqual(plantilla._render_field('subject', lead.ids)[lead.id],
                         'Antes de tratar el acné, hay algo que conviene mirar')

    def test_enlace_de_la_app_configurable(self):
        lead = self._lead_sin_cliente()
        self.env['ir.config_parameter'].sudo().set_param('nv_crm_embudo.url_app', 'https://app.ejemplo.test/descarga')
        self.assertIn('href="https://app.ejemplo.test/descarga"', self._cuerpo(PLANTILLAS[1][0], lead))


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestAvisoRespuesta(TransactionCase):
    """Aviso a la vendedora, con copia a Dirección y al jefe de equipo, cuando el lead contesta."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(skip_sync=True, no_reset_password=True)
        cls.vendedora = Users.create({'name': 'Ana Vendedora', 'login': 'ana_aviso_nv', 'email': 'ana@nuevavision.es'})
        cls.otra = Users.create({'name': 'Eva Vendedora', 'login': 'eva_aviso_nv', 'email': 'eva@nuevavision.es'})
        cls.equipo_jefe = cls.env['crm.team'].create({'name': 'Equipo Jefe Test', 'member_ids': [(6, 0, cls.vendedora.ids)]})
        parametros = cls.env['ir.config_parameter'].sudo()
        parametros.set_param('nv_crm_embudo.cc_direccion', 'direccion@nuevavision.es')
        parametros.set_param('nv_crm_embudo.cc_jefe_equipo', 'jefe@nuevavision.es')
        parametros.set_param('nv_crm_embudo.equipo_jefe_equipo', str(cls.equipo_jefe.id))

    def _lead(self, vendedora):
        return self.env['crm.lead'].create({
            'name': 'Lead aviso', 'type': 'opportunity', 'contact_name': 'Lucía',
            'email_from': 'lucia@ejemplo.test', 'user_id': vendedora.id, 'team_id': False})

    def test_vendedora_del_equipo_del_jefe_lleva_copia_al_jefe(self):
        lead = self._lead(self.vendedora)
        self.assertEqual(lead.nv_cc_aviso_respuesta(), 'direccion@nuevavision.es, jefe@nuevavision.es')

    def test_otra_vendedora_solo_copia_a_direccion(self):
        lead = self._lead(self.otra)
        self.assertEqual(lead.nv_cc_aviso_respuesta(), 'direccion@nuevavision.es')

    def test_equipo_por_nombre_y_por_equipo_del_lead(self):
        self.env['ir.config_parameter'].sudo().set_param('nv_crm_embudo.equipo_jefe_equipo', 'equipo jefe test')
        lead = self._lead(self.otra)
        lead.team_id = self.equipo_jefe
        self.assertIn('jefe@nuevavision.es', lead.nv_cc_aviso_respuesta())

    def test_no_se_copia_a_si_misma(self):
        self.env['ir.config_parameter'].sudo().set_param('nv_crm_embudo.cc_direccion', 'ANA@nuevavision.es, direccion@nuevavision.es')
        self.assertEqual(self._lead(self.otra.browse()).nv_cc_aviso_respuesta(), 'ANA@nuevavision.es, direccion@nuevavision.es')
        self.assertEqual(self._lead(self.vendedora).nv_cc_aviso_respuesta(), 'direccion@nuevavision.es, jefe@nuevavision.es')

    def test_avisar_respuesta_manda_el_correo(self):
        lead = self._lead(self.vendedora)
        lead.message_post(body='Me interesa, llámame', message_type='email', author_id=False,
                          email_from='lucia@ejemplo.test')
        antes = self.env['mail.mail'].sudo().search([])
        lead.nv_avisar_respuesta()
        correo = self.env['mail.mail'].sudo().search([]) - antes
        self.assertEqual(len(correo), 1)
        self.assertEqual(correo.email_to, 'ana@nuevavision.es')
        self.assertEqual(correo.email_cc, 'direccion@nuevavision.es, jefe@nuevavision.es')
        self.assertIn('Me interesa', correo.body_html)
        self.assertIn('Lucía', correo.subject)

    def test_sin_email_de_vendedora_no_manda_nada(self):
        lead = self._lead(self.otra.browse())
        antes = self.env['mail.mail'].sudo().search_count([])
        lead.nv_avisar_respuesta()
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), antes)


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestEnvioMasivoSinContactos(TransactionCase):
    """El envío masivo (el que hace automation_oca) no debe crear un contacto por cada lead.

    Odoo, en modo masivo, convierte el «Para» en res.partner con find_or_create. En el ensayo del
    05/11/26 en la copia salieron 67 contactos basura (uno por email de lead) y nesto_sync intentó
    publicarlos. Las plantillas del embudo llevan nv_sin_contactos para evitarlo.
    """

    def _enviar_en_masa(self, plantilla, lead):
        composer = self.env['mail.compose.message'].with_context(active_ids=lead.ids).create({
            'composition_mode': 'mass_mail', 'model': 'crm.lead', 'template_id': plantilla.id,
        })
        composer.write(composer._onchange_template_id(plantilla.id, 'mass_mail', 'crm.lead', lead.id)['value'])
        composer.with_context(active_ids=lead.ids)._action_send_mail()
        return self.env['mail.mail'].search([('model', '=', 'crm.lead'), ('res_id', '=', lead.id)], order='id desc', limit=1)

    def test_las_plantillas_del_embudo_llevan_la_marca(self):
        for xml_id, _a, _b in PLANTILLAS:
            self.assertTrue(self.env.ref(xml_id).nv_sin_contactos, xml_id)

    def test_el_envio_masivo_no_crea_contactos(self):
        email = 'lead.sin.contacto@ejemplo.test'
        Partner = self.env['res.partner']
        self.assertFalse(Partner.search([('email', '=', email)]))
        lead = self.env['crm.lead'].create({'name': 'Lead masivo', 'type': 'opportunity', 'email_from': email})
        correo = self._enviar_en_masa(self.env.ref('nv_crm_embudo.embudo_correo_01'), lead)
        self.assertFalse(Partner.search([('email', '=', email)]), 'El envío masivo no debe crear el contacto')
        self.assertIn(email, correo.email_to or '', 'El correo sale a la dirección del lead')
        self.assertFalse(correo.recipient_ids)
        self.assertNotEqual(correo.state, 'cancel')

    def test_sin_la_marca_odoo_si_crea_el_contacto(self):
        """Documenta el comportamiento estándar, para que se note si Odoo lo cambia."""
        email = 'lead.con.contacto@ejemplo.test'
        plantilla = self.env.ref('nv_crm_embudo.embudo_correo_01').copy({'nv_sin_contactos': False})
        lead = self.env['crm.lead'].create({'name': 'Lead masivo', 'type': 'opportunity', 'email_from': email})
        correo = self._enviar_en_masa(plantilla, lead)
        self.assertTrue(self.env['res.partner'].search([('email', '=', email)]))
        self.assertEqual(correo.recipient_ids.mapped('email'), [email])
