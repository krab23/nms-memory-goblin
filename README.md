# nms-memory-goblin

Early project skeleton for a No Man's Sky memory utility.

Attach, exact-value scanning, and direct value writing are implemented.
Freezing, injection, patching, DLL loading, stealth behavior, and anti-cheat
bypasses are not implemented.

## PowerShell setup

Create and activate a project-local virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation, run only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

After activation, use `python`, not `py`, for project commands.

Install the project into the virtual environment:

```powershell
python -m pip install -e .
```

## Verify

```powershell
python -m nms_memory_goblin --help
python -m nms_memory_goblin attach
python -m nms_memory_goblin attach --process NMS.exe
python -m nms_memory_goblin scan units 169647079
python -m nms_memory_goblin scan nanites 793628
python -m nms_memory_goblin rescan units 169647079
python -m nms_memory_goblin rescan nanites 793628
python -m nms_memory_goblin write units 123456789 --index 0
python -m nms_memory_goblin write nanites 999999 --index 0
python -m nms_memory_goblin write nanites 999999 --address 0x1234ABCD
python -m nms_memory_goblin freeze units 123456789 --index 0 --interval 0.1
python -m nms_memory_goblin freeze nanites 999999 --index 0 --count 50 --interval 0.05
python -m nms_memory_goblin watch units nanites --count 5
```

Scan results are saved locally in `.nms-memory-goblin\scan-results.json` so a
later `rescan` can filter the previous candidate addresses against the same or a
different value. The `watch` command reads those saved addresses repeatedly and
prints their current values.

Use `write` after narrowing candidates with `rescan`.
- If there is one saved address, it writes that address.
- If there are multiple, pass `--index` (0-based) or `--address`.
- The command verifies writes by reading the value back immediately.

Use `freeze` to keep writing a value repeatedly.
- `--count 0` (default) runs until interrupted with Ctrl+C.
- Use `--interval` to control how often writes happen.
- With finite `--count`, the command verifies by reading the value back at the end.
