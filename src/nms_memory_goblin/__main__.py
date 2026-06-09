"""Command-line entrypoint for nms-memory-goblin."""

from __future__ import annotations

import argparse
import time

from nms_memory_goblin.process import (
    ProcessNotFoundError,
    ProcessOpenError,
    ProcessReadError,
    ProcessWriteError,
    attach_to_process,
    open_process,
    read_process_bytes,
    write_process_bytes,
)
from nms_memory_goblin.scanner import (
    ValueType,
    decode_value,
    encode_value,
    read_saved_values,
    rescan_value,
    select_saved_address,
    scan_value,
    write_saved_value,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nms-memory-goblin",
        description="No Man's Sky memory helper.",
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

    write_parser = subparsers.add_parser(
        "write",
        help="Write a new integer value to a saved scan address.",
        description="Write a new integer value to a saved scan address.",
    )
    write_parser.add_argument("label", help="Saved scan label, such as units or nanites.")
    write_parser.add_argument("value", type=int, help="New integer value to write.")
    write_parser.add_argument(
        "--process",
        default="NMS.exe",
        help="Process executable name to attach to. Defaults to NMS.exe.",
    )
    write_parser.add_argument(
        "--address",
        type=_parse_int_address,
        help="Exact address to write (for example 0x1234ABCD).",
    )
    write_parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Address index from saved candidates when --address is not provided. Defaults to 0.",
    )
    write_parser.set_defaults(handler=handle_write)

    freeze_parser = subparsers.add_parser(
        "freeze",
        help="Continuously write a value to a saved scan address.",
        description="Continuously write a value to a saved scan address.",
    )
    freeze_parser.add_argument("label", help="Saved scan label, such as units or nanites.")
    freeze_parser.add_argument("value", type=int, help="Integer value to keep writing.")
    freeze_parser.add_argument(
        "--process",
        default="NMS.exe",
        help="Process executable name to attach to. Defaults to NMS.exe.",
    )
    freeze_parser.add_argument(
        "--address",
        type=_parse_int_address,
        help="Exact address to freeze (for example 0x1234ABCD).",
    )
    freeze_parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Address index from saved candidates when --address is not provided. Defaults to 0.",
    )
    freeze_parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="Seconds between writes. Defaults to 0.1.",
    )
    freeze_parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of writes. Defaults to 0, meaning run until interrupted.",
    )
    freeze_parser.set_defaults(handler=handle_freeze)

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


def handle_write(args: argparse.Namespace) -> int:
    if args.index < 0:
        print("--index must be 0 or greater.")
        return 1

    try:
        result = write_saved_value(
            args.process,
            args.label,
            args.value,
            address=args.address,
            index=args.index,
        )
    except FileNotFoundError as exc:
        print(f"{exc} Run scan first.")
        return 1
    except ValueError as exc:
        print(str(exc))
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
    except ProcessWriteError as exc:
        print(str(exc))
        return 1

    print(f"Label: {result.label}")
    print(f"Process name: {result.process_name}")
    print(f"Address: 0x{result.address:X}")
    print(f"Wrote value: {result.value} ({result.value_type})")
    print("Verification: read-back matched")
    return 0


def handle_freeze(args: argparse.Namespace) -> int:
    if args.index < 0:
        print("--index must be 0 or greater.")
        return 1
    if args.interval <= 0:
        print("--interval must be greater than 0.")
        return 1
    if args.count < 0:
        print("--count must be 0 or greater.")
        return 1

    writes = 0
    try:
        selected = select_saved_address(args.label, address=args.address, index=args.index)
        encoded_value = encode_value(args.value, selected.value_type)

        with open_process(args.process) as process:
            while args.count == 0 or writes < args.count:
                write_process_bytes(process, selected.address, encoded_value)
                writes += 1
                if args.count == 0 or writes < args.count:
                    time.sleep(args.interval)

            read_back = read_process_bytes(process, selected.address, len(encoded_value))
    except KeyboardInterrupt:
        print(f"\nFreeze stopped after {writes} writes.")
        return 0
    except FileNotFoundError as exc:
        print(f"{exc} Run scan first.")
        return 1
    except ValueError as exc:
        print(str(exc))
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
    except ProcessWriteError as exc:
        print(str(exc))
        return 1
    except ProcessReadError as exc:
        print(str(exc))
        return 1

    if decode_value(read_back, selected.value_type) != args.value:
        print(f"Verification failed at 0x{selected.address:X}; value did not persist")
        return 1

    print(f"Label: {selected.label}")
    print(f"Process name: {args.process}")
    print(f"Address: 0x{selected.address:X}")
    print(f"Frozen value: {args.value} ({selected.value_type})")
    print(f"Writes: {writes}")
    print("Verification: read-back matched")
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


def _parse_int_address(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid address: {value!r}") from exc


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
