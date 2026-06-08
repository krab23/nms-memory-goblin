# nms-memory-goblin

Early project skeleton for a No Man's Sky memory utility.

Attach and read-only exact-value scanning are implemented. Writing, freezing,
injection, patching, DLL loading, stealth behavior, anti-cheat bypasses, and
memory modification are not implemented.

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
python -m nms_memory_goblin watch units nanites --count 5
```

Scan results are saved locally in `.nms-memory-goblin\scan-results.json` so a
later `rescan` can filter the previous candidate addresses against the same or a
different value. The `watch` command reads those saved addresses repeatedly and
prints their current values.
