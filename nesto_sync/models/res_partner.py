from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['bidirectional.sync.mixin', 'res.partner']

    cliente_externo = fields.Char(string="Cliente Externo", index=True, search="_search_cliente_externo")
    contacto_externo = fields.Char(string="Contacto Externo", index=True)
    persona_contacto_externa = fields.Char(string="Persona de Contacto Externa", index=True)

    # Fechas de compras (issue #8). Las calcula Nesto sobre LinPedidoVta y son del cliente
    # (Nº_Cliente), así que llegan iguales en todos sus contactos. Solo entran: nunca se
    # devuelven a Nesto (ver 'reverse': False en entity_configs.py).
    fecha_primer_presupuesto = fields.Date(
        string="Fecha del primer presupuesto", readonly=True, copy=False, index=True,
        help="Primer presupuesto del cliente en Nesto (LinPedidoVta con Estado -3). "
             "La calcula y la mantiene Nesto; en Odoo es de solo lectura.")
    fecha_primer_pedido = fields.Date(
        string="Fecha del primer pedido", readonly=True, copy=False, index=True,
        help="Primer pedido real del cliente en Nesto (LinPedidoVta con Estado > -3). "
             "Sin fecha = el cliente todavía no ha comprado nunca.")
    fecha_ultimo_pedido = fields.Date(
        string="Fecha del último pedido", readonly=True, copy=False, index=True,
        help="Último pedido real del cliente en Nesto. La calcula y la mantiene Nesto.")

    # Origen y consentimiento (issue #43). Los manda el importador de leads de Nesto
    # (ClientesOrigen) en el contacto principal. Solo entran: nunca se devuelven a Nesto.
    origen_cliente = fields.Char(
        string="Origen del cliente", readonly=True, copy=False, index=True,
        help="Por dónde entró el cliente en Nesto (tabla ClientesOrigen), p. ej. "
             "META-HARMONIA-0926. Nesto no lo cambia nunca una vez puesto.")
    fecha_origen = fields.Datetime(
        string="Fecha de origen", readonly=True, copy=False,
        help="Cuándo entró el cliente por ese origen (para Meta, la fecha del lead).")
    acepta_comunicaciones = fields.Selection(
        [('si', 'Acepta'), ('no', 'No acepta')],
        string="Acepta comunicaciones comerciales", readonly=True, copy=False, index=True,
        help="Consentimiento de correos comerciales que guarda Nesto. Vacío = Nesto no lo "
             "ha mandado (clientes anteriores al importador de leads). Con «No acepta» el "
             "cliente no entra en ningún embudo de correos.")

    # El usuario vendedor (user_id) se resuelve SOLO por email (VendedorEmail): cada sistema
    # resuelve el código desde el email por su cuenta. Los códigos de aquí abajo son
    # informativos y para segmentar (p. ej. «NV» = sin vendedor real, que llega con
    # VendedorEmail a null y no se distingue de otro modo). Solo entran: nunca vuelven a Nesto.
    vendedor_nesto = fields.Char(
        string="Vendedor en Nesto", readonly=True, copy=False, index=True,
        help="Código del vendedor principal del contacto en Nesto (Clientes.Vendedor). "
             "«NV» es el genérico: el cliente no es cartera de nadie.")
    vendedor_peluqueria_nesto = fields.Char(
        string="Vendedor de peluquería en Nesto", readonly=True, copy=False, index=True,
        help="Código del vendedor del grupo de peluquería en Nesto "
             "(VendedoresClienteGrupoProducto). Vacío = Nesto no lo ha mandado.")
    estado_nesto = fields.Char(
        string="Estado en Nesto", readonly=True, copy=False, index=True,
        help="Clientes.Estado de Nesto tal cual (0 visita de comercial, 9 equipo telefónico, "
             "8 particular web, 93/11/22 sin compra...). Es texto para distinguir el estado 0 "
             "de «Nesto no lo ha mandado» (vacío). Los negativos son fichas anuladas.")

    # Bloques del embudo de reactivación. Solo los traen los mensajes que salen del
    # endpoint de republicación por bloques de NestoAPI; un mensaje normal no los borra.
    bloque_embudo = fields.Char(
        string="Bloque del embudo", readonly=True, copy=False, index=True,
        help="Identificador del bloque con el que Nesto mandó este cliente para el embudo "
             "(p. ej. NV-2026-11-01). Vacío = no ha llegado por ningún bloque.")
    responsable_embudo_email = fields.Char(
        string="Responsable del embudo (correo)", readonly=True, copy=False,
        help="A quién se avisa si este contacto responde al embudo o hace un pedido. Lo "
             "calcula Nesto con el código postal del contacto al encolar el bloque.")
    responsable_embudo_tipo = fields.Char(
        string="Responsable del embudo (tipo)", readonly=True, copy=False,
        help="EquipoAlberto, Vendedor o TiendaOnline, según el vendedor del código postal.")
    enviar_boletin = fields.Selection(
        [('si', 'Sí'), ('no', 'No (baja)')],
        string="Enviar boletín", readonly=True, copy=False, index=True,
        help="PersonasContactoCliente.EnviarBoletin de Nesto, por persona de contacto. «No» es "
             "una baja expresa: a esa persona no se le escribe. Vacío = Nesto no lo ha mandado.")

    @api.constrains('cliente_externo', 'contacto_externo', 'persona_contacto_externa')
    def _check_unique_combinations(self):
        for record in self:
            # Si persona_contacto_externa es None, validar unicidad solo de cliente_externo y contacto_externo
            if not record.persona_contacto_externa:
                duplicates = self.search([
                    ('id', '!=', record.id),
                    ('cliente_externo', '=', record.cliente_externo),
                    ('contacto_externo', '=', record.contacto_externo),
                    ('persona_contacto_externa', '=', False)
                ])
                if duplicates:
                    raise ValidationError(
                        "La combinación de Cliente Externo y Contacto Externo debe ser única si no se especifica una Persona de Contacto Externa."
                    )
            # Si persona_contacto_externa no es None, validar unicidad de cliente_externo, contacto_externo y persona_contacto_externa
            else:
                duplicates = self.search([
                    ('id', '!=', record.id),
                    ('cliente_externo', '=', record.cliente_externo),
                    ('contacto_externo', '=', record.contacto_externo),
                    ('persona_contacto_externa', '=', record.persona_contacto_externa)
                ])
                if duplicates:
                    raise ValidationError(
                        "La combinación de Cliente Externo, Contacto Externo y Persona de Contacto Externa debe ser única."
                    )

    @api.model
    def _search_cliente_externo(self, operator, value):
        if value and value.isdigit():
            return [('cliente_externo', '=', value)]
        return [('cliente_externo', operator, value)]

    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        # Modificar args si contiene una búsqueda por nombre/display_name
        new_args = []
        for arg in args:
            if isinstance(arg, (list, tuple)) and len(arg) == 3:
                field, operator, value = arg
                if field in ['name', 'display_name'] and value and str(value).isdigit():
                    new_args.extend(['|',
                        ('cliente_externo', '=', value),
                        (field, operator, value)
                    ])
                else:
                    new_args.append(arg)
            else:
                new_args.append(arg)
        
        return super()._search(new_args, offset=offset, limit=limit, order=order, 
                             count=count, access_rights_uid=access_rights_uid)