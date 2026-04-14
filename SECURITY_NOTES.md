# Notas de Seguridad — OpenNotebook Despliegue Endurecido

## Contexto

Este despliegue está diseñado para uso local en equipos Windows con Docker
Desktop, orientado a profesionales del sector GLAM (archivos, bibliotecas,
museos) que necesitan una herramienta de investigación con IA sin exponer
datos a internet.

El compose oficial de Open Notebook (`lfnovo/open-notebook`) está pensado
para facilidad de instalación, no para seguridad. Este despliegue endurecido
corrige los problemas detectados en una auditoría de seguridad realizada
en abril de 2026.

---

## Problemas detectados y correcciones aplicadas

### 1. SurrealDB expuesta al exterior

**Problema:** El compose oficial publica SurrealDB en `0.0.0.0:8000` (todas
las interfaces de red). Cualquier dispositivo en la red local puede conectarse
a la base de datos.

**Corrección:** Se ha eliminado completamente la sección `ports` de SurrealDB.
El servicio solo es accesible desde dentro de la red Docker interna
(`on_internal`) como `surrealdb:8000`. Ningún proceso del host ni de la red
local puede conectarse directamente.

**Verificación:**
```powershell
# Esto debe FALLAR (conexión rechazada):
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
# Esto debe mostrar que NO hay binding en el puerto 8000:
docker port on-surrealdb
```

### 2. Credenciales por defecto (root/root)

**Problema:** El compose oficial usa `--user root --pass root` para SurrealDB
y documenta estas credenciales como valores por defecto. Combinado con el
puerto abierto, cualquiera en la red tiene acceso total a la BD.

**Corrección:** Las credenciales se definen en el fichero `.env` y deben
cambiarse obligatoriamente antes del primer arranque. El usuario por defecto
es `on_admin` en lugar de `root`.

### 3. Frontend y API abiertos a toda la red

**Problema:** Los puertos 8502 y 5055 se publican sin restricción de interfaz
(`0.0.0.0`), permitiendo acceso desde cualquier equipo de la red local.

**Corrección:** Ambos puertos están restringidos a `127.0.0.1` en el compose.
Solo el navegador del propio equipo puede acceder.

**Verificación:**
```powershell
# Desde el propio equipo, esto debe funcionar:
Start-Process "http://127.0.0.1:8502"
# Desde otro equipo de la red, debe ser INACCESIBLE.
```

### 4. Vulnerabilidad de inyección SurrealQL (CVE, reportada por CERT-EU)

**Problema:** En versiones ≤ v1.8.2, el endpoint `GET /api/notebooks` acepta
entrada arbitraria en el parámetro `order_by`, permitiendo inyección de
comandos SurrealQL. Explotable vía CSRF (basta con que el usuario haga clic
en un enlace malicioso).

**Corrección:** Usar v1.8.3 o superior. Este despliegue fija la versión de la
imagen. Verificar periódicamente si hay nuevos parches de seguridad en
https://github.com/lfnovo/open-notebook/releases

**Verificación:**
```powershell
docker inspect on-app --format '{{.Config.Image}}'
# Debe mostrar una versión >= v1.8.3
```

### 5. Clave de cifrado por defecto

**Problema:** `OPEN_NOTEBOOK_ENCRYPTION_KEY` viene con el valor placeholder
`change-me-to-a-secret-string`. Esta clave cifra las API keys de proveedores
IA almacenadas en SurrealDB con AES-128-CBC. Si no se cambia, cualquiera
con acceso a la BD puede descifrar las claves.

**Corrección:** El `.env.hardened` exige cambiar este valor antes del primer
arranque. Se proporcionan comandos para generar valores aleatorios seguros.

### 6. Pull automático de imágenes (supply chain)

**Problema:** El compose oficial usa `pull_policy: always`, lo que descarga la
última versión de la imagen cada vez que se ejecuta `docker compose up`. Si la
imagen upstream se compromete, el despliegue se actualiza sin consentimiento.

**Corrección:** `pull_policy: never`. Las actualizaciones son manuales y
deliberadas:
```powershell
# Para actualizar conscientemente:
docker compose pull
docker compose up -d
```

