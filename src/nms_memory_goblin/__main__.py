"""Command-line entrypoint for nms-memory-goblin."""

from __future__ import annotations

import argparse
import time

from nms_memory_goblin.process import (
    ProcessNotFoundError,
    ProcessOpenError,
    attach_to_process,
)
from nms_memory_goblin.scanner import ValueType, read_saved_values, rescan_value, scan_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nms-memory-goblin",
        description="Read-only No Man's Sky memory helper.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="nms-memory-goblin 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command")
    attach_parser = subparsers.add_parser(
        "attach",
        help="Attach to the game process and print process details.",
        description="Attach to the game process and print process details.",
    )
    attach_parser.add_argument(
        "--process",
        default="NMS.exe",
        help="Process executable name to attach to. Defaults to NMS.exe.",
    )
    attach_parser.set_defaults(handler=handle_attach)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan readable memory for an exact integer value.",
        description="Scan readable memory for an exact integer value.",
    )
    add_scan_arguments(scan_parser)
    scan_parser.set_defaults(handler=handle_scan)

    rescan_parser = subparsers.add_parser(
        "rescan",
        help="Filter previous scan results against a new exact integer value.",
        description="Filter previous scan results against a new exact integer value.",
    )
    add_scan_arguments(rescan_parser)
    rescan_parser.set_defaults(handler=handle_rescan)

    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch saved scan result addresses.",
        description="Watch saved scan result addresses.",
    )
    watch_parser.add_argument(
        "labels",
        nargs="*",
        help="Saved labels to watch. Defaults to all saved labels.",
    )
    watch_parser.add_argument(
        "--process",
        default="NMS.exe",
        help="Process executable name to attach to. Defaults to NMS.exe.",
    )
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between reads. Defaults to 1.0.",
    )
    watch_parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of snapshots to print. Defaults to 0, meaning run until interrupted.",
    )
    watch_parser.set_defaults(handler=handle_watch)

    return parser


def add_scan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("label", help="Name for this value, such as units or nanites.")
    parser.add_argument("value", type=int, help="Exact integer value to scan for.")
    parser.add_argument(
        "--process",
        default="NMS.exe",
        help="Process executable name to attach to. Defaults to NMS.exe.",
    )
    parser.add_argument(
        "--value-type",
        choices=["uint32", "int32", "uint64", "int64"],
        default="uint32",
        help="Integer representation to scan for. Defaults to uint32.",
    )
    parser.add_argument(
        "--max-addresses",
        type=int,
        default=20,
        help="Maximum candidate addresses to print. Defaults to 20.",
    )


def handle_attach(args: argparse.Namespace) -> int:
    try:
        attached_process = attach_to_process(args.process)
    except ProcessNotFoundError:
        print(f"Could not find {args.process}. Please start the game and try again.")
        return 1
    except ProcessOpenError:
        print(
            f"Could not open {args.process}. Try running PowerShell as Administrator, "
            "then run the command again."
        )
        return 1

    print(f"Process name: {attached_process.name}")
    print(f"Process ID: {attached_process.process_id}")
    print(f"Process handle: {attached_process.process_handle}")
    return 0


def handle_scan(args: argparse.Namespace) -> int:
    try:
        result = scan_value(args.process, args.label, args.value, _value_type(args.value_type))
    except ProcessNotFoundError:
        print(f"Could not find {args.process}. Please start the game and try again.")
        return 1
    except ProcessOpenError:
        print(
            f"Could not open {args.process}. Try running PowerShell as Administrator, "
            "then run the command again."
        )
        return 1

    print(f"Label: {result.label}")
    print(f"Process name: {result.process_name}")
    print(f"Value: {result.value} ({result.value_type})")
    print(f"Matches: {len(result.addresses)}")
    print_addresses(result.addresses, args.max_addresses)
    print("Saved results: .nms-memory-goblin\\scan-results.json")
    return 0


def handle_rescan(args: argparse.Namespace) -> int:
    try:
        result = rescan_value(args.process, args.label, args.value, _value_type(args.value_type))
    except FileNotFoundError:
        print(f"No previous scan results for {args.label}. Run scan first.")
        return 1
    except ProcessNotFoundError:
        print(f"Could not find {args.process}. Please start the game and try again.")
        return 1
    except ProcessOpenError:
        print(
            f"Could not open {args.process}. Try running PowerShell as Administrator, "
            "then run the command again."
        )
        return 1

    print(f"Label: {result.label}")
    print(f"Process name: {result.process_name}")
    print(f"Value: {result.value} ({result.value_type})")
    print(f"Remaining matches: {len(result.addresses)}")
    print_addresses(result.addresses, args.max_addresses)
    print("Saved results: .nms-memory-goblin\\scan-results.json")
    return 0


def handle_watch(args: argparse.Namespace) -> int:
    if args.interval <= 0:
        print("--interval must be greater than 0.")
        return 1
    if args.count < 0:
        print("--count must be 0 or greater.")
        return 1

    iteration = 0
    try:
        while args.count == 0 or iteration < args.count:
            iteration += 1
            values = read_saved_values(args.process, args.labels)
            print_watch_snapshot(iteration, values)
            if args.count == 0 or iteration < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nWatch stopped.")
        return 0
    except FileNotFoundError as exc:
        print(f"{exc} Run scan first.")
        return 1
    except ProcessNotFoundError:
        print(f"Could not find {args.process}. Please start the game and try again.")
        return 1
    except ProcessOpenError:
        print(
            f"Could not open {args.process}. Try running PowerShell as Administrator, "
            "then run the command again."
        )
        return 1

    return 0


def print_watch_snapshot(iteration: int, values: dict[str, list[tuple[int, int | None]]]) -> None:
    print(f"Snapshot {iteration}")
    for label, address_values in values.items():
        print(f"{label}:")
        for address, value in address_values:
            value_text = "<unreadable>" if value is None else str(value)
            print(f"  0x{address:X}: {value_text}")


def print_addresses(addresses: list[int], max_addresses: int) -> None:
    if max_addresses <= 0 or not addresses:
        return

    print("Candidate addresses:")
    for address in addresses[:max_addresses]:
        print(f"  0x{address:X}")
    remaining = len(addresses) - max_addresses
    if remaining > 0:
        print(f"  ... {remaining} more")


def _value_type(value_type: str) -> ValueType:
    return value_type  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
