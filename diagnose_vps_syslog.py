import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
import os
ssh.connect("15.235.193.47", username="ubuntu", password=os.environ.get("VPS_PWD"))

commands = [
    "sudo systemctl daemon-reload",
    "sudo systemctl start ophelia-api.service",
    "sudo systemctl status ophelia-api.service --no-pager"
]

with open("vps_output3.txt", "w", encoding="utf-8") as out:
    for cmd in commands:
        out.write(f"--- RUNNING: {cmd} ---\n")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out.write(stdout.read().decode('utf-8', errors='ignore') + "\n")
        out.write(stderr.read().decode('utf-8', errors='ignore') + "\n")

ssh.close()
