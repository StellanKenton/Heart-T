"""Find and plot a CSV channel's Welch PSD peak in a frequency band."""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import welch


DEFAULT_SAMPLE_RATE_HZ = 500.0
DEFAULT_MIN_FREQUENCY_HZ = 45.0
DEFAULT_MAX_FREQUENCY_HZ = 55.0
MINIMUM_SAMPLE_COUNT = 10
CHANNEL_COLUMNS = {
    "ch1": "ch1_raw",
    "ch2": "ch2_raw",
    "ch3": "ch3",
    "ch4": "ch4",
}


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
    """Ask for ch1, ch2, ch3, or ch4 when no selection is given."""
    from tkinter import Tk, simpledialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = simpledialog.askinteger(
        "Select channel",
        "Select channel (1 = ch1, 2 = ch2, 3 = ch3, 4 = ch4):",
        minvalue=1,
        maxvalue=4,
        parent=root,
    )
    root.destroy()
    return f"ch{selected}" if selected is not None else None


def load_channel(csv_path: Path, column: str) -> np.ndarray:
    """Load finite channel samples from a CSV file."""
    samples = []
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
            if np.isfinite(sample):
                samples.append(sample)

    if len(samples) < MINIMUM_SAMPLE_COUNT:
        raise ValueError(
            f"Column '{column}' must contain at least {MINIMUM_SAMPLE_COUNT} valid samples"
        )
    return np.asarray(samples, dtype=np.float64)


def find_peak(
    samples: np.ndarray,
    sample_rate: float,
    min_frequency: float,
    max_frequency: float,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Calculate Welch PSD and return the strongest peak in the selected band."""
    frequency, psd = welch(
        samples,
        fs=sample_rate,
        nperseg=min(4096, len(samples)),
    )
    mask = (frequency >= min_frequency) & (frequency <= max_frequency)
    if not np.any(mask):
        raise ValueError(
            f"No PSD bins fall within {min_frequency:g}-{max_frequency:g} Hz; "
            f"Nyquist frequency is {sample_rate / 2.0:g} Hz"
        )

    band_psd = psd[mask]
    peak_index = int(np.argmax(band_psd))
    peak_frequency = float(frequency[mask][peak_index])
    peak_db = float(10 * np.log10(band_psd[peak_index] + 1e-20))
    return frequency, psd, peak_frequency, peak_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find a raw CSV channel's Welch PSD peak in a frequency band"
    )
    parser.add_argument("csv_file", nargs="?", type=Path, help="input CSV file")
    parser.add_argument(
        "--channel",
        choices=CHANNEL_COLUMNS,
        help="channel to analyze; opens a selection dialog when omitted",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=DEFAULT_SAMPLE_RATE_HZ,
        metavar="HZ",
        help=f"sample rate (default: {DEFAULT_SAMPLE_RATE_HZ:g} Hz)",
    )
    parser.add_argument(
        "--min-frequency",
        type=float,
        default=DEFAULT_MIN_FREQUENCY_HZ,
        metavar="HZ",
        help=f"lower search limit (default: {DEFAULT_MIN_FREQUENCY_HZ:g} Hz)",
    )
    parser.add_argument(
        "--max-frequency",
        type=float,
        default=DEFAULT_MAX_FREQUENCY_HZ,
        metavar="HZ",
        help=f"upper search limit (default: {DEFAULT_MAX_FREQUENCY_HZ:g} Hz)",
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
    if args.sample_rate <= 0:
        raise ValueError("Sample rate must be greater than zero")
    if args.min_frequency < 0 or args.max_frequency <= args.min_frequency:
        raise ValueError("Frequency limits must satisfy 0 <= min < max")

    column = CHANNEL_COLUMNS[channel]
    samples = load_channel(csv_path, column)
    frequency, psd, peak_frequency, peak_db = find_peak(
        samples,
        args.sample_rate,
        args.min_frequency,
        args.max_frequency,
    )

    print(f"Peak = {peak_frequency:.3f} Hz, {peak_db:.2f} dB/Hz")

    psd_db = 10 * np.log10(psd + 1e-20)
    plt.plot(frequency, psd_db, label=column)
    plt.axvspan(
        args.min_frequency,
        args.max_frequency,
        color="tab:orange",
        alpha=0.15,
        label="search band",
    )
    plt.scatter([peak_frequency], [peak_db], color="tab:red", zorder=3, label="peak")
    plt.xlim(0, min(max(100.0, args.max_frequency), args.sample_rate / 2.0))
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("PSD (dB/Hz)")
    plt.title(f"{column} - {csv_path.name} ({args.sample_rate:g} Hz, raw)")
    plt.grid()
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()
