# nms-memory-goblin

Early project skeleton for a future No Man's Sky memory utility.

Memory scanning is not implemented yet, and memory-related dependencies such as
`pymem` are intentionally not installed at this stage.

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
```
