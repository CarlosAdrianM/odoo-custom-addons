from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.automation_oca.tests.common import AutomationTestCase
from odoo.addons.mail.tests.common import MockEmail


@tagged('post_install', '-at_install')
class TestEnviosFiables(AutomationTestCase, MockEmail):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Como las plantillas del embudo: el correo enviado se queda guardado.
        cls.template.auto_delete = False
        cls.Paso = cls.env['automation.record.step']
        cls.Correo = cls.env['mail.mail']

    def _arrancar(self, *pasos_config):
        self.configuration.editable_domain = "[('id', '=', %s)]" % self.partner_01.id
        self.configuration.start_automation()
        self.env['automation.configuration'].cron_automation()

    def _paso(self, config_step):
        return self.Paso.search([('configuration_step_id', '=', config_step.id)])

    def _correos(self, paso):
        return self.Correo.search([('automation_record_step_id', '=', paso.id)])

    def _envejecer(self, correos, minutos=30):
        self.env.flush_all()  # si no, el write pendiente pisaría la fecha al guardarse
        self.env.cr.execute('UPDATE mail_mail SET write_date = %s, create_date = %s WHERE id IN %s', (
            fields.Datetime.now() - timedelta(minutes=minutos), fields.Datetime.now() - timedelta(minutes=minutos),
            tuple(correos.ids)))
        correos.invalidate_recordset()

    def _enviar_primer_correo(self):
        config = self.create_mail_activity()
        self._arrancar()
        with self.mock_mail_gateway():
            self.Paso._cron_automation_steps()
        paso = self._paso(config)
        return config, paso

    # ---------------------------------------------------------------- sin duplicados
    def test_paso_reprocesado_no_repite_el_correo(self):
        """Si el cron muere tras enviar y el paso vuelve a «programado», no se manda otra vez."""
        _config, paso = self._enviar_primer_correo()
        self.assertEqual(len(self._correos(paso)), 1)
        self.assertEqual(self._correos(paso).state, 'sent')
        paso.write({'state': 'scheduled'})  # lo que deja un cron cortado a medias
        with self.mock_mail_gateway():
            paso.run()
        self.assertEqual(len(self._correos(paso)), 1, 'no debe crearse un segundo correo')
        self.assertEqual(paso.state, 'done')
        self.assertEqual(paso.mail_status, 'sent')

    def test_paso_reprocesado_con_correo_en_cola_no_repite(self):
        _config, paso = self._enviar_primer_correo()
        self._correos(paso).state = 'outgoing'
        paso.write({'state': 'scheduled'})
        with self.mock_mail_gateway():
            paso.run()
        self.assertEqual(len(self._correos(paso)), 1)

    def test_paso_reprocesado_tras_fallo_anula_el_intento_viejo(self):
        _config, paso = self._enviar_primer_correo()
        viejo = self._correos(paso)
        viejo.write({'state': 'exception', 'failure_reason': 'Connection reset by peer'})
        paso.write({'state': 'scheduled'})
        with self.mock_mail_gateway():
            paso.run()
        correos = self._correos(paso)
        self.assertEqual(len(correos), 2)
        self.assertEqual(viejo.state, 'cancel')
        self.assertEqual((correos - viejo).state, 'sent')

    # ---------------------------------------------------------------- reintentos
    def test_reintenta_fallo_pasajero(self):
        _config, paso = self._enviar_primer_correo()
        correo = self._correos(paso)
        correo.write({'state': 'exception', 'failure_reason':
                      "SMTPSenderRefused: (530, b'5.7.57 Client not authenticated to send mail. Error: 451 4.7.0 "
                      "Temporary server error. Please try again later.')"})
        self._envejecer(correo)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'outgoing')
        self.assertEqual(correo.nv_reintentos, 1)
        self.assertFalse(correo.failure_reason)

    def test_reintenta_conexion_cortada(self):
        _config, paso = self._enviar_primer_correo()
        correo = self._correos(paso)
        correo.write({'state': 'exception', 'failure_reason': 'Connection unexpectedly closed: [Errno 104] Connection reset by peer'})
        self._envejecer(correo)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'outgoing')

    def test_no_reintenta_fallo_del_destinatario(self):
        _config, paso = self._enviar_primer_correo()
        correo = self._correos(paso)
        correo.write({'state': 'exception', 'failure_reason': "550 5.1.1 User unknown"})
        self._envejecer(correo)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'exception')
        correo.write({'failure_reason': 'Connection reset by peer', 'failure_type': 'mail_email_invalid'})
        self._envejecer(correo)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'exception')

    def test_espera_entre_reintentos_y_maximo(self):
        _config, paso = self._enviar_primer_correo()
        correo = self._correos(paso)
        correo.write({'state': 'exception', 'failure_reason': 'Connection reset by peer'})
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'exception', 'recién fallado: todavía no toca')
        for _i in range(3):
            self._envejecer(correo)
            self.Correo._nv_reintentar_correos_embudo()
            correo.write({'state': 'exception', 'failure_reason': 'Connection reset by peer'})
        self.assertEqual(correo.nv_reintentos, 3)
        self._envejecer(correo)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'exception', 'tras 3 reintentos se deja')

    def test_no_reintenta_correo_viejo(self):
        _config, paso = self._enviar_primer_correo()
        correo = self._correos(paso)
        correo.write({'state': 'exception', 'failure_reason': 'Connection reset by peer'})
        self._envejecer(correo, minutos=60 * 24 * 3)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(correo.state, 'exception')

    def test_fallo_con_hermano_enviado_se_anula(self):
        _config, paso = self._enviar_primer_correo()
        enviado = self._correos(paso)
        fallido = enviado.copy({'state': 'exception', 'failure_reason': 'Connection reset by peer',
                                'automation_record_step_id': paso.id})
        self._envejecer(fallido)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(fallido.state, 'cancel')
        self.assertEqual(enviado.state, 'sent')

    def test_correo_sin_paso_no_se_toca(self):
        _config, paso = self._enviar_primer_correo()
        otro = self._correos(paso).copy({'state': 'exception', 'failure_reason': 'Connection reset by peer',
                                         'automation_record_step_id': False})
        self._envejecer(otro)
        self.Correo._nv_reintentar_correos_embudo()
        self.assertEqual(otro.state, 'exception')

    # ---------------------------------------------------------------- secuencia
    def test_siguiente_correo_rechazado_si_el_anterior_no_salio(self):
        config = self.create_mail_activity()
        hijo = self.create_mail_activity(parent_id=config.id)
        self._arrancar()
        with self.mock_mail_gateway():
            self.Paso._cron_automation_steps()
        paso = self._paso(config)
        self._correos(paso).write({'state': 'exception', 'failure_reason': '550 5.1.1 User unknown'})
        paso_hijo = self._paso(hijo)
        self.assertTrue(paso_hijo)
        with self.mock_mail_gateway():
            paso_hijo.run()
        self.assertEqual(paso_hijo.state, 'rejected')
        self.assertFalse(self._correos(paso_hijo))

    def test_siguiente_correo_sale_si_el_anterior_salio(self):
        config = self.create_mail_activity()
        hijo = self.create_mail_activity(parent_id=config.id)
        self._arrancar()
        with self.mock_mail_gateway():
            self.Paso._cron_automation_steps()
        paso_hijo = self._paso(hijo)
        with self.mock_mail_gateway():
            paso_hijo.run()
        self.assertEqual(paso_hijo.state, 'done')
        self.assertEqual(len(self._correos(paso_hijo)), 1)
