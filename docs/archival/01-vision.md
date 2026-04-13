# Visión del fork archivístico

## Tesis de producto

OpenNotebook-Archival no debe competir como clon genérico de NotebookLM. Debe posicionarse como una estación de trabajo local para profesionales de archivo, bibliotecas especializadas y gestión documental.

## Problema que resuelve

Muchos archivos y pequeñas instituciones necesitan trabajar con documentos sensibles sin exponerlos a servicios cloud y sin depender de proveedores externos. Además, requieren una interfaz sencilla que oculte complejidad técnica y ofrezca tareas útiles para su práctica diaria.

## Propuesta de valor

- consulta semántica sobre corpus documentales;
- resúmenes de expedientes;
- extracción asistida de metadatos;
- apoyo a clasificación y descripción;
- generación de borradores técnicos revisables;
- despliegue local sencillo con Docker y Ollama.

## Restricción crítica

El sistema no debe permitir proveedores remotos por defecto. La política del fork será local-first y, en despliegue institucional, local-only.

## Público inicial

- archivos municipales pequeños;
- archivos religiosos;
- centros de documentación con datos sensibles;
- instituciones que necesiten soberanía tecnológica y bajo coste.
