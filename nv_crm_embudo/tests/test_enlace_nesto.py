from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestEnlaceClientesNesto(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env['crm.lead']
        cls.Partner = cls.env['res.partner'].with_context(skip_sync=True)
        cls.vendedora = cls.env['res.users'].with_context(skip_sync=True, no_reset_password=True).create({'name': 'Vendedora Test', 'login': 'vend_test_nv'})
        cls.etapa_nuevo = cls.env['crm.stage'].create({'name': 'Nuevo test', 'sequence': 1})
        cls.etapa_cliente = cls.env.ref('nv_crm_embudo.stage_cliente_nesto')

    def _lead(self, **vals):
        return self.Lead.create(dict({'name': 'Lead test', 'type': 'opportunity', 'user_id': self.vendedora.id,
                                      'stage_id': self.etapa_nuevo.id}, **vals))

    def _envejecer(self, cliente, minutos):
        self.env.cr.execute('UPDATE res_partner SET create_date = %s WHERE id = %s',
                            (fields.Datetime.now() - timedelta(minutes=minutos), cliente.id))
        cliente.invalidate_recordset(['create_date'])

    def _cliente_nesto(self, numero, email=None, telefono=None, antiguedad_min=5):
        cliente = self.Partner.create({'name': 'Cliente %s' % numero, 'cliente_externo': numero,
                                       'contacto_externo': '0', 'phone': telefono, 'is_company': True})
        if email:
            self._persona_contacto(cliente, email)
        self._envejecer(cliente, antiguedad_min)
        return cliente

    def _persona_contacto(self, cliente, email):
        """Una persona de contacto, que es como llega de verdad el email del cliente."""
        return self.Partner.create({'name': 'Contacto', 'parent_id': cliente.id, 'email': email,
                                    'cliente_externo': cliente.cliente_externo, 'contacto_externo': '0',
                                    'persona_contacto_externa': '1'})

    def _actividades_nesto(self, lead):
        return lead.activity_ids.filtered(lambda a: 'Nesto' in (a.summary or ''))

    def test_enlaza_por_email_y_avanza_etapa(self):
        lead = self._lead(email_from='Cliente <Uno@Ejemplo.test>', partner_name='Mi salón')
        cliente = self._cliente_nesto('T0001', email='uno@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(lead.partner_id, cliente)
        self.assertEqual(lead.stage_id, self.etapa_cliente)
        self.assertTrue(cliente.nv_lead_revisado)
        self.assertIn('Mi salón', lead.message_ids.filtered(lambda m: m.message_type == 'comment')[:1].body)

    def test_enlaza_por_telefono_ultimos_9_digitos(self):
        lead = self._lead(mobile='+34 612 34 56 78')
        cliente = self._cliente_nesto('T0002', telefono='612345678')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(lead.partner_id, cliente)

    def test_varios_candidatos_crea_tarea_y_no_enlaza(self):
        l1 = self._lead(phone='911111111')
        l2 = self._lead(phone='91 111 11 11')
        cliente = self._cliente_nesto('T0003', telefono='911111111')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        for lead in (l1, l2):
            self.assertFalse(lead.partner_id)
            self.assertEqual(len(self._actividades_nesto(lead)), 1)
        self.assertTrue(cliente.nv_lead_revisado, 'Queda en manos de la vendedora, no se vuelve a mirar')

    def test_sin_coincidencia_no_hace_nada(self):
        lead = self._lead(email_from='otro@ejemplo.test')
        self._cliente_nesto('T0004', email='nadie@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id)
        self.assertFalse(self._actividades_nesto(lead))

    def test_ignora_emails_propios_de_la_empresa(self):
        lead = self._lead(email_from='vendedora@nuevavision.es')
        self._cliente_nesto('T0005', email='vendedora@nuevavision.es')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id)

    def test_no_toca_leads_ganados_ni_ya_enlazados(self):
        ganado = self._lead(email_from='dos@ejemplo.test')
        ganado.action_set_won()
        # Mismos datos en lead y ficha: si el lead trajera un email o teléfono que la ficha no tiene,
        # crm los copiaría a la ficha y nesto_sync la publicaría (comportamiento estándar, no del enlace)
        otro_cliente = self._cliente_nesto('T0006', telefono='622222222', antiguedad_min=60)
        enlazado = self._lead(phone='622222222', partner_id=otro_cliente.id)
        self._cliente_nesto('T0007', email='dos@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(ganado.partner_id)
        self.assertEqual(enlazado.partner_id, otro_cliente)

    def test_solo_oportunidades(self):
        lead = self._lead(email_from='cinco@ejemplo.test', type='lead')
        self._cliente_nesto('T0010', email='cinco@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id, 'Los leads sin convertir no entran en el embudo')

    def test_respeta_margen_de_sincronizacion_y_no_repite(self):
        lead = self._lead(email_from='tres@ejemplo.test')
        cliente = self._cliente_nesto('T0008', email='tres@ejemplo.test', antiguedad_min=0)
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id, 'Un cliente recién creado espera a la siguiente pasada')
        self._envejecer(cliente, 5)
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(lead.partner_id, cliente)
        lead.write({'partner_id': False})
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id, 'Un cliente ya revisado no se vuelve a procesar')

    def test_reintenta_cuando_la_persona_de_contacto_llega_despues(self):
        """El caso real: el cliente principal se crea antes que sus personas de contacto."""
        lead = self._lead(email_from='seis@ejemplo.test')
        cliente = self._cliente_nesto('T0011', antiguedad_min=5)
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id)
        self.assertFalse(cliente.nv_lead_revisado, 'Sin datos de contacto todavía no se da por revisado')

        self._persona_contacto(cliente, 'seis@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(lead.partner_id, cliente, 'El email llega en el mensaje de la persona de contacto')

    def test_deja_de_buscar_pasado_el_plazo(self):
        cliente = self._cliente_nesto('T0012', antiguedad_min=60 * 25)
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertTrue(cliente.nv_lead_revisado)
        # Una persona de contacto que llegue ahora ya no reabre la búsqueda
        lead = self._lead(email_from='siete@ejemplo.test')
        self._persona_contacto(cliente, 'siete@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertFalse(lead.partner_id)

    def test_no_modifica_la_ficha_del_cliente(self):
        self._lead(email_from='cuatro@ejemplo.test', phone='699999999', street='Calle del lead')
        cliente = self._cliente_nesto('T0009', email='cuatro@ejemplo.test')
        antes = cliente.read(['name', 'street', 'phone', 'email'])[0]
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(cliente.read(['name', 'street', 'phone', 'email'])[0], antes)

    def test_anota_el_cliente_anterior_al_reenlazar(self):
        otro = self.Partner.create({'name': 'Cliente de otro sitio'})
        lead = self._lead(email_from='ocho@ejemplo.test', partner_id=otro.id)
        cliente = self._cliente_nesto('T0013', email='ocho@ejemplo.test')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(lead.partner_id, cliente)
        nota = lead.message_ids.filtered(lambda m: m.message_type == 'comment')[:1].body
        self.assertIn('Cliente de otro sitio', nota)

    def test_sin_vendedora_activa_no_crea_tarea(self):
        self.vendedora.active = False
        l1 = self._lead(phone='933333333')
        l2 = self._lead(phone='933333333')
        self._cliente_nesto('T0014', telefono='933333333')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        for lead in (l1, l2):
            self.assertFalse(self._actividades_nesto(lead), 'Una tarea de OdooBot no la ve nadie')
