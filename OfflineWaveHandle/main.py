"""Start the offline CH2/CH4 ECG viewer."""

import argparse
from pathlib import Path
from tkinter import Tk, filedialog

from data import load_ecg
from waveform import show_waveforms


DEFAULT_DATA_DIR = Path(r"C:\Users\senki\Desktop\ECGDATA")


def choose_csv() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askopenfilename(
        title="Select ECG CSV file",
        initialdir=DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd(),
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
    )
    root.destroy()
    return Path(selected) if selected else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Display raw CH2 and filtered CH4 ECG waveforms")
    parser.add_argument("csv_file", nargs="?", type=Path, help="CSV file; omit to select one")
    parser.add_argument("--save", type=Path, metavar="IMAGE", help="Save an image instead of opening a window")
    args = parser.parse_args()
    source = args.csv_file or choose_csv()
    if source is None:
        return 0
    if not source.is_file():
        parser.error(f"CSV file not found: {source}")
    show_waveforms(load_ecg(source), source, args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
