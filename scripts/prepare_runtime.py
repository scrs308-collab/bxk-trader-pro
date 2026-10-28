"""Run TLS checks and production migrations without migrating isolated staging."""
import subprocess
import sys
from start_runtime import isolated

def main():
    staging=isolated()
    subprocess.run([sys.executable,"scripts/check_tls_trust.py"]+([] if staging else ["--probe"]),check=True)
    if not staging:
        subprocess.run([sys.executable,"-m","alembic","upgrade","head"],check=True)

if __name__=="__main__":
    main()
