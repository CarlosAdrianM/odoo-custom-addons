"""
Tests del aviso de asignación de vendedor (issue #36)

Cada cambio de vendedor que llegaba de Nesto le mandaba al vendedor un correo
«Ha sido asignado/a a Contacto X». La asignación ya está hecha en Nesto, así
que el aviso no aporta nada: la carga masiva del 23/09 mandó 412 en 23 minutos.

Cada test comprueba también el caso contrario (sin el contexto de Nesto el
aviso SÍ sale). Si no, un test que no encontrase avisos pasaría igual aunque
Odoo dejase de mandarlos por otro motivo.

Van en post_install porque Odoo no manda este aviso mientras está cargando
módulos (registry.ready es False): en at_install no saldría NUNCA, con o sin
el arreglo, y el test pasaría en falso.
"""

from odoo.tests import TransactionCase, new_test_user, tagged

from ..config.entity_configs import get_entity_config
from ..core.generic_service import GenericEntityService


@tagged('post_install', '-at_install')
class TestAvisoAsignacion(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vendedor = new_test_user(
            self.env, login='vendedor_aviso_36', name='Vendedor Aviso',
            email='vendedor.aviso.36@example.com', groups='base.group_user',
        )
        # Quien escribe no puede ser el propio vendedor: Odoo no avisa a quien
        # se asigna a sí mismo (mail_thread._message_auto_subscribe_followers)
        self.otro = new_test_user(
            self.env, login='otro_aviso_36', name='Otro',
            groups='base.group_user,base.group_partner_manager',
        )
        service = GenericEntityService(
            self.env, get_entity_config('cliente'), test_mode=True
        )
        self.contexto_nesto = service._contexto_de_escritura()

    def _avisos(self, partner):
        return self.env['mail.message'].sudo().search([
            ('model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
            ('message_type', '=', 'user_notification'),
            ('partner_ids', 'in', self.vendedor.partner_id.ids),
        ])

    def _partner(self, env):
        return env['res.partner'].with_user(self.otro).create(
            {'name': 'Cliente aviso 36'}
        )

    def test_cambio_de_vendedor_desde_nesto_no_avisa(self):
        partner = self._partner(self.env(context=dict(self.env.context, **self.contexto_nesto)))

        partner.write({'user_id': self.vendedor.id})

        self.assertFalse(self._avisos(partner))
        # Pero sigue quedando como seguidor
        self.assertIn(self.vendedor.partner_id, partner.message_partner_ids)

    def test_alta_con_vendedor_desde_nesto_no_avisa(self):
        partner = self.env['res.partner'].with_user(self.otro).with_context(
            **self.contexto_nesto
        ).create({'name': 'Cliente aviso 36', 'user_id': self.vendedor.id})

        self.assertFalse(self._avisos(partner))

    def test_a_mano_en_odoo_si_avisa(self):
        partner = self._partner(self.env)

        partner.write({'user_id': self.vendedor.id})

        self.assertTrue(self._avisos(partner))
