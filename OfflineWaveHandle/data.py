"""Load CH2 ECG samples and prepare the filtered CH4 waveform."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, iirnotch, savgol_filter, sosfiltfilt


SAMPLE_RATE_HZ = 500.0


@dataclass(frozen=True)
class BeatMeasurement:
    start: int
    stop: int
    r: int
    q_onset: int | None
    q_end: int | None
    s_onset: int | None
    s_end: int | None
    qrs_onset: int | None
    qrs_end: int | None


@dataclass(frozen=True)
class EcgData:
    times: np.ndarray
    ch2: np.ndarray
    ch4: np.ndarray
    r_peaks: np.ndarray
    rr_intervals: np.ndarray
    instantaneous_hr: np.ndarray
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

    def visible_heart_rates(self, start: float, end: float) -> tuple[np.ndarray, np.ndarray]:
        """Return visible beat rates, including rejected intervals as gaps."""
        beat_times = self.times[self.r_peaks[1:]]
        left = int(np.searchsorted(beat_times, start, side="left"))
        right = int(np.searchsorted(beat_times, end, side="right"))
        return beat_times[left:right], self.instantaneous_hr[left:right]

    def beat_near(self, target: float) -> BeatMeasurement | None:
        """Select a detected R peak near a click and measure its isolated beat."""
        if not self.r_peaks.size:
            return None
        peak_times = self.times[self.r_peaks]
        position = int(np.searchsorted(peak_times, target))
        candidates = [index for index in (position - 1, position) if 0 <= index < self.r_peaks.size]
        nearest = min(candidates, key=lambda index: abs(peak_times[index] - target))
        if abs(peak_times[nearest] - target) > 0.20:
            return None
        r = int(self.r_peaks[nearest])
        start = max(0, r - int(0.30 * SAMPLE_RATE_HZ))
        stop = min(self.times.size, r + int(0.40 * SAMPLE_RATE_HZ) + 1)
        if nearest:
            start = max(start, (int(self.r_peaks[nearest - 1]) + r) // 2 + 1)
        if nearest + 1 < self.r_peaks.size:
            stop = min(stop, (r + int(self.r_peaks[nearest + 1])) // 2 + 1)
        return _measure_beat(self.ch4, start, stop, r)

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
    if ecg.size < 7:
        return np.empty(0, dtype=np.int64)
    smoothed = savgol_filter(ecg, 7, 2)
    candidates, properties = find_peaks(smoothed, distance=int(0.25 * SAMPLE_RATE_HZ),
                                       prominence=0, wlen=int(0.30 * SAMPLE_RATE_HZ) + 1)
    if not candidates.size:
        return candidates.astype(np.int64)
    threshold = 0.45 * float(np.percentile(properties["prominences"], 75))
    margin = int(0.15 * SAMPLE_RATE_HZ)
    valid = (properties["prominences"] >= threshold) & (candidates >= margin) & (candidates < ecg.size - margin)
    return candidates[valid].astype(np.int64)


def _measure_beat(ecg: np.ndarray, start: int, stop: int, r: int) -> BeatMeasurement:
    """Measure local Q/S deflections without assuming a stable zero baseline."""
    if r - start < 35 or stop - r < 45:
        return BeatMeasurement(start, stop, r, None, None, None, None, None, None)
    smooth = savgol_filter(ecg[start:stop], 7, 2)
    peak = r - start
    pre = smooth[max(0, peak - 55):peak - 30]
    noise = float(np.median(np.abs(np.diff(pre)))) if pre.size > 1 else 0.0
    amplitude = float(smooth[peak] - np.median(pre)) if pre.size else 0.0
    if amplitude <= 0:
        return BeatMeasurement(start, stop, r, None, None, None, None, None, None)

    # The last significant negative notch before R is Q; its 10% crossings bound Q.
    q_onset = q_end = s_onset = s_end = None
    q_left, q_right = max(0, peak - 50), peak - 5
    q_candidates, _ = find_peaks(-smooth[q_left:q_right], prominence=max(4 * noise, 0.02 * amplitude))
    if q_candidates.size:
        q = q_left + int(q_candidates[-1])
        before = max(0, q - 25)
        reference = float(np.max(smooth[before:q]))
        level = reference - 0.1 * (reference - smooth[q])
        onset = next((i for i in range(q - 1, before - 1, -1) if smooth[i] >= level), None)
        end = next((i for i in range(q + 1, peak) if smooth[i] >= level), None)
        if (onset is not None and end is not None
                and end - onset <= int(0.08 * SAMPLE_RATE_HZ)
                and end - q <= int(0.04 * SAMPLE_RATE_HZ)):
            q_onset, q_end = start + onset, start + end

    # S is the sharp negative deflection after R; use its recovery plateau locally.
    s = peak + 3 + int(np.argmin(smooth[peak + 3:min(smooth.size, peak + 40)]))
    recovery = smooth[s + 15:min(smooth.size, s + 35)]
    if recovery.size and float(np.median(recovery) - smooth[s]) >= max(4 * noise, 0.05 * amplitude):
        level = float(np.median(recovery))
        onset = next((i for i in range(s - 1, peak, -1) if smooth[i] >= level), None)
        end = next((i for i in range(s + 1, min(smooth.size, s + 45)) if smooth[i] >= level), None)
        if onset is not None and end is not None:
            s_onset, s_end = start + onset, start + end

    # Without a Q wave, the steep R upstroke supplies the QRS onset.
    rise = np.diff(smooth[max(0, peak - 35):peak + 1])
    r_onset = None
    if rise.size:
        steepest = int(np.argmax(rise))
        threshold = 0.12 * float(rise[steepest])
        if threshold > 0:
            foot = next((i + 1 for i in range(steepest - 1, -1, -1) if rise[i] <= threshold), None)
            if foot is not None:
                r_onset = start + max(0, peak - 35) + foot
    qrs_onset = q_onset if q_onset is not None else r_onset
    return BeatMeasurement(start, stop, r, q_onset, q_end, s_onset, s_end,
                           qrs_onset if s_end is not None else None, s_end if qrs_onset is not None else None)


def _calculate_rates(peak_times: np.ndarray) -> tuple[np.ndarray, np.ndarray, float | None]:
    """Calculate beat-to-beat HR and reject implausible or isolated RR intervals."""
    intervals = np.diff(peak_times)
    rates = np.full(intervals.shape, np.nan, dtype=np.float64)
    plausible = (intervals >= 0.30) & (intervals <= 2.0)
    for index in np.flatnonzero(plausible):
        nearby = intervals[max(index - 2, 0):index + 3]
        nearby = nearby[(nearby >= 0.30) & (nearby <= 2.0)]
        if nearby.size >= 3:
            median = float(np.median(nearby))
            if abs(intervals[index] - median) > 0.30 * median:
                continue
        rates[index] = 60.0 / intervals[index]
    accepted = np.isfinite(rates)
    average = float(60.0 / np.mean(intervals[accepted])) if np.any(accepted) else None
    return intervals, rates, average


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
    sos = butter(4, (0.5, 35.0), btype="bandpass", fs=SAMPLE_RATE_HZ, output="sos")
    filtered = sosfiltfilt(sos, raw)
    notch_b, notch_a = iirnotch(50.07, 40.0, fs=SAMPLE_RATE_HZ)
    filtered = filtfilt(notch_b, notch_a, filtered)
    peaks = _detect_r_peaks(filtered)
    sample_times = np.asarray(times)
    intervals, rates, heart_rate = _calculate_rates(sample_times[peaks])
    return EcgData(sample_times, raw, filtered, peaks, intervals, rates, heart_rate)
