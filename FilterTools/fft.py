"""Plot the Welch PSD of ch1 or ch2 from a CSV file."""

import argparse
import csv
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import welch


DEFAULT_SAMPLE_RATE_HZ = 500.0
CHANNEL_COLUMNS = {"ch1": "ch1_raw", "ch2": "ch2_raw"}


def choose_csv() -> Path | None:
    """Open a file picker when no CSV path is given."""
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askopenfilename(
        title="Select CSV file",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
    )
    root.destroy()
    return Path(selected) if selected else None


def choose_channel() -> str | None:
    """Ask for ch1 or ch2 when no command-line selection is given."""
    from tkinter import Tk, simpledialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = simpledialog.askinteger(
        "Select channel",
        "Select channel (1 = ch1, 2 = ch2):",
        minvalue=1,
        maxvalue=2,
        parent=root,
    )
    root.destroy()
    return f"ch{selected}" if selected is not None else None


def infer_sample_rate(elapsed_ms: list[float]) -> float:
    """Infer sample rate from the median positive time interval."""
    intervals = [
        end - start
        for start, end in zip(elapsed_ms, elapsed_ms[1:])
        if end > start
    ]
    return 1000.0 / median(intervals) if intervals else DEFAULT_SAMPLE_RATE_HZ


def load_channel(csv_path: Path, column: str) -> tuple[np.ndarray, list[float]]:
    """Load finite channel samples and their elapsed times."""
    samples = []
    elapsed_ms = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames or column not in reader.fieldnames:
            available = ", ".join(reader.fieldnames or []) or "none"
            raise ValueError(f"Missing column '{column}'; available columns: {available}")

        for row in reader:
            try:
                sample = float(row[column])
            except (TypeError, ValueError):
                continue
            if not np.isfinite(sample):
                continue
            samples.append(sample)

            try:
                elapsed = float(row.get("elapsed_ms", ""))
            except (TypeError, ValueError):
                continue
            if np.isfinite(elapsed):
                elapsed_ms.append(elapsed)

    if len(samples) < 2:
        raise ValueError(f"Column '{column}' must contain at least two valid samples")
    return np.asarray(samples, dtype=np.float64), elapsed_ms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot ch1 or ch2 PSD from CSV data")
    parser.add_argument("csv_file", nargs="?", type=Path, help="input CSV file")
    parser.add_argument(
        "--channel",
        choices=CHANNEL_COLUMNS,
        help="channel to analyze; opens a selection dialog when omitted",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        metavar="HZ",
        help="sample rate; defaults to elapsed_ms inference or 500 Hz",
    )
    parser.add_argument(
        "--max-frequency",
        type=float,
        default=100.0,
        metavar="HZ",
        help="maximum displayed frequency (default: 100 Hz)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = args.csv_file or choose_csv()
    if csv_path is None:
        return
    channel = args.channel or choose_channel()
    if channel is None:
        return
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if args.sample_rate is not None and args.sample_rate <= 0:
        raise ValueError("Sample rate must be greater than zero")
    if args.max_frequency <= 0:
        raise ValueError("Maximum frequency must be greater than zero")

    column = CHANNEL_COLUMNS[channel]
    samples, elapsed_ms = load_channel(csv_path, column)
    sample_rate = args.sample_rate or infer_sample_rate(elapsed_ms)
    frequency, psd = welch(
        samples,
        fs=sample_rate,
        nperseg=min(4096, len(samples)),
    )

    plt.plot(frequency, psd, label=column)
    plt.xlim(0, min(args.max_frequency, sample_rate / 2.0))
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("PSD")
    plt.title(f"{column} - {csv_path.name} ({sample_rate:g} Hz)")
    plt.grid()
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()
