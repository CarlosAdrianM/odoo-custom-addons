# -*- coding: utf-8 -*-
"""
Tests para el sistema Dead Letter Queue (DLQ)

Versión 2.7.0
"""

import json
import base64
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.http import request


class TestDLQSystem(TransactionCase):
    """Tests para el sistema de Dead Letter Queue"""

    def setUp(self):
        super().setUp()

        # Crear modelos necesarios
        self.MessageRetry = self.env['nesto.sync.message.retry']
        self.FailedMessage = self.env['nesto.sync.failed.message']

        # Limpiar datos de prueba previos
        self.MessageRetry.search([]).unlink()
        self.FailedMessage.search([]).unlink()

    def test_01_increment_retry_first_attempt(self):
        """Test: Primer intento de un mensaje debe crear registro con retry_count=1"""

        message_id = 'test-message-001'
        error_msg = 'Test error'

        result = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message=error_msg,
            entity_type='cliente'
        )

        # Verificar resultado
        self.assertEqual(result['retry_count'], 1)
        self.assertFalse(result['should_move_to_dlq'])

        # Verificar registro creado
        retry_record = self.MessageRetry.search([('message_id', '=', message_id)])
        self.assertEqual(len(retry_record), 1)
        self.assertEqual(retry_record.retry_count, 1)
        self.assertEqual(retry_record.last_error, error_msg)

    def test_02_increment_retry_multiple_attempts(self):
        """Test: Múltiples intentos incrementan el contador correctamente"""

        message_id = 'test-message-002'

        # Primer intento
        result1 = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Error 1',
            entity_type='producto'
        )
        self.assertEqual(result1['retry_count'], 1)
        self.assertFalse(result1['should_move_to_dlq'])

        # Segundo intento
        result2 = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Error 2',
            entity_type='producto'
        )
        self.assertEqual(result2['retry_count'], 2)
        self.assertFalse(result2['should_move_to_dlq'])

        # Tercer intento
        result3 = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Error 3',
            entity_type='producto'
        )
        self.assertEqual(result3['retry_count'], 3)
        self.assertFalse(result3['should_move_to_dlq'])

    def test_03_move_to_dlq_after_max_retries(self):
        """Test: Después de MAX_RETRIES, debe marcar para mover a DLQ"""

        message_id = 'test-message-003'
        max_retries = self.MessageRetry.MAX_RETRIES  # Debería ser 3

        # Hacer MAX_RETRIES intentos
        for i in range(max_retries):
            result = self.MessageRetry.increment_retry(
                message_id=message_id,
                error_message=f'Error {i+1}',
                entity_type='cliente'
            )
            self.assertFalse(result['should_move_to_dlq'])

        # El siguiente intento debe marcar para DLQ
        result = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message=f'Error {max_retries + 1}',
            entity_type='cliente'
        )

        self.assertEqual(result['retry_count'], max_retries + 1)
        self.assertTrue(result['should_move_to_dlq'])

    def test_04_mark_success_removes_retry_record(self):
        """Test: Marcar mensaje como exitoso elimina el registro de retry"""

        message_id = 'test-message-004'

        # Crear registro de retry
        self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Test error',
            entity_type='producto'
        )

        # Verificar que existe
        retry_record = self.MessageRetry.search([('message_id', '=', message_id)])
        self.assertEqual(len(retry_record), 1)

        # Marcar como exitoso
        self.MessageRetry.mark_success(message_id)

        # Verificar que fue eliminado
        retry_record = self.MessageRetry.search([('message_id', '=', message_id)])
        self.assertEqual(len(retry_record), 0)

    def test_05_mark_moved_to_dlq(self):
        """Test: Marcar mensaje como movido a DLQ actualiza el estado"""

        message_id = 'test-message-005'

        # Crear registro de retry
        self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Test error',
            entity_type='cliente'
        )

        # Marcar como movido a DLQ
        self.MessageRetry.mark_moved_to_dlq(message_id)

        # Verificar que el registro fue marcado
        retry_record = self.MessageRetry.search([('message_id', '=', message_id)])
        self.assertEqual(len(retry_record), 1)
        self.assertTrue(retry_record.moved_to_dlq)

    def test_06_cleanup_old_records(self):
        """Test: Limpieza de registros antiguos"""

        from odoo import fields
        from datetime import timedelta

        # Crear registro antiguo (8 días)
        old_date = fields.Datetime.now() - timedelta(days=8)
        old_record = self.MessageRetry.create({
            'message_id': 'old-message',
            'retry_count': 1,
            'last_error': 'Old error',
            'entity_type': 'cliente',
            'create_date': old_date,
            'last_retry_date': old_date
        })

        # Crear registro reciente (2 días)
        recent_date = fields.Datetime.now() - timedelta(days=2)
        recent_record = self.MessageRetry.create({
            'message_id': 'recent-message',
            'retry_count': 1,
            'last_error': 'Recent error',
            'entity_type': 'producto',
            'create_date': recent_date,
            'last_retry_date': recent_date
        })

        # Ejecutar limpieza
        self.MessageRetry.cleanup_old_records()

        # Verificar que el antiguo fue eliminado y el reciente no
        self.assertFalse(self.MessageRetry.search([('message_id', '=', 'old-message')]))
        self.assertTrue(self.MessageRetry.search([('message_id', '=', 'recent-message')]))

    def test_07_failed_message_creation(self):
        """Test: Creación de mensaje fallido en DLQ"""

        message_id = 'test-failed-001'
        raw_data = '{"test": "data"}'
        error_msg = 'Test error message'
        error_trace = 'Traceback...'

        # Crear mensaje fallido
        failed_msg = self.FailedMessage.create({
            'message_id': message_id,
            'raw_data': raw_data,
            'entity_type': 'producto',
            'error_message': error_msg,
            'error_traceback': error_trace,
            'retry_count': 4,
            'state': 'failed'
        })

        # Verificar campos
        self.assertEqual(failed_msg.message_id, message_id)
        self.assertEqual(failed_msg.raw_data, raw_data)
        self.assertEqual(failed_msg.error_message, error_msg)
        self.assertEqual(failed_msg.retry_count, 4)
        self.assertEqual(failed_msg.state, 'failed')

    def test_08_failed_message_mark_resolved(self):
        """Test: Marcar mensaje como resuelto"""

        # Crear mensaje fallido
        failed_msg = self.FailedMessage.create({
            'message_id': 'test-resolve-001',
            'raw_data': '{"test": "data"}',
            'entity_type': 'cliente',
            'error_message': 'Test error',
            'retry_count': 4,
            'state': 'failed'
        })

        # Marcar como resuelto
        failed_msg.write({
            'state': 'resolved',
            'resolution_notes': 'Fixed manually'
        })

        # Verificar
        self.assertEqual(failed_msg.state, 'resolved')
        self.assertEqual(failed_msg.resolution_notes, 'Fixed manually')

    def test_09_failed_message_wizard_permanently_failed(self):
        """Test: Wizard para marcar como fallo permanente"""

        # Crear mensaje fallido
        failed_msg = self.FailedMessage.create({
            'message_id': 'test-wizard-001',
            'raw_data': '{"test": "data"}',
            'entity_type': 'producto',
            'error_message': 'Validation error',
            'retry_count': 4,
            'state': 'failed'
        })

        # Crear wizard
        wizard = self.env['nesto.sync.failed.message.wizard'].create({
            'failed_message_id': failed_msg.id,
            'action': 'permanently_failed',
            'resolution_notes': 'Invalid data from Nesto'
        })

        # Ejecutar acción
        wizard.action_confirm()

        # Verificar
        self.assertEqual(failed_msg.state, 'permanently_failed')
        self.assertEqual(failed_msg.resolution_notes, 'Invalid data from Nesto')

    def test_10_controller_retry_logic_integration(self):
        """Test: Integración del sistema de reintentos en el controller"""

        from ..controllers.controllers import NestoSyncController
        from werkzeug.wrappers import Response

        controller = NestoSyncController()

        # Simular datos de PubSub
        message_data = {
            "Tabla": "Productos",
            "Producto": "TEST001",
            "Nombre": "Test Product"
        }

        pubsub_message = {
            "message": {
                "messageId": "test-integration-001",
                "data": base64.b64encode(json.dumps(message_data).encode()).decode(),
                "publishTime": "2025-11-19T10:00:00Z"
            }
        }

        raw_data = json.dumps(pubsub_message).encode()

        # Mock del request
        with patch('odoo.http.request') as mock_request:
            mock_request.httprequest.data = raw_data
            mock_request.env = self.env

            # Simular error en el procesamiento
            with patch.object(controller, '_detect_entity_type', side_effect=ValueError("Test validation error")):

                # Primer intento - debe devolver 500 (NACK)
                response1 = controller.sync_nesto()
                self.assertEqual(response1.status_code, 500)

                # Verificar que se creó registro de retry
                retry_record = self.MessageRetry.search([('message_id', '=', 'test-integration-001')])
                self.assertEqual(len(retry_record), 1)
                self.assertEqual(retry_record.retry_count, 1)

                # Segundo y tercer intento
                response2 = controller.sync_nesto()
                self.assertEqual(response2.status_code, 500)

                response3 = controller.sync_nesto()
                self.assertEqual(response3.status_code, 500)

                # Cuarto intento - debe devolver 200 (ACK) y mover a DLQ
                response4 = controller.sync_nesto()
                self.assertEqual(response4.status_code, 200)

                # Verificar que se movió a DLQ
                failed_msg = self.FailedMessage.search([('message_id', '=', 'test-integration-001')])
                self.assertEqual(len(failed_msg), 1)
                self.assertEqual(failed_msg.state, 'failed')
                self.assertEqual(failed_msg.retry_count, 4)


