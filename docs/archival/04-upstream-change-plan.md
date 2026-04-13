# Plan de cambios sobre upstream

## Backend

Archivos a intervenir primero:

- `api/credentials_service.py`
- `api/routers/credentials.py`
- `open_notebook/ai/model_discovery.py`

Cambios:

- lista blanca estricta de proveedores;
- validación de URL local o privada;
- rechazo explícito de credenciales cloud;
- descubrimiento limitado a Ollama y OpenAI-compatible local.

## Frontend

Archivo a intervenir primero:

- `frontend/src/app/(dashboard)/settings/api-keys/page.tsx`

Cambios:

- ocultar proveedores no permitidos;
- textos orientados a despliegue local;
- placeholders específicos para Ollama y endpoints locales.

## Artefactos auxiliares

- política local-only reutilizable;
- prompts guiados para archiveros;
- docker compose de referencia;
- variables de entorno ejemplo.
