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
- el aviso del pie se sustituye por el pie legal con el enlace de baja.
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
) % RUTA_IMG

# Mismo estilo que el aviso que sustituye (fondo #eeeeee, 11 px, centrado)
PIE_LEGAL = '''<td style="padding:20px 32px; background-color:#eeeeee; border-bottom:4px solid #BD052B;">
              <p style="margin:0 0 8px; font-size:11px; line-height:17px; color:#777777; text-align:center;">Recibe este correo porque dejó sus datos a Nueva Visión para recibir información profesional. Si no quiere recibir más, puede <a t-att-href="object.nv_url_baja()" target="_blank" style="color:#777777; text-decoration:underline;">darse de baja</a>.</p>
              <p style="margin:0; font-size:11px; line-height:17px; color:#777777; text-align:center;">Responsable: Nueva Visión, S.A. · CIF A78368255 · C/ Río Tiétar, 11, Polígono Industrial Los Nogales, 28119 Algete (Madrid). Puede ejercer sus derechos de acceso, rectificación, supresión y oposición respondiendo a este correo.</p>
            </td>'''

AVISO_PIE = re.compile(
    r'<td[^>]*>\s*<p[^>]*>El enlace de baja y el pie legal se incorporan automáticamente desde Odoo\.</p>\s*</td>')

FINALES = re.compile(
    r'<!-- FINAL A[^>]*-->\s*<td[^>]*>(?P<a>.*?)</td>\s*<!-- FIN FINAL A -->\s*'
    r'<!-- FINAL B[^>]*-->\s*<td[^>]*>(?P<b>.*?)</td>\s*<!-- FIN FINAL B -->',
    re.S)

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
        <field name="reply_to">{{{{ object.user_id.email }}}}</field>
        <field name="email_to">{{{{ object.email_from }}}}</field>
        <field name="use_default_to" eval="False"/>
        <field name="auto_delete" eval="False"/>
        <field name="lang">{{{{ object.lang_id.code or object.partner_id.lang }}}}</field>
        <field name="description">Correo del embudo de leads (Marketing). Un solo cierre: FINAL A si el lead no compra todavía, FINAL B si ya compra.</field>
        <field name="body_html" type="html">
{cuerpo}
        </field>
    </record>
'''.format(xml_id=xml_id, nombre=html.escape(nombre, quote=False), asunto=html.escape(asunto, quote=False),
           cuerpo=cuerpo)


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
<odoo noupdate="0">%s</odoo>
''' % ''.join(registros)
    xml.dom.minidom.parseString(contenido.encode('utf-8'))  # falla si no es XML bien formado
    SALIDA.write_text(contenido, encoding='utf-8', newline='\n')
    print('Escrito %s (%s bytes)' % (SALIDA, len(contenido.encode('utf-8'))))


if __name__ == '__main__':
    main()
