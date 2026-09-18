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

Cada 10 minutos se revisan los clientes principales de Nesto (`cliente_externo` y sin padre) que todavía no se han mirado, dejando un margen de 2 minutos para no adelantarse a una sincronización en curso.

Se comparan email y teléfono (últimos 9 dígitos) del cliente y de sus personas de contacto con los leads abiertos que no tienen cliente de Nesto:

- **Un solo lead:** se enlaza (`partner_id`) y pasa a «Cliente en Nesto». En el lead queda una nota con los datos que tenía antes, incluido el cliente anterior si lo tenía.
- **Varios leads:** cada uno recibe una tarea para su vendedora (la del lead o, si no tiene, la del cliente; si ninguna está activa no se crea la tarea y se avisa por log).
- **Ningún lead:** no se hace nada.

Solo se miran oportunidades; los leads sin convertir no entran.

### Cuándo se da un cliente por revisado

El control es el campo `nv_lead_revisado` de `res.partner`, no un marcador de «último id visto». Hace falta porque **Nesto manda un mensaje por contacto y el cliente principal llega el primero**: el email suele venir en la persona de contacto, que puede tardar. Mientras el cliente no tenga 24 horas (`HORAS_REINTENTO`) se vuelve a mirar en cada pasada; después se marca aunque no haya salido nada. Un cliente que falle tampoco se marca, así que se reintenta solo.

Al instalar el módulo, el `post_init_hook` marca como revisados todos los contactos que ya existían: solo se buscan leads para los clientes creados a partir de la instalación.

Para forzar que se vuelva a mirar un cliente, poner su `nv_lead_revisado` a `False`.

Los emails `@nuevavision.es` se ignoran.

Va separado de `nesto_sync` a propósito: un fallo aquí no afecta a los mensajes de Nesto. La ficha del cliente no se modifica, así que no se publica nada hacia Nesto (la marca `nv_lead_revisado` se escribe con `skip_sync=True`).

## Instalación

Depende de `crm`, `mail` y `nesto_sync`. Los embudos usan `automation_oca` (OCA/automation 16.0), pero este módulo no lo necesita.

Instalar desde una carpeta que el usuario `odoo` pueda leer. Desde `/root` falla la generación de la descripción del módulo (`PermissionError: html4css1.css`).

## Tests

```
odoo -c <conf> -d <bd> -u nv_crm_embudo --test-enable --test-tags /nv_crm_embudo --stop-after-init
```
