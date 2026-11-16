# NV CRM Embudo · envíos fiables con automation_oca

Módulo puente entre `nv_crm_embudo` y `automation_oca` (se instala solo si están los dos).
`nv_crm_embudo` sigue funcionando sin automation_oca; lo que necesita heredar sus modelos vive aquí.

## Por qué

El 12-13/11/2026 Office 365 iba lento y cortaba conexiones. La tarea «Automation: Execute
scheduled activities» manda los correos dentro de su propia ejecución (envío masivo con
`auto_commit`) y Odoo la cortó 169 veces por pasar de 120 s. En el bloque NV-2026-11-04:

- **12 clientes no recibieron el correo 01**, pero su paso quedó como «enviado»: automation_oca
  marca `mail_status = sent` al crear el correo, no cuando sale. Nadie lo reintentaba y el
  correo 02 les iba a llegar sin el 01.
- **6 clientes lo recibieron dos veces**: el correo ya había salido (y estaba guardado) cuando
  se cortó la tarea; el paso volvió a «programado» y en la siguiente pasada se mandó otra vez.
- La recomendación de ritmo contó 19 correos fallidos y no subió a 75.

## Qué hace

1. **No repite un correo** (`automation.record.step._run_mail`): si el paso ya tiene un correo
   en cola o enviado, no crea otro. Si solo tiene intentos fallidos, los anula y manda uno nuevo.
2. **Reintenta los fallos pasajeros** (tarea «CRM: reintentar correos fallidos del embudo»,
   cada 10 min): correos del embudo en error por conexión cortada, códigos 4xx o «temporary»;
   hasta 3 veces, con 20 min entre intentos, y solo si tienen menos de 2 días. Los fallos del
   destinatario (5.1.x, correo no válido, lista negra) no se reintentan. Un intento fallido de
   un paso que ya tiene el correo enviado se anula.
3. **No sigue la secuencia con quien no recibió el correo anterior**
   (`_check_to_execute`): si el correo del paso padre acabó en error, el siguiente se rechaza.
   Si no hay correo guardado (borrado automático, pruebas) todo sigue como siempre.

## Despliegue

Módulo nuevo: hay que instalarlo, no basta con reiniciar.

```
/opt/odoo/backup/backup_odoo.sh --completo
cd /opt/odoo/custom_addons && git pull
systemctl stop odoo
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -i nv_crm_embudo_automation --stop-after-init
systemctl start odoo
```

Las pruebas no corren en el CI (no instala automation_oca). En la copia:
`odoo -c /opt/odoo/pruebas/odoo_pruebas.conf --http-port=8079 -u nv_crm_embudo_automation --test-tags /nv_crm_embudo_automation --stop-after-init`.
