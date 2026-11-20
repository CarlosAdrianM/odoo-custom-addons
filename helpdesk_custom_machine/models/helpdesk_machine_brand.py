import unicodedata

from odoo import fields, models


def normalizar(texto):
    """Mayúsculas sin acentos, para comparar nombres de máquina escritos a mano."""
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).upper()


class HelpdeskMachineBrand(models.Model):
    _name = "helpdesk.machine.brand"
    _description = "Marca de máquina (decide el logo del informe de reparación)"
    _order = "sequence, id"

    name = fields.Char(string="Marca", required=True)
    sequence = fields.Integer(default=10)
    logo = fields.Image(string="Logo", max_width=1024, max_height=1024)
    keywords = fields.Char(
        string="Palabras clave de modelo",
        help="Separadas por comas. Si el nombre de la máquina contiene alguna, "
        "la máquina se asigna a esta marca. No distingue mayúsculas ni acentos.",
    )
    machine_count = fields.Integer(compute="_compute_machine_count", string="Máquinas")

    def _compute_machine_count(self):
        datos = self.env["helpdesk.machine"].read_group(
            [("brand_id", "in", self.ids)], ["brand_id"], ["brand_id"]
        )
        cuenta = {d["brand_id"][0]: d["brand_id_count"] for d in datos}
        for marca in self:
            marca.machine_count = cuenta.get(marca.id, 0)

    def _claves(self):
        self.ensure_one()
        return [normalizar(k).strip() for k in (self.keywords or "").split(",") if k.strip()]

    def _marca_para(self, nombre_maquina):
        """Primera marca (por orden) con una palabra clave contenida en el nombre."""
        nombre = normalizar(nombre_maquina)
        if not nombre:
            return self.browse()
        for marca in self.search([]):
            if any(clave in nombre for clave in marca._claves()):
                return marca
        return self.browse()

    def action_reasignar_maquinas(self):
        """Vuelve a calcular la marca de TODAS las máquinas según las palabras clave."""
        maquinas = self.env["helpdesk.machine"].search([])
        maquinas._compute_brand_id()
        return True