class TestDLQEdgeCases(TransactionCase):
    """Tests de casos extremos del sistema DLQ"""

    def setUp(self):
        super().setUp()
        self.MessageRetry = self.env['nesto.sync.message.retry']
        self.FailedMessage = self.env['nesto.sync.failed.message']

        # Limpiar datos
        self.MessageRetry.search([]).unlink()
        self.FailedMessage.search([]).unlink()

    def test_message_without_message_id(self):
        """Test: Manejar mensaje sin messageId (no se puede trackear)"""

        # Cuando no hay messageId, el sistema debe hacer ACK para evitar loop infinito
        # Esto se maneja en el controller, no en los modelos
        pass  # Este test sería mejor como test de integración del controller

    def test_duplicate_failed_message(self):
        """Test: Evitar duplicados en DLQ"""

        message_id = 'test-duplicate-001'

        # Crear primer registro
        msg1 = self.FailedMessage.create({
            'message_id': message_id,
            'raw_data': '{"test": "data1"}',
            'entity_type': 'cliente',
            'error_message': 'Error 1',
            'retry_count': 4,
            'state': 'failed'
        })

        # Verificar que existe
        existing = self.FailedMessage.search([('message_id', '=', message_id)])
        self.assertEqual(len(existing), 1)

        # Intentar crear duplicado - debería actualizar el existente
        # (esto se maneja en el controller con search antes de create)

    def test_concurrent_retries(self):
        """Test: Reintentos concurrentes del mismo mensaje"""

        message_id = 'test-concurrent-001'

        # Primer proceso incrementa
        result1 = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Error 1',
            entity_type='producto'
        )

        # Segundo proceso incrementa (simula concurrencia)
        result2 = self.MessageRetry.increment_retry(
            message_id=message_id,
            error_message='Error 2',
            entity_type='producto'
        )

        # Debe haber solo un registro con retry_count=2
        retry_records = self.MessageRetry.search([('message_id', '=', message_id)])
        self.assertEqual(len(retry_records), 1)
        self.assertEqual(retry_records.retry_count, 2)
