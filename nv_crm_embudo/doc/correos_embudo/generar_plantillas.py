"""Genera data/mail_template_embudo_data.xml a partir de los HTML de Marketing.

Uso (desde la raíz del repo, con cualquier Python 3):

    python nv_crm_embudo/doc/correos_embudo/generar_plantillas.py

Lee los HTML de esta carpeta y asuntos-y-preencabezados.md, y deja una plantilla
mail.template por correo. No importa nada de Odoo: solo transforma texto.

Lo que hace con cada HTML:
- quita <!doctype>, <head> y los comentarios; el <body> pasa a ser un <div> con su estilo;
- entidades HTML (&nbsp;, &zwnj;) a numéricas y etiquetas vacías cerradas, para que sea XML;
- [NOMBRE] y [NOMBRE DE LA VENDEDORA] a expresiones QWeb;
- las imágenes de assets/ a URL absoluta del servidor (/nv_crm_embudo/static/src/img/);
- de los dos cierres (FINAL A / FINAL B) deja uno solo con t-if / t-else, a todo el ancho;
- tras la firma, la posdata de la app (POSDATA_APP, igual en todos los correos);
- el aviso del pie se sustituye por el pie legal con el enlace de baja.

Además deja la plantilla interna embudo_aviso_respuesta (aviso a la vendedora con copias
cuando el lead contesta), que no sale de ningún HTML de Marketing.
"""
import html
import pathlib
import re
import sys
import xml.dom.minidom

AQUI = pathlib.Path(__file__).resolve().parent
MODULO = AQUI.parent.parent
SALIDA = MODULO / 'data' / 'mail_template_embudo_data.xml'

CORREOS = [
    # (xml_id, fichero, número en asuntos-y-preencabezados.md, nombre de la plantilla)
    ('embudo_correo_01', '01-acne-en-cabina.html', '01', 'Embudo leads 01 · Acné en cabina'),
    ('embudo_correo_02', '02-nad-pdrn-exosomas.html', '02', 'Embudo leads 02 · NAD, PDRN y exosomas'),
    ('embudo_correo_03', '03-microdermoabrasion-punta-diamante.html', '03',
     'Embudo leads 03 · Microdermoabrasión con punta de diamante'),
]

RUTA_IMG = '/nv_crm_embudo/static/src/img/'

CABECERA_QWEB = (
    '<t t-set="nv_img" t-value="object.get_base_url() + \'%s\'"/>'
    '<t t-set="nv_nombre" t-value="object.nv_nombre_saludo()"/>'
    '<t t-set="nv_ya_compra" t-value="object.nv_ya_compra()"/>'
    '<t t-set="nv_url_app" t-value="object.nv_url_app()"/>'
) % RUTA_IMG

# Posdata de la app (decisión de Carlos 05/11/26). De tú, como el cuerpo de Marketing. Va en los dos
# finales: todos los leads tienen ficha de cliente en la app. Solo Android: no hay enlace de iOS.
# Va tras la firma, con el mismo separador que «Responde a este correo…».
POSDATA_APP = '''<p style="margin:22px 0 0; padding-top:18px; border-top:1px solid #dddddd; font-size:14px; line-height:22px; color:#555555;"><strong style="color:#222222;">PD:</strong> Tienes los protocolos en vídeo de nuestras marcas en la app de Nueva Visión. Entra con tu correo y tu NIF, sin contraseña. Descárgala aquí: <a t-att-href="nv_url_app" target="_blank" style="color:#BD052B; font-weight:600; text-decoration:underline;">Android</a></p>'''

FIRMA_FIN = '<span style="color:#777777;">Nueva Visión</span></p>'
SALTO_PD = '\n' + ' ' * 14

