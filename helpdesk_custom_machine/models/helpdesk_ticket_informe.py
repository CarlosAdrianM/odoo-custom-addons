import base64
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from . import informe_ia, informe_pdf

_logger = logging.getLogger(__name__)

MAX_INTENTOS = 5
ACT_FALTA = "Faltan notas para el informe de reparación"
ACT_REVISAR = "Revisar y aprobar el informe de reparación"
ACT_PAPEL = "Imprimir el informe de reparación y entregarlo con la máquina"
ACT_ERROR = "No se ha podido redactar el informe de reparación"

# Campo del ticket <- clave del borrador que devuelve la IA
CAMPOS = {
    "informe_averia": "averia_comunicada",
    "informe_diagnostico": "diagnostico",
    "informe_trabajo": "trabajo_realizado",
    "informe_piezas": "piezas_sustituidas",
    "informe_recomendaciones": "recomendaciones",
    "informe_pendiente": "pendiente",
    "informe_avisos": "avisos_revision",
}


class HelpdeskTicketInforme(models.Model):
    _inherit = "helpdesk.ticket"

    informe_state = fields.Selection(
        [
            ("no", "Sin informe"),
            ("en_cola", "Preparando borrador"),
            ("falta_info", "Faltan notas del técnico"),
            ("borrador", "Pendiente de aprobar"),
            ("papel", "Aprobado: entregar impreso"),
            ("enviado", "Entregado al cliente"),
            ("error", "Error al redactar"),
        ],
        string="Informe de reparación",
        default="no",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    informe_brand_id = fields.Many2one(
        "helpdesk.machine.brand",
        string="Logo del informe",
        compute="_compute_informe_brand_id",
        store=True,
        readonly=False,
        help="Marca cuyo logo encabeza el informe. Vacío: logo de la empresa.",
    )
    informe_averia = fields.Text(string="Avería comunicada", copy=False)
    informe_diagnostico = fields.Text(string="Diagnóstico", copy=False)
    informe_trabajo = fields.Text(string="Trabajo realizado", copy=False)
    informe_piezas = fields.Text(string="Piezas sustituidas", copy=False)
    informe_recomendaciones = fields.Text(string="Recomendaciones", copy=False)
    informe_pendiente = fields.Text(string="Pendiente para una próxima visita", copy=False)
    informe_avisos = fields.Text(
        string="Avisos para quien revisa",
        copy=False,
        help="Dudas que ha dejado la IA al redactar. No se imprimen en el informe.",
    )
    informe_motivo_falta = fields.Text(string="Qué falta", copy=False)
    informe_error = fields.Text(string="Último error", copy=False)
    informe_intentos = fields.Integer(copy=False)
    informe_attachment_id = fields.Many2one("ir.attachment", string="PDF del informe", copy=False)
    informe_via = fields.Selection(
        [("correo", "Correo electrónico"), ("papel", "Impreso")], string="Entregado por", copy=False
    )
    informe_fecha = fields.Datetime(string="Aprobado el", copy=False)
    informe_aprobado_por = fields.Many2one("res.users", string="Aprobado por", copy=False)
    informe_correo = fields.Char(string="Correo del cliente", compute="_compute_informe_correo")

    @api.depends("machine_id.brand_id")
    def _compute_informe_brand_id(self):
        for ticket in self:
            ticket.informe_brand_id = ticket.machine_id.brand_id

    @api.depends("partner_email", "partner_id.email")
    def _compute_informe_correo(self):
        for ticket in self:
            ticket.informe_correo = (ticket.partner_email or ticket.partner_id.email or "").strip()

    # ------------------------------------------------------------------
    # Disparadores
    # ------------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        if vals.get("stage_id"):
            etapa = self.env["helpdesk.ticket.stage"].browse(vals["stage_id"])
            if etapa.genera_informe:
                self.filtered(lambda t: t.informe_state in ("no", "error"))._informe_encolar()
        return res

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, **kwargs):
        mensaje = super().message_post(**kwargs)
        # Una nota nueva del personal en un ticket al que le faltaban notas
        # vuelve a lanzar la redacción del borrador.
        if kwargs.get("message_type") == "comment" and not self.env.user.share:
            self.filtered(lambda t: t.informe_state == "falta_info")._informe_encolar()
        return mensaje

    def _informe_encolar(self):
        if self:
            self.write({"informe_state": "en_cola", "informe_intentos": 0, "informe_error": False})

    @api.model
    def _cron_informes(self, limite=5):
        for ticket in self.search([("informe_state", "=", "en_cola")], order="write_date", limit=limite):
            ticket._informe_procesar()

    # ------------------------------------------------------------------
    # Redacción del borrador
    # ------------------------------------------------------------------
    def _informe_notas(self):
        """[(fecha, es_del_personal, texto)] con las notas y los mensajes del cliente."""
        self.ensure_one()
        notas = []
        for mensaje in self.message_ids.sorted(lambda m: (m.date, m.id)):
            if mensaje.message_type not in ("comment", "email"):
                continue
            texto = html2plaintext(mensaje.body or "").strip()
            if not texto:
                continue
            usuarios = mensaje.author_id.sudo().with_context(active_test=False).user_ids
            interno = any(not u.share for u in usuarios)
            if interno and mensaje.message_type == "email":
                continue  # avisos automáticos de cambio de etapa enviados al cliente
            notas.append((mensaje.date, interno, texto))
        return notas

    def _informe_texto_para_ia(self, notas):
        """Lo que se envía a la IA: datos técnicos, sin nombre ni contacto del cliente."""
        self.ensure_one()
        lineas = [
            "<ticket>",
            "<maquina>%s</maquina>" % (self.machine_id.name or "No indicada"),
            "<asunto>%s</asunto>" % (self.name or ""),
            "<descripcion_inicial>\n%s\n</descripcion_inicial>"
            % (html2plaintext(self.description or "").strip() or "(vacía)"),
            "<notas>",
        ]
        for fecha, interno, texto in notas:
            lineas.append(
                '<nota fecha="%s" autor="%s">\n%s\n</nota>'
                % (fecha.strftime("%d/%m/%Y"), "personal del taller" if interno else "cliente", texto)
            )
        lineas += ["</notas>", "</ticket>", "", "Redacta el borrador del informe de reparación de este ticket."]
        return "\n".join(lineas)

    def _informe_generar(self):
        self.ensure_one()
        notas = self._informe_notas()
        if not any(interno for _fecha, interno, _texto in notas):
            return self._informe_marcar_falta(
                "El ticket no tiene ninguna nota del taller que explique qué se le ha hecho a la máquina."
            )
        parametros = self.env["ir.config_parameter"].sudo()
        clave = informe_ia.leer_clave(parametros.get_param("helpdesk_informe.fichero_clave"))
        borrador = informe_ia.redactar(
            self._informe_texto_para_ia(notas), clave, parametros.get_param("helpdesk_informe.modelo")
        )
        if not borrador.get("suficiente") or not (borrador.get("trabajo_realizado") or "").strip():
            return self._informe_marcar_falta(
                borrador.get("motivo_insuficiente")
                or "Las notas del ticket no describen qué se le ha hecho a la máquina."
            )
        valores = {campo: (borrador.get(clave_ia) or "").strip() or False for campo, clave_ia in CAMPOS.items()}
        valores.update(informe_state="borrador", informe_motivo_falta=False, informe_error=False)
        if self.kanban_state == "blocked" and self.informe_state in ("falta_info", "en_cola"):
            valores["kanban_state"] = "normal"
        self.write(valores)
        self._informe_cerrar_actividades(ACT_FALTA, ACT_ERROR)
        self._informe_actividad(self.team_id.informe_revisor_id, ACT_REVISAR)
        return True

    def _informe_marcar_falta(self, motivo):
        self.write({
            "informe_state": "falta_info",
            "informe_motivo_falta": motivo,
            "informe_error": False,
            "kanban_state": "blocked",
        })
        self._informe_actividad(
            self.team_id.informe_tecnico_id or self.user_id,
            ACT_FALTA,
            nota="%s Añada una nota en el ticket con lo que se le ha hecho a la máquina; "
            "el borrador del informe se redactará solo." % motivo,
        )
        return False

    def _informe_procesar(self):
        """Redacta el borrador sin dejar que un fallo de la IA rompa nada más."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._informe_generar()
        except informe_ia.ErrorInformeIA as error:
            intentos = self.informe_intentos + 1
            _logger.warning("Informe de reparación del ticket %s: %s", self.number, error)
            if error.reintentable and intentos < MAX_INTENTOS and self.informe_state == "en_cola":
                self.write({"informe_intentos": intentos, "informe_error": str(error)})
            else:
                self.write({"informe_state": "error", "informe_intentos": intentos, "informe_error": str(error)})
                self._informe_actividad(self.team_id.informe_revisor_id, ACT_ERROR, nota=str(error))

    # ------------------------------------------------------------------
    # Actividades
    # ------------------------------------------------------------------
    def _informe_actividad(self, usuario, resumen, nota=None):
        self.ensure_one()
        usuario = usuario or self.user_id
        if not usuario:
            return
        if self.activity_ids.filtered(lambda a: a.summary == resumen and a.user_id == usuario):
            return
        self.activity_schedule(
            "mail.mail_activity_data_todo", summary=resumen, note=nota, user_id=usuario.id
        )

    def _informe_cerrar_actividades(self, *resumenes):
        self.mapped("activity_ids").filtered(lambda a: a.summary in resumenes).action_done()

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def _informe_datos_pdf(self):
        self.ensure_one()
        empresa = self.company_id or self.env.company
        socio = empresa.partner_id
        direccion = ", ".join(p for p in (socio.street, " ".join(filter(None, (socio.zip, socio.city)))) if p)
        contacto = " · ".join(
            p for p in (
                socio.phone and "Tel. %s" % socio.phone,
                socio.email,
                (socio.website or "").replace("https://", "").replace("http://", ""),
            ) if p
        )
        pie = [p for p in (" · ".join(p for p in (empresa.name, socio.vat) if p), direccion, contacto) if p]
        return {
            "logo": self.informe_brand_id.logo or empresa.logo,
            "numero": self.number,
            "fecha": fields.Date.context_today(self).strftime("%d/%m/%Y"),
            "filas": [
                ("Cliente", self.partner_id.name or self.partner_name),
                ("Número de cliente", self._informe_numero_cliente()),
                ("Máquina", self.machine_id.name),
                ("Número de serie", self.machine_id.serial_number),
                ("Fecha de entrada", fields.Datetime.context_timestamp(self, self.create_date).strftime("%d/%m/%Y")),
            ],
            "secciones": [
                ("Avería comunicada", self.informe_averia),
                ("Diagnóstico", self.informe_diagnostico),
                ("Trabajo realizado", self.informe_trabajo),
                ("Piezas sustituidas", self.informe_piezas),
                ("Recomendaciones", self.informe_recomendaciones),
                ("Pendiente para una próxima visita", self.informe_pendiente),
            ],
            "pie": pie,
        }

    def _informe_numero_cliente(self):
        """Número de cliente de Nesto, si el módulo nesto_sync está instalado."""
        self.ensure_one()
        socio = self.partner_id
        if "cliente_externo" not in socio._fields:
            return False
        return socio.cliente_externo or socio.commercial_partner_id.cliente_externo

    def _informe_crear_pdf(self):
        """Genera el PDF y lo deja como adjunto del ticket (sustituye al anterior)."""
        self.ensure_one()
        contenido = informe_pdf.generar(self._informe_datos_pdf())
        valores = {
            "name": "Informe de reparación %s.pdf" % self.number,
            "datas": base64.b64encode(contenido),
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
        }
        adjunto = self.informe_attachment_id.sudo()
        if adjunto.exists():
            adjunto.write(valores)
        else:
            adjunto = self.env["ir.attachment"].sudo().create(valores)
            self.informe_attachment_id = adjunto
        return adjunto

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def _informe_comprobar_editable(self):
        for ticket in self:
            if ticket.informe_state in ("papel", "enviado"):
                raise UserError(_("El informe del ticket %s ya está aprobado.") % ticket.number)

    def action_informe_generar(self):
        self._informe_comprobar_editable()
        for ticket in self:
            ticket.write({"informe_state": "en_cola", "informe_intentos": MAX_INTENTOS, "informe_error": False})
            ticket._informe_procesar()
        return True

    def action_informe_vista_previa(self):
        self.ensure_one()
        if not (self.informe_trabajo or "").strip():
            raise UserError(_("El apartado «Trabajo realizado» está vacío."))
        adjunto = self.informe_attachment_id
        if self.informe_state not in ("papel", "enviado") or not adjunto.exists():
            adjunto = self._informe_crear_pdf()
        return {"type": "ir.actions.act_url", "url": "/web/content/%s" % adjunto.id, "target": "new"}

    def action_informe_aprobar(self):
        for ticket in self:
            ticket._informe_comprobar_editable()
            if not (ticket.informe_trabajo or "").strip():
                raise UserError(_("No se puede aprobar: el apartado «Trabajo realizado» está vacío."))
            adjunto = ticket._informe_crear_pdf()
            correo = ticket.informe_correo
            ticket.write({
                "informe_state": "enviado" if correo else "papel",
                "informe_via": "correo" if correo else False,
                "informe_fecha": fields.Datetime.now(),
                "informe_aprobado_por": self.env.user.id,
                "informe_error": False,
            })
            if ticket.kanban_state == "blocked" and ticket.informe_motivo_falta:
                ticket.write({"kanban_state": "normal", "informe_motivo_falta": False})
            ticket._informe_cerrar_actividades(ACT_REVISAR, ACT_FALTA, ACT_ERROR)
            if correo:
                ticket._informe_enviar_correo(adjunto, correo)
                nota = _("Informe de reparación aprobado y enviado a %s.") % correo
            else:
                ticket._informe_actividad(ticket.team_id.informe_revisor_id or self.env.user, ACT_PAPEL)
                nota = _("Informe de reparación aprobado. El cliente no tiene correo: hay que entregarlo impreso.")
            ticket.message_post(body=nota, attachment_ids=adjunto.ids)
        return True

    def _informe_enviar_correo(self, adjunto, correo):
        self.ensure_one()
        empresa = self.company_id or self.env.company
        maquina = self.machine_id.name
        cuerpo = Markup(
            "<p>Estimado cliente:</p>"
            "<p>Le adjuntamos el informe de la reparación realizada%s (referencia %s).</p>"
            "<p>Si tiene cualquier duda sobre su contenido, puede responder a este correo%s.</p>"
            "<p>Un saludo,<br/>Servicio técnico<br/>%s</p>"
        ) % (
            Markup(" a su equipo <strong>%s</strong>") % maquina if maquina else "",
            self.number,
            Markup(" o llamarnos al %s") % empresa.phone if empresa.phone else "",
            empresa.name,
        )
        self.env["mail.mail"].sudo().create({
            "subject": "Informe de reparación de su equipo (%s)" % self.number,
            "body_html": cuerpo,
            "email_from": empresa.partner_id.email_formatted or empresa.email,
            "email_to": correo,
            "attachment_ids": [(4, adjunto.id)],
            "auto_delete": True,
        })

    def action_informe_entregado(self):
        for ticket in self.filtered(lambda t: t.informe_state == "papel"):
            ticket.write({"informe_state": "enviado", "informe_via": "papel"})
            ticket._informe_cerrar_actividades(ACT_PAPEL)
        return True

    def action_informe_reabrir(self):
        """Devuelve a borrador un informe aprobado, para corregirlo y volver a aprobarlo."""
        for ticket in self.filtered(lambda t: t.informe_state in ("papel", "enviado")):
            ticket.write({"informe_state": "borrador", "informe_via": False})
            ticket._informe_cerrar_actividades(ACT_PAPEL)
        return True
