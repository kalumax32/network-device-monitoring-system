import subprocess
import socket
import platform
import re
import psutil
import time
from pysnmp.hlapi import *
from getmac import get_mac_address
from mac_vendor_lookup import MacLookup

# --- CONFIGURATION ---
ROUTER_IP = "192.168.1.1"       
SNMP_COMMUNITY = "public"       
SNMP_PORT = 161
# ---------------------

snmp_cache = {}
local_bw_cache = None
local_ip_cache = None

# Initialize Vendor Database (Loads locally first)
try:
    mac_lookup = MacLookup()
    # Optional: mac_lookup.update_vendors() # Uncomment to download latest list from internet
except:
    mac_lookup = None

def get_local_ip():
    global local_ip_cache
    now = time.time()
    if isinstance(local_ip_cache, dict) and (now - local_ip_cache.get("time", 0)) < 60 and local_ip_cache.get("ip"):
        return local_ip_cache["ip"]

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Use the local gateway first (works without internet).
        try:
            s.connect((ROUTER_IP, 80))
        except:
            s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        local_ip_cache = {"ip": local_ip, "time": now}
        return local_ip
    except:
        return "127.0.0.1"

def format_speed(bytes_per_sec):
    if bytes_per_sec > 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"
    elif bytes_per_sec > 1024:
        return f"{bytes_per_sec / 1024:.2f} KB/s"
    else:
        return f"{bytes_per_sec:.0f} B/s"

def get_local_bandwidth_in_out():
    global local_bw_cache

    stats = psutil.net_io_counters()
    now = time.time()

    if local_bw_cache is None:
        local_bw_cache = {"sent": stats.bytes_sent, "recv": stats.bytes_recv, "time": now}
        return "Calculating...", "Calculating..."

    dt = now - local_bw_cache["time"]
    if dt <= 0:
        return "0 B/s", "0 B/s"

    delta_out = stats.bytes_sent - local_bw_cache["sent"]
    delta_in = stats.bytes_recv - local_bw_cache["recv"]

    # Counters should be monotonic, but be defensive.
    if delta_out < 0:
        delta_out = 0
    if delta_in < 0:
        delta_in = 0

    local_bw_cache = {"sent": stats.bytes_sent, "recv": stats.bytes_recv, "time": now}
    return format_speed(delta_in / dt), format_speed(delta_out / dt)

def _snmp_get_many(ip, oid_strs):
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(SNMP_COMMUNITY, mpModel=1),
        UdpTransportTarget((ip, SNMP_PORT), timeout=1, retries=0),
        ContextData(),
        *[ObjectType(ObjectIdentity(oid)) for oid in oid_strs],
    )
    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
    if errorIndication or errorStatus:
        raise RuntimeError("SNMP Error")
    return [vb[1] for vb in varBinds]

