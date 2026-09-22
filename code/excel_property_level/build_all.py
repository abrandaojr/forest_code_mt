"""Build the property-level formula workbooks from the existing model outputs."""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run(name, env=None):
    subprocess.run([sys.executable, str(SCRIPTS / name)], check=True, env=env)


if __name__ == "__main__":
    run("build_inputs.py")
    for part in range(1, 12):
        env = os.environ.copy()
        env["FC_PART"] = str(part)
        env["FC_PART_SIZE"] = "16000"
        run("build_formula_excel.py", env)
    run("verify_excels.py")
