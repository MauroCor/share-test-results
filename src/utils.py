from datetime import datetime
import time
from src.tools import authenticate_xray, build_test_summary, merge_junit_reports, upload_report, run_command, send_google_chat_message

date = datetime.now().strftime("%d-%m")
GCS_BUCKET = f"gs://bucket/_reports_{date}"
XRAY_BASE_URL = "https://xray.example.com/browse/"

def check_argoCD():
    """Verifica salud de apps en ArgoCD"""
    healthy = False

    # Consultar apps en uso con status !Synced o !Healthy
    cmd = """kubectl get apps -n argocd -o json \
        | jq -r '([.items[].metadata.name|select(endswith("-qa"))|rtrimstr("-qa")] as $qaBases|(.items[]|select((.metadata.name=="example" or ((.metadata.name|endswith("-qa")|not) and ((.metadata.name|rtrimstr("-dev")|rtrimstr("-qa") as $b|($qaBases|index($b)!=null))))) and ((.status.sync.status!="Synced") or (.status.health.status!="Healthy")))|[.metadata.name,.status.sync.status,.status.health.status]|@tsv))' \
        | column -ts $'\t'"""
    
    try:
        output = run_command(cmd, use_shell=True, capture_output=True)
    except Exception as e:
        print(f"Error: {str(e)}")
        return healthy
    
    if output:
        apps = output.strip().splitlines()
        
        print("\n---------- SYNC & HEALTH ----------")

        if apps:
            msg = "⚠️  Revisar estado de Apps:\n\n" + "\n".join(apps)
            print(msg)
            print("\n→ ArgoCD: https://argocd.example.com/applications")
        else:
            total_apps = """kubectl get apps -n argocd -o json | jq -r '([.items[].metadata.name|select(endswith("-qa"))|rtrimstr("-qa")] as $qaBases|(["APP NAME","SYNC","HEALTH"]|@tsv),(.items[]|select(.metadata.name=="example"or((.metadata.name|endswith("-qa")|not)and((.metadata.name|rtrimstr("-dev")|rtrimstr("-qa")as $b|($qaBases|index($b)!=null)))))|[.metadata.name,.status.sync.status,.status.health.status]|@tsv))' | column -ts $'\t'"""
            print(run_command(total_apps, use_shell=True, capture_output=True))
            print("✅ Apps Sync & Healthy!")
            healthy = True
    return healthy

def check_jobs_vs_apps():
    """Alerta si existen apps sin job de pruebas"""
    jobs_vs_apps = False
    apps_cmd = r"""kubectl get apps -n argocd -o json | jq -r '[.items[].metadata.name | select(endswith("-qa")) | rtrimstr("-qa")] as $qaBases | .items[] | select(.metadata.name == "example" or ((.metadata.name | endswith("-qa") | not) and ((.metadata.name | rtrimstr("-dev") | rtrimstr("-qa")) as $b | ($qaBases | index($b)) != null))) | .metadata.name'"""

    jobs_cmd = r"""kubectl get jobs -n example -o json | jq -r '.items[].metadata.name'"""

    ignore_apps = {"example-dev"}

    try:
        app_names_raw = run_command(apps_cmd, use_shell=True, capture_output=True).strip().splitlines()
        job_names = set(run_command(jobs_cmd, use_shell=True, capture_output=True).strip().splitlines())
    except Exception as e:
        print(f"Error al obtener apps o jobs: {e}")
        return jobs_vs_apps

    apps_sin_job = []
    total_apps = 0
    ignored_count = 0

    for app in app_names_raw:
        if app in ignore_apps:
            ignored_count += 1
            continue
        total_apps += 1
        base = app.replace("-dev", "").replace("-qa", "")
        expected_job_prefix = f"{base}-test-job"
        expected_alt_job = f"{base}-job"
        if not any(job.startswith(expected_job_prefix) or job == expected_alt_job for job in job_names):
            apps_sin_job.append(app)

    if total_apps != 0:
        print("\n---------- JOBS vs APPS ----------")
        print(f"➣ Apps consideradas: {total_apps} | Ignoradas: {ignored_count}")
        print(f"➣ Apps ignoradas: {ignore_apps}")
        print(f"➣ Jobs encontrados : {len(job_names)} | Faltantes: {len(apps_sin_job)}\n")

        if apps_sin_job:
            print("⚠️  Faltan Jobs en estas Apps:")
            for app in apps_sin_job:
                print(f"- {app}")
        else:
            print("✅ Apps tienen TestJob.")
            jobs_vs_apps = True
    return jobs_vs_apps

