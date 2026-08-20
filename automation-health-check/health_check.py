#!/usr/bin/env python3
"""
Automation Health Check Script
Pings all Test Managers (TM) and Test Beds (TB) in parallel from testbeds.yaml.
Strips any ':1' or port suffix automatically.
"""

import os
import sys
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor

try:
    import yaml
except ImportError:
    print("Error: PyYAML module is required. Install it using: pip install pyyaml")
    sys.exit(1)


def clean_ip(raw_ip):
    """Strip port numbers or ':1' suffix from IP address."""
    if not raw_ip:
        return ""
    return str(raw_ip).split(':')[0].strip()


def ping_ip(ip):
    """Ping an IP address once and return True if reachable, False otherwise."""
    if not ip:
        return False
    
    system = platform.system().lower()
    param = '-n' if system == 'windows' else '-c'
    timeout_param = '-w' if system == 'windows' else '-W'
    timeout_val = '1000' if system == 'windows' else '1'

    cmd = ['ping', param, '1', timeout_param, timeout_val, ip]
    
    try:
        output = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output.returncode == 0
    except Exception:
        return False


def extract_nodes(data, path=""):
    """Recursively parse YAML structure and collect all nodes containing 'ip'."""
    nodes = []
    if isinstance(data, dict):
        if 'ip' in data:
            nodes.append((path, data))
        else:
            for key, value in data.items():
                new_path = f"{path} > {key}" if path else str(key)
                nodes.extend(extract_nodes(value, new_path))
    return nodes


def check_node_health(item):
    """Ping worker function."""
    path, node = item
    raw_ip = node.get('ip', '')
    ip = clean_ip(raw_ip)
    owner = node.get('owner', 'N/A')
    
    is_online = ping_ip(ip) if ip else False
    
    return {
        'path': path,
        'raw_ip': raw_ip,
        'clean_ip': ip,
        'owner': owner,
        'online': is_online
    }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file = os.path.join(script_dir, "testbeds.yaml")

    if not os.path.exists(yaml_file):
        print(f"Error: YAML file not found at '{yaml_file}'")
        sys.exit(1)

    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)

    nodes = extract_nodes(data)
    print(f"Found {len(nodes)} devices in configuration. Starting health check (pinging in parallel)...\n")

    # Run pings concurrently using 20 threads
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(check_node_health, nodes))

    # Print Report
    print("=" * 105)
    print(f"{'DEVICE PATH':<50} | {'IP ADDRESS':<16} | {'STATUS':<10} | {'OWNER'}")
    print("=" * 105)

    online_count = 0
    offline_count = 0

    for res in results:
        status_str = "[ ONLINE ]" if res['online'] else "[OFFLINE]"
        if res['online']:
            online_count += 1
        else:
            offline_count += 1

        print(f"{res['path']:<50} | {res['clean_ip']:<16} | {status_str:<10} | {res['owner']}")

    print("=" * 105)
    print(f"SUMMARY: Total: {len(results)} | Online: {online_count} | Offline: {offline_count}")
    print("=" * 105)


if __name__ == "__main__":
    main()
