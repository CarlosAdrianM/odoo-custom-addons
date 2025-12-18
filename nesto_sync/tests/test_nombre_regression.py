"""
Tests de Regresión Críticos - Protección de Nombres

CONTEXTO DEL BUG:
Al modificar una persona de contacto, el nombre de esa persona se propagaba
incorrectamente al cliente principal, sobrescribiendo el nombre fiscal del cliente.
Este es un error grave porque el nombre fiscal no se puede recuperar fácilmente.

ESTOS TESTS GARANTIZAN QUE:
1. El nombre del cliente principal SOLO se modifica cuando se sincroniza el cliente principal
2. El nombre de una dirección de entrega SOLO se modifica cuando se sincroniza esa dirección
3. El nombre de una persona de contacto SOLO se modifica cuando se sincroniza esa persona
4. NUNCA se propaga un nombre de una entidad a otra

La estructura jerárquica en Odoo es:
- Cliente Principal (is_company=True, type='invoice', parent_id=None)
  - Dirección de entrega 1 (is_company=False, type='delivery', parent_id=cliente)
  - Dirección de entrega 2 (is_company=False, type='delivery', parent_id=cliente)
  - Persona de contacto 1 (type='contact', parent_id=cliente, persona_contacto_externa=1)
  - Persona de contacto 2 (type='contact', parent_id=cliente, persona_contacto_externa=2)
"""

import json
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.addons.nesto_sync.core.entity_registry import EntityRegistry


