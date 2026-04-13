# Open Notebook Archivística

Este fork inicia la especialización de Open Notebook para entornos archivísticos y documentales.

## Objetivo

Convertir Open Notebook en una estación de trabajo local para archiveros con estas restricciones de diseño:

- uso exclusivamente local de modelos;
- proveedor principal: Ollama;
- proveedor secundario permitido: endpoints OpenAI-compatible locales o de red privada controlada;
- exclusión de proveedores cloud en interfaz y backend;
- orientación a descripción, análisis y apoyo documental, no a automatización autónoma.

## Principios

1. Soberanía del dato.
2. Simplicidad de despliegue institucional.
3. Trazabilidad de las salidas.
4. Supervisión humana obligatoria.
5. Compatibilidad con flujos archivísticos reales.

## Primer alcance

- endurecimiento local-only;
- reducción de proveedores visibles;
- plantillas funcionales para archiveros;
- documentación de despliegue base.

## Próximos pasos

- bloquear credenciales remotas en backend;
- limitar descubrimiento de modelos a Ollama y OpenAI-compatible local;
- simplificar la pantalla de API Keys;
- crear asistentes archivísticos guiados;
- preparar una primera demo para clasificación, extracción de metadatos y síntesis documental.
