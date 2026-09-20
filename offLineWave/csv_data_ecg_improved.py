"""Load and process raw ECG/respiration channel data from CSV files."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch, sosfiltfilt


CHANNEL_1_NAME = "ch1_raw"   # respiration channel
CHANNEL_2_NAME = "ch2_raw"   # ECG channel
DEFAULT_SAMPLE_RATE_HZ = 500.0

ECG_NOTCH_HZ = 50.07
ECG_NOTCH_Q = 10.0
ECG_LOW_HZ = 0.5
ECG_HIGH_HZ = 40.0
ECG_FILTER_ORDER = 4


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
    """Export processed CH3 and CH4 samples."""

    if len(channel_3) != len(channel_4):
        raise ValueError("CH3 and CH4 must contain the same number of samples")

    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(("ch3", "ch4"))
        writer.writerows(zip(channel_3, channel_4))


def load_channels(
    csv_path: Path,
) -> tuple[list[float], list[float], list[float], str]:
    """Load sample time and the two raw channels from a CSV file."""

    times: list[float] = []
    channel_1: list[float] = []
    channel_2: list[float] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("The CSV file has no header")

        missing_columns = {CHANNEL_1_NAME, CHANNEL_2_NAME} - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                f"Missing CSV columns: {', '.join(sorted(missing_columns))}"
            )

        time_name = "elapsed_ms" if "elapsed_ms" in reader.fieldnames else None

        for row in reader:
            if not row.get(CHANNEL_1_NAME) or not row.get(CHANNEL_2_NAME):
                continue

            try:
                ch1 = float(row[CHANNEL_1_NAME])
                ch2 = float(row[CHANNEL_2_NAME])

                if time_name:
                    time_s = float(row[time_name]) / 1000.0
                else:
                    time_s = len(times) / DEFAULT_SAMPLE_RATE_HZ
            except (TypeError, ValueError):
                continue

            channel_1.append(ch1)
            channel_2.append(ch2)
            times.append(time_s)

    if not channel_1:
        raise ValueError("No valid channel samples were found")

    return times, channel_1, channel_2, "Time (s)"


def estimate_sample_rate(times: list[float]) -> float:
    """Return the ADS1292 configured sample rate.

    For this data set the samples are exactly 2 ms apart, so the correct
    processing rate is 500 SPS. Do not estimate it from PC/UART arrival time.
    """
    return DEFAULT_SAMPLE_RATE_HZ


def notch_filter(
    values: list[float],
    sample_rate_hz: float,
    notch_frequency_hz: float = ECG_NOTCH_HZ,
    quality_factor: float = ECG_NOTCH_Q,
) -> list[float]:
    """Apply a zero-phase IIR mains-frequency notch filter."""

    if not values:
        return []

    x = np.asarray(values, dtype=np.float64)

    b, a = iirnotch(
        notch_frequency_hz,
        quality_factor,
        fs=sample_rate_hz,
    )

    return filtfilt(b, a, x).tolist()


def bandpass_filter(
    values: list[float],
    sample_rate_hz: float,
    low_hz: float,
    high_hz: float,
    order: int = ECG_FILTER_ORDER,
) -> list[float]:
    """Apply a zero-phase Butterworth band-pass filter using SOS form."""

    if not values:
        return []

    if not 0.0 < low_hz < high_hz < sample_rate_hz / 2.0:
        raise ValueError("Band-pass frequencies must lie inside the Nyquist range")

    x = np.asarray(values, dtype=np.float64)

    sos = butter(
        order,
        [low_hz, high_hz],
        btype="bandpass",
        fs=sample_rate_hz,
        output="sos",
    )

    return sosfiltfilt(sos, x).tolist()


def process_ecg(
    values: list[float],
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
) -> list[float]:
    """Prepare CH2 for ECG waveform display.

    Pipeline:
        raw CH2
        -> 50.07 Hz zero-phase notch
        -> 0.5-40 Hz zero-phase Butterworth band-pass
    """

    notched = notch_filter(
        values,
        sample_rate_hz,
        notch_frequency_hz=ECG_NOTCH_HZ,
        quality_factor=ECG_NOTCH_Q,
    )

    return bandpass_filter(
        notched,
        sample_rate_hz,
        low_hz=ECG_LOW_HZ,
        high_hz=ECG_HIGH_HZ,
        order=ECG_FILTER_ORDER,
    )


def process_qrs_detection(
    values: list[float],
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
) -> list[float]:
    """Optional QRS-detection path; do not use this as the displayed ECG."""

    notched = notch_filter(
        values,
        sample_rate_hz,
        notch_frequency_hz=ECG_NOTCH_HZ,
        quality_factor=ECG_NOTCH_Q,
    )

    return bandpass_filter(
        notched,
        sample_rate_hz,
        low_hz=5.0,
        high_hz=20.0,
        order=4,
    )


def load_show_plot_data(csv_path: Path) -> ShowPlotData:
    """Load raw channels and prepare the displayed processed channels."""

    times, showPlotCh1, showPlotCh2, xLabel = load_channels(csv_path)
    fs = estimate_sample_rate(times)

    # CH1 is respiration. Do not pass it through the ECG 0.5-40 Hz chain.
    # Keep CH3 as a mains-notch-only view for now.
    showPlotCh3 = notch_filter(
        showPlotCh1,
        fs,
        notch_frequency_hz=ECG_NOTCH_HZ,
        quality_factor=ECG_NOTCH_Q,
    )

    # CH2 is the ECG waveform.
    showPlotCh4 = process_ecg(showPlotCh2, fs)

    return ShowPlotData(
        times=times,
        xLabel=xLabel,
        showPlotCh1=showPlotCh1,
        showPlotCh2=showPlotCh2,
        showPlotCh3=showPlotCh3,
        showPlotCh4=showPlotCh4,
    )