# Mismo estilo que el aviso que sustituye (fondo #eeeeee, 11 px, centrado)
PIE_LEGAL = '''<td style="padding:20px 32px; background-color:#eeeeee; border-bottom:4px solid #BD052B;">
              <p style="margin:0 0 8px; font-size:11px; line-height:17px; color:#777777; text-align:center;">Recibes este correo porque dejaste tus datos a Nueva Visión para recibir información profesional. Si no quieres recibir más, puedes <a t-att-href="object.nv_url_baja()" target="_blank" style="color:#777777; text-decoration:underline;">darte de baja</a>.</p>
              <p style="margin:0; font-size:11px; line-height:17px; color:#777777; text-align:center;">Responsable: Nueva Visión, S.A. · CIF A78368255 · C/ Río Tiétar, 11, Polígono Industrial Los Nogales, 28119 Algete (Madrid). Puedes ejercer tus derechos de acceso, rectificación, supresión y oposición respondiendo a este correo.</p>
            </td>'''

AVISO_PIE = re.compile(
    r'<td[^>]*>\s*<p[^>]*>El enlace de baja y el pie legal se incorporan automáticamente desde Odoo\.</p>\s*</td>')

FINALES = re.compile(
    r'<!-- FINAL A[^>]*-->\s*<td[^>]*>(?P<a>.*?)</td>\s*<!-- FIN FINAL A -->\s*'
    r'<!-- FINAL B[^>]*-->\s*<td[^>]*>(?P<b>.*?)</td>\s*<!-- FIN FINAL B -->',
    re.S)

# Botón «Contacta con nosotros» (Laura, 06/11/26) bajo la invitación a responder
RESPONDE = ('<p style="margin:22px 0 18px; padding-top:20px; border-top:1px solid #dddddd; font-size:15px; '
            'line-height:24px; color:#333333;">Responde a este correo y cuéntame qué necesitas.</p>')
URL_CONTACTO = ('https://www.productosdeesteticaypeluqueriaprofesional.com/content/'
                '136-contacta-con-nueva-vision-distribuidor-de-estetica-y-peluqueria-profesional-en-madrid')
RESPONDE_CON_BOTON = (
    '<p style="margin:22px 0 14px; padding-top:20px; border-top:1px solid #dddddd; font-size:15px; '
    'line-height:24px; color:#333333;">Responde a este correo y cuéntame qué necesitas, o escríbenos desde la web:</p>\n'
    '              <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="border-collapse:separate; margin:0 0 24px;">\n'
    '                <tr>\n'
    '                  <td align="center" bgcolor="#BD052B" style="border-radius:3px;">\n'
    '                    <a href="%s" target="_blank" style="display:inline-block; padding:13px 24px; font-size:15px; '
    'line-height:20px; font-weight:600; color:#ffffff; text-decoration:none; border:1px solid #BD052B; '
    'border-radius:3px;">Contacta con nosotros</a>\n'
    '                  </td>\n'
    '                </tr>\n'
    '              </table>' % URL_CONTACTO)
TD_FINAL = '<td %s width="100%%" valign="top" style="width:100%%; padding:0;">%s</td>'


def asuntos():
    texto = (AQUI / 'asuntos-y-preencabezados.md').read_text(encoding='utf-8')
    resultado = {}
    for bloque in re.split(r'^## Correo ', texto, flags=re.M)[1:]:
        numero = bloque[:2]
        asunto = re.search(r'^- \*\*Asunto:\*\* (.+)$', bloque, re.M).group(1).strip()
        preencabezado = re.search(r'^- \*\*Preencabezado:\*\* (.+)$', bloque, re.M).group(1).strip()
        resultado[numero] = (asunto, preencabezado)
    return resultado


def una_vez(patron, sustituto, texto, que, flags=0):
    nuevo, veces = re.subn(patron, sustituto, texto, flags=flags)
    if veces != 1:
        sys.exit('%s: se esperaba 1 y hay %s' % (que, veces))
    return nuevo


