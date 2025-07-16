from datetime import datetime
import glob
import json
import subprocess
import requests
import xml.etree.ElementTree as ET

WEBHOOK_URL = "https://chat.example.com/webhook"
XRAY_BASE_URL = "https://xray.example.com"


def run_command(command, use_shell=False, capture_output=False):
    """Ejecuta un comando en la terminal y maneja errores."""
    result = subprocess.run(
        command,
        shell=use_shell,
        check=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.stdout if capture_output else None


def load_json(file_path):
    """Carga un archivo JSON y lo devuelve como diccionario."""
    with open(file_path) as f:
        return json.load(f)


def merge_junit_reports():
    merged_tree = None
    merged_root = None
    
    files = glob.glob('_reports_*/*.xml')
    
    for file in files:
        tree = ET.parse(file)
        root = tree.getroot()

        if merged_root is None:
            # Inicializar el root para el primer archivo
            merged_root = root
        else:
            # Fusionar los <testsuite> de los archivos adicionales
            for testsuite in root.findall('testsuite'):
                merged_root.append(testsuite)
    
    # Guardar el archivo fusionado
    merged_tree = ET.ElementTree(merged_root)
    merged_tree.write('merged_report.xml', encoding='utf-8', xml_declaration=True)


def build_test_summary():
    """Construye el mensaje de resumen de pruebas a partir de los datos de JUnit."""
    
    tree = ET.parse("merged_report.xml")
    root = tree.getroot()

    coverage = {'tests': 0, 'errors': 0, 'failures': 0, 'skipped': 0}
    e2e = {'tests': 0, 'errors': 0, 'failures': 0, 'skipped': 0}

    # Procesar cada testsuite
    for testsuite in root.findall('testsuite'):
        suite_type = e2e if testsuite.find('testcase').get('classname', '').startswith("E2E") else coverage
        suite_type['tests'] += int(testsuite.get('tests', 0))
        suite_type['errors'] += int(testsuite.get('errors', 0))
        suite_type['failures'] += int(testsuite.get('failures', 0))
        suite_type['skipped'] += int(testsuite.get('skipped', 0))

    # Total de pruebas
    total_tests = coverage['tests'] + e2e['tests']
    suites_msg = f"Total de pruebas: <b>{total_tests}</b>.<br>"

    # Función para crear el mensaje de cada suite
    def create_suite_msg(suite, name):
        if suite['tests'] > 0:
            suites_msg = f"- <b>{name}</b>:<br>"
            for label, icon, count in [
                ("ok", "✅", suite['tests'] - (suite['errors'] + suite['failures'] + suite['skipped'])),
                ("fail", "❌", suite['failures']),
                ("break", "⚠️", suite['errors']),
                ("skip", "⏸️", suite['skipped']),
            ]:
                if count > 0:
                    suites_msg += f"&nbsp;&nbsp;&nbsp;&nbsp; {icon} {count} ({label})<br>"
            suites_msg += "<br>"
            return suites_msg
        return ""

    suites_msg += create_suite_msg(coverage, "Coverage")
    suites_msg += create_suite_msg(e2e, "E2E")

    # Si no hay pruebas, mostrar mensaje específico
    if total_tests == 0:
        return "No se realizaron pruebas."
    
    return suites_msg


def authenticate_xray():
    xray_credentials = load_json("regression/config/cloud_xray_credential.json")
    xray_execution = load_json("regression/config/test_exec_info.json")

    # Modificar JSON de ejecución en Xray
    date = datetime.now().strftime("%d/%m/%Y")
    xray_execution["fields"]["summary"] += f" - {date}"
    with open("temp-exec-info.json", "w") as f:
        json.dump(xray_execution, f, indent=2)
    print(f"📄 Archivo generado: temp-exec-info.json")

    # Autenticación en Xray
    auth_response = requests.post(
        f"{XRAY_BASE_URL}/api/v2/authenticate",
        headers={"Content-Type": "application/json"},
        json=xray_credentials,
        verify=False)
    if auth_response.status_code != 200:
        print("❌ Error en autenticación Xray:", auth_response.text)
        exit(1)

    return auth_response.text.strip('"')


def upload_report(xray_token):
    """Crea un Test Execution en Jira y crea o actualiza Test Cases según el contenido del XML JUnit."""
    with open("temp-exec-info.json", "rb") as info_file, open("merged_report.xml", "rb") as report_file:
        response = requests.post(
            f"{XRAY_BASE_URL}/api/v2/import/execution/junit/multipart",
            headers={"Authorization": f"Bearer {xray_token}"},
            files={"info": info_file, "results": report_file},
            verify=False
        )

    response_data = response.json()
    issueKey = response_data.get("key")

    if not issueKey:
        print("❌ No se pudo obtener el issueKey.")
        exit(1)

    print(f"🎫 Ticket generado en Jira: {issueKey}")
    return issueKey


def send_google_chat_message(body):
    """Envía una notificación a Google Chat."""
    headers = {"Content-Type": "application/json"}
    response = requests.post(WEBHOOK_URL, json=body, headers=headers)
    response.raise_for_status()
