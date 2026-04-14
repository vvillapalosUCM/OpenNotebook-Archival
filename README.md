# OpenNotebook-Archival

OpenNotebook-Archival es un fork orientado a archivos, bibliotecas y entornos GLAM que prioriza despliegue local, privacidad, trazabilidad y adaptación institucional. Su enfoque no es “usar más proveedores”, sino ofrecer una base controlada para trabajar con modelos locales —especialmente Ollama— y con documentación sensible.

Este repositorio parte del trabajo original de `lfnovo/open-notebook`, pero aquí se reorienta a un escenario archivístico y de investigación documental: instalación local, endurecimiento de seguridad, configuración comprensible y futura especialización funcional para descripción, análisis y transformación documental.

## Estado actual del fork

La base funcional existe, pero este fork sigue en fase de saneamiento estructural. Antes de ampliar funciones archivísticas conviene dejar cerradas estas capas:

- seguridad del backend y del despliegue;
- instalación reproducible en Windows;
- documentación alineada con el fork;
- defaults seguros para uso local e institucional.

## Qué se ha corregido en esta tanda

Esta versión de archivos deja preparada una línea de trabajo más segura y coherente:

- CORS restringido a orígenes explícitos.
- `/api/config` deja de ser público.
- documentación Swagger/ReDoc controlada por variable de entorno.
- cabeceras HTTP de seguridad en backend y frontend.
- almacenamiento de autenticación en `sessionStorage` en vez de `localStorage`.
- validación de rutas de audio de podcasts para evitar lecturas fuera del directorio previsto.
- `Dockerfile` preparado para ejecutar como usuario no privilegiado.
- `docker-compose.yml` principal orientado al build local del fork, no a la imagen upstream.
- creación del compose específico para Windows que faltaba en el repositorio.
- instalador de Windows con contraseña oculta y política mínima más exigente.
- actualización de comprobación de versión apuntando al fork, no al upstream.

## Identidad del proyecto

Este fork está pensado para:

- profesionales de archivos, bibliotecas, documentación y gestión del conocimiento;
- uso local o semilocal dentro de red controlada;
- integración futura con Ollama y endpoints OpenAI-compatible locales;
- extensiones archivísticas como transformaciones ISAD(G), extracción de metadatos y exportación interoperable.

No está planteado como producto SaaS ni como entorno multiusuario abierto a Internet sin una capa adicional de reverse proxy, TLS y endurecimiento de sistema.

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

- frontend: `http://localhost:8502`
- API: `http://localhost:5055`

Por defecto, el `docker-compose.yml` principal publica solo frontend y API en `127.0.0.1`. SurrealDB no se publica externamente.

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

### Seguridad y autenticación

- `OPEN_NOTEBOOK_PASSWORD`: contraseña de acceso a la aplicación.
- `OPEN_NOTEBOOK_ENCRYPTION_KEY`: clave de cifrado para credenciales almacenadas.
- `OPEN_NOTEBOOK_ALLOWED_ORIGINS`: lista CSV de orígenes permitidos para CORS.
- `OPEN_NOTEBOOK_PUBLIC_DOCS`: `true` o `false` para exponer Swagger/ReDoc.
- `OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK`: activa o desactiva la comprobación de actualizaciones.
- `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS`: controla si se permiten URLs privadas en fuentes.

### Base de datos

- `SURREAL_ROOT_USER`
- `SURREAL_ROOT_PASSWORD`
- `SURREAL_NAMESPACE`
- `SURREAL_DATABASE`

### Modelos locales

- `OLLAMA_API_BASE`: endpoint de Ollama visto desde el contenedor.
- `OPENAI_COMPATIBLE_BASE_URL`: endpoint compatible con OpenAI en local o red privada.
- `OPENAI_COMPATIBLE_API_KEY`: credencial opcional para dicho endpoint.

## Consideraciones de seguridad

Este fork se orienta a un despliegue local endurecido, pero eso no convierte automáticamente la aplicación en apta para Internet abierta. Si vas a exponerla fuera de localhost, debes añadir como mínimo:

- TLS terminado correctamente;
- reverse proxy controlado;
- política de logs y copias de seguridad;
- revisión de permisos y puertos;
- endurecimiento del host.

Recomendaciones inmediatas:

- no reutilices contraseñas;
- usa secretos largos y aleatorios;
- no actives `OPEN_NOTEBOOK_PUBLIC_DOCS` salvo necesidad real;
- mantén `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS=false` mientras no haya un caso justificado;
- si cambias el puerto del frontend, actualiza también `OPEN_NOTEBOOK_ALLOWED_ORIGINS`.

## Orientación funcional del fork

La dirección natural de OpenNotebook-Archival no es competir por cantidad de proveedores ni por marketing de “productividad genérica”. Su valor diferencial está en:

- adaptación al trabajo archivístico y documental;
- apoyo a análisis local de fuentes;
- transformaciones especializadas;
- trazabilidad y control institucional;
- integración futura con herramientas como ArchivesSpace, AtoM o flujos exportables.

Líneas funcionales previstas:

- prompts archivísticos especializados;
- transformaciones predefinidas para ISAD(G) y tareas de análisis documental;
- mayor simplificación de la UI para escenarios solo-locales;
- internacionalización al español;
- exportaciones orientadas a entornos GLAM.

## Diferencias respecto al upstream

Este fork no debe seguir presentándose como una simple copia de Open Notebook. A nivel documental y operativo se recomienda mantener:

- identidad propia del fork;
- documentación propia de instalación;
- política de versiones propia;
- referencias al upstream solo como atribución técnica, no como centro del proyecto.

## Desarrollo

Para trabajar sobre el código del fork:

```bash
docker compose up -d --build
```

El compose principal ya está planteado para construir la imagen desde este mismo repositorio. Eso evita el problema anterior de estar modificando el código del fork mientras el despliegue seguía ejecutando la imagen upstream.

## Estructura útil del repositorio

- `api/`: backend FastAPI
- `frontend/`: interfaz Next.js
- `commands/`: comandos y trabajos de procesamiento
- `open_notebook/`: dominio y lógica principal
- `configs/archival/`: compose alternativo local-only
- `deployment/windows/`: instalación guiada para Windows

## Créditos

Proyecto derivado del trabajo original de `lfnovo/open-notebook`, adaptado aquí como fork orientado a necesidades archivísticas y documentales.

## Licencia

Se mantiene la licencia del proyecto original salvo que se indique expresamente otra cosa en el repositorio.
