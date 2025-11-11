#!/usr/bin/env python3
"""
Script de prueba para verificar sincronización bidireccional

Uso:
    python3 test_bidirectional.py
"""

import sys
import os

# Añadir Odoo al path
sys.path.insert(0, '/opt/odoo16')
os.environ['ODOO_RC'] = '/opt/odoo16/odoo.conf'

import odoo
from odoo import api, SUPERUSER_ID

def test_bidirectional_sync():
    """Test de sincronización bidireccional"""

    # Inicializar Odoo
    odoo.tools.config.parse_config(['-c', '/opt/odoo16/odoo.conf'])

    with odoo.registry('odoo16').cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})

        print("=" * 60)
        print("TEST DE SINCRONIZACIÓN BIDIRECCIONAL")
        print("=" * 60)

        # 1. Buscar un cliente de prueba
        partner = env['res.partner'].search([
            ('cliente_externo', '!=', False),
            ('contacto_externo', '!=', False)
        ], limit=1)

        if not partner:
            print("\n❌ No se encontró ningún cliente con cliente_externo y contacto_externo")
            print("   Crea un cliente primero desde Nesto para poder probar")
            return

        print(f"\n✅ Cliente encontrado:")
        print(f"   ID: {partner.id}")
        print(f"   Nombre: {partner.name}")
        print(f"   Cliente externo: {partner.cliente_externo}")
        print(f"   Contacto externo: {partner.contacto_externo}")
        print(f"   Teléfono actual: {partner.mobile}")

        # 2. Verificar que el mixin está activo
        if 'bidirectional.sync.mixin' not in partner._inherits and \
           'bidirectional.sync.mixin' not in partner._inherit:
            print("\n❌ ERROR: BidirectionalSyncMixin NO está heredado en res.partner")
            print(f"   _inherit actual: {partner._inherit}")
            return

        print("\n✅ BidirectionalSyncMixin está heredado correctamente")

        # 3. Verificar configuración de entidad
        from nesto_sync.config.entity_configs import get_entity_config

        try:
            config = get_entity_config('cliente')
            bidirectional = config.get('bidirectional', False)

            print(f"\n✅ Configuración de entidad encontrada:")
            print(f"   bidirectional: {bidirectional}")
            print(f"   pubsub_topic: {config.get('pubsub_topic', 'N/A')}")
            print(f"   nesto_table: {config.get('nesto_table', 'N/A')}")

            if not bidirectional:
                print("\n❌ ERROR: bidirectional=False en entity_configs.py")
                print("   Cambia 'bidirectional': True en la configuración de 'cliente'")
                return

        except Exception as e:
            print(f"\n❌ ERROR al obtener configuración: {e}")
            return

        # 4. Verificar credenciales Google Cloud
        import os
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

        if creds_path:
            print(f"\n✅ Variable de entorno GOOGLE_APPLICATION_CREDENTIALS configurada:")
            print(f"   Ruta: {creds_path}")

            if os.path.exists(creds_path):
                print(f"   ✅ Archivo existe")
            else:
                print(f"   ❌ Archivo NO existe")
                return
        else:
            print("\n⚠️  Variable GOOGLE_APPLICATION_CREDENTIALS no configurada")
            print("   Intentando con System Parameters de Odoo...")

            project_id = env['ir.config_parameter'].sudo().get_param('nesto_sync.google_project_id')
            creds_path = env['ir.config_parameter'].sudo().get_param('nesto_sync.google_credentials_path')

            if project_id and creds_path:
                print(f"   ✅ System Parameters configurados:")
                print(f"      Project ID: {project_id}")
                print(f"      Credentials: {creds_path}")
            else:
                print("   ❌ System Parameters NO configurados")
                print("   Configura las credenciales de Google Cloud")
                return

        # 5. Probar actualización
        print("\n" + "=" * 60)
        print("PRUEBA DE ACTUALIZACIÓN")
        print("=" * 60)

        import random
        nuevo_telefono = f"666{random.randint(100000, 999999)}"

        print(f"\n📝 Actualizando teléfono a: {nuevo_telefono}")

        try:
            # Esto debería triggerar el BidirectionalSyncMixin
            partner.write({'mobile': nuevo_telefono})
            cr.commit()

            print(f"\n✅ Actualización exitosa")
            print(f"   Teléfono nuevo: {partner.mobile}")

            print("\n" + "=" * 60)
            print("VERIFICACIÓN DE LOGS")
            print("=" * 60)
            print("\nAhora verifica los logs con:")
            print("  sudo journalctl -u odoo16 --since '1 minute ago' | grep -E '(BidirectionalSyncMixin|OdooPublisher|PublisherFactory)'")

            print("\nSi ves:")
            print("  - 'Sincronizando X registros' → El mixin se ejecutó")
            print("  - 'ModuleNotFoundError: google' → Falta instalar google-cloud-pubsub")
            print("  - 'PermissionDenied' → Problema con credenciales")
            print("  - 'Sin cambios' → El anti-bucle está funcionando (ok si ejecutas 2 veces)")

        except Exception as e:
            print(f"\n❌ ERROR al actualizar: {e}")
            import traceback
            traceback.print_exc()
            return

if __name__ == '__main__':
    test_bidirectional_sync()
