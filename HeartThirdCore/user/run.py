"""Launch from any working directory with py -3 path/to/user/run.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    try:
        from user.main import main
    except ModuleNotFoundError as error:
        sys.stderr.write(f"Missing dependency: {error.name}. Run: py -3 -m pip install -r "
                         f'"{Path(__file__).resolve().parents[1] / "requirements.txt"}"\n')
        raise SystemExit(1)
    raise SystemExit(main())
