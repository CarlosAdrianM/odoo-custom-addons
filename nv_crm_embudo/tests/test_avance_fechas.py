"""El embudo avanza solo con las fechas de compras de Nesto (#9, paso 2; necesita #8).

Nuevo → … → Cliente en Nesto → Presupuesto (FechaPrimerPresupuesto) → Ganado (FechaPrimerPedido)
"""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestAvancePorFechas(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner'].with_context(skip_sync=True)
        cls.etapa_nuevo = cls.env['crm.stage'].create({'name': 'Nuevo test', 'sequence': 1})
        cls.etapa_cliente = cls.env.ref('nv_crm_embudo.stage_cliente_nesto')
        cls.etapa_presupuesto = cls.env.ref('nv_crm_embudo.stage_presupuesto')

    def _cliente(self, numero='C0001', **vals):
        return self.Partner.create(dict({
            'name': 'Cliente %s' % numero, 'cliente_externo': numero, 'contacto_externo': '0',
            'is_company': True}, **vals))

    def _lead(self, cliente, etapa=None):
        # Sin email ni teléfono propios: si el lead trajera datos que la ficha no tiene,
        # crm los copiaría a la ficha y nesto_sync la publicaría hacia Nesto
        return self.env['crm.lead'].create({
            'name': 'Lead de %s' % cliente.name, 'type': 'opportunity',
            'partner_id': cliente.id, 'stage_id': (etapa or self.etapa_cliente).id,
        })

    def _etapa_ganado(self):
        return self.env['crm.stage'].search([('is_won', '=', True)], limit=1)

    # ------------------------------------------------------------ presupuesto

    def test_primer_presupuesto_pasa_el_lead_a_presupuesto(self):
        cliente = self._cliente('C0001')
        lead = self._lead(cliente)
        cliente.write({'fecha_primer_presupuesto': date(2026, 3, 1)})
        self.assertEqual(lead.stage_id, self.etapa_presupuesto)
        self.assertIn('2026-03-01', lead.message_ids[:1].body)

    def test_la_fecha_llega_en_una_persona_de_contacto(self):
        """Nesto manda un mensaje por contacto: la fecha es del cliente y llega en todos."""
        cliente = self._cliente('C0002')
        contacto = self.Partner.create({
            'name': 'Contacto', 'parent_id': cliente.id, 'cliente_externo': 'C0002',
            'contacto_externo': '0', 'persona_contacto_externa': '1'})
        lead = self._lead(cliente)
        contacto.write({'fecha_primer_presupuesto': date(2026, 3, 1)})
        self.assertEqual(lead.stage_id, self.etapa_presupuesto)

    def test_no_retrocede_desde_una_etapa_mas_avanzada(self):
        cliente = self._cliente('C0003')
        etapa_posterior = self.env['crm.stage'].create({'name': 'Negociación test', 'sequence': 60})
        lead = self._lead(cliente, etapa=etapa_posterior)
        cliente.write({'fecha_primer_presupuesto': date(2026, 3, 1)})
        self.assertEqual(lead.stage_id, etapa_posterior)

    def test_un_presupuesto_aceptado_no_devuelve_el_lead(self):
        """Al aceptar el único presupuesto, Nesto manda FechaPrimerPresupuesto a null."""
        cliente = self._cliente('C0004')
        lead = self._lead(cliente)
        cliente.write({'fecha_primer_presupuesto': date(2026, 3, 1)})
        self.assertEqual(lead.stage_id, self.etapa_presupuesto)
        cliente.write({'fecha_primer_presupuesto': False, 'fecha_primer_pedido': date(2026, 3, 5)})
        self.assertTrue(lead.stage_id.is_won)

    # ----------------------------------------------------------------- ganado

    def test_primer_pedido_gana_el_lead(self):
        cliente = self._cliente('C0005')
        lead = self._lead(cliente)
        cliente.write({'fecha_primer_pedido': date(2026, 4, 10)})
        self.assertTrue(lead.stage_id.is_won)
        self.assertEqual(lead.probability, 100)
        self.assertIn('2026-04-10', lead.message_ids.filtered(
            lambda m: 'primer pedido' in (m.body or ''))[:1].body)

    def test_el_pedido_manda_sobre_el_presupuesto(self):
        cliente = self._cliente('C0006')
        lead = self._lead(cliente)
        cliente.write({'fecha_primer_presupuesto': date(2026, 3, 1),
                       'fecha_primer_pedido': date(2026, 4, 10)})
        self.assertTrue(lead.stage_id.is_won)

    def test_un_lead_ya_ganado_no_se_vuelve_a_tocar(self):
        cliente = self._cliente('C0007')
        lead = self._lead(cliente)
        lead.action_set_won()
        mensajes = len(lead.message_ids)
        cliente.write({'fecha_primer_pedido': date(2026, 4, 10)})
        self.assertEqual(len(lead.message_ids), mensajes, 'No se le añade ninguna nota')

    def test_un_lead_perdido_no_revive(self):
        cliente = self._cliente('C0008')
        lead = self._lead(cliente)
        lead.action_set_lost()
        cliente.write({'fecha_primer_pedido': date(2026, 4, 10)})
        self.assertFalse(lead.active)
        self.assertFalse(lead.stage_id.is_won)

    # ------------------------------------------------------------ sin efectos

    def test_sin_leads_no_pasa_nada(self):
        cliente = self._cliente('C0009')
        cliente.write({'fecha_primer_pedido': date(2026, 4, 10)})
        self.assertEqual(cliente.fecha_primer_pedido, date(2026, 4, 10))

    def test_fecha_ultimo_pedido_no_mueve_el_embudo(self):
        cliente = self._cliente('C0010')
        lead = self._lead(cliente)
        cliente.write({'fecha_ultimo_pedido': date(2026, 9, 1)})
        self.assertEqual(lead.stage_id, self.etapa_cliente)

    def test_escribir_la_misma_fecha_no_reabre_nada(self):
        cliente = self._cliente('C0011')
        lead = self._lead(cliente)
        cliente.write({'fecha_primer_presupuesto': date(2026, 3, 1)})
        mensajes = len(lead.message_ids)
        cliente.write({'fecha_primer_presupuesto': date(2026, 3, 1)})
        self.assertEqual(len(lead.message_ids), mensajes)

    def test_un_lead_de_otro_cliente_no_se_toca(self):
        cliente = self._cliente('C0012')
        otro = self._cliente('C0013')
        lead_otro = self._lead(otro)
        self._lead(cliente)
        cliente.write({'fecha_primer_pedido': date(2026, 4, 10)})
        self.assertEqual(lead_otro.stage_id, self.etapa_cliente)
