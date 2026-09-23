"""Load CH2 ECG samples and prepare the filtered CH4 waveform."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, iirnotch, sosfiltfilt


SAMPLE_RATE_HZ = 500.0


@dataclass(frozen=True)
class EcgData:
    times: np.ndarray
    ch2: np.ndarray
    ch4: np.ndarray
    r_peaks: np.ndarray
    heart_rate: float | None

    def limits(self, values: np.ndarray) -> tuple[float, float]:
        low, high = float(np.min(values)), float(np.max(values))
        if low == high:
            padding = max(abs(low) * 0.05, 1.0)
            return low - padding, high + padding
        return low, high

    def nearest_time(self, target: float) -> float:
        index = int(np.clip(np.searchsorted(self.times, target), 0, self.times.size - 1))
        if index > 0 and abs(self.times[index - 1] - target) < abs(self.times[index] - target):
            index -= 1
        return float(self.times[index])

    def visible(self, start: float, end: float, max_points: int) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
        """Return peak-preserving, time-ordered samples for both visible curves."""
        left = max(int(np.searchsorted(self.times, start, side="left")) - 1, 0)
        right = min(int(np.searchsorted(self.times, end, side="right")) + 1, self.times.size)
        if right <= left:
            right = min(left + 1, self.times.size)
        indices = np.arange(left, right)
        if indices.size > max_points:
            # One minimum and one maximum per display bucket retain narrow QRS spikes.
            bucket_size = max(int(np.ceil(indices.size / max(max_points // 2, 1))), 1)
            selected = []
            for offset in range(left, right, bucket_size):
                stop = min(offset + bucket_size, right)
                for values in (self.ch2, self.ch4):
                    block = values[offset:stop]
                    selected.extend((offset + int(np.argmin(block)), offset + int(np.argmax(block))))
            indices = np.unique(np.asarray(selected, dtype=np.int64))
        return ((self.times[indices], self.ch2[indices]), (self.times[indices], self.ch4[indices]))

    def visible_peaks(self, start: float, end: float) -> np.ndarray:
        peak_times = self.times[self.r_peaks]
        left = np.searchsorted(peak_times, start, side="left")
        right = np.searchsorted(peak_times, end, side="right")
        indices = self.r_peaks[left:right]
        return np.column_stack((self.times[indices], self.ch4[indices]))

    def measurement(self, first: float, second: float) -> str:
        start, end = sorted((first, second))
        left = int(np.searchsorted(self.times, start, side="left"))
        right = int(np.searchsorted(self.times, end, side="right"))
        lines = [f"Point 1: {first:.3f} s", f"Point 2: {second:.3f} s", f"Delta: {end - start:.3f} s"]
        if left == right:
            return "Measurement\nNo samples selected"
        for name, values in (("Raw CH2", self.ch2), ("Filtered CH4", self.ch4)):
            segment = values[left:right]
            low, high = float(np.min(segment)), float(np.max(segment))
            lines.extend(("", name, f"max: {high:.0f}", f"min: {low:.0f}", f"diff: {high - low:.0f}"))
        return "\n".join(lines)

    def export(self, path: Path) -> None:
        """Write only the two displayed channels."""
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("ch2_raw", "ch4"))
            writer.writerows(zip(self.ch2, self.ch4))


def _detect_r_peaks(ecg: np.ndarray) -> np.ndarray:
    if ecg.size < 3:
        return np.empty(0, dtype=np.int64)
    derivative = np.diff(ecg, prepend=ecg[0])
    window = min(max(int(round(0.15 * SAMPLE_RATE_HZ)), 1), ecg.size)
    integrated = np.convolve(derivative * derivative, np.ones(window) / window, mode="same")
    baseline = np.median(integrated)
    mad = np.median(np.abs(integrated - baseline))
    threshold = baseline + max(3.0 * mad, 0.12 * (np.percentile(integrated, 95) - baseline))
    distance = max(int(0.30 * SAMPLE_RATE_HZ), 1)
    candidates, _ = find_peaks(integrated, height=threshold, distance=distance)
    radius = max(int(round(0.12 * SAMPLE_RATE_HZ)), 1)
    peaks = []
    energies = []
    for candidate in candidates:
        start = max(candidate - radius, 0)
        stop = min(candidate + radius + 1, ecg.size)
        peak = start + int(np.argmax(ecg[start:stop]))
        if peaks and peak - peaks[-1] < distance:
            if integrated[candidate] > energies[-1]:
                peaks[-1], energies[-1] = peak, integrated[candidate]
        else:
            peaks.append(peak)
            energies.append(integrated[candidate])
    return np.asarray(peaks, dtype=np.int64)


def load_ecg(path: Path) -> EcgData:
    """Read CH2 only; apply the original 0.5–40 Hz and 50.07 Hz filters."""
    times = []
    samples = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "ch2_raw" not in reader.fieldnames:
            raise ValueError("CSV must contain a ch2_raw column")
        has_time = "elapsed_ms" in reader.fieldnames
        for row in reader:
            try:
                value = float(row["ch2_raw"])
                time = float(row["elapsed_ms"]) / 1000.0 if has_time else len(samples) / SAMPLE_RATE_HZ
            except (TypeError, ValueError):
                continue
            if not np.isfinite(value) or not np.isfinite(time):
                continue
            if times and time <= times[-1]:
                continue
            times.append(time)
            samples.append(value)
    if len(samples) < 32:
        raise ValueError("At least 32 valid CH2 samples are required for filtering")

    raw = np.asarray(samples, dtype=np.float64)
    sos = butter(4, (0.5, 40.0), btype="bandpass", fs=SAMPLE_RATE_HZ, output="sos")
    filtered = sosfiltfilt(sos, raw)
    notch_b, notch_a = iirnotch(50.07, 10.0, fs=SAMPLE_RATE_HZ)
    filtered = filtfilt(notch_b, notch_a, filtered)
    peaks = _detect_r_peaks(filtered)
    peak_times = np.asarray(times)[peaks]
    intervals = np.diff(peak_times)
    intervals = intervals[intervals > 0]
    heart_rate = float(60.0 / np.mean(intervals)) if intervals.size else None
    return EcgData(np.asarray(times), raw, filtered, peaks, heart_rate)
