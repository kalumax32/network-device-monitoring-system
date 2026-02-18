import subprocess
import socket
import platform
import re
import random

def ping(ip):
    param = "-n" if platform.system().lower()=="windows" else "-c"
    command = ["ping", param, "1", ip]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        output = result.stdout
        match = re.search(r'time[=<]\s?(\d+\.?\d*)', output)
        response_time = match.group(1) + " ms" if match else "N/A"

        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except:
            hostname = "Unknown"

        bandwidth_in = str(random.randint(100, 1000)) + " KB/s"
        bandwidth_out = str(random.randint(100, 1000)) + " KB/s"

        return "Online", response_time, hostname, bandwidth_in, bandwidth_out
    else:
        return "Offline", "-", "-", "-", "-"

def scan_network(base_ip):
    devices = []
    for i in range(1, 21):
        ip = base_ip + str(i)
        status, response_time, hostname, bw_in, bw_out = ping(ip)
        devices.append({
            "ip": ip,
            "hostname": hostname,
            "status": status,
            "response_time": response_time,
            "bandwidth_in": bw_in,
            "bandwidth_out": bw_out
        })
    return devices
