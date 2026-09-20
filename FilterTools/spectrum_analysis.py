"""Analyze FFT amplitude and Welch PSD for two channels in a CSV file."""

import argparse
import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
import numpy as np


LOG = logging.getLogger(__name__)
DEFAULT_SAMPLE_RATE_HZ = 500.0
DEFAULT_CHANNELS = ("ch1_raw", "ch2_raw")
MINIMUM_SAMPLE_COUNT = 8


@dataclass(frozen=True)
class ChannelData:
    """Two synchronized channels and their effective sample rate."""

    channel_1: np.ndarray
    channel_2: np.ndarray
    sample_rate_hz: float


@dataclass(frozen=True)
class Spectrum:
    """Frequency axis and values for two channels."""

    frequency_hz: np.ndarray
    channel_1: np.ndarray
    channel_2: np.ndarray


def infer_sample_rate(elapsed_ms: list[float]) -> float:
    """Infer sample rate from positive adjacent elapsed-time intervals."""
    intervals = [
        end - start
        for start, end in zip(elapsed_ms, elapsed_ms[1:])
        if end > start
    ]
    if not intervals:
        return DEFAULT_SAMPLE_RATE_HZ
    interval_ms = median(intervals)
    if interval_ms <= 0.0:
        return DEFAULT_SAMPLE_RATE_HZ
    return 1000.0 / interval_ms


def load_channels(
    csv_path: Path,
    channel_names: tuple[str, str],
    sample_rate_hz: float | None,
) -> ChannelData:
    """Read valid synchronized channel rows and determine the sample rate."""
    values_1 = []
    values_2 = []
    elapsed_ms = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("CSV file has no header")

        missing = set(channel_names) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")

        has_elapsed_time = "elapsed_ms" in reader.fieldnames
        for row in reader:
            try:
                value_1 = float(row[channel_names[0]])
                value_2 = float(row[channel_names[1]])
            except (KeyError, TypeError, ValueError):
                continue
            if not np.isfinite(value_1) or not np.isfinite(value_2):
                continue
            values_1.append(value_1)
            values_2.append(value_2)
            if has_elapsed_time:
                try:
                    elapsed = float(row["elapsed_ms"])
                    if np.isfinite(elapsed):
                        elapsed_ms.append(elapsed)
                except (KeyError, TypeError, ValueError):
                    pass

    if len(values_1) < MINIMUM_SAMPLE_COUNT:
        raise ValueError(
            f"At least {MINIMUM_SAMPLE_COUNT} valid sample pairs are required; "
            f"found {len(values_1)}"
        )

    effective_rate = sample_rate_hz
    if effective_rate is None:
        effective_rate = infer_sample_rate(elapsed_ms)
    if effective_rate <= 0.0:
        raise ValueError("Sample rate must be greater than zero")

    return ChannelData(
        channel_1=np.asarray(values_1, dtype=np.float64),
        channel_2=np.asarray(values_2, dtype=np.float64),
        sample_rate_hz=effective_rate,
    )


