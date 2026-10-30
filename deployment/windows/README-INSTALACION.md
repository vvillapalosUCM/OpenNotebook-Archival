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

## Configuración privada y empaquetado

La configuración `runtime/settings.env`, los diagnósticos de `runtime/` y las
copias de `backups/` permanecen en el equipo: no forman parte del contexto de
construcción ni de las nuevas imágenes Docker. Los dos Dockerfiles copian
únicamente los componentes necesarios para ejecutar la aplicación. Las
credenciales se siguen suministrando al arrancar mediante Docker Compose.

Para aplicar esta corrección a una instalación existente, actualice el código
y utilice `03-ACTUALIZAR.bat`, que reconstruye la imagen. Conserve `settings.env`
y los volúmenes de datos: no es necesario reinstalar ni cambiar contraseñas
para reconstruir. La corrección no elimina imágenes, cachés ni archivos
exportados anteriormente; no comparta una imagen antigua que pudiera contener
su configuración. Si ya la compartió, cambie las credenciales que incluía.

La prueba `python tests/docker-packaging.py` requiere Docker en ejecución y
comprueba ambos Dockerfiles con archivos ficticios, sin leer la configuración
personal ni iniciar los servicios de la aplicación. También se ejecuta en CI.
