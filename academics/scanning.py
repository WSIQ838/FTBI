import socket
import struct
from django.conf import settings

def scan_clean(data):
    """ClamAV INSTREAM protocol. Fail closed on any non-clean response."""
    try:
        with socket.create_connection((settings.FTBI_CLAMAV_HOST,settings.FTBI_CLAMAV_PORT),timeout=10) as sock:
            sock.settimeout(20)
            sock.sendall(b"zINSTREAM\0")
            for i in range(0,len(data),65536):
                chunk=data[i:i+65536]
                sock.sendall(struct.pack("!I",len(chunk))+chunk)
            sock.sendall(struct.pack("!I",0))
            response=b""
            while len(response)<4096 and b"\0" not in response:
                chunk=sock.recv(1024)
                if not chunk:
                    break
                response+=chunk
            return response==b"stream: OK\0"
    except (OSError,ValueError):
        return False
