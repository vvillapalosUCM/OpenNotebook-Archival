# Revisión de seguridad inicial del fork archivístico

## Riesgos identificados en la base heredada

1. Comparación de contraseñas sin `constant-time compare`.
2. Ausencia de rate limiting frente a intentos repetidos de autenticación.
3. Configuración CORS demasiado permisiva para un despliegue institucional.
4. Documentación OpenAPI expuesta por defecto.
5. Descubrimiento de modelos con múltiples proveedores remotos.
6. Posible SSRF al procesar URLs de tipo `link`.
7. Carga de ficheros en memoria completa, con riesgo de DoS por archivos grandes.
8. Falta de límite explícito de tamaño de subida.

## Medidas ya aplicadas en la rama `archival-bootstrap`

- política local-only para credenciales y descubrimiento de modelos;
- limitación a `ollama` y `openai_compatible`;
- validación de endpoints locales o de red privada controlada;
- endurecimiento de autenticación con comparación constante y bloqueo temporal por IP;
- CORS restringido a orígenes configurables;
- documentación `/docs` y `/openapi.json` deshabilitada por defecto;
- validación anti-SSRF para fuentes URL;
- escritura de subidas por streaming con límite de tamaño configurable.

## Nuevas variables de entorno relevantes

- `OPEN_NOTEBOOK_ALLOWED_ORIGINS`
- `OPEN_NOTEBOOK_PUBLIC_DOCS`
- `OPEN_NOTEBOOK_AUTH_MAX_ATTEMPTS`
- `OPEN_NOTEBOOK_AUTH_WINDOW_SECONDS`
- `OPEN_NOTEBOOK_AUTH_BLOCK_SECONDS`
- `OPEN_NOTEBOOK_AUTH_FAILURE_DELAY_MS`
- `OPEN_NOTEBOOK_MAX_UPLOAD_BYTES`
- `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS`

## Próxima fase recomendada

1. Simplificar la UI para que solo muestre proveedores locales.
2. Añadir tests de seguridad para autenticación, SSRF y límites de subida.
3. Revisar logs para evitar exposición de rutas, URLs sensibles o metadatos innecesarios.
4. Añadir cabeceras HTTP de endurecimiento si se expone tras proxy inverso.
5. Documentar un despliegue de referencia con reverse proxy, TLS y red segmentada.
