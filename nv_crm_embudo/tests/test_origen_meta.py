"""Clientes de Nesto que entran por los leads de Meta (issue #43)."""
from datetime import date, datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

from odoo.addons.nv_crm_embudo.models.origen_cliente import (
    CAMPANA_HARMONIA, DOMINIO_SECUENCIA_HARMONIA, EXCLUSION_EMBUDO_GENERAL,
    NOMBRE_SECUENCIA_HARMONIA, _con_exclusion)

DOMINIO_GENERAL = ("[('type', '=', 'opportunity'), ('active', '=', True), ('stage_id.is_won', '=', False), "
                   "('email_from', '!=', False), ('create_date', '<=', (datetime.datetime.now() - "
                   "datetime.timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S'))]")


class TestConExclusion(TransactionCase):

    def test_anade_al_final_sin_evaluar(self):
        nuevo = _con_exclusion(DOMINIO_GENERAL)
        # El «hace 15 días» sigue siendo una expresión, no una fecha fija
        self.assertIn('datetime.timedelta(days=15)', nuevo)
        self.assertTrue(nuevo.endswith("('campaign_id.name', '!=', '%s')]" % CAMPANA_HARMONIA))

    def test_idempotente(self):
        una = _con_exclusion(DOMINIO_GENERAL)
        self.assertEqual(_con_exclusion(una), una)

    def test_dominio_vacio(self):
        self.assertEqual(safe_eval(_con_exclusion('[]')), EXCLUSION_EMBUDO_GENERAL)
        self.assertEqual(safe_eval(_con_exclusion(False)), EXCLUSION_EMBUDO_GENERAL)

    def test_formato_raro_no_se_toca(self):
        with self.assertRaises(ValueError):
            _con_exclusion("expression.AND([])")


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestOrigenMeta(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env['crm.lead']
        cls.Partner = cls.env['res.partner'].with_context(skip_sync=True)
        cls.comercial = cls.env['res.users'].with_context(skip_sync=True, no_reset_password=True).create(
            {'name': 'Comercial Meta', 'login': 'comercial_meta_nv', 'email': 'comercial@ejemplo.test'})
        cls.etapa = cls.env['crm.stage'].create({'name': 'Nuevo meta', 'sequence': 1})

    def _cliente(self, numero, origen=CAMPANA_HARMONIA, acepta=None, email=None, **vals):
        cliente = self.Partner.create(dict({
            'name': 'CLIENTE %s' % numero, 'cliente_externo': numero, 'contacto_externo': '0',
            'is_company': True, 'origen_cliente': origen, 'acepta_comunicaciones': acepta,
            'fecha_origen': datetime(2026, 11, 5, 20, 48), 'user_id': self.comercial.id,
            'comment': 'Lead de Meta (Instagram) 05/11 21:48: tengo un centro de estética',
        }, **vals))
        if email:
            self.Partner.create({'name': 'Persona', 'parent_id': cliente.id, 'email': email,
                                 'cliente_externo': numero, 'contacto_externo': '0',
                                 'persona_contacto_externa': '1'})
            cliente.email = email
        return cliente

    def _oportunidades(self, cliente):
        return self.Lead.with_context(active_test=False).search(
            [('partner_id.commercial_partner_id', '=', cliente.id)])

    # ------------------------------------------------------- oportunidad

    def test_crea_la_oportunidad_con_la_campana_y_el_comercial(self):
        cliente = self._cliente('M0001', acepta='si', email='meta1@ejemplo.test')
        self.Lead._nv_crear_oportunidades_origen()
        lead = self._oportunidades(cliente)
        self.assertEqual(len(lead), 1)
        self.assertEqual(lead.type, 'opportunity')
        self.assertEqual(lead.campaign_id.name, CAMPANA_HARMONIA)
        self.assertEqual(lead.user_id, self.comercial)
        self.assertEqual(lead.email_from, 'meta1@ejemplo.test')
        self.assertIn('centro de estética', lead.description)
        self.assertIn('Acepta', lead.message_ids.filtered(lambda m: m.message_type == 'comment')[:1].body)
        self.assertIn('05/11/2026 21:48', lead.message_ids.filtered(lambda m: m.message_type == 'comment')[:1].body)
        self.assertTrue(cliente.nv_oportunidad_origen)

    def test_no_duplica_si_se_repite(self):
        cliente = self._cliente('M0002')
        self.Lead._nv_crear_oportunidades_origen()
        cliente.with_context(skip_sync=True).nv_oportunidad_origen = False  # p. ej. Nesto lo republica
        self.Lead._nv_crear_oportunidades_origen()
        self.assertEqual(len(self._oportunidades(cliente)), 1)

    def test_sin_comercial_queda_sin_asignar(self):
        cliente = self._cliente('M0003', user_id=False)
        self.Lead._nv_crear_oportunidades_origen()
        self.assertFalse(self._oportunidades(cliente).user_id)

    def test_cliente_sin_origen_o_de_otro_origen_no_crea_nada(self):
        normal = self._cliente('M0004', origen=False)
        otro = self._cliente('M0005', origen='FERIA-2026')
        self.Lead._nv_crear_oportunidades_origen()
        self.assertFalse(self._oportunidades(normal))
        self.assertFalse(self._oportunidades(otro))

    def test_si_ya_ha_comprado_se_gana(self):
        cliente = self._cliente('M0006', fecha_primer_pedido=date(2026, 11, 7))
        self.Lead._nv_crear_oportunidades_origen()
        self.assertTrue(self._oportunidades(cliente).stage_id.is_won)

    def test_el_cron_del_enlace_las_crea(self):
        cliente = self._cliente('M0007')
        self.Lead._nv_cron_enlazar_clientes_nesto()
        self.assertEqual(len(self._oportunidades(cliente)), 1)

    # ------------------------------------------- dominios de los embudos

    def _entran(self, dominio, leads):
        return self.Lead.search(safe_eval(dominio, {'datetime': datetime}) + [('id', 'in', leads.ids)])

    def test_exclusion_del_embudo_general(self):
        def lead(**vals):
            return self.Lead.create(dict({'name': 'L', 'type': 'opportunity', 'stage_id': self.etapa.id,
                                          'email_from': 'x@ejemplo.test'}, **vals))
        no_acepta = self._cliente('M0010', origen=False, acepta='no')
        acepta = self._cliente('M0011', origen=False, acepta='si')
        sin_dato = self._cliente('M0012', origen=False)
        meta = self._cliente('M0013', acepta='si')
        persona_no = self.Partner.create({'name': 'P', 'parent_id': no_acepta.id})
        campana = self.Lead._nv_campana(CAMPANA_HARMONIA)

        dentro = lead() | lead(partner_id=acepta.id) | lead(partner_id=sin_dato.id)
        fuera = (lead(partner_id=no_acepta.id) | lead(partner_id=persona_no.id)
                 | lead(partner_id=meta.id) | lead(campaign_id=campana.id))
        # Sin el «hace 15 días», que aquí no viene a cuento
        dominio = _con_exclusion("[('type', '=', 'opportunity')]")
        self.assertEqual(self._entran(dominio, dentro | fuera), dentro)

    def test_dominio_de_la_secuencia_harmonia(self):
        si = self._cliente('M0020', acepta='si', email='si@ejemplo.test')
        no = self._cliente('M0021', acepta='no', email='no@ejemplo.test')
        sin_dato = self._cliente('M0022', email='nada@ejemplo.test')
        self.Lead._nv_crear_oportunidades_origen()
        todas = self._oportunidades(si) | self._oportunidades(no) | self._oportunidades(sin_dato)
        self.assertEqual(self._entran(DOMINIO_SECUENCIA_HARMONIA, todas), self._oportunidades(si))

    # ------------------------------------------------- automation_oca

    def test_preparar_embudos(self):
        if 'automation.configuration' not in self.env:
            self.skipTest('automation_oca no está instalado')
        Config = self.env['automation.configuration'].with_context(active_test=False)
        modelo = self.env['ir.model']._get('crm.lead')
        general = Config.search([('name', '=', 'Embudo de conversión')], limit=1) or Config.create({
            'name': 'Embudo de conversión', 'model_id': modelo.id, 'editable_domain': DOMINIO_GENERAL})
        self.Lead._nv_preparar_embudos_origen()
        self.Lead._nv_preparar_embudos_origen()  # repetir no duplica nada
        self.assertIn("acepta_comunicaciones', '!=', 'no'", general.editable_domain)
        self.assertEqual(general.editable_domain.count('acepta_comunicaciones'), 1)
        for paso in general.automation_step_ids.filtered(lambda s: not s.apply_parent_domain and s.step_type == 'mail'):
            self.assertIn("acepta_comunicaciones', '!=', 'no'", paso.domain)
        secuencia = Config.search([('name', '=', NOMBRE_SECUENCIA_HARMONIA)])
        self.assertEqual(len(secuencia), 1)
        self.assertEqual(secuencia.state, 'draft')
        self.assertEqual(secuencia.editable_domain, DOMINIO_SECUENCIA_HARMONIA)
