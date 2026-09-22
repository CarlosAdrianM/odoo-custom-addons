#!/usr/bin/env python3
"""Revisa el log de tests de Odoo y falla si:
- algún módulo ejecuta menos tests de los esperados (p. ej. el paquete tests/ no se importó),
- aparece un fallo que no está en la lista de fallos conocidos,
- no aparece la línea de resumen de odoo.tests.result (Odoo se cayó antes de acabar).
Uso: comprobar_tests.py LOG CONOCIDOS MODULO=MINIMO [MODULO=MINIMO ...]
"""
import re, sys, collections

log_path, conocidos_path, *minimos = sys.argv[1:]
log = open(log_path, encoding='utf-8', errors='replace').read()
conocidos = {l.split('#')[0].strip() for l in open(conocidos_path, encoding='utf-8')} - {''}

ejecutados = collections.Counter(re.findall(r'odoo\.addons\.(\w+)\.tests\.\w+: Starting \w+\.\w+', log))
fallos = set(re.findall(r' (?:FAIL|ERROR): (\w+\.\w+)', log))
resumen = re.findall(r'odoo\.tests\.result: (.*)', log)

errores = []
for par in minimos:
    modulo, minimo = par.split('=')
    if ejecutados[modulo] < int(minimo):
        errores.append(f'{modulo}: se han ejecutado {ejecutados[modulo]} tests y se esperaban al menos {minimo}. '
                       f'¿Falla el import de {modulo}/tests/__init__.py?')
if not resumen:
    errores.append('No aparece el resumen de odoo.tests.result: Odoo no terminó la pasada de tests.')
nuevos = sorted(fallos - conocidos)
arreglados = sorted(conocidos - fallos)

print('Tests ejecutados por módulo:', dict(ejecutados))
print('Resumen de Odoo:', resumen[-1] if resumen else '—')
print(f'Fallos: {len(fallos)} ({len(fallos & conocidos)} conocidos, {len(nuevos)} nuevos)')
for t in nuevos:
    errores.append(f'Fallo NUEVO: {t}')
if arreglados:
    print('Ya no fallan (quitadlos de la lista de conocidos):')
    for t in arreglados:
        print('   ', t)
if errores:
    print('\n'.join(['', 'RESULTADO: KO'] + ['  - ' + e for e in errores]))
    sys.exit(1)
print('\nRESULTADO: OK')
