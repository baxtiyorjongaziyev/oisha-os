
import os
import subprocess
import sys

def run_command(command):
    print(f"Executing: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while True:
        output = process.stdout.readline()
        if output == b'' and process.poll() is not None:
            break
        if output:
            print(output.decode().strip())
    rc = process.poll()
    return rc

def deploy():
    project_id = "jonbranding-85662071-ea38e"
    region = "europe-west3" # Frankfurt (Stratejik joylashuv)
    service_name = "oisha-master-bot"
    
    print(f"🚀 Deploying {service_name} to Google Cloud Run in {region}...")

    # 1. Google Cloud Auth check (optional but recommended)
    # run_command("gcloud auth list")

    # 2. Build and Push using Cloud Build (Optimized)
    # Bu command Dockerfile ni ishlatadi va image ni GCR ga push qiladi
    build_cmd = f"gcloud builds submit --tag gcr.io/{project_id}/{service_name} ."
    if run_command(build_cmd) != 0:
        print("❌ Cloud Build failed!")
        sys.exit(1)

    # 3. Deploy to Cloud Run
    # Barcha .env o'zgaruvchilarini --set-env-vars orqali uzatish mumkin, 
    # lekin xavfsizlik uchun Secret Manager ishlatish tavsiya etiladi.
    # Hozircha .env fayldan o'qiymiz (Sodda usul)
    
    env_vars = []
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    env_vars.append(line.strip())
    
    env_vars_str = ",".join(env_vars)
    
    deploy_cmd = (
        f"gcloud run deploy {service_name} "
        f"--image gcr.io/{project_id}/{service_name} "
        f"--platform managed "
        f"--region {region} "
        f"--allow-unauthenticated "
        f"--set-env-vars \"{env_vars_str}\" "
        f"--memory 1Gi "
        f"--cpu 1 "
        f"--timeout 3600"
    )

    if run_command(deploy_cmd) != 0:
        print("❌ Cloud Run deployment failed!")
        sys.exit(1)

    print(f"✅ Deployment successful! Service {service_name} is up and running.")

if __name__ == "__main__":
    deploy()