### 7. Contenedor SurrealDB como root

**Problema:** El compose oficial usa `user: root` en el servicio SurrealDB,
necesario para bind mounts en Linux pero innecesario en Docker Desktop
para Windows.

**Corrección:** Se ha eliminado `user: root`. Se usan volúmenes nombrados
en lugar de bind mounts, lo que evita problemas de permisos en cualquier SO.

### 8. Contenedores sin restricciones de seguridad

**Problema:** El compose oficial no aplica ninguna restricción de seguridad
a los contenedores.

**Corrección aplicada:**
- `security_opt: no-new-privileges` — impide escalada de privilegios dentro
  del contenedor.
- `read_only: true` en SurrealDB — el sistema de ficheros del contenedor es
  de solo lectura excepto el volumen de datos y /tmp.
- `tmpfs` para directorios temporales con límite de tamaño.
- Límites de memoria y CPU para prevenir agotamiento de recursos.

### 9. Llamadas salientes no solicitadas

**Problema:** La comprobación automática de actualizaciones envía peticiones
a servidores externos sin consentimiento del usuario.

**Corrección:** `OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK=false` en el `.env`.

### 10. Variables de API externa con valores residuales

**Problema:** Si `OPENAI_COMPATIBLE_BASE_URL` o `OPENAI_COMPATIBLE_API_KEY`
quedan con valores de ejemplo, la aplicación puede intentar conectarse a
endpoints externos, filtrando datos.

**Corrección:** Estas variables están comentadas por defecto en `.env.hardened`.
Solo se descomentan si el usuario decide conscientemente usar un servicio
externo.

---

## Qué NO cubre este endurecimiento

Este despliegue asume un modelo de amenaza de **uso local en equipo personal
o de trabajo**. No protege contra:

- **Acceso físico al equipo:** si alguien tiene acceso al equipo, puede leer
  los volúmenes Docker directamente.
- **Malware en el host:** un programa malicioso con privilegios de
  administrador puede acceder a la red Docker y a los volúmenes.
- **Vulnerabilidades zero-day** en Docker, SurrealDB u Open Notebook.
- **Exposición deliberada a internet** (por ejemplo, abriendo puertos en el
  router o usando un túnel). Este despliegue NO está diseñado para ser
  accesible desde internet.

---

## Mantenimiento

### Actualizar Open Notebook

```powershell
# 1. Comprobar nueva versión en GitHub releases
# 2. Cambiar la versión de la imagen en docker-compose.yml
# 3. Descargar y reiniciar
docker compose pull
docker compose up -d
```

### Backup de datos

```powershell
# Los datos están en volúmenes Docker nombrados.
# Para hacer backup:
docker run --rm -v on-surreal-data:/data -v ${PWD}:/backup `
  alpine tar czf /backup/surreal-backup.tar.gz -C /data .

docker run --rm -v on-notebook-data:/data -v ${PWD}:/backup `
  alpine tar czf /backup/notebook-backup.tar.gz -C /data .
```

### Verificar que los puertos están correctamente restringidos

```powershell
# Listar puertos publicados de cada contenedor:
docker port on-surrealdb    # Debe estar VACÍO
docker port on-app           # Debe mostrar 127.0.0.1:8502 y 127.0.0.1:5055
```

---

## Checklist de primer arranque

- [ ] He copiado `.env.hardened` como `.env`
- [ ] He cambiado `OPEN_NOTEBOOK_ENCRYPTION_KEY` por un valor aleatorio
- [ ] He cambiado `SURREAL_PASSWORD` por una contraseña fuerte
- [ ] He verificado que la imagen es v1.8.3 o superior
- [ ] He ejecutado `docker compose up -d`
- [ ] He verificado que `docker port on-surrealdb` está vacío
- [ ] He verificado que `docker port on-app` muestra 127.0.0.1
- [ ] He accedido a http://127.0.0.1:8502 y funciona correctamente
- [ ] He configurado Ollama como proveedor de IA en la interfaz web
