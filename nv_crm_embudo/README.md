# NV CRM Embudo

Personalizaciones del CRM de Nueva Visión para los embudos automáticos (Odoo 16).

## Qué hace

| Pieza | Dónde | Issue |
| --- | --- | --- |
| Enlace de baja firmado para los correos de los embudos, con página de confirmación y alta en la lista negra | `object.nv_url_baja()` en las plantillas y ruta `/nv/baja/<lead>/<token>` | #10 |
| Vista «Leads vivos por vendedora» | CRM › Ventas | #10 |
| Webhook de bajas de Mailchimp (eventos `unsubscribe` y `cleaned`) | `/nv/mailchimp/<secreto>`, parámetro `nv_crm_embudo.mailchimp_secreto` | #10 |
| Etapas «Cliente en Nesto» y «Presupuesto» | `data/crm_stage_data.xml` | #9 |
| Enlace automático del lead con el cliente nuevo de Nesto | Tarea programada cada 10 min, `crm.lead._nv_cron_enlazar_clientes_nesto` | #9 |

## Enlace automático con Nesto

Cada 10 minutos se revisan los clientes principales (`cliente_externo` y sin padre) creados desde la última pasada. El punto de partida se guarda en el parámetro `nv_crm_embudo.ultimo_cliente_nesto_revisado`; en la primera ejecución solo se fija el punto de partida.

Se deja un margen de 2 minutos para no adelantarse a una sincronización que aún no ha terminado.

Se comparan email y teléfono (últimos 9 dígitos) del cliente y de sus personas de contacto con los leads abiertos que no tienen cliente de Nesto:

- **Un solo lead:** se enlaza (`partner_id`) y pasa a «Cliente en Nesto». En el lead queda una nota con los datos que tenía antes.
- **Varios leads:** cada uno recibe una tarea para su vendedora.
- **Ningún lead:** no se hace nada.

Los emails `@nuevavision.es` se ignoran.

Va separado de `nesto_sync` a propósito: un fallo aquí no afecta a los mensajes de Nesto. La ficha del cliente no se modifica, así que no se publica nada hacia Nesto.

## Instalación

Depende de `crm`, `mail` y `nesto_sync`. Los embudos usan `automation_oca` (OCA/automation 16.0), pero este módulo no lo necesita.

Instalar desde una carpeta que el usuario `odoo` pueda leer. Desde `/root` falla la generación de la descripción del módulo (`PermissionError: html4css1.css`).

## Tests

```
odoo -c <conf> -d <bd> -u nv_crm_embudo --test-enable --test-tags /nv_crm_embudo --stop-after-init
```
