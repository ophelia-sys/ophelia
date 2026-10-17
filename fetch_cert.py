import ssl
import socket
import sys

hostname = '15.235.193.47'
port = 443

try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((hostname, port)) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert(binary_form=True)
            cert_pem = ssl.DER_cert_to_PEM_cert(cert)
            with open("C:\\Users\\dopa.mine\\Desktop\\ophelia\\android-app\\app\\src\\main\\res\\raw\\vps_cert.crt", "w") as f:
                f.write(cert_pem)
            print("Certificate fetched and saved to vps_cert.crt")
except Exception as e:
    print(f"Error: {e}")