@tagged('post_install', '-at_install', 'nesto_sync', 'regression')
class TestNombreNoSePropaga(TransactionCase):
    """
    Tests críticos para verificar que los nombres NO se propagan entre entidades.

    Cada test simula un escenario real donde antes del fix, el nombre se
    propagaba incorrectamente.
    """

    def setUp(self):
        super().setUp()
        self.registry = EntityRegistry()

        # Crear estructura completa: Cliente + Direcciones + Personas de contacto
        self.cliente_principal = self.env['res.partner'].create({
            'name': 'EMPRESA FISCAL S.L.',  # Nombre fiscal - NO debe cambiar
            'cliente_externo': 'REGR001',
            'contacto_externo': '0',  # Cliente principal
            'is_company': True,
            'type': 'invoice',
            'vat': 'B12345678',
            'street': 'Calle Fiscal 1',
            'city': 'Madrid',
        })

        self.direccion_entrega_1 = self.env['res.partner'].create({
            'name': 'Almacén Norte',  # Nombre dirección - NO debe cambiar por persona
            'cliente_externo': 'REGR001',
            'contacto_externo': '1',  # Dirección de entrega 1
            'is_company': False,
            'type': 'delivery',
            'parent_id': self.cliente_principal.id,
            'street': 'Calle Almacén 1',
        })

        self.direccion_entrega_2 = self.env['res.partner'].create({
            'name': 'Almacén Sur',  # Nombre dirección - NO debe cambiar por persona
            'cliente_externo': 'REGR001',
            'contacto_externo': '2',  # Dirección de entrega 2
            'is_company': False,
            'type': 'delivery',
            'parent_id': self.cliente_principal.id,
            'street': 'Calle Almacén 2',
        })

        self.persona_contacto_1 = self.env['res.partner'].create({
            'name': 'Juan Pérez',
            'cliente_externo': 'REGR001',
            'contacto_externo': '0',
            'persona_contacto_externa': '1',  # Persona de contacto 1
            'type': 'contact',
            'parent_id': self.cliente_principal.id,
            'email': 'juan@empresa.com',
        })

        self.persona_contacto_2 = self.env['res.partner'].create({
            'name': 'María García',
            'cliente_externo': 'REGR001',
            'contacto_externo': '0',
            'persona_contacto_externa': '2',  # Persona de contacto 2
            'type': 'contact',
            'parent_id': self.cliente_principal.id,
            'email': 'maria@empresa.com',
        })

    def test_modificar_persona_contacto_no_cambia_nombre_cliente(self):
        """
        REGRESIÓN CRÍTICA: Modificar persona de contacto NO debe cambiar nombre del cliente.

        Este es el bug que ocurrió:
        1. Usuario modifica PersonaContacto 1 en Nesto, cambiando nombre a "Juan Actualizado"
        2. Nesto envía mensaje con PersonasContacto actualizada
        3. Odoo procesaba incorrectamente y ponía "Juan Actualizado" en el cliente principal
        4. El nombre fiscal "EMPRESA FISCAL S.L." se perdía

        Este test verifica que eso NUNCA vuelva a pasar.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        # Mensaje que actualiza SOLO la persona de contacto 1
        mensaje_actualiza_persona = {
            "Cliente": "REGR001",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "EMPRESA FISCAL S.L.",  # Nombre cliente NO cambia
            "Direccion": "Calle Fiscal 1",
            "Poblacion": "Madrid",
            "Estado": 1,
            "PersonasContacto": [
                {
                    "Id": "1",
                    "Nombre": "Juan Pérez ACTUALIZADO",  # ← Este nombre cambió
                    "CorreoElectronico": "juan.nuevo@empresa.com",
                },
                {
                    "Id": "2",
                    "Nombre": "María García",  # Sin cambios
                    "CorreoElectronico": "maria@empresa.com",
                }
            ]
        }

        # Guardar nombre original del cliente
        nombre_cliente_original = self.cliente_principal.name

        # Procesar mensaje
        processed = processor.process(mensaje_actualiza_persona)
        service.create_or_update_contact(processed)

        # Refrescar registros
        self.cliente_principal.refresh()
        self.persona_contacto_1.refresh()
        self.persona_contacto_2.refresh()

        # VERIFICACIÓN CRÍTICA: El nombre del cliente NO debe haber cambiado
        self.assertEqual(
            self.cliente_principal.name,
            nombre_cliente_original,
            f"ERROR CRÍTICO: El nombre del cliente cambió de '{nombre_cliente_original}' "
            f"a '{self.cliente_principal.name}'. El nombre de la persona de contacto "
            f"se propagó incorrectamente al cliente principal."
        )

        # Verificar que la persona de contacto SÍ se actualizó
        self.assertEqual(self.persona_contacto_1.name, "Juan Pérez ACTUALIZADO")
        self.assertEqual(self.persona_contacto_1.email, "juan.nuevo@empresa.com")

        # Verificar que la otra persona NO cambió
        self.assertEqual(self.persona_contacto_2.name, "María García")

    def test_modificar_persona_contacto_no_cambia_nombre_direcciones(self):
        """
        Modificar persona de contacto NO debe cambiar nombres de direcciones de entrega.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        mensaje = {
            "Cliente": "REGR001",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "EMPRESA FISCAL S.L.",
            "Estado": 1,
            "PersonasContacto": [
                {
                    "Id": "1",
                    "Nombre": "Nombre Persona Cambiado",
                }
            ]
        }

        # Guardar nombres originales
        nombre_dir1 = self.direccion_entrega_1.name
        nombre_dir2 = self.direccion_entrega_2.name

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        self.direccion_entrega_1.refresh()
        self.direccion_entrega_2.refresh()

        # Las direcciones NO deben haber cambiado
        self.assertEqual(self.direccion_entrega_1.name, nombre_dir1)
        self.assertEqual(self.direccion_entrega_2.name, nombre_dir2)

    def test_modificar_direccion_no_cambia_nombre_cliente(self):
        """
        Modificar dirección de entrega NO debe cambiar nombre del cliente principal.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        # Mensaje que actualiza dirección de entrega (Contacto=1)
        mensaje = {
            "Cliente": "REGR001",
            "Contacto": "1",  # Dirección de entrega 1
            "ClientePrincipal": False,
            "Nombre": "Almacén Norte RENOVADO",  # Nombre de dirección cambia
            "Direccion": "Nueva Calle Almacén 100",
            "Estado": 1,
        }

        nombre_cliente_original = self.cliente_principal.name

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        self.cliente_principal.refresh()
        self.direccion_entrega_1.refresh()

        # Cliente NO debe haber cambiado
        self.assertEqual(
            self.cliente_principal.name,
            nombre_cliente_original,
            "El nombre de la dirección se propagó al cliente principal"
        )

        # Dirección SÍ debe haber cambiado
        self.assertEqual(self.direccion_entrega_1.name, "Almacén Norte RENOVADO")
        self.assertEqual(self.direccion_entrega_1.street, "Nueva Calle Almacén 100")

    def test_modificar_direccion_no_cambia_otras_direcciones(self):
        """
        Modificar una dirección NO debe cambiar otras direcciones.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        mensaje = {
            "Cliente": "REGR001",
            "Contacto": "1",
            "ClientePrincipal": False,
            "Nombre": "Nuevo Nombre Dir 1",
            "Estado": 1,
        }

        nombre_dir2_original = self.direccion_entrega_2.name

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        self.direccion_entrega_2.refresh()

        # Dirección 2 NO debe haber cambiado
        self.assertEqual(self.direccion_entrega_2.name, nombre_dir2_original)

    def test_modificar_cliente_principal_cambia_solo_cliente(self):
        """
        Modificar cliente principal SOLO debe cambiar el cliente, no hijos.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        mensaje = {
            "Cliente": "REGR001",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "NUEVO NOMBRE FISCAL S.A.",  # Cambio legítimo del cliente
            "Direccion": "Nueva Sede Central",
            "Estado": 1,
            "PersonasContacto": []  # Sin personas en este mensaje
        }

        # Guardar nombres de hijos
        nombre_dir1 = self.direccion_entrega_1.name
        nombre_dir2 = self.direccion_entrega_2.name
        nombre_persona1 = self.persona_contacto_1.name
        nombre_persona2 = self.persona_contacto_2.name

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        # Refrescar todo
        self.cliente_principal.refresh()
        self.direccion_entrega_1.refresh()
        self.direccion_entrega_2.refresh()
        self.persona_contacto_1.refresh()
        self.persona_contacto_2.refresh()

        # Cliente SÍ debe haber cambiado
        self.assertEqual(self.cliente_principal.name, "NUEVO NOMBRE FISCAL S.A.")
        self.assertEqual(self.cliente_principal.street, "Nueva Sede Central")

        # NINGÚN hijo debe haber cambiado su nombre
        self.assertEqual(self.direccion_entrega_1.name, nombre_dir1)
        self.assertEqual(self.direccion_entrega_2.name, nombre_dir2)
        self.assertEqual(self.persona_contacto_1.name, nombre_persona1)
        self.assertEqual(self.persona_contacto_2.name, nombre_persona2)

    def test_crear_persona_contacto_no_modifica_cliente_existente(self):
        """
        Crear nueva persona de contacto NO debe modificar nombre del cliente.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        mensaje = {
            "Cliente": "REGR001",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "EMPRESA FISCAL S.L.",
            "Estado": 1,
            "PersonasContacto": [
                {
                    "Id": "1",
                    "Nombre": "Juan Pérez",
                },
                {
                    "Id": "2",
                    "Nombre": "María García",
                },
                {
                    "Id": "3",  # NUEVA persona de contacto
                    "Nombre": "Pedro López NUEVO",
                    "CorreoElectronico": "pedro@empresa.com",
                }
            ]
        }

        nombre_cliente_original = self.cliente_principal.name

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        self.cliente_principal.refresh()

        # Cliente NO debe haber cambiado
        self.assertEqual(self.cliente_principal.name, nombre_cliente_original)

        # Nueva persona debe existir
        nueva_persona = self.env['res.partner'].search([
            ('cliente_externo', '=', 'REGR001'),
            ('persona_contacto_externa', '=', '3'),
        ])
        self.assertTrue(nueva_persona.exists())
        self.assertEqual(nueva_persona.name, "Pedro López NUEVO")