def convertir(origen, preencabezado):
    fuente = origen.read_text(encoding='utf-8')
    if preencabezado not in fuente:
        sys.exit('%s: el preencabezado del .md no coincide con el del HTML' % origen.name)

    estilo_body = re.search(r'<body style="([^"]*)">', fuente).group(1)
    cuerpo = re.search(r'<body[^>]*>(.*)</body>', fuente, re.S).group(1)

    # Un solo cierre, a todo el ancho (las dos columnas eran para verlos juntos)
    finales = FINALES.search(cuerpo)
    if not finales:
        sys.exit('%s: no encuentro los dos cierres FINAL A / FINAL B' % origen.name)
    cuerpo = cuerpo[:finales.start()] + (
        TD_FINAL % ('t-if="not nv_ya_compra"', finales.group('a'))
        + '\n                  '
        + TD_FINAL % ('t-else=""', finales.group('b'))
    ) + cuerpo[finales.end():]

    cuerpo = una_vez(re.escape(FIRMA_FIN), lambda m: FIRMA_FIN + SALTO_PD + POSDATA_APP,
                     cuerpo, '%s: fin de la firma' % origen.name)
    cuerpo = una_vez(re.escape(RESPONDE), lambda m: RESPONDE_CON_BOTON, cuerpo,
                     '%s: invitación a responder' % origen.name)
    cuerpo = una_vez(AVISO_PIE.pattern, lambda m: PIE_LEGAL, cuerpo, '%s: aviso del pie' % origen.name)
    cuerpo = re.sub(r'<!--.*?-->\s*', '', cuerpo, flags=re.S)

    # Firma antes que el saludo: [NOMBRE] es prefijo de [NOMBRE DE LA VENDEDORA]
    cuerpo = una_vez(r'\[NOMBRE DE LA VENDEDORA\]',
                     '<t t-out="object.user_id.name or \'El equipo de Nueva Visión\'"/>',
                     cuerpo, '%s: firma' % origen.name)
    cuerpo = una_vez(r'Hola \[NOMBRE\],', 'Hola<t t-if="nv_nombre"> <t t-out="nv_nombre"/></t>,',
                     cuerpo, '%s: saludo' % origen.name)

    # Imágenes de assets/ a URL absoluta del servidor
    cuerpo = re.sub(r'\b(src|background)="assets/([^"]+)"', r't-attf-\1="{{ nv_img }}\2"', cuerpo)
    cuerpo = re.sub(r'\bstyle="([^"]*)url\(\'assets/([^\']+)\'\)([^"]*)"',
                    lambda m: 't-attf-style="%surl(\'{{ nv_img }}%s\')%s"' % m.groups(), cuerpo)

    # De HTML a XML
    cuerpo = cuerpo.replace('&nbsp;', '&#160;').replace('&zwnj;', '&#8204;')
    cuerpo = re.sub(r'<(img|br)\b([^>]*?)\s*/?>', r'<\1\2/>', cuerpo)

    for resto in ('[NOMBRE', 'assets/', 'FINAL A', 'FINAL B'):
        if resto in cuerpo:
            sys.exit('%s: queda «%s»' % (origen.name, resto))

    return '<div style="%s">%s%s</div>' % (estilo_body, CABECERA_QWEB, cuerpo.strip())


def registro(xml_id, nombre, asunto, cuerpo):
    return '''
    <record id="{xml_id}" model="mail.template">
        <field name="name">{nombre}</field>
        <field name="model_id" ref="crm.model_crm_lead"/>
        <field name="subject">{asunto}</field>
        <field name="email_from">{{{{ object.nv_email_from_embudo() }}}}</field>
        <!-- Sin reply_to: Odoo pone el alias del equipo del lead y la respuesta entra en el lead
             (ruta probada en #10/#26), que es lo que necesita la rama «ha contestado». -->
        <field name="email_to">{{{{ object.email_from }}}}</field>
        <field name="use_default_to" eval="False"/>
        <field name="nv_sin_contactos" eval="True"/>
        <field name="auto_delete" eval="False"/>
        <field name="lang">{{{{ object.lang_id.code or object.partner_id.lang }}}}</field>
        <field name="description">Correo del embudo de leads (Marketing). Un solo cierre: FINAL A si el lead no compra todavía, FINAL B si ya compra.</field>
        <field name="body_html" type="html">
{cuerpo}
        </field>
    </record>
'''.format(xml_id=xml_id, nombre=html.escape(nombre, quote=False), asunto=html.escape(asunto, quote=False),
           cuerpo=cuerpo)


