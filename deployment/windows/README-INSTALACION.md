# Instalación simplificada en Windows

## Qué es esta carpeta

Esta carpeta está pensada para que una persona sin conocimientos técnicos pueda instalar y manejar Open ArchiBook LLM con el menor número posible de pasos.

## Requisitos previos

Antes de empezar, deben estar instalados:

- Docker Desktop
- Git
- Ollama, si se van a usar modelos locales

## Instalación inicial

1. Abra esta carpeta:
   `deployment/windows/`
2. Haga doble clic en:
   `00-PRIMERA-INSTALACION.bat`
3. Introduzca la contraseña inicial cuando se le pida.
4. Revise la URL local de Ollama.
5. Espere a que Docker construya y arranque la aplicación.
6. El navegador se abrirá automáticamente.

## Qué hace el instalador

- crea la configuración de trabajo en `deployment/windows/runtime/settings.env`
- prepara carpetas de datos persistentes
- construye una imagen local del fork
- arranca los contenedores
- abre la aplicación en el navegador
