# Notas de implementación de esta tanda

Este paquete corrige y mejora:

1. `api/main.py`
   - CORS cerrado a orígenes permitidos.
   - `/api/config` ya no queda público.
   - docs públicas controladas por `OPEN_NOTEBOOK_PUBLIC_DOCS`.
   - cabeceras de seguridad.

2. `api/routers/config.py`
   - comprobación de versión contra el fork.

3. `api/routers/podcasts.py`
   - validación de rutas de audio dentro de `DATA_FOLDER/podcasts/episodes`.

4. `frontend/src/lib/stores/auth-store.ts`
   - persistencia en `sessionStorage` en vez de `localStorage`.

5. `frontend/next.config.ts`
   - cabeceras frontend de seguridad.

6. `Dockerfile`
   - sin `curl | bash` para Node.
   - usuario no privilegiado en runtime.

7. `docker-compose.yml`
   - build local del fork.
   - SurrealDB no expuesto por defecto.
   - secretos y defaults seguros por `.env`.

8. `configs/archival/docker-compose.local-only.yml`
   - alineado con el fork y build local.

9. `deployment/windows/docker-compose.windows.local.yml`
   - archivo nuevo, requerido por los scripts de Windows.

10. `deployment/windows/env.template`
    - nuevas variables de SurrealDB.

11. `deployment/windows/scripts/Common.ps1`
    - generación de secretos internos y ruta de compose operativa.

12. `deployment/windows/scripts/Install.ps1`
    - entrada de contraseña oculta y política mínima más robusta.

13. `.env.example`
    - plantilla para despliegue local seguro.

14. `README.md`
    - documentación realineada con el fork.
