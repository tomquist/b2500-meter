#!/usr/bin/env python3
import json
import os
import readline

FIELDS = [
    "A_phase_power",
    "B_phase_power",
    "C_phase_power",
    "total_power",
    "A_chrg_nb",
    "B_chrg_nb",
    "C_chrg_nb",
    "ABC_chrg_nb",
    "wifi_rssi",
    "info_idx",
    "x_chrg_power",
    "A_chrg_power",
    "B_chrg_power",
    "C_chrg_power",
    "ABC_chrg_power",
    "x_dchrg_power",
    "A_dchrg_power",
    "B_dchrg_power",
    "C_dchrg_power",
    "ABC_dchrg_power",
]


def load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {k: 0 for k in FIELDS}


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def print_help():
    print("Commands:")
    print("  show                - show current values")
    print("  set <field> <value> - set field")
    print("  zero                - set all fields to 0")
    print("  save                - write file")
    print("  help                - show this")
    print("  quit                - exit")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to override JSON")
    args = parser.parse_args()

    data = load(args.file)
    save(args.file, data)
    print(f"Loaded {args.file}")
    print_help()

    while True:
        try:
            cmd = input("ct002> ").strip()
        except EOFError:
            break
        if not cmd:
            continue
        if cmd in ("quit", "exit"):
            break
        if cmd == "help":
            print_help()
            continue
        if cmd == "show":
            for k in FIELDS:
                print(f"{k}: {data.get(k, 0)}")
            continue
        if cmd == "zero":
            for k in FIELDS:
                data[k] = 0
            save(args.file, data)
            print("All zeroed and saved.")
            continue
        if cmd == "save":
            save(args.file, data)
            print("Saved.")
            continue
        if cmd.startswith("set "):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: set <field> <value>")
                continue
            field, value = parts[1], parts[2]
            if field not in FIELDS:
                print("Unknown field")
                continue
            try:
                value = int(value)
            except ValueError:
                print("Value must be int")
                continue
            data[field] = value
            save(args.file, data)
            print(f"Set {field}={value}")
            continue
        print("Unknown command. Type 'help'.")


if __name__ == "__main__":
    main()
