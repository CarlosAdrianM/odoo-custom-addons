# Configuración de Credenciales Google Cloud (SEGURA)

**IMPORTANTE**: Este archivo documenta cómo configurar credenciales. **NUNCA** incluyas las credenciales reales en este repositorio.

## Método Recomendado: Variables de Entorno

### 1. Obtener el archivo de credenciales

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto
3. Ve a **IAM & Admin → Service Accounts**
4. Encuentra tu cuenta de servicio (o crea una nueva)
5. **Keys → Add Key → Create New Key → JSON**
6. Descarga el archivo JSON

### 2. Colocar credenciales en el servidor

```bash
# Crear directorio seguro (fuera del repositorio git)
sudo mkdir -p /opt/odoo16/secrets
sudo chmod 700 /opt/odoo16/secrets

# Copiar archivo de credenciales
sudo cp ~/google-cloud-credentials.json /opt/odoo16/secrets/
sudo chmod 600 /opt/odoo16/secrets/google-cloud-credentials.json
sudo chown odoo16:odoo16 /opt/odoo16/secrets/google-cloud-credentials.json

# Eliminar archivo temporal
rm ~/google-cloud-credentials.json
```

### 3. Configurar variable de entorno

Edita el archivo de servicio systemd:

```bash
sudo systemctl edit odoo16 --full
```

Añade en la sección `[Service]`:

```ini
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/odoo16/secrets/google-cloud-credentials.json"
```

Guarda y reinicia:

```bash
sudo systemctl daemon-reload
sudo systemctl restart odoo16
```

### 4. Verificar configuración

```bash
# Verificar que la variable está disponible
sudo systemctl show odoo16 | grep GOOGLE_APPLICATION_CREDENTIALS

# Verificar logs de Odoo
sudo journalctl -u odoo16 -f
```

## Método Alternativo: System Parameters de Odoo

Si prefieres configurar desde la UI de Odoo:

1. **Colocar credenciales** (igual que paso 2 anterior)

2. **Configurar en Odoo UI:**
   - Settings → Technical → Parameters → System Parameters
   - Crear parámetros:
     - `nesto_sync.google_project_id` = `tu-proyecto-id`
     - `nesto_sync.google_credentials_path` = `/opt/odoo16/secrets/google-cloud-credentials.json`

3. **Reiniciar Odoo**

## Verificación de Seguridad

### ✅ Checklist

- [ ] Credenciales están en `/opt/odoo16/secrets/` (fuera de custom_addons)
- [ ] Permisos del archivo: 600 (solo lectura para owner)
- [ ] Permisos del directorio: 700 (solo acceso para owner)
- [ ] Owner correcto: `odoo16:odoo16`
- [ ] `.gitignore` bloquea `*.json`, `*credentials*`, `secrets/`
- [ ] Variable de entorno configurada en systemd
- [ ] Servicio Odoo reiniciado

### ❌ NUNCA hacer esto

```bash
# ❌ NO copiar credenciales dentro del repositorio
cp credentials.json /opt/odoo16/custom_addons/nesto_sync/

# ❌ NO commitear archivos JSON
git add *.json

# ❌ NO hardcodear credenciales en código
credentials = {"type": "service_account", ...}  # ¡NO!
```

## Troubleshooting

### Error: "Could not load credentials"

```bash
# Verificar que el archivo existe
ls -la /opt/odoo16/secrets/google-cloud-credentials.json

# Verificar permisos
sudo -u odoo16 cat /opt/odoo16/secrets/google-cloud-credentials.json

# Verificar logs de Odoo
sudo journalctl -u odoo16 -n 100 | grep -i google
```

### Error: "Permission denied"

```bash
# Arreglar permisos
sudo chown odoo16:odoo16 /opt/odoo16/secrets/google-cloud-credentials.json
sudo chmod 600 /opt/odoo16/secrets/google-cloud-credentials.json
```

## Estructura del archivo de credenciales

Tu archivo `google-cloud-credentials.json` debe tener esta estructura:

```json
{
  "type": "service_account",
  "project_id": "tu-proyecto-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "...",
  "client_x509_cert_url": "..."
}
```

## Rotación de Credenciales

Para rotar credenciales periódicamente (buena práctica de seguridad):

1. Crear nueva key en Google Cloud Console
2. Descargar nueva credencial
3. Copiar a `/opt/odoo16/secrets/google-cloud-credentials-new.json`
4. Actualizar variable de entorno a `-new.json`
5. Reiniciar Odoo
6. Verificar que funciona
7. Eliminar credencial antigua
8. Revocar key antigua en Google Cloud Console

---

**Fecha última actualización**: 2025-11-10
**Responsable**: Equipo de desarrollo
