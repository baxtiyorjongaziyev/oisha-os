import paramiko
import os
import scp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VPS_DEPLOY")

def deploy():
    # VPS Ma'lumotlari (JonBranding Discovery verified: baxti@34.159.150.1)
    vps_ip = '34.159.150.1'
    username = 'baxti'
    password = 'parol1122'
    remote_path = '/home/baxti/oisha-os'

    try:
        # 1. SSH ulanish
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger.info(f"Connecting to {vps_ip}...")
        ssh.connect(vps_ip, username=username, password=password)

        # 2. Papkani yaratish
        ssh.exec_command(f"mkdir -p {remote_path}")

        # 3. Fayllarni uzatish (SCP)
        with scp.SCPClient(ssh.get_transport()) as scp_client:
            logger.info("Transferring files to cloud...")
            # Muhim fayllarni uzatamiz
            files_to_send = [
                'userbot.py', 
                'settings.py', 
                'agent_tools.py', 
                '.env', 
                'requirements.txt',
                'userbot_session.session',
                'oisha_userbot.session',
                'oisha.service',
                'deploy/oisha_sync.service',
                'scripts/tez_natija_master_sync.py',
                'C:/tmp/bot_database.db' # Progress migration
            ]
            
            # Papkalarni ham (Handlers va Services)
            # Bu yerda oddiyroq bo'lishi uchun butun papkani jo'natamiz
            # (Lekin .git va __pycache__ larni chetlab o'tish tavsiya etiladi)
            local_dir = os.path.dirname(os.path.abspath(__file__))
            scp_client.put(local_dir, remote_path, recursive=True)

        # 4. Serverda kutubxonalarni o'rnatish
        logger.info("Installing dependencies on VPS...")
        ssh.exec_command(f"cd {remote_path} && pip3 install -r requirements.txt --break-system-packages")

        # 5. Systemd xizmatini yoqish
        logger.info("Starting Oisha 24/7 System service...")
        setup_cmd = (
            f"sudo cp {remote_path}/oisha.service /etc/systemd/system/ && "
            "sudo systemctl daemon-reload && "
            "sudo systemctl enable oisha && "
            "sudo systemctl restart oisha"
        )
        ssh.exec_command(setup_cmd)

        logger.info("✅ SUCCESS! Oisha is now running on the Cloud 24/7.")
        ssh.close()

    except Exception as e:
        logger.error(f"Deployment failed: {e}")

if __name__ == "__main__":
    deploy()
