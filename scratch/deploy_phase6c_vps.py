import os
import sys

sys.path.insert(0, os.path.abspath("."))
from scratch.vps_helper import get_vps_client, run_vps_command

FILES_TO_DEPLOY = [
    ("models/microstructure.py", "/opt/ophelia/models/microstructure.py"),
    ("control_plane/microstructure_engine.py", "/opt/ophelia/control_plane/microstructure_engine.py"),
    ("control_plane/db.py", "/opt/ophelia/control_plane/db.py"),
    ("control_plane/api.py", "/opt/ophelia/control_plane/api.py"),
    ("tests/test_microstructure_phase6b.py", "/opt/ophelia/tests/test_microstructure_phase6b.py"),
    ("tests/test_microstructure_phase6c.py", "/opt/ophelia/tests/test_microstructure_phase6c.py"),
]

def deploy():
    print("Connecting to VPS (15.235.193.47)...")
    ssh = get_vps_client()
    
    run_vps_command("mkdir -p /tmp/phase6c_deploy /tmp/phase6c_deploy/models /tmp/phase6c_deploy/control_plane /tmp/phase6c_deploy/tests /tmp/phase6c_deploy/scratch")
    sftp = ssh.open_sftp()

    for local_path, remote_path in FILES_TO_DEPLOY:
        tmp_target = "/tmp/phase6c_deploy/" + local_path
        print(f"Staging {local_path} -> {tmp_target}...")
        sftp.put(local_path, tmp_target)

    # Staging verify script if present
    if os.path.exists("scratch/verify_phase6c_live_vps.py"):
        print("Staging verify_phase6c_live_vps.py...")
        sftp.put("scratch/verify_phase6c_live_vps.py", "/tmp/phase6c_deploy/scratch/verify_phase6c_live_vps.py")
    
    # Upload APKs if present
    admin_apk = "android-app/app/build/outputs/apk/admin/debug/app-admin-debug.apk"
    user_apk = "android-app/app/build/outputs/apk/user/debug/app-user-debug.apk"
    if os.path.exists(admin_apk):
        print("Staging admin APK...")
        sftp.put(admin_apk, "/tmp/phase6c_deploy/ophelia-admin.apk")
    if os.path.exists(user_apk):
        print("Staging user APK...")
        sftp.put(user_apk, "/tmp/phase6c_deploy/ophelia-user.apk")
    
    sftp.close()
    ssh.close()
    print("Files staged. Copying to /opt/ophelia with sudo...")

    cmd = (
        "sudo cp /tmp/phase6c_deploy/models/microstructure.py /opt/ophelia/models/microstructure.py && "
        "sudo cp /tmp/phase6c_deploy/control_plane/microstructure_engine.py /opt/ophelia/control_plane/microstructure_engine.py && "
        "sudo cp /tmp/phase6c_deploy/control_plane/db.py /opt/ophelia/control_plane/db.py && "
        "sudo cp /tmp/phase6c_deploy/control_plane/api.py /opt/ophelia/control_plane/api.py && "
        "sudo cp /tmp/phase6c_deploy/tests/test_microstructure_phase6b.py /opt/ophelia/tests/test_microstructure_phase6b.py && "
        "sudo cp /tmp/phase6c_deploy/tests/test_microstructure_phase6c.py /opt/ophelia/tests/test_microstructure_phase6c.py && "
        "([ ! -f /tmp/phase6c_deploy/scratch/verify_phase6c_live_vps.py ] || sudo cp /tmp/phase6c_deploy/scratch/verify_phase6c_live_vps.py /opt/ophelia/scratch/verify_phase6c_live_vps.py) && "
        "sudo chown -R ophelia:ophelia /opt/ophelia && "
        "mkdir -p /opt/ophelia/control_data/apk /opt/ophelia/static && "
        "([ ! -f /tmp/phase6c_deploy/ophelia-admin.apk ] || sudo cp /tmp/phase6c_deploy/ophelia-admin.apk /opt/ophelia/control_data/apk/ophelia-admin.apk) && "
        "([ ! -f /tmp/phase6c_deploy/ophelia-admin.apk ] || sudo cp /tmp/phase6c_deploy/ophelia-admin.apk /opt/ophelia/static/ophelia-admin-latest.apk) && "
        "([ ! -f /tmp/phase6c_deploy/ophelia-admin.apk ] || sudo cp /tmp/phase6c_deploy/ophelia-admin.apk /opt/ophelia/static/ophelia-latest.apk) && "
        "([ ! -f /tmp/phase6c_deploy/ophelia-user.apk ] || sudo cp /tmp/phase6c_deploy/ophelia-user.apk /opt/ophelia/control_data/apk/ophelia-user.apk) && "
        "([ ! -f /tmp/phase6c_deploy/ophelia-user.apk ] || sudo cp /tmp/phase6c_deploy/ophelia-user.apk /opt/ophelia/static/ophelia-user-latest.apk) && "
        "sudo systemctl restart ophelia-api ophelia-control"
    )
    out, err = run_vps_command(cmd)
    print("Deploy output:\n", out.strip())
    if err:
        print("Deploy err:\n", err.strip())
    
    out, err = run_vps_command("sudo systemctl status ophelia-api ophelia-control --no-pager")
    print("Status output:\n", out.strip())

if __name__ == "__main__":
    deploy()
