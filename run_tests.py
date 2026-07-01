#!.venv/Scripts/python.exe
import subprocess
import sys
import os

def main():
    # Construct path to virtual environment python executable
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    cmd = [venv_python, "-m", "pytest", "tests/", "-v", "--ignore=tests/test_app.py"]
    
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
