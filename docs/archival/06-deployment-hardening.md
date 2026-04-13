# Endurecimiento de despliegue recomendado

## Objetivo

Este fork debe desplegarse como aplicación local o de red privada controlada. No está pensado para exposición directa a Internet sin proxy inverso y TLS.

## Medidas mínimas

1. Publicar puertos solo en `127.0.0.1` cuando sea posible.
2. Configurar `OPEN_NOTEBOOK_PASSWORD` y `OPEN_NOTEBOOK_ENCRYPTION_KEY` con valores robustos.
3. Mantener `OPEN_NOTEBOOK_PUBLIC_DOCS=false` salvo necesidad operativa temporal.
4. Limitar `OPEN_NOTEBOOK_ALLOWED_ORIGINS` a las URLs reales del frontend.
5. Mantener `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS=false` en despliegues normales.
6. Mantener `OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK=false` en entornos institucionales cerrados.
7. Confiar en cabeceras de proxy solo si el despliegue está detrás de un proxy controlado y se activa `OPEN_NOTEBOOK_TRUST_PROXY_HEADERS=true`.
8. Fijar un límite de subida razonable con `OPEN_NOTEBOOK_MAX_UPLOAD_BYTES`.
9. Situar la aplicación detrás de proxy con TLS si se sale de localhost.

## Recomendaciones adicionales

- segmentar la red del contenedor;
- aplicar copias de seguridad cifradas de base de datos y volumen de trabajo;
- centralizar logs y revisar intentos fallidos de autenticación;
- actualizar dependencias y contenedores con periodicidad;
- no reutilizar la misma clave de cifrado en distintos entornos;
- no exponer SurrealDB públicamente.

## Despliegue institucional aconsejado

- usuario accede por HTTPS al proxy;
- proxy reenvía solo al frontend/API permitidos;
- Ollama o endpoint compatible vive en la misma máquina o red interna;
- puertos de base de datos y API no quedan expuestos públicamente.

## Punto pendiente de interfaz

La UI debe simplificarse por completo para mostrar únicamente proveedores locales. El backend ya impone esta restricción, pero conviene que la interfaz no muestre opciones heredadas del upstream.
