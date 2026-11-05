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
| Avance del lead con las fechas de compras de Nesto | `res.partner.write` → `crm.lead._nv_avanzar_por_fechas` | #9 |
| Plantillas de los correos 01-03 del embudo de leads (Marketing) | `data/mail_template_embudo_data.xml` | #10 |
| Aviso a la vendedora (con copias) cuando el lead contesta | plantilla `embudo_aviso_respuesta`, `crm.lead.nv_avisar_respuesta()` | #10 |

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

## Avance por las fechas de compras

Con las fechas que manda Nesto (`nesto_sync`, odoo-custom-addons#8) el embudo se mueve solo:

```
Nuevo → Calificado → Propuesta → Cliente en Nesto → Presupuesto → Ganado
                                 (enlace)          (FechaPrimer  (FechaPrimer
                                                    Presupuesto)  Pedido)
```

Cuando cambia `fecha_primer_presupuesto` o `fecha_primer_pedido` de un contacto, se revisan los leads abiertos del cliente:

- con **primer pedido**, `action_set_won()`;
- si no, con **primer presupuesto**, a la etapa «Presupuesto».

Detalles:

- **Nunca se retrocede de etapa.** Un lead que ya esté más avanzado se queda donde está, y un lead ganado o perdido no se toca.
- Se mira el **estado actual** del cliente, no qué campo ha cambiado, así que da igual el orden en que lleguen los mensajes y volver a llamar no hace daño.
- Las fechas son del cliente pero llegan en el mensaje de cada contacto, y Odoo no las propaga entre la empresa y sus contactos: se busca en **toda la familia** y se coge la más antigua.
- Al aceptar el único presupuesto de un cliente, Nesto manda `FechaPrimerPresupuesto` a `null`. El lead **no** vuelve atrás: se queda en «Presupuesto» hasta que llega `FechaPrimerPedido`.
- `fecha_ultimo_pedido` no mueve nada; es para segmentar clientes que llevan tiempo sin comprar.
- Cuando el enlace automático encuentra el lead de un cliente que ya traía fechas, el lead avanza en el acto.

**Ojo con la carga inicial de fechas** (NestoAPI#498, paso 3): al reenviar todos los clientes, los leads abiertos de clientes que ya han comprado pasarán a Ganado de golpe. Es lo que se busca, pero conviene avisar a las vendedoras antes.

Pasar a «Ganado» a mano sigue permitido; si se quiere impedir, es una decisión aparte (#9).

## Correos del embudo de leads

Tres plantillas `mail.template` sobre `crm.lead`, hechas con los HTML de Marketing (Laura Villacieros, 05/11/26):

| xml_id | Asunto | Guía que enlaza |
| --- | --- | --- |
| `nv_crm_embudo.embudo_correo_01` | Antes de tratar el acné, hay algo que conviene mirar | Acné en cabina |
| `nv_crm_embudo.embudo_correo_02` | NAD, PDRN y exosomas: no hacen lo mismo | NAD, PDRN y exosomas |
| `nv_crm_embudo.embudo_correo_03` | Microdermoabrasión: la potencia no se elige por costumbre | Microdermoabrasión con punta de diamante |

En Odoo: Ajustes › Técnico › Correo electrónico › Plantillas, buscando «Embudo leads».

### Qué rellena Odoo

| En el HTML de Marketing | En la plantilla |
| --- | --- |
| `[NOMBRE]` | `object.nv_nombre_saludo()`: la primera palabra del contacto del lead (o de su cliente, si es una persona); si viene en mayúsculas, «MARÍA» → «María». Si solo hay empresa, el nombre de la empresa entero; si no hay nada, «Hola,». |
| `[NOMBRE DE LA VENDEDORA]` | `object.user_id.name` (sin vendedora: «El equipo de Nueva Visión») |
| FINAL A / FINAL B | Uno solo, a todo el ancho: FINAL B si `object.nv_ya_compra()`, FINAL A si no |
| `assets/...` | `https://<web.base.url>/nv_crm_embudo/static/src/img/...` (las imágenes van en el módulo) |
| (nuevo, tras la firma) | Posdata de la app (en los dos finales): «PD: Tienes los protocolos en vídeo de nuestras marcas en la app de Nueva Visión. Entra con tu correo (si no tienes contraseña, pulsa «He olvidado mi contraseña»). Descárgala aquí: Android», con enlace a Google Play, con el enlace del parámetro `nv_crm_embudo.url_app`. La frase está en `POSDATA_APP` del generador, así que sale igual en los correos siguientes |
| Aviso del pie | Pie legal y enlace de baja firmado (`object.nv_url_baja()`) |
| Preencabezado | Ya venía en el HTML como `div` oculto al principio del cuerpo; se deja tal cual |

**FINAL B («ya compra»)** = el lead tiene cliente y en la familia de ese cliente (`commercial_partner_id` y sus contactos) hay `fecha_primer_pedido`. Es el mismo criterio que pasa el lead a Ganado (`_nv_fechas_cliente`). Un presupuesto no cuenta. Sin cliente, FINAL A.

**Remitente:** `Nueva Visión | <vendedora>` con la dirección del parámetro del sistema **`nv_crm_embudo.email_from_embudo`** (Ajustes › Técnico › Parámetros del sistema; hay que crearlo). Si no existe se usa `marketing@nuevavision.es`. Ojo: el servidor SMTP tiene `from_filter` (#26) y cualquier dirección que no encaje la reescribe Odoo a `mail.default.from`; se mantiene el nombre visible, pero la dirección que ve el cliente será la de `mail.default.from` hasta que se resuelva #26.

**Sin contactos basura:** las tres plantillas llevan la marca «No crear contactos al enviar en masa» (`nv_sin_contactos`). Sin ella, el envío masivo de Odoo (el que hace `automation_oca`) convierte el «Para» de cada lead en un `res.partner` con `find_or_create`: en el ensayo del 05/11/26 salieron 67 contactos nuevos, uno por email, y `nesto_sync` intentó publicarlos (no llegan a Nesto porque no tienen `cliente_externo`, pero se quedan en Odoo). Con la marca el correo sale a la dirección tal cual.

**Responder a:** las plantillas no llevan `reply_to`, así que Odoo pone el alias del equipo del lead (p. ej. `ventatelefonica@`). La respuesta entra en el lead por el fetchmail y de ahí sale la rama «ha contestado» de `automation_oca` (ruta probada en #10 y #26). No poner el correo de la vendedora: la respuesta no entraría en Odoo. **Para:** `object.email_from` del lead. `auto_delete` desactivado para que quede el correo enviado.

Las imágenes salen del servidor de Odoo (`web.base.url`), igual que el enlace de baja: tiene que ser una dirección `https://` pública y conviene tener `web.base.url.freeze` a `True` para que no la cambie un acceso interno.

### Aviso «el lead ha contestado»

Cuando el cliente responde, la rama «ha contestado» de `automation_oca` (disparador «respuesta al correo») hace dos cosas:

1. **Tarea a la vendedora** (paso de tipo actividad, el que ya existe en la configuración de #10). Odoo manda el correo «Se le ha asignado…» solo si la vendedora tiene en sus preferencias **Notificación = «Gestionar por correo»** (`res.users.notification_type = 'email'`). Con «Gestionar en Odoo» (`inbox`) solo le sale en el Inbox de Odoo. **Hay que ponérselo en «Correo» a todas las vendedoras del embudo.**
2. **Aviso con copias** (paso nuevo, de tipo acción de servidor): una acción de servidor sobre `crm.lead` con el código

   ```
   records.nv_avisar_respuesta()
   ```

   Manda la plantilla `embudo_aviso_respuesta` («Embudo leads · Aviso a la vendedora…») a la vendedora, con copia a Dirección y, si la vendedora es del equipo del jefe de equipo (Alberto Sancho), también a él. Lleva el texto de la respuesta y el enlace al lead. Si la vendedora no tiene email no se manda nada (queda en el log).

   Se hace con un método y no con un paso de correo porque un paso de correo de `automation_oca` es un envío masivo: respeta la lista negra del lead y lo cuenta como correo del embudo. El aviso es interno y tiene que salir siempre.

**«Del equipo del jefe»** = el equipo de ventas (`crm.team`) del lead o cualquiera de los equipos de los que es miembro la vendedora es el del parámetro `nv_crm_embudo.equipo_jefe_equipo` (su id o su nombre exacto, sin distinguir mayúsculas).

En la configuración de Automation: en la rama del paso «Ha contestado» (disparador respuesta al correo, el mismo padre que la tarea), añadir un paso de tipo **acción de servidor** con esa acción. Va junto a la tarea, sin espera.

### Parámetros del sistema

Ajustes › Técnico › Parámetros del sistema. Hay que crearlos; los que tienen valor por defecto funcionan sin crearlos.

| Clave | Para qué | Por defecto |
| --- | --- | --- |
| `nv_crm_embudo.email_from_embudo` | Dirección de envío de los correos del embudo | `marketing@nuevavision.es` |
| `nv_crm_embudo.url_app` | Enlace de la posdata de la app (Google Play; no hay enlace de iOS en los repos, así que solo va Android) | `https://play.google.com/store/apps/details?id=com.nuevavision.nestotiendas&referrer=utm_source%3Dembudo%26utm_medium%3Dcorreo%26utm_campaign%3Dembudo_leads` |
| `nv_crm_embudo.cc_direccion` | Copia del aviso de respuesta a Dirección (varias, separadas por comas) | (vacío: sin copia) |
| `nv_crm_embudo.cc_jefe_equipo` | Copia del aviso al jefe de equipo (Alberto Sancho) | (vacío: sin copia) |
| `nv_crm_embudo.equipo_jefe_equipo` | Id o nombre del `crm.team` del jefe de equipo | (vacío: nadie es de su equipo) |

Si una copia coincide con el correo de la vendedora, no se repite.

### Dónde cambiar los textos

Los HTML originales y los asuntos están en `doc/correos_embudo/`. El XML se genera con:

```
python nv_crm_embudo/doc/correos_embudo/generar_plantillas.py
```

Para un cambio de texto: cambiar el HTML (o `asuntos-y-preencabezados.md` para el asunto), volver a generar y actualizar el módulo. Las plantillas van con `noupdate="0"`: **lo que se cambie en la pantalla de Odoo se pierde al actualizar el módulo**. Para probar un asunto alternativo (A/B) desde la pantalla, mejor duplicar la plantilla.

### Cómo probarlas

1. Actualizar el módulo y crear los parámetros del sistema (tabla de arriba).
2. Crear un lead de pruebas con el email de una vendedora como `email_from`, un nombre de contacto y una vendedora asignada.
3. En el lead, «Enviar mensaje» › icono de plantilla › «Embudo leads 01». Revisar nombre, firma, imágenes y que solo sale un cierre (FINAL A).
4. Ponerle al lead un cliente con `fecha_primer_pedido` y repetir: tiene que salir el FINAL B.
5. Aviso: responder desde la cuenta del lead de pruebas a uno de esos correos y, cuando entre en el lead, ejecutar la acción de servidor a mano sobre él (o dejar que la lance la rama «ha contestado»). Tiene que llegar el aviso a la vendedora con las copias.

Al enviar desde el chatter, Odoo pasa el cuerpo por el sanitizador y lo envuelve en su maqueta de notificación; el correo que manda `automation_oca` (envío masivo) sale tal cual. Lo que cuenta es lo que llega por el embudo.

### En la secuencia de `automation_oca`

Son tres pasos de tipo correo, uno tras otro, con 30 días entre ellos. Se añaden en la configuración de Automation (la del embudo exportada en #10 se importa desde la vista kanban de Automation y queda en borrador):

1. Paso «Correo 01»: tipo correo, plantilla «Embudo leads 01», al empezar (o tras el paso de entrada que corresponda).
2. Paso «Correo 02»: tipo correo, plantilla «Embudo leads 02», hijo del paso 01, 30 días después.
3. Paso «Correo 03»: tipo correo, plantilla «Embudo leads 03», hijo del paso 02, 30 días después.

Y en la rama «ha contestado», junto a la tarea, el paso de acción de servidor del aviso (ver arriba).

Antes de activar la configuración, exportarla de nuevo para guardar la versión con los tres pasos.

## Instalación

Depende de `crm`, `mail` y `nesto_sync`. Los embudos usan `automation_oca` (OCA/automation 16.0), pero este módulo no lo necesita.

Instalar desde una carpeta que el usuario `odoo` pueda leer. Desde `/root` falla la generación de la descripción del módulo (`PermissionError: html4css1.css`).

## Tests

```
odoo -c <conf> -d <bd> -u nv_crm_embudo --test-enable --test-tags /nv_crm_embudo --stop-after-init
```

Las plantillas del embudo se prueban en `tests/test_plantillas_embudo.py` (un solo cierre, nombre, firma, baja, remitente).
