#!/usr/bin/env python3
from src.utils import check_argoCD, check_jobs_vs_apps, download_and_merge_reports, print_logs, regression_and_check, send_test_summary, xray_test_execution

"""
__________ GCHAT ALERT __________
- Script para regresión de pruebas -

Ejecutar: ./regression/gchat_alert.py

"""

healthy = check_argoCD()
check_jobs = check_jobs_vs_apps()

if check_jobs:
    if healthy == False:
        while True:
            respuesta = input("\n---------- 📢 ATENCIÓN 📢 ----------\n🤔 Hay apps no saludables ¿Desea continuar? (s/n): ").strip().lower()
            if respuesta == "s":
                print("Continuando...")
                break
            else:
                print("Proceso cancelado por el usuario.")
                exit(0)
        regression_and_check()
        print_logs("process")
        download_and_merge_reports()
        issueKey = xray_test_execution()
        send_test_summary(issueKey)
        print_logs("done", issueKey)
else:
    print_logs("stop", hthy=healthy, jobs=check_jobs)
