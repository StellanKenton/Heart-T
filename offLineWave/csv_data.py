"""Load and process raw ECG channel data from CSV files."""

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median


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
    """Estimate the sample rate from monotonically increasing time values."""
    intervals = [end - start for start, end in zip(times, times[1:]) if end > start]
    if not intervals:
        return DEFAULT_SAMPLE_RATE_HZ
    return 1.0 / median(intervals)


def notch_filter(
    values: list[float],
    sample_rate_hz: float,
    notch_frequency_hz: float = 50.0,
    quality_factor: float = 30.0,
) -> list[float]:
    """Apply a second-order IIR notch filter to one signal channel."""
    if not values:
        return []
    if sample_rate_hz <= 2.0 * notch_frequency_hz:
        raise ValueError("Sample rate must be greater than twice the notch frequency")
    if quality_factor <= 0.0:
        raise ValueError("Quality factor must be positive")

    omega = 2.0 * math.pi * notch_frequency_hz / sample_rate_hz
    alpha = math.sin(omega) / (2.0 * quality_factor)
    a0 = 1.0 + alpha
    b0 = 1.0 / a0
    b1 = -2.0 * math.cos(omega) / a0
    b2 = 1.0 / a0
    a1 = -2.0 * math.cos(omega) / a0
    a2 = (1.0 - alpha) / a0

    first_value = float(values[0])
    previous_input_1 = first_value
    previous_input_2 = first_value
    previous_output_1 = first_value
    previous_output_2 = first_value
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


def apply_50hz_notch(
    times: list[float], channel_1: list[float], channel_2: list[float]
) -> tuple[list[float], list[float]]:
    """Apply the standard 50 Hz notch filter to both raw channels."""
    sample_rate_hz = estimate_sample_rate(times)
    return (
        notch_filter(channel_1, sample_rate_hz),
        notch_filter(channel_2, sample_rate_hz),
    )


def load_show_plot_data(csv_path: Path) -> ShowPlotData:
    """Load raw CSV channels and prepare every channel shown by the UI."""
    times, showPlotCh1, showPlotCh2, xLabel = load_channels(csv_path)
    showPlotCh3, showPlotCh4 = apply_50hz_notch(times, showPlotCh1, showPlotCh2)
    return ShowPlotData(
        times=times,
        xLabel=xLabel,
        showPlotCh1=showPlotCh1,
        showPlotCh2=showPlotCh2,
        showPlotCh3=showPlotCh3,
        showPlotCh4=showPlotCh4,
    )
