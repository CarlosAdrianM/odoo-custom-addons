#!/bin/bash
# Script para probar cambio de teléfono del cliente 15191
# Simula lo que hace la UI cuando cambias un campo y guardas

echo "============================================================"
echo "TEST: Cambiar teléfono del cliente 15191 via Odoo Shell"
echo "============================================================"
echo ""

echo "📋 Instrucciones:"
echo "   1. Este script ejecutará el shell de Odoo"
echo "   2. Buscará el cliente con cliente_externo='15191'"
echo "   3. Cambiará su teléfono móvil"
echo "   4. Guardará los cambios (esto dispara el mixin)"
echo ""
echo "📝 Logs esperados (en otra terminal ejecuta):"
echo "   sudo journalctl -u odoo16 -f | grep -E '⭐|🔔|Publicando'"
echo ""
echo "⏳ Presiona ENTER para continuar..."
read

echo ""
echo "🚀 Ejecutando Odoo Shell..."
echo ""

/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo-bin shell \
  -c /opt/odoo16/odoo.conf \
  -d odoo16 \
  --no-http << 'PYTHON_CODE'

import logging
_logger = logging.getLogger(__name__)

print("=" * 60)
print("Buscando cliente con cliente_externo = '15191'...")
print("=" * 60)

# Buscar el cliente (Parent)
partner = env['res.partner'].search([
    ('cliente_externo', '=', '15191'),
    ('parent_id', '=', False)
], limit=1)

if not partner:
    print("❌ ERROR: Cliente no encontrado")
    exit()

print(f"✅ Cliente encontrado:")
print(f"   ID: {partner.id}")
print(f"   Nombre: {partner.name}")
print(f"   NIF: {partner.vat}")
print(f"   cliente_externo: {partner.cliente_externo}")
print(f"   contacto_externo: {partner.contacto_externo}")
print(f"   parent_id: {partner.parent_id.id if partner.parent_id else 'NULL (es Parent)'}")
print(f"   Teléfono móvil actual: '{partner.mobile or ''}'")
print("")

# Determinar nuevo teléfono
if partner.mobile == '666TEST999':
    nuevo_telefono = '666TEST888'
else:
    nuevo_telefono = '666TEST999'

print(f"🔄 Cambiando teléfono móvil a: '{nuevo_telefono}'")
print("")
print("📋 Logs esperados:")
print("   ⭐ ResPartner.write() llamado con vals: {'mobile': '...'}")
print("   🔔 BidirectionalSyncMixin.write() llamado")
print("   Creando publisher para proveedor: google_pubsub")
print("   Publicando cliente desde Odoo")
print("")
print("⏳ Ejecutando write()...")
print("-" * 60)

try:
    # Este write() debe disparar:
    # 1. ResPartner.write() (con ⭐)
    # 2. BidirectionalSyncMixin.write() (con 🔔)
    # 3. OdooPublisher.publish_record()
    partner.write({'mobile': nuevo_telefono})
    env.cr.commit()

    print("-" * 60)
    print("")
    print(f"✅ write() ejecutado correctamente")
    print(f"   Nuevo valor: '{partner.mobile}'")
    print("")
    print("📝 Verifica los logs en la otra terminal")
    print("   Deben aparecer ⭐ y 🔔")

except Exception as e:
    print("-" * 60)
    print("")
    print(f"❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

print("")
print("=" * 60)
print("TEST COMPLETADO")
print("=" * 60)

PYTHON_CODE

echo ""
echo "✅ Script completado"
echo ""
echo "Revisa los logs para ver si se publicó el mensaje:"
echo "  sudo journalctl -u odoo16 --since '1 minute ago' | grep -E '⭐|🔔|Publicando|google'"
echo ""