AVISO_RESPUESTA = '''
    <!-- Aviso interno: el lead ha contestado a un correo del embudo. Lo manda
         crm.lead.nv_avisar_respuesta(), que llama el paso de acción de servidor de la
         rama «ha contestado» de automation_oca. Ver README. -->
    <record id="embudo_aviso_respuesta" model="mail.template">
        <field name="name">Embudo leads · Aviso a la vendedora: el lead ha contestado</field>
        <field name="model_id" ref="crm.model_crm_lead"/>
        <field name="subject">Ha contestado {{ object.contact_name or object.partner_name or object.email_from or object.name }} (embudo de leads)</field>
        <field name="email_from">{{ object.nv_email_from_embudo() }}</field>
        <field name="email_to">{{ object.user_id.email }}</field>
        <field name="email_cc">{{ object.nv_cc_aviso_respuesta() }}</field>
        <field name="use_default_to" eval="False"/>
        <field name="auto_delete" eval="True"/>
        <field name="description">Aviso interno a la vendedora (con copia a Dirección y, si es del equipo del jefe de equipo, a él) cuando un lead contesta a un correo del embudo.</field>
        <field name="body_html" type="html">
<div style="margin:0; padding:0; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:22px; color:#333333;">
    <p style="margin:0 0 12px;">Hola<t t-if="object.user_id"> <t t-out="object.user_id.name"/></t>,</p>
    <p style="margin:0 0 12px;"><strong><t t-out="object.contact_name or object.partner_name or object.email_from or object.name"/></strong> ha contestado a un correo del embudo de leads. Tienes una tarea en el lead para atenderle.</p>
    <t t-set="nv_respuesta" t-value="object.nv_ultima_respuesta()"/>
    <div t-if="nv_respuesta" style="margin:0 0 12px; padding:0 0 0 14px; border-left:3px solid #BD052B; color:#555555;"><t t-out="nv_respuesta.body"/></div>
    <p style="margin:0;"><a t-att-href="object.get_base_url() + '/web#model=crm.lead&amp;view_type=form&amp;id=%s' % object.id" target="_blank" style="color:#BD052B; font-weight:600;">Abrir el lead en Odoo</a></p>
</div>
        </field>
    </record>
'''


def main():
    datos = asuntos()
    registros = []
    for xml_id, fichero, numero, nombre in CORREOS:
        asunto, preencabezado = datos[numero]
        cuerpo = convertir(AQUI / fichero, preencabezado)
        registros.append(registro(xml_id, nombre, asunto, cuerpo))

    contenido = '''<?xml version="1.0" encoding="utf-8"?>
<!--
    GENERADO por doc/correos_embudo/generar_plantillas.py a partir de los HTML de Marketing
    (Laura Villacieros, 05/11/26). Para cambiar un texto: cambiar el HTML y volver a generar,
    o editar aquí y copiar el cambio al HTML. Lo que se cambie en la pantalla de Odoo se pierde
    al actualizar el módulo (noupdate="0").
-->
<odoo noupdate="0">%s%s</odoo>
''' % (''.join(registros), AVISO_RESPUESTA)
    xml.dom.minidom.parseString(contenido.encode('utf-8'))  # falla si no es XML bien formado
    SALIDA.write_text(contenido, encoding='utf-8', newline='\n')
    print('Escrito %s (%s bytes)' % (SALIDA, len(contenido.encode('utf-8'))))


if __name__ == '__main__':
    main()
