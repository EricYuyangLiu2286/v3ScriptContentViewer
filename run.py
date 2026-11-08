"""Run v3tree without installing:  python run.py <command>   (see python run.py --help)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from v3tree.cli import main  # noqa: E402

sys.exit(main())
