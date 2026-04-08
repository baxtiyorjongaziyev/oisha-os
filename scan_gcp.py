import subprocess
import json
import os

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return ""

print("Scanning for projects with billing enabled...")
projects_json = run_cmd("gcloud projects list --format=json")
if not projects_json:
    print("No projects found or gcloud error.")
    exit()

projects = json.loads(projects_json)
for p in projects:
    p_id = p['projectId']
    # Check billing
    billing_json = run_cmd(f"gcloud beta billing projects describe {p_id} --format=json")
    if not billing_json: continue
    
    billing_info = json.loads(billing_json)
    if billing_info.get('billingEnabled'):
        print(f"\n--- PROJECT: {p_id} (BILLING ENABLED) ---")
        # Check resources
        # GCE
        instances = run_cmd(f"gcloud compute instances list --project {p_id} --format=json")
        if instances and instances != "[]":
            data = json.loads(instances)
            for inst in data:
                print(f"VM Found: {inst['name']} ({inst['machineType'].split('/')[-1]}) - {inst['status']}")
        
        # Cloud Run
        services = run_cmd(f"gcloud run services list --project {p_id} --format=json")
        if services and services != "[]":
            data = json.loads(services)
            for svc in data:
                print(f"Cloud Run Found: {svc['metadata']['name']}")

        # Cloud SQL
        sql = run_cmd(f"gcloud sql instances list --project {p_id} --format=json")
        if sql and sql != "[]":
            data = json.loads(sql)
            for inst in data:
                print(f"Cloud SQL Found: {inst['name']} ({inst['settings']['tier']})")

        # Static IPs
        ips = run_cmd(f"gcloud compute addresses list --project {p_id} --format=json")
        if ips and ips != "[]":
            data = json.loads(ips)
            for ip in data:
                print(f"Static IP Found: {ip['address']} ({ip['status']})")
