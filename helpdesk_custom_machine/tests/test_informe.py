from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models import informe_ia

RUTA = "odoo.addons.helpdesk_custom_machine.models.helpdesk_ticket_informe.informe_ia"

BORRADOR = {
    "suficiente": True,
    "motivo_insuficiente": "",
    "averia_comunicada": "El equipo no encendía.",
    "diagnostico": "Interruptor de encendido averiado.",
    "trabajo_realizado": "Se ha sustituido el interruptor de encendido y se ha probado el equipo.",
    "piezas_sustituidas": "Interruptor de encendido",
    "recomendaciones": "",
    "pendiente": "",
    "avisos_revision": "",
}


@tagged("post_install", "-at_install")
class TestInformeReparacion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.tecnico = cls.env["res.users"].create({"name": "Técnico", "login": "tec_informe"})
        cls.revisor = cls.env["res.users"].create({"name": "Revisora", "login": "rev_informe"})
        cls.equipo = cls.env["helpdesk.ticket.team"].create({
            "name": "Taller pruebas",
            "informe_tecnico_id": cls.tecnico.id,
            "informe_revisor_id": cls.revisor.id,
        })
        Etapa = cls.env["helpdesk.ticket.stage"]
        cls.en_progreso = Etapa.create({"name": "Progreso pruebas", "sequence": 90})
        cls.listo = Etapa.create({"name": "Listo pruebas", "sequence": 91, "genera_informe": True})
        cls.marca = cls.env["helpdesk.machine.brand"].create({"name": "Marca Propia", "keywords": "zeta, ÓMICRON", "sequence": -1})
        cls.maquina = cls.env["helpdesk.machine"].create({"name": "Modelo 7 omicron+", "serial_number": "T-INF-1"})
        cls.cliente = cls.env["res.partner"].create({"name": "Centro Pruebas", "email": "cliente@example.com"})

    def _ticket(self, **valores):
        datos = {
            "name": "c/1 no enciende",
            "description": "<p>No enciende</p>",
            "team_id": self.equipo.id,
            "stage_id": self.en_progreso.id,
            "machine_id": self.maquina.id,
            "partner_id": self.cliente.id,
            "partner_email": self.cliente.email,
        }
        datos.update(valores)
        return self.env["helpdesk.ticket"].create(datos)

    def _nota(self, ticket, texto="Se cambia el interruptor de encendido."):
        ticket.with_user(self.tecnico).sudo().message_post(
            body=texto, message_type="comment", subtype_xmlid="mail.mt_note", author_id=self.tecnico.partner_id.id
        )

    def _procesar(self, ticket, borrador=None, error=None):
        with patch(RUTA + ".leer_clave", return_value="clave"), patch(
            RUTA + ".redactar", return_value=borrador or BORRADOR, side_effect=error
        ) as redactar:
            self.env["helpdesk.ticket"]._cron_informes(limite=1000)
        return redactar

    def test_marca_por_palabra_clave(self):
        self.assertEqual(self.maquina.brand_id, self.marca, "ÓMICRON debe casar con 'omicron+' sin acento")
        otra = self.env["helpdesk.machine"].create({"name": "Aparato sin marca conocida"})
        self.assertFalse(otra.brand_id)
        self.assertEqual(self._ticket().informe_brand_id, self.marca)

    def test_etapa_sin_marca_no_encola(self):
        ticket = self._ticket()
        ticket.stage_id = self.env["helpdesk.ticket.stage"].create({"name": "Otra", "sequence": 92})
        self.assertEqual(ticket.informe_state, "no")

    def test_sin_notas_no_llama_a_la_ia_y_avisa_al_tecnico(self):
        ticket = self._ticket()
        ticket.stage_id = self.listo
        self.assertEqual(ticket.informe_state, "en_cola")
        redactar = self._procesar(ticket)
        redactar.assert_not_called()
        self.assertEqual(ticket.informe_state, "falta_info")
        self.assertEqual(ticket.kanban_state, "blocked")
        self.assertEqual(ticket.activity_ids.user_id, self.tecnico)
        # La nota del técnico vuelve a lanzar la redacción
        self._nota(ticket)
        self.assertEqual(ticket.informe_state, "en_cola")
        self._procesar(ticket)
        self.assertEqual(ticket.informe_state, "borrador")
        self.assertEqual(ticket.kanban_state, "normal")
        self.assertEqual(ticket.activity_ids.user_id, self.revisor)

    def test_borrador_y_datos_enviados_a_la_ia(self):
        ticket = self._ticket()
        self._nota(ticket)
        ticket.stage_id = self.listo
        redactar = self._procesar(ticket)
        self.assertEqual(ticket.informe_state, "borrador")
        self.assertIn("interruptor", ticket.informe_trabajo)
        self.assertFalse(ticket.informe_recomendaciones)
        enviado = redactar.call_args[0][0]
        self.assertIn("Se cambia el interruptor", enviado)
        self.assertIn("Modelo 7", enviado)
        self.assertNotIn("Centro Pruebas", enviado)
        self.assertNotIn("cliente@example.com", enviado)

    def test_ia_dice_insuficiente(self):
        ticket = self._ticket()
        self._nota(ticket, "No coge el teléfono.")
        ticket.stage_id = self.listo
        self._procesar(ticket, dict(BORRADOR, suficiente=False, motivo_insuficiente="Falta la intervención."))
        self.assertEqual(ticket.informe_state, "falta_info")
        self.assertEqual(ticket.informe_motivo_falta, "Falta la intervención.")

    def test_error_reintentable_y_definitivo(self):
        ticket = self._ticket()
        self._nota(ticket)
        ticket.stage_id = self.listo
        self._procesar(ticket, error=informe_ia.ErrorInformeIA("caída", reintentable=True))
        self.assertEqual((ticket.informe_state, ticket.informe_intentos), ("en_cola", 1))
        self._procesar(ticket, error=informe_ia.ErrorInformeIA("sin clave", reintentable=False))
        self.assertEqual(ticket.informe_state, "error")
        self.assertEqual(ticket.activity_ids.user_id, self.revisor)
        # Al volver a entrar en la etapa se reintenta
        ticket.stage_id = self.en_progreso
        ticket.stage_id = self.listo
        self.assertEqual(ticket.informe_state, "en_cola")

    def test_aprobar_envia_pdf_por_correo(self):
        ticket = self._ticket()
        self._nota(ticket)
        ticket.stage_id = self.listo
        self._procesar(ticket)
        antes = self.env["mail.mail"].search([("email_to", "=", "cliente@example.com")])
        ticket.with_user(self.revisor).sudo().action_informe_aprobar()
        self.assertEqual((ticket.informe_state, ticket.informe_via), ("enviado", "correo"))
        self.assertTrue(ticket.informe_attachment_id.raw.startswith(b"%PDF"))
        correo = self.env["mail.mail"].search([("email_to", "=", "cliente@example.com")]) - antes
        self.assertEqual(len(correo), 1)
        self.assertEqual(correo.attachment_ids, ticket.informe_attachment_id)
        self.assertFalse(ticket.activity_ids)
        with self.assertRaises(UserError):
            ticket.action_informe_aprobar()
        # No se vuelve a redactar un informe ya aprobado
        ticket.stage_id = self.en_progreso
        ticket.stage_id = self.listo
        self.assertEqual(ticket.informe_state, "enviado")

    def test_sin_correo_entrega_impresa(self):
        sin_correo = self.env["res.partner"].create({"name": "Sin correo"})
        ticket = self._ticket(partner_id=sin_correo.id, partner_email=False)
        self._nota(ticket)
        ticket.stage_id = self.listo
        self._procesar(ticket)
        ticket.action_informe_aprobar()
        self.assertEqual(ticket.informe_state, "papel")
        self.assertEqual(ticket.activity_ids.summary, "Imprimir el informe de reparación y entregarlo con la máquina")
        ticket.action_informe_entregado()
        self.assertEqual((ticket.informe_state, ticket.informe_via), ("enviado", "papel"))
        self.assertFalse(ticket.activity_ids)

    def test_no_aprueba_sin_trabajo_realizado(self):
        ticket = self._ticket()
        with self.assertRaises(UserError):
            ticket.action_informe_aprobar()