@tagged('post_install', '-at_install', 'nesto_sync', 'regression')
class TestNombreIdentificacionCorrecta(TransactionCase):
    """
    Tests para verificar que cada entidad se identifica correctamente
    y se actualiza solo esa entidad.
    """

    def setUp(self):
        super().setUp()
        self.registry = EntityRegistry()

    def test_identificar_cliente_por_cliente_contacto_0(self):
        """
        Cliente principal se identifica por (Cliente, Contacto=0, PersonaContacto=None)
        """
        # Crear cliente
        cliente = self.env['res.partner'].create({
            'name': 'Cliente Principal',
            'cliente_externo': 'ID001',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
        })

        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        mensaje = {
            "Cliente": "ID001",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "Nombre Actualizado",
            "Estado": 1,
        }

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        cliente.refresh()
        self.assertEqual(cliente.name, "Nombre Actualizado")

    def test_identificar_direccion_por_cliente_contacto_N(self):
        """
        Dirección de entrega se identifica por (Cliente, Contacto=N donde N>0)
        """
        cliente = self.env['res.partner'].create({
            'name': 'Cliente',
            'cliente_externo': 'ID002',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
        })

        direccion = self.env['res.partner'].create({
            'name': 'Dirección Original',
            'cliente_externo': 'ID002',
            'contacto_externo': '5',  # Contacto específico
            'is_company': False,
            'type': 'delivery',
            'parent_id': cliente.id,
        })

        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        mensaje = {
            "Cliente": "ID002",
            "Contacto": "5",  # Debe matchear esta dirección específica
            "ClientePrincipal": False,
            "Nombre": "Dirección Actualizada",
            "Estado": 1,
        }

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        cliente.refresh()
        direccion.refresh()

        # Cliente NO debe cambiar
        self.assertEqual(cliente.name, "Cliente")

        # Dirección SÍ debe cambiar
        self.assertEqual(direccion.name, "Dirección Actualizada")

    def test_identificar_persona_por_cliente_contacto_personacontacto(self):
        """
        Persona de contacto se identifica por (Cliente, Contacto, PersonaContacto)
        """
        cliente = self.env['res.partner'].create({
            'name': 'Cliente',
            'cliente_externo': 'ID003',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
        })

        persona = self.env['res.partner'].create({
            'name': 'Persona Original',
            'cliente_externo': 'ID003',
            'contacto_externo': '0',
            'persona_contacto_externa': '7',  # ID específico
            'type': 'contact',
            'parent_id': cliente.id,
        })

        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        # Mensaje que envía PersonasContacto con Id=7
        mensaje = {
            "Cliente": "ID003",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "Cliente",  # Sin cambios
            "Estado": 1,
            "PersonasContacto": [
                {
                    "Id": "7",
                    "Nombre": "Persona Actualizada",
                }
            ]
        }

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        cliente.refresh()
        persona.refresh()

        # Cliente NO debe cambiar
        self.assertEqual(cliente.name, "Cliente")

        # Persona SÍ debe cambiar
        self.assertEqual(persona.name, "Persona Actualizada")


