# Arquitectura local-only

## Componentes base

1. Open Notebook como interfaz y capa de orquestación.
2. Ollama como proveedor principal de modelos.
3. Endpoint OpenAI-compatible local como opción secundaria.
4. SurrealDB como persistencia.
5. Docker Compose como despliegue de referencia.

## Política técnica

- solo se admiten proveedores `ollama` y `openai_compatible`;
- las URLs deben resolver a `localhost`, `127.0.0.1`, `host.docker.internal` o rangos privados RFC1918;
- se deshabilitan listados y ayudas de proveedores cloud en frontend;
- el descubrimiento de modelos queda restringido a proveedores locales;
- se recomienda bloquear salida a Internet a nivel de infraestructura.

## Garantías buscadas

- reducción del riesgo de exfiltración;
- menor complejidad de configuración;
- coherencia entre UI, backend y despliegue;
- trazabilidad del comportamiento permitido.