def regression_and_check():
    """Reinicia TestJobs y espera el estado Complete"""
    print("---------- REGRESSION & CHECK ----------")
    print("\n🔄 Reiniciando TestJobs...")
    cmd = r"""
    for i in $(kubectl get job -n example | grep test | awk '{print $1}'); do kubectl delete job -n example $i; done
    """   
    run_command(cmd, use_shell=True)
    time.sleep(10)
    print("\n☕️  Coffe Time! ⋆°•☁︎")
    time.sleep(10)
    print("\n⏳🫠  Espere... ⏰ 👀\n")
    time.sleep(10)

    c = 0
    while True:
        jobs_output = run_command("kubectl get job -n example", use_shell=True, capture_output=True)
        print(jobs_output)

        if any("Complete" not in line for line in jobs_output.splitlines()[1:]):
            if c < 4:
                print(f"⏳ Todavía hay jobs en ejecución... esperando 1 minuto más [{c+1}/4].\n")
                c += 1
                time.sleep(60)
            else:
                print("... Espera manual activada ...")
                print("→ El proceso continúa cuando todos los Jobs finalicen ←")
                respuesta = input("» Presiona Enter para volver a verificar jobs: ")
        else:
            print("✅ TestJobs completados.")
            break

    while True:
        respuesta = input("\n---------- 📢 ATENCIÓN 📢 ----------\n🔎 Verifica la carpeta _junit_reports en GCS.\n→ GCS: https://console.cloud.google.com/storage/browser/example\n\n¿Desea enviar gchat_alert e importar en XRAY? (s/n): ").strip().lower()
        if respuesta in ["s", "n"]:
            if respuesta == "s":
                print("Continuando...")
                break
            else:
                print("Proceso cancelado por el usuario.")
                exit(0)
        else:
            print("Respuesta inválida. Ingresá 's' para sí o 'n' para no.")

def print_logs(type, id=None, hthy=False, jobs=False):
    print("\n---------- 🔊 Gchat Alert 🔊 ----------")
    if type == "stop":
        print(f"{'✅' if hthy else '🚫'} Apps Sync & Healthy")
        print(f"{'✅' if jobs else '🚫'} Apps tienen TestJob")
        print("✋ Ejecución detenida ✋")
        print("🎯 Solucionar problemas y reintentar 😉")
    elif type == "process":
        print("✅ Apps Sync & Healthy!")
        print("✅ Apps tienen TestJob")
        print("✅ TestJobs completados")
        print("⏳ Procesando pruebas...")
        print("⏳ Importando en XRAY...")
        print("⏳ Enviando Alerta...")
    elif type == "done":
        print("✅ Apps Sync & Healthy")
        print("✅ Apps tienen TestJob")
        print("✅ TestJobs completados")
        print("✅ Pruebas procesadas")
        print(f"✅ Importado en XRAY: {id}")
        print("✅ Alerta enviada")
    print("---------------------------------------")

def download_and_merge_reports():
    """Descarga de GCS reportes de JUnit y los fusiona"""
    run_command(["gsutil", "-m", "cp", "-r", GCS_BUCKET, "."])
    merge_junit_reports()

def xray_test_execution():
    """Importa en XRAY la ejecución de pruebas"""
    xray_token = authenticate_xray()
    issueKey = upload_report(xray_token)
    return issueKey

def send_test_summary(issueKey):
    """Envía el resumen de pruebas a Google Chat"""
    suites_msg = build_test_summary()
    body = {
        "cards": [
            {
                "header": {
                    "title": "Regresión de Pruebas Automatizadas",
                    "subtitle": "Reporte"
                },
                "sections": [
                    {
                        "widgets": [
                            {"textParagraph": {"text": suites_msg}},
                            {
                                "buttons": [
                                    {
                                        "textButton": {
                                            "text": "Ver reporte en XRAY",
                                            "onClick": {"openLink": {"url": f"{XRAY_BASE_URL}{issueKey}"}}
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    send_google_chat_message(body)
