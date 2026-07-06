#!/usr/bin/env python3
"""MikroTik API dump tool.

Connects to a MikroTik router and dumps raw API responses for key paths.
Use this to inspect what the API actually returns before writing parsing code.

Usage:
    pip install librouteros
    python tools/api_dump.py 192.168.2.1 -u admin
    python tools/api_dump.py 192.168.1.1 -u admin --port 8729 --tls
"""

import argparse
import sys
import traceback
from pprint import pformat


def try_import():
    try:
        from librouteros import connect
        from librouteros.login import plain, token
        return connect, plain, token
    except ImportError:
        print("ERROR: librouteros is not installed.")
        print("Install it with: pip install librouteros")
        sys.exit(1)


def query(api, path, command=None, args=None):
    """Execute an API query and return (success, result)."""
    if args is None:
        args = {}
    try:
        response = api.path(path)
        if command:
            result = list(response(command, **args))
        else:
            result = list(response)
        return True, result
    except Exception as e:
        return False, {"path": path, "command": command, "args": args, "error": str(e)}


def dump_entry(entry, indent=2):
    """Dump a single API entry dict, showing field names, values, and types."""
    prefix = " " * indent
    for k in sorted(entry.keys()):
        v = entry[k]
        vtype = type(v).__name__
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace")
        print(f"{prefix}{k} ({vtype}) = {v!r}")


def dump_result(success, result, label):
    """Dump a query result."""
    border = "=" * 66
    print(f"\n{border}")
    print(f"  {label}")
    print(border)
    if not success:
        print(f"  ERROR: {result['error']}")
        print(f"  Path: {result['path']}")
        if result.get("command"):
            print(f"  Command: {result['command']}")
        if result.get("args"):
            print(f"  Args: {result['args']}")
        return
    if not result:
        print("  (empty result)")
        return
    if isinstance(result, list):
        print(f"  Count: {len(result)}")
        for i, entry in enumerate(result):
            print(f"\n  --- Entry {i} ---")
            dump_entry(entry)
    else:
        dump_entry(result)


def main():
    parser = argparse.ArgumentParser(
        description="Dump raw MikroTik API responses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("host", help="Router hostname or IP address")
    parser.add_argument("-u", "--username", default="admin", help="API username")
    parser.add_argument("-p", "--password", default="", help="API password")
    parser.add_argument("--port", type=int, default=None,
                        help="API port (default: 8728, or 8729 with --tls)")
    parser.add_argument("--tls", action="store_true",
                        help="Connect via TLS (port 8729)")
    parser.add_argument("--login-method", choices=["plain", "token", "auto"],
                        default="auto", help="Login method (default: auto)")
    args = parser.parse_args()

    connect, plain, token = try_import()

    port = args.port or (8729 if args.tls else 8728)

    # Build connection kwargs
    kwargs = {
        "host": args.host,
        "port": port,
        "username": args.username,
        "password": args.password,
    }
    if args.login_method == "plain":
        kwargs["login_method"] = plain
    elif args.login_method == "token":
        kwargs["login_method"] = token

    print(f"Connecting to {args.host}:{port} as {args.username}...")
    sys.stdout.flush()

    try:
        api = connect(**kwargs)
    except Exception as e:
        print(f"Connection failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    print("Connected.")

    # =============================================
    # 1. /interface  — All interfaces
    # =============================================
    ok, result = query(api, "/interface")
    dump_result(ok, result, "/interface  (all interfaces)")

    if ok and isinstance(result, list):
        # Find LTE interfaces for monitoring
        lte_interfaces = [e for e in result if e.get("type") == "lte"]
        ether_interfaces = [e for e in result if e.get("type") == "ether"]

        # =============================================
        # 2. /interface/ethernet monitor (first few)
        # =============================================
        for iface in ether_interfaces[:3]:
            label = f"/interface/ethernet monitor .id={iface['.id']} once="
            ok2, result2 = query(api, "/interface/ethernet",
                                command="monitor",
                                args={".id": iface[".id"], "once": True})
            dump_result(ok2, result2, label)

        # =============================================
        # 3. /interface/lte monitor
        # =============================================
        for iface in lte_interfaces:
            label = f"/interface/lte monitor .id={iface['.id']} once="
            ok2, result2 = query(api, "/interface/lte",
                                command="monitor",
                                args={".id": iface[".id"], "once": True})
            dump_result(ok2, result2, label)

            # Also try with name as .id
            label2 = f"/interface/lte monitor .id={iface['name']} once=  (using name)"
            ok3, result3 = query(api, "/interface/lte",
                                command="monitor",
                                args={".id": iface["name"], "once": True})
            dump_result(ok3, result3, label2)

        # =============================================
        # 4. /interface/lte print
        # =============================================
        ok2, result2 = query(api, "/interface/lte")
        dump_result(ok2, result2, "/interface/lte  (LTE config)")

    # =============================================
    # 5. /ip/route
    # =============================================
    ok, result = query(api, "/ip/route")
    dump_result(ok, result, "/ip/route")

    # =============================================
    # 6. /queue/type
    # =============================================
    ok, result = query(api, "/queue/type")
    dump_result(ok, result, "/queue/type")

    # =============================================
    # 7. /system resource
    # =============================================
    ok, result = query(api, "/system/resource")
    dump_result(ok, result, "/system/resource")

    # =============================================
    # 8. /system health
    # =============================================
    ok, result = query(api, "/system/health")
    dump_result(ok, result, "/system/health")

    print("\nDone.")


if __name__ == "__main__":
    main()
