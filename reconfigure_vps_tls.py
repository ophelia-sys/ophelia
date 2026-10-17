import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
import os
ssh.connect("15.235.193.47", username="ubuntu", password=os.environ.get("VPS_PWD"))

commands = [
    # Re-generate the self-signed cert with Subject Alternative Name (SAN)
    "sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/ophelia-selfsigned.key -out /etc/ssl/certs/ophelia-selfsigned.crt -subj '/CN=15.235.193.47' -addext 'subjectAltName = IP:15.235.193.47'",
    # Restart nginx to pick up the new certificate
    "sudo systemctl restart nginx"
]

for cmd in commands:
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    try:
        print(stdout.read().decode('utf-8', errors='ignore'))
        print(stderr.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        print(f"Error printing output: {e}")

ssh.close()
