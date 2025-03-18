from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    machine_id = fields.Many2one(
        'helpdesk.machine',  # Nombre del modelo de máquina
        string='Machine',    # Etiqueta del campo
        help='Select the machine associated with this ticket.'
    )
    serial_number = fields.Char(
        related='machine_id.serial_number',  # Campo relacionado
        string='Serial Number',              # Etiqueta del campo
        readonly=True,                       # Solo lectura
        store=True,  
        index=True
    )
    purchase_date = fields.Date(
        related='machine_id.purchase_date',  # Campo relacionado
        string='Purchase Date',              # Etiqueta del campo
        readonly=True,                       # Solo lectura
        store=True,
        index=True
    )

    def _modify_search_domain(self, domain):
        """
        Método auxiliar para modificar el dominio de búsqueda e incluir el campo serial_number.
        """
        new_domain = []
        for arg in domain:
            if isinstance(arg, (list, tuple)) and len(arg) == 3:
                field, operator, value = arg
                # Si estamos buscando por nombre o número y el valor podría ser un número de serie
                if field in ['name', 'number'] and value and isinstance(value, str):
                    new_domain.extend(['|',
                        ('serial_number', 'ilike', value),
                        (field, operator, value)
                    ])
                else:
                    new_domain.append(arg)
            else:
                new_domain.append(arg)
        
        _logger.info("Dominio de búsqueda modificado: %s", new_domain)
        return new_domain

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """Sobreescribimos _search para incluir búsquedas por serial_number"""
        new_args = self._modify_search_domain(args)
        return super()._search(new_args, offset=offset, limit=limit, order=order, 
                            count=count, access_rights_uid=access_rights_uid)

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True, **kwargs):
        """
        Sobrescribimos web_read_group para incluir búsquedas por serial_number.
        """
        new_domain = self._modify_search_domain(domain)
        return super().web_read_group(new_domain, fields, groupby, limit=limit, offset=offset, orderby=orderby, lazy=lazy)