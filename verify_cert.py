import ssl
import hashlib
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import ExtensionOID

cert_path = "C:\\Users\\dopa.mine\\Desktop\\ophelia\\android-app\\app\\src\\main\\res\\raw\\vps_cert.crt"

try:
    with open(cert_path, "rb") as f:
        cert_data = f.read()
    
    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    
    # Fingerprint
    fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    
    # SAN
    try:
        san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san_list = san_ext.value.get_values_for_type(x509.IPAddress)
        sans = [str(ip) for ip in san_list]
    except x509.ExtensionNotFound:
        sans = []

    print(f"SAN: {sans}")
    print(f"Fingerprint (SHA-256): {fingerprint}")
except Exception as e:
    # cryptography module might not be installed, use ssl to parse if possible, or just raw hex
    pass

import subprocess
import socket

# Another simpler way to get cert details using python's ssl module
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with socket.create_connection(('15.235.193.47', 443)) as sock:
    with ctx.wrap_socket(sock, server_hostname='15.235.193.47') as ssock:
        cert = ssock.getpeercert(binary_form=True)
        import hashlib
        fp = hashlib.sha256(cert).hexdigest()
        print(f"Fallback Fingerprint (SHA-256): {fp}")
        # Note: python's built-in getpeercert(binary_form=False) might have SAN if verify_mode != CERT_NONE