def fft_amplitude(values: np.ndarray, sample_rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """Return the one-sided Hann-windowed FFT amplitude spectrum."""
    centered = values - np.mean(values)
    window = np.hanning(len(centered))
    frequency_hz = np.fft.rfftfreq(len(centered), d=1.0 / sample_rate_hz)
    amplitude = np.abs(np.fft.rfft(centered * window)) / np.sum(window)

    if len(amplitude) > 1:
        last = -1 if len(centered) % 2 == 0 else None
        amplitude[1:last] *= 2.0
    return frequency_hz, amplitude


def welch_psd(
    values: np.ndarray,
    sample_rate_hz: float,
    segment_length: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate one-sided power spectral density using 50%-overlap Welch averaging."""
    segment_length = min(segment_length, len(values))
    if segment_length < MINIMUM_SAMPLE_COUNT:
        raise ValueError(f"Welch segment length must be at least {MINIMUM_SAMPLE_COUNT}")

    step = max(segment_length // 2, 1)
    starts = range(0, len(values) - segment_length + 1, step)
    window = np.hanning(segment_length)
    scale = sample_rate_hz * np.sum(window**2)
    accumulated = None
    segment_count = 0

    for start in starts:
        segment = values[start : start + segment_length]
        segment = (segment - np.mean(segment)) * window
        density = np.abs(np.fft.rfft(segment)) ** 2 / scale
        if len(density) > 1:
            last = -1 if segment_length % 2 == 0 else None
            density[1:last] *= 2.0
        accumulated = density if accumulated is None else accumulated + density
        segment_count += 1

    frequency_hz = np.fft.rfftfreq(segment_length, d=1.0 / sample_rate_hz)
    return frequency_hz, accumulated / segment_count


def analyze(data: ChannelData, segment_length: int) -> tuple[Spectrum, Spectrum]:
    """Calculate FFT amplitude and PSD for both channels."""
    fft_frequency, fft_1 = fft_amplitude(data.channel_1, data.sample_rate_hz)
    _, fft_2 = fft_amplitude(data.channel_2, data.sample_rate_hz)
    psd_frequency, psd_1 = welch_psd(
        data.channel_1, data.sample_rate_hz, segment_length
    )
    _, psd_2 = welch_psd(data.channel_2, data.sample_rate_hz, segment_length)
    return (
        Spectrum(fft_frequency, fft_1, fft_2),
        Spectrum(psd_frequency, psd_1, psd_2),
    )


def write_spectrum_csv(
    output_path: Path,
    spectrum: Spectrum,
    value_names: tuple[str, str],
) -> None:
    """Write one spectrum to a CSV file."""
    with output_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(("frequency_hz", *value_names))
        writer.writerows(
            zip(spectrum.frequency_hz, spectrum.channel_1, spectrum.channel_2)
        )


def plot_spectra(
    output_path: Path,
    source_name: str,
    channel_names: tuple[str, str],
    fft: Spectrum,
    psd: Spectrum,
    max_frequency_hz: float,
    show: bool,
) -> None:
    """Save the FFT and PSD overview and optionally show it interactively."""
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    figure.suptitle(f"Two-channel spectrum - {source_name}")

    axes[0].plot(fft.frequency_hz, fft.channel_1, linewidth=0.9, label=channel_names[0])
    axes[0].plot(fft.frequency_hz, fft.channel_2, linewidth=0.9, label=channel_names[1])
    axes[0].set_ylabel("FFT amplitude")

    positive_1 = np.maximum(psd.channel_1, np.finfo(float).tiny)
    positive_2 = np.maximum(psd.channel_2, np.finfo(float).tiny)
    axes[1].semilogy(psd.frequency_hz, positive_1, linewidth=0.9, label=channel_names[0])
    axes[1].semilogy(psd.frequency_hz, positive_2, linewidth=0.9, label=channel_names[1])
    axes[1].set_ylabel("PSD (unit^2/Hz)")
    axes[1].set_xlabel("Frequency (Hz)")

    for axis in axes:
        axis.set_xlim(0.0, max_frequency_hz)
        axis.grid(True, alpha=0.3)
        axis.legend()

    figure.savefig(output_path, dpi=160)
    if show:
        plt.show()
    plt.close(figure)


def dominant_frequency(spectrum: Spectrum, values: np.ndarray) -> float:
    """Return the strongest non-DC frequency in a spectrum."""
    if len(values) <= 1:
        return 0.0
    return float(spectrum.frequency_hz[1 + int(np.argmax(values[1:]))])


def choose_csv() -> Path | None:
    """Open a native file picker when no input path is supplied."""
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askopenfilename(
        title="Select a two-channel CSV file",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
    )
    root.destroy()
    return Path(selected) if selected else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate FFT amplitude and Welch PSD for two CSV channels."
    )
    parser.add_argument("csv_file", nargs="?", type=Path, help="input CSV file")
    parser.add_argument(
        "--channels",
        nargs=2,
        default=DEFAULT_CHANNELS,
        metavar=("CH1", "CH2"),
        help="channel column names (default: ch1_raw ch2_raw)",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        metavar="HZ",
        help="override sample rate; otherwise infer it from elapsed_ms or use 500 Hz",
    )
    parser.add_argument(
        "--segment-length",
        type=int,
        default=2048,
        metavar="N",
        help="Welch PSD segment length (default: 2048, limited by sample count)",
    )
    parser.add_argument(
        "--max-frequency",
        type=float,
        metavar="HZ",
        help="plot upper frequency limit (default: Nyquist frequency)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="output directory (default: <CSV name>_spectrum beside input)",
    )
    parser.add_argument("--show", action="store_true", help="also open the result plot")
    return parser.parse_args()


def run(args: argparse.Namespace) -> Path | None:
    """Run analysis from parsed command-line arguments."""
    csv_path = args.csv_file or choose_csv()
    if csv_path is None:
        return None
    csv_path = csv_path.resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if args.segment_length < MINIMUM_SAMPLE_COUNT:
        raise ValueError(f"Segment length must be at least {MINIMUM_SAMPLE_COUNT}")

    channel_names = tuple(args.channels)
    data = load_channels(csv_path, channel_names, args.sample_rate)
    fft, psd = analyze(data, args.segment_length)

    nyquist_hz = data.sample_rate_hz / 2.0
    max_frequency_hz = (
        args.max_frequency if args.max_frequency is not None else nyquist_hz
    )
    if not 0.0 < max_frequency_hz <= nyquist_hz:
        raise ValueError(
            f"Maximum frequency must be in (0, {nyquist_hz:g}] Hz"
        )

    output_dir = args.output_dir or csv_path.with_name(f"{csv_path.stem}_spectrum")
    output_dir.mkdir(parents=True, exist_ok=True)
    fft_path = output_dir / "fft.csv"
    psd_path = output_dir / "psd.csv"
    plot_path = output_dir / "spectrum.png"
    write_spectrum_csv(
        fft_path,
        fft,
        (f"{channel_names[0]}_amplitude", f"{channel_names[1]}_amplitude"),
    )
    write_spectrum_csv(
        psd_path,
        psd,
        (f"{channel_names[0]}_psd", f"{channel_names[1]}_psd"),
    )
    plot_spectra(
        plot_path,
        csv_path.name,
        channel_names,
        fft,
        psd,
        max_frequency_hz,
        args.show,
    )

    LOG.info("Loaded %d sample pairs at %.6g Hz", len(data.channel_1), data.sample_rate_hz)
    LOG.info(
        "Dominant FFT frequencies: %s=%.6g Hz, %s=%.6g Hz",
        channel_names[0],
        dominant_frequency(fft, fft.channel_1),
        channel_names[1],
        dominant_frequency(fft, fft.channel_2),
    )
    LOG.info("Results written to %s", output_dir)
    return output_dir


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run(parse_args())
    except (OSError, ValueError) as error:
        LOG.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
