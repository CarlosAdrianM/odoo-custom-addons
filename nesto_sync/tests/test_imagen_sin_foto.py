"""URL de imagen «sin foto» de la tienda (issue #55).

La tienda contesta …/-home_default/nombre.jpg si el producto no tiene portada y
…/REF-home_default/.jpg si no conoce la referencia. Ninguna es una imagen: no se
descarga y no se toca ni la imagen ni la URL guardada.
"""
import unittest
from unittest.mock import MagicMock, patch

from odoo.addons.nesto_sync.transformers.field_transformers import FieldTransformerRegistry

TIENDA = 'https://www.productosdeesteticaypeluqueriaprofesional.com'


class TestImagenSinFoto(unittest.TestCase):

    def _transformar(self, url):
        existente = MagicMock()
        existente.url_imagen_actual = f'{TIENDA}/95013-home_default/kit-ejemplo.jpg'
        with patch('requests.get') as descarga:
            valores = FieldTransformerRegistry.get('url_to_image').transform(
                url, {'existing_record': existente})
        return valores, descarga

    def test_sin_portada_no_descarga_ni_toca(self):
        valores, descarga = self._transformar(f'{TIENDA}/-home_default/kit-ejemplo.jpg')
        self.assertEqual(valores, {})
        descarga.assert_not_called()

    def test_referencia_desconocida_no_descarga_ni_toca(self):
        valores, descarga = self._transformar(f'{TIENDA}/84584-home_default/.jpg')
        self.assertEqual(valores, {})
        descarga.assert_not_called()

    def test_una_url_normal_si_se_descarga(self):
        _valores, descarga = self._transformar(f'{TIENDA}/95014-home_default/kit-ejemplo.jpg')
        descarga.assert_called_once()