@tagged('post_install', '-at_install', 'nesto_sync', 'regression')
class TestNombreMultiplesPersonasContacto(TransactionCase):
    """
    Tests específicos para escenarios con múltiples personas de contacto.

    Este fue el escenario exacto del bug: cliente con varias personas de contacto
    donde modificar una afectaba al nombre del cliente.
    """

    def setUp(self):
        super().setUp()
        self.registry = EntityRegistry()

        # Recrear el escenario exacto del bug
        self.cliente = self.env['res.partner'].create({
            'name': 'CENTRO DE ESTÉTICA EL EDÉN, S.L.U.',  # Nombre fiscal real
            'cliente_externo': '15191',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
        })

        self.contacto_angela = self.env['res.partner'].create({
            'name': 'Ángela',
            'cliente_externo': '15191',
            'contacto_externo': '0',
            'persona_contacto_externa': '1',
            'type': 'contact',
            'parent_id': self.cliente.id,
        })

        self.contacto_carlos = self.env['res.partner'].create({
            'name': 'Carlos',
            'cliente_externo': '15191',
            'contacto_externo': '0',
            'persona_contacto_externa': '2',
            'type': 'contact',
            'parent_id': self.cliente.id,
        })

    def test_escenario_real_bug_nombre_pisado(self):
        """
        Reproduce el escenario exacto del bug reportado.

        Usuario modificó PersonaContacto Ángela en Nesto.
        El nombre 'Ángela' se propagó al cliente, pisando 'CENTRO DE ESTÉTICA EL EDÉN, S.L.U.'
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        # Mensaje exacto como el que causó el problema
        mensaje = {
            "Cliente": "15191",
            "Contacto": "0",
            "ClientePrincipal": True,
            "Nombre": "CENTRO DE ESTÉTICA EL EDÉN, S.L.U.",
            "Estado": 1,
            "PersonasContacto": [
                {
                    "Id": "1",
                    "Nombre": "Ángela Modificada",  # Solo cambia el nombre de Ángela
                    "CorreoElectronico": "angela.nuevo@email.com",
                },
                {
                    "Id": "2",
                    "Nombre": "Carlos",
                }
            ]
        }

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        self.cliente.refresh()
        self.contacto_angela.refresh()
        self.contacto_carlos.refresh()

        # VERIFICACIÓN CRÍTICA
        self.assertEqual(
            self.cliente.name,
            'CENTRO DE ESTÉTICA EL EDÉN, S.L.U.',
            f"BUG REPRODUCIDO: El nombre del cliente cambió a '{self.cliente.name}'. "
            f"El nombre de la persona de contacto se propagó al cliente."
        )

        # Persona modificada SÍ debe cambiar
        self.assertEqual(self.contacto_angela.name, "Ángela Modificada")
        self.assertEqual(self.contacto_angela.email, "angela.nuevo@email.com")

        # Otra persona NO debe cambiar
        self.assertEqual(self.contacto_carlos.name, "Carlos")

    def test_mensaje_solo_persona_contacto_plano(self):
        """
        Test para mensaje plano que solo actualiza una persona de contacto.

        Algunos mensajes de Nesto vienen en formato plano (sin PersonasContacto array)
        cuando solo se modifica una persona.
        """
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        # Mensaje plano con PersonaContacto en la raíz
        mensaje = {
            "Cliente": "15191",
            "Contacto": "0",
            "PersonaContacto": "1",  # ID de persona en la raíz
            "Nombre": "Ángela Nueva",
            "CorreoElectronico": "angela.nueva@email.com",
            "Estado": 1,
        }

        nombre_cliente_original = self.cliente.name

        processed = processor.process(mensaje)
        service.create_or_update_contact(processed)

        self.cliente.refresh()
        self.contacto_angela.refresh()

        # Cliente NO debe cambiar (este mensaje es solo para la persona)
        self.assertEqual(
            self.cliente.name,
            nombre_cliente_original,
            "El nombre de persona de contacto se propagó al cliente en mensaje plano"
        )

        # Persona SÍ debe cambiar
        self.assertEqual(self.contacto_angela.name, "Ángela Nueva")