def get_snmp_bandwidth_in_out(ip):
    global snmp_cache
    if_number_oid = "1.3.6.1.2.1.2.1.0"

    # Prefer 64-bit octet counters.
    hc_in_base = "1.3.6.1.2.1.31.1.1.1.6"
    hc_out_base = "1.3.6.1.2.1.31.1.1.1.10"

    # Fallback to 32-bit octet counters.
    in_base = "1.3.6.1.2.1.2.2.1.10"
    out_base = "1.3.6.1.2.1.2.2.1.16"

    now = time.time()

    try:
        ip_state = snmp_cache.get(ip)
        if isinstance(ip_state, dict):
            fail_until = ip_state.get("snmp_fail_until")
            if isinstance(fail_until, (int, float)) and now < fail_until:
                return "N/A", "N/A"

        if_count_val = _snmp_get_many(ip, [if_number_oid])[0]
        if_count = int(if_count_val)
        if if_count <= 0:
            return "N/A", "N/A"

        best_index = None
        if ip in snmp_cache and isinstance(snmp_cache[ip], dict):
            best_index = snmp_cache[ip].get("best_index")

        # Query a limited number of interfaces for speed.
        max_ifaces = min(if_count, 16)
        candidate_indices = list(range(1, max_ifaces + 1))
        if best_index is not None and best_index in candidate_indices:
            # Put last-known best first.
            candidate_indices = [best_index] + [i for i in candidate_indices if i != best_index]

        def fetch_counters(base_in, base_out):
            oid_strs = []
            for idx in candidate_indices:
                oid_strs.append(f"{base_in}.{idx}")
                oid_strs.append(f"{base_out}.{idx}")
            vals = _snmp_get_many(ip, oid_strs)
            counters = {}
            for i, idx in enumerate(candidate_indices):
                v_in = vals[i * 2]
                v_out = vals[i * 2 + 1]
                try:
                    counters[idx] = (int(v_in), int(v_out))
                except:
                    continue
            return counters

        counter_bits = 64
        try:
            counters = fetch_counters(hc_in_base, hc_out_base)
        except:
            counter_bits = 32
            counters = fetch_counters(in_base, out_base)

        if not counters:
            return "N/A", "N/A"

        ip_state = snmp_cache.get(ip)
        if not isinstance(ip_state, dict):
            ip_state = {"interfaces": {}, "best_index": None, "snmp_fail_until": None}

        interfaces_state = ip_state.get("interfaces")
        if not isinstance(interfaces_state, dict):
            interfaces_state = {}

        wrap = 2 ** counter_bits
        best = {"idx": None, "rin": None, "rout": None, "score": -1, "has_rate": False}

        for idx, (bytes_in, bytes_out) in counters.items():
            prev = interfaces_state.get(idx)
            if isinstance(prev, dict) and "time" in prev:
                dt = now - prev["time"]
                if dt > 0:
                    d_in = bytes_in - int(prev.get("in", 0))
                    d_out = bytes_out - int(prev.get("out", 0))
                    if d_in < 0:
                        d_in += wrap
                    if d_out < 0:
                        d_out += wrap
                    r_in = d_in / dt
                    r_out = d_out / dt
                    score = r_in + r_out
                    if score > best["score"]:
                        best = {"idx": idx, "rin": r_in, "rout": r_out, "score": score, "has_rate": True}
            else:
                # No previous sample; pick the most active interface as a heuristic.
                score = bytes_in + bytes_out
                if not best["has_rate"] and score > best["score"]:
                    best = {"idx": idx, "rin": None, "rout": None, "score": score, "has_rate": False}

            interfaces_state[idx] = {"in": bytes_in, "out": bytes_out, "time": now}

        ip_state["interfaces"] = interfaces_state
        ip_state["best_index"] = best["idx"]
        ip_state["snmp_fail_until"] = None
        snmp_cache[ip] = ip_state

        if best["idx"] is None:
            return "N/A", "N/A"
        if not best["has_rate"]:
            return "Calculating...", "Calculating..."

        return format_speed(best["rin"]), format_speed(best["rout"])
    except:
        ip_state = snmp_cache.get(ip)
        if not isinstance(ip_state, dict):
            ip_state = {"interfaces": {}, "best_index": None}
        # Don't re-timeout on every refresh for devices without SNMP.
        ip_state["snmp_fail_until"] = now + 300
        snmp_cache[ip] = ip_state
        return "N/A", "N/A"

def get_bandwidth_in_out_for_ip(ip):
    local_ip = get_local_ip()
    if ip == local_ip:
        return get_local_bandwidth_in_out()
    return get_snmp_bandwidth_in_out(ip)

def resolve_hostname(ip):
    # 1. Try standard DNS
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        if hostname and hostname != ip:
            return hostname
    except:
        pass

    # 2. Try MAC Address Vendor Lookup
    try:
        mac = get_mac_address(ip=ip)
        if mac and mac_lookup:
            try:
                vendor = mac_lookup.lookup(mac)
                return f"{vendor} Device"
            except:
                return f"Device [{mac}]" # Vendor not found, show MAC
    except:
        pass
        
    return "Unknown Device"

def ping(ip, local_ip):
    # 1. Localhost
    if ip == local_ip:
        bw_in, bw_out = get_local_bandwidth_in_out()
        return "Online", "0 ms", "This Server", bw_in, bw_out

    # 2. Router
    if ip == ROUTER_IP:
        try:
            param = "-n" if platform.system().lower()=="windows" else "-c"
            subprocess.run(["ping", param, "1", ip], capture_output=True)
            bw_in, bw_out = get_snmp_bandwidth_in_out(ip)
            return "Online", "1 ms", "Router Gateway", bw_in, bw_out
        except:
            pass

    # 3. Other Devices
    param = "-n" if platform.system().lower()=="windows" else "-c"
    command = ["ping", param, "1", "-w", "500", ip] if platform.system().lower()=="windows" else ["ping", param, "1", "-W", "1", ip]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        is_online = result.returncode == 0
        if is_online:
            output = result.stdout
            if platform.system().lower()=="windows":
                 match = re.search(r'time[=<](\d+)', output)
            else:
                 match = re.search(r'time=(\d+\.?\d*)', output)
            response_time = (match.group(1) + " ms") if match else "<1 ms"
            
            # USE THE NEW RESOLVER
            hostname = resolve_hostname(ip)
            bw_in, bw_out = get_snmp_bandwidth_in_out(ip)
            return "Online", response_time, hostname, bw_in, bw_out
    except:
        pass

    return "Offline", "-", "-", "-", "-"

def scan_network(base_ip):
    devices = []
    local_ip = get_local_ip()
    
    # Scanning 1 to 20
    for i in range(1, 21):
        ip = base_ip + str(i)
        status, response_time, hostname, bw_in, bw_out = ping(ip, local_ip)
        
        devices.append({
            "ip": ip,
            "hostname": hostname,
            "status": status,
            "response_time": response_time,
            "bandwidth_in": bw_in,
            "bandwidth_out": bw_out
        })
    return devices