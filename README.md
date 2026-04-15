# OpenNotebook-Archival

OpenNotebook-Archival es un fork orientado a archivos, bibliotecas y trabajo documental con un objetivo deliberadamente acotado: servir como herramienta de uso estrictamente local y personal para profesionales que necesitan trabajar con documentación sensible y modelos locales desde su propio equipo.

## Alcance del proyecto

Este proyecto está diseñado exclusivamente para:

- uso local en `localhost` o `127.0.0.1`;
- una sola persona usuaria por instalación;
- trabajo en el propio equipo del profesional;
- uso preferente con modelos locales, especialmente Ollama, o con endpoints expresamente configurados por la propia persona usuaria bajo su responsabilidad.

Este proyecto **no está diseñado ni soportado** para:

- acceso desde otros equipos de la red;
- uso multiusuario;
- exposición a Internet;
- despliegue como servicio institucional compartido;
- sustitución de una plataforma corporativa con autenticación, auditoría y administración centralizada.

## Filosofía del fork

OpenNotebook-Archival no pretende convertirse en una plataforma SaaS ni en un servicio web empresarial. Su propósito es más concreto: ofrecer un cuaderno documental local, privado y controlable para trabajo individual con fuentes sensibles y modelos locales.

## Qué significa “seguridad” en este proyecto

La seguridad de este fork debe interpretarse dentro de su modelo de uso:

- reducir exposición accidental en red;
- mantener la aplicación confinada a `localhost`;
- dificultar errores de configuración comunes;
- proteger de accesos casuales al interfaz en el propio equipo;
- favorecer trazabilidad y control local del trabajo documental.

Esto no significa que la aplicación esté preparada para operar como servicio abierto, multiusuario o institucional sin rediseño adicional.

## Declaración de soporte

Solo se considera configuración soportada aquella en la que:

- la aplicación se ejecuta en el propio equipo del usuario;
- frontend y API están publicados únicamente en `127.0.0.1`;
- no existe acceso desde otros dispositivos;
- no se usa como herramienta compartida entre varias personas;
- no se expone mediante túneles, reverse proxy público o publicación en Internet.

Cualquier uso fuera de ese perímetro debe considerarse fuera de alcance del proyecto.

## Estado actual del fork

La base funcional existe y el despliegue principal se orienta a build local del propio fork, con frontend y API enlazados a `127.0.0.1`. El objetivo del proyecto no es crecer hacia “más red”, sino reforzar su identidad como herramienta local, personal y documental.

## Qué se ha corregido en esta línea del fork

- `docker-compose.yml` principal orientado al build local del fork.
- `docker-compose.windows.local.yml` orientado también a build local.
- frontend y API publicados en `127.0.0.1`.
- SurrealDB no publicado al host.
- CORS restringido a orígenes explícitos.
- documentación Swagger/ReDoc controlada por variable de entorno.
- cabeceras HTTP de seguridad en backend y frontend.
- almacenamiento de autenticación en `sessionStorage` en vez de `localStorage`.
- validación de rutas de descarga y audio más estricta.
- instalación de Windows con flujo más guiado para entorno local.

## Instalación rápida en Linux/macOS

1. Clona el repositorio.
2. Copia `.env.example` a `.env`.
3. Sustituye los secretos `CHANGE_ME`.
4. Arranca el entorno.

```bash
cp .env.example .env
docker compose up -d --build
```

La aplicación quedará accesible en:

- frontend: `http://127.0.0.1:8502`
- API: `http://127.0.0.1:5055`

## Instalación en Windows

El repositorio incluye un flujo específico para Windows en `deployment/windows/`.

Pasos recomendados:

1. Asegúrate de tener Docker Desktop iniciado.
2. Abre PowerShell en la carpeta del repositorio.
3. Ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\deployment\windows\scripts\Install.ps1
```

El instalador:

- genera secretos internos si faltan;
- solicita la contraseña de acceso en modo oculto;
- construye la imagen local del fork;
- guarda la configuración en `deployment/windows/runtime/settings.env`.

## Variables de entorno relevantes

### Seguridad y acceso local

- `OPEN_NOTEBOOK_PASSWORD`: clave de acceso local a la aplicación.
- `OPEN_NOTEBOOK_ENCRYPTION_KEY`: clave de cifrado para credenciales almacenadas.
- `OPEN_NOTEBOOK_ALLOWED_ORIGINS`: lista CSV de orígenes permitidos para CORS.
- `OPEN_NOTEBOOK_PUBLIC_DOCS`: `true` o `false` para exponer Swagger/ReDoc.
- `OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK`: activa o desactiva la comprobación de actualizaciones.
- `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS`: controla si se permiten URLs privadas en fuentes.
- `OPEN_NOTEBOOK_ALLOW_NO_PASSWORD`: solo para desarrollo local consciente; no recomendado.

### Base de datos

- `SURREAL_ROOT_USER`
- `SURREAL_ROOT_PASSWORD`
- `SURREAL_NAMESPACE`
- `SURREAL_DATABASE`

### Modelos locales

- `OLLAMA_API_BASE`: endpoint de Ollama visto desde el contenedor.
- `OPENAI_COMPATIBLE_BASE_URL`: endpoint compatible con OpenAI configurado expresamente por la persona usuaria.
- `OPENAI_COMPATIBLE_API_KEY`: credencial opcional para dicho endpoint.

## Qué no debe hacerse

No utilices este proyecto:

- como servicio compartido entre trabajadores;
- como aplicación accesible desde la LAN;
- detrás de un reverse proxy para terceros;
- como servicio publicado en Internet;
- como sustituto de una solución corporativa con identidades, trazabilidad y administración centralizadas.

## Estructura útil del repositorio

- `api/`: backend FastAPI
- `frontend/`: interfaz Next.js
- `commands/`: comandos y trabajos de procesamiento
- `open_notebook/`: dominio y lógica principal
- `deployment/windows/`: instalación guiada para Windows

## Créditos

Proyecto derivado del trabajo original de `lfnovo/open-notebook`, adaptado aquí como fork orientado a necesidades archivísticas y documentales con foco en uso local y personal.

## Licencia

Se mantiene la licencia del proyecto original salvo que se indique expresamente otra cosa en el repositorio.
