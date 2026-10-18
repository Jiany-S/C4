"""Execute all notebook cells in a fresh project-venv kernel, without paid calls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="c4-kernel-") as tmp:
    kernel_dir = Path(tmp) / "kernels" / "c4-verify"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "kernel.json").write_text(json.dumps({"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "C4 verification", "language": "python"}))
    os.environ["JUPYTER_PATH"] = tmp
    os.environ["RUN_LIVE"] = "false"
    os.environ["RUN_UI"] = "false"
    notebook = nbformat.read(ROOT / "react_agent.ipynb", as_version=4)
    NotebookClient(notebook, timeout=180, kernel_name="c4-verify", resources={"metadata": {"path": str(ROOT)}}).execute()
    nbformat.write(notebook, ROOT / "react_agent.ipynb")
    summary = {"mode": "fresh kernel; actual Python/SDK/Gradio imports, MOCK model tests",
        "code_cells_executed": sum(c.cell_type == 'code' for c in notebook.cells),
        "live_api_in_notebook": "disabled", "ui_server_in_notebook": "disabled", "status": "PASS"}
    (ROOT / 'evidence/notebook_execution.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
