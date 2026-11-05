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
        self.assertEqual(plantilla._render_field('reply_to', lead.ids)[lead.id], 'ana.vendedora@nuevavision.es')
        self.assertEqual(plantilla._render_field('email_to', lead.ids)[lead.id], 'maria@ejemplo.test')
        self.assertEqual(plantilla._render_field('subject', lead.ids)[lead.id],
                         'Antes de tratar el acné, hay algo que conviene mirar')
