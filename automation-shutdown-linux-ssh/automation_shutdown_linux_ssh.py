#!/usr/bin/env python3
"""
Automation Linux Shutdown / Reboot Script via SSH
Reads TM and TB IPs from testbeds.yaml (stripping ports/suffixes like ':1')
and performs a remote SSH reboot operation.

ONLY reboots TM (Test Manager) and TB (Test Bed) machines.
Ignores WPS, Pearle, Vaunix, and other auxiliary devices.
"""

import os
import sys
import re
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


def is_tm_or_tb_key(key):
    """Check if the YAML node key represents a Test Manager (TM) or Test Bed (TB)."""
    key_upper = str(key).strip().upper()
    # Matches TM, TB, TM1, TB1, 1TM, 1TB, etc.
    return 'TM' in key_upper or 'TB' in key_upper


def extract_tm_tb_nodes(data, path=""):
    """Recursively parse YAML structure and collect ONLY TM and TB nodes."""
    nodes = []
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path} > {key}" if path else str(key)
            if isinstance(value, dict):
                # If key is a TM or TB node and contains an 'ip' field
                if is_tm_or_tb_key(key) and 'ip' in value:
                    nodes.append((new_path, key, value))
                else:
                    nodes.extend(extract_tm_tb_nodes(value, new_path))
    return nodes


def execute_ssh_reboot(item, username="root", ssh_key=None, password=None):
    """
    SSH into the specified TM/TB host and execute reboot.
    """
    path, node_key, node = item
    raw_ip = node.get('ip', '')
    ip = clean_ip(raw_ip)
    owner = node.get('owner', 'N/A')

    if not ip:
        return {'path': path, 'ip': ip, 'success': False, 'message': 'Invalid/Empty IP'}

    # Construct SSH command
    # StrictHostKeyChecking=no avoids interactive prompts
    ssh_opts = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=5",
        "-o", "BatchMode=yes"  # Prevents hanging if password prompt appears without key
    ]

    if ssh_key:
        ssh_opts.extend(["-i", ssh_key])

    remote_target = f"{username}@{ip}"
    reboot_cmd = "reboot || sudo reboot || shutdown -r now"

    cmd = ["ssh"] + ssh_opts + [remote_target, reboot_cmd]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        # Reboot command usually terminates SSH connection immediately
        if res.returncode == 0 or "Closed" in res.stderr or "Connection to" in res.stderr or "Connection closed" in res.stderr:
            return {'path': path, 'ip': ip, 'owner': owner, 'success': True, 'message': 'Reboot command sent'}
        else:
            return {'path': path, 'ip': ip, 'owner': owner, 'success': False, 'message': res.stderr.strip() or 'SSH failed'}
    except subprocess.TimeoutExpired:
        # Timeout often happens because reboot was triggered and closed the socket
        return {'path': path, 'ip': ip, 'owner': owner, 'success': True, 'message': 'Reboot initiated (SSH socket closed)'}
    except Exception as e:
        return {'path': path, 'ip': ip, 'owner': owner, 'success': False, 'message': str(e)}


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file = os.path.join(script_dir, "testbeds.yaml")

    if not os.path.exists(yaml_file):
        print(f"Error: YAML file not found at '{yaml_file}'")
        sys.exit(1)

    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)

    nodes = extract_tm_tb_nodes(data)
    print("=" * 105)
    print(f"Automation SSH Reboot Script")
    print(f"Targeting ONLY TM (Test Manager) and TB (Test Bed) machines.")
    print(f"Excluded WPS, Pearle, Vaunix, and all other auxiliary hardware.")
    print(f"Found {len(nodes)} TM/TB nodes in '{os.path.basename(yaml_file)}'.")
    print("=" * 105)

    # Prompt confirmation to prevent accidental reboot
    print("\nWARNING: This will send SSH reboot commands to all identified TM and TB nodes!")
    confirm = input("Are you sure you want to proceed with reboot? (type 'yes' to confirm): ").strip().lower()
    
    if confirm != 'yes':
        print("Reboot operation cancelled by user.")
        sys.exit(0)

    username = input("Enter SSH Username [default: root]: ").strip() or "root"

    print(f"\nSending SSH reboot commands in parallel (username: {username})...\n")

    def worker(item):
        return execute_ssh_reboot(item, username=username)

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(worker, nodes))

    print("\n" + "=" * 105)
    print(f"{'DEVICE PATH':<50} | {'IP ADDRESS':<16} | {'REBOOT STATUS':<12} | {'MESSAGE'}")
    print("=" * 105)

    success_count = 0
    fail_count = 0

    for res in results:
        status_str = "[ SUCCESS ]" if res['success'] else "[ FAILED  ]"
        if res['success']:
            success_count += 1
        else:
            fail_count += 1

        print(f"{res['path']:<50} | {res['ip']:<16} | {status_str:<12} | {res['message']}")

    print("=" * 105)
    print(f"SUMMARY: Total TM/TB Nodes: {len(results)} | Successfully Triggered: {success_count} | Failed: {fail_count}")
    print("=" * 105)


if __name__ == "__main__":
    main()
