"""Load and process raw ECG channel data from CSV files."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, iirnotch, sosfiltfilt


CHANNEL_1_NAME = "ch1_raw"
CHANNEL_2_NAME = "ch2_raw"
DEFAULT_SAMPLE_RATE_HZ = 500.0
BANDPASS_LOW_HZ = 0.5
BANDPASS_HIGH_HZ = 40.0
BANDPASS_ORDER = 4


def detect_r_peaks(ecg, fs: float = DEFAULT_SAMPLE_RATE_HZ) -> np.ndarray:
    """Detect R peaks in a filtered ECG signal."""
    if fs <= 0.0:
        raise ValueError("Sample rate must be greater than zero")

    x = np.asarray(ecg, dtype=np.float64)
    if x.size == 0:
        return np.asarray([], dtype=np.int64)

    # Remove the overall DC offset before peak detection.
    x = x - np.median(x)

    # Keep R peaks at least 300 ms apart (about 200 bpm maximum).
    min_distance = max(int(0.30 * fs), 1)

    # Use the median absolute deviation as a robust noise estimate.
    median = np.median(x)
    mad = np.median(np.abs(x - median))
    prominence = max(3.0 * mad, 1.0)

    peaks, _ = find_peaks(
        x,
        distance=min_distance,
        prominence=prominence,
    )
    return peaks


def calculate_heart_rate(r_times: np.ndarray) -> float | None:
    """Return the average heart rate in bpm from R-peak times."""
    if len(r_times) < 2:
        return None

    rr_intervals = np.diff(r_times)
    valid_intervals = rr_intervals[rr_intervals > 0.0]
    if valid_intervals.size == 0:
        return None
    return float(60.0 / np.mean(valid_intervals))


@dataclass(frozen=True)
class ShowPlotData:
    """All processed channel data required by the waveform UI."""

    times: list[float]
    xLabel: str
    showPlotCh1: list[float]
    showPlotCh2: list[float]
    showPlotCh3: list[float]
    showPlotCh4: list[float]


def export_processed_channels(
    csv_path: Path, channel_3: list[float], channel_4: list[float]
) -> None:
    """Export only the processed CH3 and CH4 samples to a CSV file."""
    if len(channel_3) != len(channel_4):
        raise ValueError("CH3 and CH4 must contain the same number of samples")

    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(("ch3", "ch4"))
        writer.writerows(zip(channel_3, channel_4))


def load_channels(csv_path: Path) -> tuple[list[float], list[float], list[float], str]:
    """Load sample time and the two raw channels from a CSV file."""
    times = []
    channel_1 = []
    channel_2 = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("The CSV file has no header")

        missing_columns = {CHANNEL_1_NAME, CHANNEL_2_NAME} - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing_columns))}")
        time_name = "elapsed_ms" if "elapsed_ms" in reader.fieldnames else None

        for row in reader:
            if not row.get(CHANNEL_1_NAME) or not row.get(CHANNEL_2_NAME):
                continue
            try:
                channel_1.append(float(row[CHANNEL_1_NAME]))
                channel_2.append(float(row[CHANNEL_2_NAME]))
                times.append(
                    float(row[time_name]) / 1000.0
                    if time_name
                    else len(times) / DEFAULT_SAMPLE_RATE_HZ
                )
            except (TypeError, ValueError):
                continue

    if not channel_1:
        raise ValueError("No valid channel samples were found")
    return times, channel_1, channel_2, "Time (s)"


def estimate_sample_rate(times: list[float]) -> float:
    # """Estimate the sample rate from monotonically increasing time values."""
    # intervals = [end - start for start, end in zip(times, times[1:]) if end > start]
    # if not intervals:
    #     return DEFAULT_SAMPLE_RATE_HZ
    # return 1.0 / median(intervals)
    return DEFAULT_SAMPLE_RATE_HZ


def notch_filter(
    values: list[float],
    sample_rate_hz: float,
    notch_frequency_hz: float = 50.07,
    quality_factor: float = 10.0,
) -> list[float]:
    """Apply a zero-phase IIR notch filter to one signal channel."""
    x = np.asarray(values, dtype=np.float64)

    b, a = iirnotch(
        notch_frequency_hz,
        quality_factor,
        fs=sample_rate_hz,
    )

    return filtfilt(b, a, x).tolist()


def apply_notch_filter(
    times: list[float],
    channel_1: list[float],
    channel_2: list[float],
    notch_frequency_hz: float = 50.0,
) -> tuple[list[float], list[float]]:
    """Apply a configurable mains-frequency notch filter to both raw channels."""
    sample_rate_hz = estimate_sample_rate(times)
    return (
        notch_filter(channel_1, sample_rate_hz, notch_frequency_hz),
        notch_filter(channel_2, sample_rate_hz, notch_frequency_hz),
    )


def bandpass_filter(
    values: list[float],
    sample_rate_hz: float,
    low_frequency_hz: float = BANDPASS_LOW_HZ,
    high_frequency_hz: float = BANDPASS_HIGH_HZ,
    order: int = BANDPASS_ORDER,
) -> list[float]:
    """Apply a zero-phase Butterworth band-pass filter to one channel."""
    if not values:
        return []
    if not 0.0 < low_frequency_hz < high_frequency_hz < sample_rate_hz / 2.0:
        raise ValueError("Band-pass frequencies must be inside the Nyquist range")

    sos = butter(
        order,
        (low_frequency_hz, high_frequency_hz),
        btype="bandpass",
        fs=sample_rate_hz,
        output="sos",
    )
    return sosfiltfilt(sos, np.asarray(values, dtype=np.float64)).tolist()


def apply_frequency_limits(
    times: list[float], channel_1: list[float], channel_2: list[float]
) -> tuple[list[float], list[float]]:
    """Apply the standard 0.5-40 Hz band-pass filter to both channels."""
    sample_rate_hz = estimate_sample_rate(times)
    return (
        bandpass_filter(channel_1, sample_rate_hz),
        bandpass_filter(channel_2, sample_rate_hz),
    )


def load_show_plot_data(csv_path: Path) -> ShowPlotData:
    """Load raw CSV channels and prepare every channel shown by the UI."""
    times, showPlotCh1, showPlotCh2, xLabel = load_channels(csv_path)  
    showPlotCh3, showPlotCh4 = apply_frequency_limits(times, showPlotCh1, showPlotCh2)
    showPlotCh3, showPlotCh4 = apply_notch_filter(times, showPlotCh3, showPlotCh4, 50.07)
    return ShowPlotData(
        times=times,
        xLabel=xLabel,
        showPlotCh1=showPlotCh1,
        showPlotCh2=showPlotCh2,
        showPlotCh3=showPlotCh3,
        showPlotCh4=showPlotCh4,
    )
