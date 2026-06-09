"""Process attachment helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import pymem.memory
from pymem import Pymem
from pymem.exception import (
    CouldNotOpenProcess,
    MemoryReadError,
    MemoryWriteError,
    ProcessNotFound,
    PymemError,
    WinAPIError,
)
from pymem.ressources.structure import MEMORY_PROTECTION, MEMORY_STATE


class AttachError(Exception):
    """Base class for attach failures."""


class ProcessNotFoundError(AttachError):
    """Raised when the target process is not running."""


class ProcessOpenError(AttachError):
    """Raised when the target process exists but cannot be opened."""


class ProcessReadError(AttachError):
    """Raised when process memory cannot be read."""


class ProcessWriteError(AttachError):
    """Raised when process memory cannot be written."""


@dataclass(frozen=True)
class AttachedProcess:
    """Details for a successfully opened process."""

    name: str
    process_id: int
    process_handle: int


@dataclass(frozen=True)
class MemoryRegion:
    """Readable memory region details."""

    base_address: int
    size: int
    protection: int


@contextmanager
def open_process(process_name: str) -> Iterator[Pymem]:
    """Open a process by executable name and close its handle on exit."""

    try:
        process = Pymem(process_name)
    except ProcessNotFound as exc:
        raise ProcessNotFoundError(process_name) from exc
    except CouldNotOpenProcess as exc:
        raise ProcessOpenError(process_name) from exc
    except PymemError as exc:
        raise ProcessOpenError(process_name) from exc

    try:
        yield process
    finally:
        process.close_process()


def attach_to_process(process_name: str) -> AttachedProcess:
    """Attach to a running process by executable name."""

    with open_process(process_name) as process:
        return AttachedProcess(
            name=process_name,
            process_id=process.process_id,
            process_handle=process.process_handle,
        )


def iter_readable_regions(process: Pymem) -> Iterator[MemoryRegion]:
    """Yield committed, readable memory regions for an open process."""

    address = 0
    max_address = 0x7FFF_FFFF_FFFF

    while address < max_address:
        try:
            region = pymem.memory.virtual_query(process.process_handle, address)
        except WinAPIError:
            break

        base_address = int(region.BaseAddress)
        region_size = int(region.RegionSize)
        if region_size <= 0:
            address += 0x1000
            continue

        if _is_readable_region(int(region.State), int(region.Protect)):
            yield MemoryRegion(
                base_address=base_address,
                size=region_size,
                protection=int(region.Protect),
            )

        next_address = base_address + region_size
        if next_address <= address:
            address += 0x1000
        else:
            address = next_address


def read_process_bytes(process: Pymem, address: int, size: int) -> bytes:
    """Read bytes from an open process."""

    try:
        return process.read_bytes(address, size)
    except MemoryReadError as exc:
        raise ProcessReadError(f"Could not read {size} bytes at 0x{address:X}") from exc


def write_process_bytes(process: Pymem, address: int, data: bytes) -> None:
    """Write bytes to an open process."""

    try:
        process.write_bytes(address, data, len(data))
    except MemoryWriteError as exc:
        raise ProcessWriteError(f"Could not write {len(data)} bytes at 0x{address:X}") from exc


def _is_readable_region(state: int, protection: int) -> bool:
    if state != MEMORY_STATE.MEM_COMMIT.value:
        return False
    if protection & MEMORY_PROTECTION.PAGE_GUARD.value:
        return False
    if protection & MEMORY_PROTECTION.PAGE_NOACCESS.value:
        return False

    readable = {
        MEMORY_PROTECTION.PAGE_READONLY.value,
        MEMORY_PROTECTION.PAGE_READWRITE.value,
        MEMORY_PROTECTION.PAGE_WRITECOPY.value,
        MEMORY_PROTECTION.PAGE_EXECUTE_READ.value,
        MEMORY_PROTECTION.PAGE_EXECUTE_READWRITE.value,
        MEMORY_PROTECTION.PAGE_EXECUTE_WRITECOPY.value,
    }
    return bool(protection & sum(readable))
