"""Exact value scanning and saved-address value writing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from nms_memory_goblin.process import (
    ProcessReadError,
    ProcessWriteError,
    iter_readable_regions,
    open_process,
    read_process_bytes,
    write_process_bytes,
)

ValueType = Literal["uint32", "int32", "uint64", "int64"]

STATE_DIR = Path(".nms-memory-goblin")
STATE_FILE = STATE_DIR / "scan-results.json"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ScanResult:
    label: str
    process_name: str
    value: int
    value_type: ValueType
    addresses: list[int]


@dataclass(frozen=True)
class WriteResult:
    label: str
    process_name: str
    address: int
    value: int
    value_type: ValueType


@dataclass(frozen=True)
class SelectedAddress:
    label: str
    address: int
    value_type: ValueType


def scan_value(process_name: str, label: str, value: int, value_type: ValueType) -> ScanResult:
    pattern = encode_value(value, value_type)
    addresses: list[int] = []

    with open_process(process_name) as process:
        for region in iter_readable_regions(process):
            addresses.extend(_scan_region(process, region.base_address, region.size, pattern))

    result = ScanResult(
        label=label,
        process_name=process_name,
        value=value,
        value_type=value_type,
        addresses=addresses,
    )
    save_scan_result(result)
    return result


def rescan_value(process_name: str, label: str, value: int, value_type: ValueType) -> ScanResult:
    previous = load_scan_result(label)
    pattern = encode_value(value, value_type)
    addresses: list[int] = []

    with open_process(process_name) as process:
        for address in previous.addresses:
            try:
                data = read_process_bytes(process, address, len(pattern))
            except ProcessReadError:
                continue
            if data == pattern:
                addresses.append(address)

    result = ScanResult(
        label=label,
        process_name=process_name,
        value=value,
        value_type=value_type,
        addresses=addresses,
    )
    save_scan_result(result)
    return result


def read_saved_values(process_name: str, labels: list[str]) -> dict[str, list[tuple[int, int | None]]]:
    results = load_scan_results(labels)
    values: dict[str, list[tuple[int, int | None]]] = {}

    with open_process(process_name) as process:
        for result in results:
            value_size = len(encode_value(result.value, result.value_type))
            label_values: list[tuple[int, int | None]] = []
            for address in result.addresses:
                try:
                    data = read_process_bytes(process, address, value_size)
                except ProcessReadError:
                    label_values.append((address, None))
                    continue
                label_values.append((address, decode_value(data, result.value_type)))
            values[result.label] = label_values

    return values


def write_saved_value(
    process_name: str,
    label: str,
    value: int,
    address: int | None = None,
    index: int = 0,
) -> WriteResult:
    selected = select_saved_address(label, address=address, index=index)
    encoded_value = encode_value(value, selected.value_type)

    with open_process(process_name) as process:
        write_process_bytes(process, selected.address, encoded_value)
        try:
            read_back = read_process_bytes(process, selected.address, len(encoded_value))
        except ProcessReadError as exc:
            raise ProcessWriteError(
                f"Wrote value, but could not verify read at 0x{selected.address:X}"
            ) from exc

    if decode_value(read_back, selected.value_type) != value:
        raise ProcessWriteError(
            f"Verification failed at 0x{selected.address:X}; value did not persist"
        )

    return WriteResult(
        label=selected.label,
        process_name=process_name,
        address=selected.address,
        value=value,
        value_type=selected.value_type,
    )


def select_saved_address(label: str, address: int | None = None, index: int = 0) -> SelectedAddress:
    result = load_scan_result(label)

    if not result.addresses:
        raise ValueError(f"No saved addresses for {label!r}.")
    if index < 0:
        raise ValueError("index must be 0 or greater")

    selected_address = _resolve_address(result.addresses, address, index)
    return SelectedAddress(
        label=result.label,
        address=selected_address,
        value_type=result.value_type,
    )


def encode_value(value: int, value_type: ValueType) -> bytes:
    if value_type == "uint32":
        return value.to_bytes(4, byteorder="little", signed=False)
    if value_type == "int32":
        return value.to_bytes(4, byteorder="little", signed=True)
    if value_type == "uint64":
        return value.to_bytes(8, byteorder="little", signed=False)
    if value_type == "int64":
        return value.to_bytes(8, byteorder="little", signed=True)
    raise ValueError(f"Unsupported value type: {value_type}")


def decode_value(data: bytes, value_type: ValueType) -> int:
    if value_type == "uint32":
        return int.from_bytes(data[:4], byteorder="little", signed=False)
    if value_type == "int32":
        return int.from_bytes(data[:4], byteorder="little", signed=True)
    if value_type == "uint64":
        return int.from_bytes(data[:8], byteorder="little", signed=False)
    if value_type == "int64":
        return int.from_bytes(data[:8], byteorder="little", signed=True)
    raise ValueError(f"Unsupported value type: {value_type}")


def save_scan_result(result: ScanResult) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    state[_clean_label(result.label)] = {
        "label": result.label,
        "process_name": result.process_name,
        "value": result.value,
        "value_type": result.value_type,
        "addresses": [f"0x{address:X}" for address in result.addresses],
    }
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def load_scan_results(labels: list[str] | None = None) -> list[ScanResult]:
    state = _load_state()
    if not state:
        raise FileNotFoundError("No saved scan results.")

    if labels:
        return [load_scan_result(label) for label in labels]

    return [_scan_result_from_state_item(item) for item in state.values()]


def load_scan_result(label: str) -> ScanResult:
    state = _load_state()
    key = _clean_label(label)
    if key not in state:
        raise FileNotFoundError(f"No previous scan results for {label!r}.")

    return _scan_result_from_state_item(state[key])


def _scan_result_from_state_item(item: object) -> ScanResult:
    if not isinstance(item, dict):
        raise ValueError("Invalid scan result state.")

    return ScanResult(
        label=str(item["label"]),
        process_name=str(item["process_name"]),
        value=int(item["value"]),
        value_type=str(item["value_type"]),  # type: ignore[arg-type]
        addresses=[int(address, 16) for address in item["addresses"]],
    )


def _scan_region(process: object, base_address: int, region_size: int, pattern: bytes) -> list[int]:
    addresses: list[int] = []
    overlap = max(len(pattern) - 1, 0)
    offset = 0
    previous_tail = b""

    while offset < region_size:
        read_size = min(CHUNK_SIZE, region_size - offset)
        address = base_address + offset
        try:
            data = read_process_bytes(process, address, read_size)
        except ProcessReadError:
            previous_tail = b""
            offset += read_size
            continue

        searchable = previous_tail + data
        chunk_base = address - len(previous_tail)
        addresses.extend(_find_pattern_addresses(searchable, pattern, chunk_base))
        previous_tail = data[-overlap:] if overlap else b""
        offset += read_size

    return addresses


def _find_pattern_addresses(data: bytes, pattern: bytes, base_address: int) -> Iterable[int]:
    start = 0
    while True:
        index = data.find(pattern, start)
        if index == -1:
            break
        yield base_address + index
        start = index + 1


def _resolve_address(addresses: list[int], address: int | None, index: int) -> int:
    if address is not None:
        if address in addresses:
            return address
        raise ValueError(
            f"Address 0x{address:X} is not in saved candidates ({len(addresses)} total)."
        )

    if len(addresses) == 1:
        return addresses[0]
    if index >= len(addresses):
        raise ValueError(f"index {index} is out of range for {len(addresses)} candidates")
    return addresses[index]


def _load_state() -> dict[str, object]:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _clean_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", label.strip().lower())
    return cleaned.strip("-") or "value"
