"""
Tests para GenericEntityService

Especialmente importante: tests de detección de cambios (anti-bucle)
"""

from odoo.tests.common import TransactionCase
from unittest.mock import Mock, MagicMock, patch
from ..core.generic_service import GenericEntityService


class TestGenericEntityServiceChangeDetection(TransactionCase):
    """Tests para detección de cambios (función crítica anti-bucle)"""

    def setUp(self):
        super().setUp()

        # Configuración mínima de entidad
        self.entity_config = {
            'odoo_model': 'res.partner',
            'message_type': 'cliente',
            'id_fields': ['cliente_externo']
        }

        self.service = GenericEntityService(self.env, self.entity_config, test_mode=True)

    def test_has_changes_char_field_different(self):
        """Test: Campo char diferente = hay cambios"""
        # Crear partner real
        partner = self.env['res.partner'].create({
            'name': 'Cliente Original',
            'cliente_externo': '12345'
        })

        new_values = {'name': 'Cliente Modificado'}

        has_changes = self.service._has_changes(partner, new_values)

        self.assertTrue(has_changes)

    def test_has_changes_char_field_same(self):
        """Test: Campo char igual = sin cambios"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345'
        })

        new_values = {'name': 'Cliente Test'}

        has_changes = self.service._has_changes(partner, new_values)

        self.assertFalse(has_changes)

    def test_has_changes_char_field_whitespace_normalized(self):
        """Test: Espacios normalizados, sin cambios reales"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test  ',  # Espacios al final
            'cliente_externo': '12345'
        })

        new_values = {'name': '  Cliente Test'}  # Espacios al inicio

        has_changes = self.service._has_changes(partner, new_values)

        # Después de normalizar espacios, son iguales
        self.assertFalse(has_changes)

    def test_has_changes_boolean_field(self):
        """Test: Campo boolean diferente"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345',
            'active': True
        })

        new_values = {'active': False}

        has_changes = self.service._has_changes(partner, new_values)

        self.assertTrue(has_changes)

    def test_has_changes_boolean_field_same(self):
        """Test: Campo boolean igual"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345',
            'active': True
        })

        new_values = {'active': True}

        has_changes = self.service._has_changes(partner, new_values)

        self.assertFalse(has_changes)

    def test_has_changes_many2one_field(self):
        """Test: Campo many2one diferente"""
        # Crear países
        country1 = self.env['res.country'].search([('code', '=', 'ES')], limit=1)
        country2 = self.env['res.country'].search([('code', '=', 'FR')], limit=1)

        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345',
            'country_id': country1.id
        })

        new_values = {'country_id': country2.id}

        has_changes = self.service._has_changes(partner, new_values)

        self.assertTrue(has_changes)

    def test_has_changes_many2one_field_same(self):
        """Test: Campo many2one igual"""
        country = self.env['res.country'].search([('code', '=', 'ES')], limit=1)

        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345',
            'country_id': country.id
        })

        new_values = {'country_id': country.id}

        has_changes = self.service._has_changes(partner, new_values)

        self.assertFalse(has_changes)

    def test_has_changes_nonexistent_field(self):
        """Test: Campo que no existe en el modelo se ignora"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345'
        })

        new_values = {'campo_inexistente': 'valor'}

        # No debe lanzar error, solo ignorar el campo
        has_changes = self.service._has_changes(partner, new_values)

        # Como solo hay un campo inexistente, no hay cambios reales
        self.assertFalse(has_changes)

    def test_has_changes_multiple_fields_one_different(self):
        """Test: Múltiples campos, uno diferente = hay cambios"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345',
            'vat': 'B12345678',
            'active': True
        })

        new_values = {
            'name': 'Cliente Test',  # Igual
            'vat': 'B12345678',      # Igual
            'active': False           # DIFERENTE
        }

        has_changes = self.service._has_changes(partner, new_values)

        self.assertTrue(has_changes)

    def test_has_changes_none_vs_empty_string(self):
        """Test: None vs string vacío se normalizan"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345',
            'comment': None
        })

        new_values = {'comment': ''}

        has_changes = self.service._has_changes(partner, new_values)

        # None y '' se normalizan ambos a '', sin cambios
        self.assertFalse(has_changes)


class TestGenericEntityServiceCRUD(TransactionCase):
    """Tests para operaciones CRUD del GenericEntityService"""

    def setUp(self):
        super().setUp()

        self.entity_config = {
            'odoo_model': 'res.partner',
            'message_type': 'cliente',
            'id_fields': ['cliente_externo']
        }

        self.service = GenericEntityService(self.env, self.entity_config, test_mode=True)

    def test_create_record_success(self):
        """Test: Crear registro nuevo"""
        values = {
            'name': 'Cliente Nuevo',
            'cliente_externo': '99999'
        }

        response = self.service._create_record(values)

        self.assertEqual(response.status_code, 200)

        # Verificar que se creó
        partner = self.env['res.partner'].search([('cliente_externo', '=', '99999')])
        self.assertTrue(partner)
        self.assertEqual(partner.name, 'Cliente Nuevo')

    def test_update_record_success(self):
        """Test: Actualizar registro existente"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Original',
            'cliente_externo': '12345'
        })

        new_values = {'name': 'Cliente Actualizado'}

        response = self.service._update_record(partner, new_values)

        self.assertEqual(response.status_code, 200)

        # Verificar que se actualizó
        partner.refresh()
        self.assertEqual(partner.name, 'Cliente Actualizado')

    def test_find_record_by_id_fields(self):
        """Test: Encontrar registro por id_fields"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345'
        })

        values = {'cliente_externo': '12345'}

        found = self.service._find_record(values)

        self.assertTrue(found)
        self.assertEqual(found.id, partner.id)

    def test_find_record_not_exists(self):
        """Test: Buscar registro que no existe"""
        values = {'cliente_externo': '99999'}

        found = self.service._find_record(values)

        self.assertFalse(found)

    def test_find_record_includes_inactive(self):
        """Test: Búsqueda incluye registros inactivos"""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Inactivo',
            'cliente_externo': '12345',
            'active': False
        })

        values = {'cliente_externo': '12345'}

        found = self.service._find_record(values)

        self.assertTrue(found)
        self.assertEqual(found.id, partner.id)

    def test_create_or_update_single_creates_when_not_exists(self):
        """Test: create_or_update crea cuando no existe"""
        values = {
            'name': 'Cliente Nuevo',
            'cliente_externo': '99999'
        }

        response = self.service._create_or_update_single(values)

        self.assertEqual(response.status_code, 200)

        # Verificar que se creó
        partner = self.env['res.partner'].search([('cliente_externo', '=', '99999')])
        self.assertTrue(partner)

    def test_create_or_update_single_updates_when_exists_and_different(self):
        """Test: create_or_update actualiza cuando existe y hay cambios"""
        self.env['res.partner'].create({
            'name': 'Cliente Original',
            'cliente_externo': '12345'
        })

        values = {
            'name': 'Cliente Modificado',
            'cliente_externo': '12345'
        }

        response = self.service._create_or_update_single(values)

        self.assertEqual(response.status_code, 200)

        # Verificar que se actualizó
        partner = self.env['res.partner'].search([('cliente_externo', '=', '12345')])
        self.assertEqual(partner.name, 'Cliente Modificado')

    def test_create_or_update_single_skips_when_no_changes(self):
        """Test: create_or_update NO actualiza cuando no hay cambios (ANTI-BUCLE)"""
        self.env['res.partner'].create({
            'name': 'Cliente Test',
            'cliente_externo': '12345'
        })

        values = {
            'name': 'Cliente Test',  # Mismo valor
            'cliente_externo': '12345'
        }

        response = self.service._create_or_update_single(values)

        # Debe retornar 200 pero con mensaje "Sin cambios"
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sin cambios', response.response[0].decode())


class TestGenericEntityServiceBuildDomain(TransactionCase):
    """Tests para construcción de dominios de búsqueda"""

    def setUp(self):
        super().setUp()

        # Config con múltiples id_fields
        self.entity_config = {
            'odoo_model': 'res.partner',
            'message_type': 'cliente',
            'id_fields': ['cliente_externo', 'contacto_externo', 'persona_contacto_externa']
        }

        self.service = GenericEntityService(self.env, self.entity_config, test_mode=True)

    def test_build_search_domain_single_id_field(self):
        """Test: Dominio con un solo id_field"""
        values = {'cliente_externo': '12345'}

        domain = self.service._build_search_domain(values)

        # Debe incluir el id_field y los criterios de active
        self.assertIn(('cliente_externo', '=', '12345'), domain)
        self.assertIn('|', domain)
        self.assertIn(('active', '=', True), domain)
        self.assertIn(('active', '=', False), domain)

    def test_build_search_domain_multiple_id_fields(self):
        """Test: Dominio con múltiples id_fields"""
        values = {
            'cliente_externo': '12345',
            'contacto_externo': '1',
            'persona_contacto_externa': 'P1'
        }

        domain = self.service._build_search_domain(values)

        # Debe incluir todos los id_fields
        self.assertIn(('cliente_externo', '=', '12345'), domain)
        self.assertIn(('contacto_externo', '=', '1'), domain)
        self.assertIn(('persona_contacto_externa', '=', 'P1'), domain)
