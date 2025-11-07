"""
Tests para Post Processors

Valida que los post-processors funcionan correctamente
"""

from odoo.tests.common import TransactionCase
from ..transformers.post_processors import (
    AssignEmailFromChildren,
    MergeComments,
    SetParentIdForChildren,
    NormalizePhoneNumbers,
    PostProcessorRegistry
)


class TestAssignEmailFromChildren(TransactionCase):
    """Tests para AssignEmailFromChildren"""

    def setUp(self):
        super().setUp()
        self.processor = AssignEmailFromChildren()
        self.context = {}

    def test_assign_email_from_first_child(self):
        """Test: Asignar email del primer child que tenga"""
        parent_values = {'name': 'Cliente Test'}
        children_values = [
            {'name': 'Hijo 1'},  # Sin email
            {'name': 'Hijo 2', 'email': 'hijo2@test.com'},
            {'name': 'Hijo 3', 'email': 'hijo3@test.com'},
        ]

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(parent['email'], 'hijo2@test.com')

    def test_parent_already_has_email(self):
        """Test: Parent ya tiene email, no sobreescribir"""
        parent_values = {'name': 'Cliente Test', 'email': 'parent@test.com'}
        children_values = [
            {'name': 'Hijo 1', 'email': 'hijo1@test.com'},
        ]

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(parent['email'], 'parent@test.com')

    def test_no_children_with_email(self):
        """Test: Ningún child tiene email"""
        parent_values = {'name': 'Cliente Test'}
        children_values = [
            {'name': 'Hijo 1'},
            {'name': 'Hijo 2'},
        ]

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertNotIn('email', parent)

    def test_empty_children(self):
        """Test: Sin children"""
        parent_values = {'name': 'Cliente Test'}
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertNotIn('email', parent)


class TestMergeComments(TransactionCase):
    """Tests para MergeComments"""

    def setUp(self):
        super().setUp()
        self.processor = MergeComments()
        self.context = {}

    def test_merge_comment_and_append(self):
        """Test: Combinar comment base con _append_comment"""
        parent_values = {
            'name': 'Cliente Test',
            'comment': 'Comentario base',
            '_append_comment': 'Teléfonos extra: 123456'
        }
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertIn('Comentario base', parent['comment'])
        self.assertIn('Teléfonos extra', parent['comment'])
        self.assertNotIn('_append_comment', parent)

    def test_only_append_comment(self):
        """Test: Solo _append_comment sin comment base"""
        parent_values = {
            'name': 'Cliente Test',
            '_append_comment': 'Teléfonos extra: 123456'
        }
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(parent['comment'], 'Teléfonos extra: 123456')
        self.assertNotIn('_append_comment', parent)

    def test_only_base_comment(self):
        """Test: Solo comment base sin _append"""
        parent_values = {
            'name': 'Cliente Test',
            'comment': 'Comentario base'
        }
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(parent['comment'], 'Comentario base')

    def test_no_comments(self):
        """Test: Sin comentarios"""
        parent_values = {'name': 'Cliente Test'}
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertNotIn('comment', parent)


class TestSetParentIdForChildren(TransactionCase):
    """Tests para SetParentIdForChildren"""

    def setUp(self):
        super().setUp()
        self.processor = SetParentIdForChildren()

    def test_set_parent_id_to_children(self):
        """Test: Asignar parent_id a todos los children"""
        parent_values = {'name': 'Cliente Test'}
        children_values = [
            {'name': 'Hijo 1'},
            {'name': 'Hijo 2'},
            {'name': 'Hijo 3'},
        ]
        context = {'parent_id': 100}

        parent, children = self.processor.process(parent_values, children_values, context)

        for child in children:
            self.assertEqual(child['parent_id'], 100)

    def test_no_parent_id_in_context(self):
        """Test: Sin parent_id en contexto"""
        parent_values = {'name': 'Cliente Test'}
        children_values = [
            {'name': 'Hijo 1'},
        ]
        context = {}

        parent, children = self.processor.process(parent_values, children_values, context)

        # No debe asignar parent_id
        self.assertNotIn('parent_id', children[0])

    def test_child_already_has_parent_id(self):
        """Test: Child ya tiene parent_id, no sobreescribir"""
        parent_values = {'name': 'Cliente Test'}
        children_values = [
            {'name': 'Hijo 1', 'parent_id': 50},
        ]
        context = {'parent_id': 100}

        parent, children = self.processor.process(parent_values, children_values, context)

        # No debe cambiar el parent_id existente
        self.assertEqual(children[0]['parent_id'], 50)

    def test_empty_children(self):
        """Test: Sin children"""
        parent_values = {'name': 'Cliente Test'}
        children_values = []
        context = {'parent_id': 100}

        parent, children = self.processor.process(parent_values, children_values, context)

        self.assertEqual(len(children), 0)


class TestNormalizePhoneNumbers(TransactionCase):
    """Tests para NormalizePhoneNumbers"""

    def setUp(self):
        super().setUp()
        self.processor = NormalizePhoneNumbers()
        self.context = {}

    def test_normalize_phone_removes_spaces(self):
        """Test: Normalizar elimina espacios"""
        parent_values = {
            'name': 'Cliente Test',
            'mobile': '666 123 456',
            'phone': '91 234 56 78'
        }
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(parent['mobile'], '666123456')
        self.assertEqual(parent['phone'], '912345678')  # Elimina espacios

    def test_normalize_phone_removes_hyphens(self):
        """Test: Normalizar elimina guiones"""
        parent_values = {
            'name': 'Cliente Test',
            'mobile': '666-123-456'
        }
        children_values = []

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(parent['mobile'], '666123456')

    def test_normalize_children_phones(self):
        """Test: Normalizar teléfonos de children también"""
        parent_values = {'name': 'Cliente Test'}
        children_values = [
            {'name': 'Hijo 1', 'mobile': '777 888 999'},
        ]

        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertEqual(children[0]['mobile'], '777888999')

    def test_normalize_empty_phone(self):
        """Test: Teléfono vacío no causa error"""
        parent_values = {
            'name': 'Cliente Test',
            'mobile': None,
            'phone': ''
        }
        children_values = []

        # No debe lanzar excepción
        parent, children = self.processor.process(parent_values, children_values, self.context)

        self.assertIsNone(parent['mobile'])


class TestPostProcessorRegistry(TransactionCase):
    """Tests para PostProcessorRegistry"""

    def test_get_registered_post_processor(self):
        """Test: Obtener post_processor registrado"""
        processor = PostProcessorRegistry.get('assign_email_from_children')
        self.assertIsInstance(processor, AssignEmailFromChildren)

    def test_get_nonexistent_post_processor(self):
        """Test: Obtener post_processor que no existe lanza error"""
        with self.assertRaises(ValueError):
            PostProcessorRegistry.get('nonexistent')

    def test_multiple_post_processors_registered(self):
        """Test: Verificar que hay múltiples post_processors registrados"""
        processors = PostProcessorRegistry.get_all()

        self.assertIn('assign_email_from_children', processors)
        self.assertIn('merge_comments', processors)
        self.assertGreater(len(list(processors)), 2)
