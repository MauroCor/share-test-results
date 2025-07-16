# share-test-results

Automatización para la regresión de pruebas, integración con Google Chat y Jira/Xray, y manejo de reportes JUnit.

## Funcionalidades

- Verifica el estado de las aplicaciones en ArgoCD.
- Comprueba que todas las apps tengan su job de pruebas correspondiente.
- Reinicia los jobs de pruebas y espera su finalización.
- Descarga y fusiona reportes JUnit desde Google Cloud Storage.
- Sube los resultados a Jira/Xray.
- Envía un resumen de la ejecución a Google Chat.

## Requisitos

- Python 3.7+
- Acceso a Kubernetes (`kubectl`)
- Acceso a Google Cloud Storage (`gsutil`)
- Acceso a Jira/Xray (API)
- Acceso a Google Chat (Webhook)
- jq, column (para procesamiento de JSON en shell)

## Instalación

1. Clona el repositorio.
2. Configura:
   - `WEBHOOK_URL`: URL del webhook de Google Chat.
   - `XRAY_BASE_URL`: URL base de Xray/Jira.
   - Credenciales de Xray en `regression/config/cloud_xray_credential.json`.
   - Información de ejecución en `regression/config/test_exec_info.json`.
   - Nombre del bucket de GCS en la variable `GCS_BUCKET` (puedes parametrizarlo).

**Importante:**  
No subas archivos de credenciales ni datos sensibles al repositorio. Usa variables de entorno o archivos de configuración para todo dato privado.

## Uso

1. Asegúrate de haber exportado el `PYTHONPATH` correctamente:
   ```sh
   export PYTHONPATH=$PWD
   ```
2. Ejecuta el script principal:
   ```sh
   python3 src/gchat_alert.py
   ```
3. Sigue las instrucciones interactivas en consola para validar el estado de las apps, jobs y reportes.


