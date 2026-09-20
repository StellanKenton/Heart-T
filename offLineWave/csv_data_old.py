"""Load and process raw ECG channel data from CSV files."""

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import numpy as np
from scipy.signal import filtfilt, iirnotch


CHANNEL_1_NAME = "ch1_raw"
CHANNEL_2_NAME = "ch2_raw"
DEFAULT_SAMPLE_RATE_HZ = 500.0


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


def butterworth_filter(
    values: list[float],
    sample_rate_hz: float,
    cutoff_frequency_hz: float,
    high_pass: bool,
) -> list[float]:
    """Apply a second-order Butterworth high-pass or low-pass filter."""
    if not values:
        return []
    if not 0.0 < cutoff_frequency_hz < sample_rate_hz / 2.0:
        raise ValueError("Cutoff frequency must be between zero and the Nyquist frequency")

    frequency_ratio = math.tan(math.pi * cutoff_frequency_hz / sample_rate_hz)
    normalization = 1.0 / (1.0 + math.sqrt(2.0) * frequency_ratio + frequency_ratio**2)
    if high_pass:
        b0 = normalization
        b1 = -2.0 * normalization
        b2 = normalization
    else:
        b0 = frequency_ratio**2 * normalization
        b1 = 2.0 * b0
        b2 = b0
    a1 = 2.0 * (frequency_ratio**2 - 1.0) * normalization
    a2 = (1.0 - math.sqrt(2.0) * frequency_ratio + frequency_ratio**2) * normalization

    first_value = float(values[0])
    previous_input_1 = first_value
    previous_input_2 = first_value
    previous_output_1 = 0.0 if high_pass else first_value
    previous_output_2 = previous_output_1
    filtered = []

    for value in values:
        current_input = float(value)
        current_output = (
            b0 * current_input
            + b1 * previous_input_1
            + b2 * previous_input_2
            - a1 * previous_output_1
            - a2 * previous_output_2
        )
        filtered.append(current_output)
        previous_input_2 = previous_input_1
        previous_input_1 = current_input
        previous_output_2 = previous_output_1
        previous_output_1 = current_output

    return filtered


def apply_frequency_limits(
    times: list[float], channel_1: list[float], channel_2: list[float]
) -> tuple[list[float], list[float]]:
    """Apply the standard 0.5 Hz high-pass and 40 Hz low-pass filters."""
    sample_rate_hz = estimate_sample_rate(times)
    high_passed_1 = butterworth_filter(channel_1, sample_rate_hz, 0.5, True)
    high_passed_2 = butterworth_filter(channel_2, sample_rate_hz, 0.5, True)
    return (
        butterworth_filter(high_passed_1, sample_rate_hz, 40.0, False),
        butterworth_filter(high_passed_2, sample_rate_hz, 40.0, False),
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
