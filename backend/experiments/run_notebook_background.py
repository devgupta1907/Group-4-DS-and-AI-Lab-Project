"""Execute a notebook's code cells sequentially without nbconvert/nbclient."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from IPython.core.interactiveshell import InteractiveShell


async def execute(notebook_path: Path) -> None:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    os.chdir(notebook_path.parent)
    shell = InteractiveShell.instance()
    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    for index, cell in enumerate(code_cells, 1):
        print(f"[cell {index}/{len(code_cells)}] starting", flush=True)
        result = await shell.run_cell_async("".join(cell.get("source", [])), store_history=False)
        if result.error_before_exec is not None:
            raise result.error_before_exec
        if result.error_in_exec is not None:
            raise result.error_in_exec
        print(f"[cell {index}/{len(code_cells)}] complete", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    args = parser.parse_args()
    notebook_path = args.notebook.resolve()
    print(f"Executing {notebook_path}", flush=True)
    asyncio.run(execute(notebook_path))
    print("Notebook execution completed successfully.", flush=True)


if __name__ == "__main__":
    main()
