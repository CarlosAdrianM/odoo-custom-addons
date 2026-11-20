from odoo import fields, models


class HelpdeskTicketStage(models.Model):
    _inherit = "helpdesk.ticket.stage"

    genera_informe = fields.Boolean(
        string="Genera informe de reparación",
        help="Al entrar un ticket en esta etapa se prepara el borrador del "
        "informe de reparación para el cliente (si aún no lo tiene).",
    )


class HelpdeskTicketTeam(models.Model):
    _inherit = "helpdesk.ticket.team"

    informe_tecnico_id = fields.Many2one(
        "res.users",
        string="Técnico (informes)",
        help="Recibe el aviso cuando faltan notas para redactar el informe.",
    )
    informe_revisor_id = fields.Many2one(
        "res.users",
        string="Revisor de informes",
        help="Recibe el aviso para revisar y aprobar cada informe.",
    )
