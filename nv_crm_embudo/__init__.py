from . import models, controllers


def post_init_hook(cr, registry):
    """Los clientes que ya existían no vienen de este embudo: no se les busca lead de origen.

    Con SQL directo para no publicar nada hacia Nesto ni cargar miles de registros en el ORM.
    """
    cr.execute("UPDATE res_partner SET nv_lead_revisado = TRUE WHERE nv_lead_revisado IS NOT TRUE")
