"""Open an ECG CSV file and plot its two raw channels."""

import argparse
import csv
from bisect import bisect_left, bisect_right
from pathlib import Path
from tkinter import Tk, filedialog

import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RangeSlider


DEFAULT_DATA_DIR = Path(r"C:\Users\senki\Desktop\ECGDATA")
CHANNEL_1_NAMES = ("rawch1", "ch1_raw")
CHANNEL_2_NAMES = ("rawch2", "ch2_raw")


class MovableRangeSlider(RangeSlider):
    """Range slider whose selected span can be dragged as one window."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._span_drag_start = None
        self._span_drag_values = None

    def _event_position(self, event) -> float:
        data_x, data_y = self.ax.transData.inverted().transform((event.x, event.y))
        return data_x if self.orientation == "horizontal" else data_y

    def _is_near_handle(self, event) -> bool:
        pointer = event.x if self.orientation == "horizontal" else event.y
        handle_pixels = []
        for value in self.val:
            point = (value, 0.5) if self.orientation == "horizontal" else (0.5, value)
            display_x, display_y = self.ax.transData.transform(point)
            handle_pixels.append(display_x if self.orientation == "horizontal" else display_y)
        return min(abs(pointer - pixel) for pixel in handle_pixels) <= 12

    def _update(self, event) -> None:
        if self.ignore(event) or event.button != 1:
            return

        if event.name == "button_press_event" and self.ax.contains(event)[0]:
            position = self._event_position(event)
            if self.val[0] < position < self.val[1] and not self._is_near_handle(event):
                self._span_drag_start = position
                self._span_drag_values = tuple(self.val)
                event.canvas.grab_mouse(self.ax)
                return

        if self._span_drag_start is not None:
            if event.name == "button_release_event":
                self._span_drag_start = None
                self._span_drag_values = None
                event.canvas.release_mouse(self.ax)
                return
            if event.name == "motion_notify_event":
                position = self._event_position(event)
                lower, upper = self._span_drag_values
                width = upper - lower
                new_lower = lower + position - self._span_drag_start
                new_lower = min(max(new_lower, self.valmin), self.valmax - width)
                self.set_val((new_lower, new_lower + width))
                return

        super()._update(event)


def choose_csv() -> Path | None:
    """Show a file picker rooted at the default ECG data directory."""
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


def find_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str:
    """Return the first matching column name, ignoring letter case."""
    normalized = {name.strip().lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    raise ValueError(f"Missing channel column; expected one of: {', '.join(candidates)}")


def load_channels(csv_path: Path) -> tuple[list[float], list[float], list[float], str]:
    """Load sample time and the two raw channels from a CSV file."""
    times = []
    channel_1 = []
    channel_2 = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("The CSV file has no header")

        ch1_name = find_column(reader.fieldnames, CHANNEL_1_NAMES)
        ch2_name = find_column(reader.fieldnames, CHANNEL_2_NAMES)
        time_name = "elapsed_ms" if "elapsed_ms" in reader.fieldnames else None

        for row in reader:
            if not row.get(ch1_name) or not row.get(ch2_name):
                continue
            try:
                channel_1.append(float(row[ch1_name]))
                channel_2.append(float(row[ch2_name]))
                times.append(float(row[time_name]) / 1000.0 if time_name else len(times))
            except (TypeError, ValueError):
                continue

    if not channel_1:
        raise ValueError("No valid channel samples were found")
    return times, channel_1, channel_2, "Time (s)" if time_name else "Sample index"


def plot_channels(csv_path: Path, output_path: Path | None = None) -> None:
    """Plot raw channels with sliders controlling all visible axis limits."""
    times, channel_1, channel_2, x_label = load_channels(csv_path)
    figure, axes = plt.subplots(2, 1, sharex=True, figsize=(15, 9))
    figure.canvas.manager.set_window_title(f"ECG raw waveform - {csv_path.name}")
    figure.suptitle(csv_path.name)
    figure.subplots_adjust(left=0.08, right=0.79, bottom=0.16, top=0.92, hspace=0.12)

    axes[0].plot(times, channel_1, color="tab:blue", linewidth=0.8)
    axes[0].set_ylabel("Raw CH1")
    axes[1].plot(times, channel_2, color="tab:orange", linewidth=0.8)
    axes[1].set_ylabel("Raw CH2")
    axes[1].set_xlabel(x_label)

    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.margins(x=0)

    x_min, x_max = min(times), max(times)
    ch1_min, ch1_max = padded_limits(channel_1)
    ch2_min, ch2_max = padded_limits(channel_2)
    axes[0].set_ylim(ch1_min, ch1_max)
    axes[1].set_ylim(ch2_min, ch2_max)

    x_slider_axis = figure.add_axes((0.14, 0.055, 0.58, 0.03))
    ch1_slider_axis = figure.add_axes((0.815, 0.58, 0.016, 0.30))
    ch2_slider_axis = figure.add_axes((0.815, 0.20, 0.016, 0.30))
    x_slider = MovableRangeSlider(
        x_slider_axis,
        "X range",
        x_min,
        x_max,
        valinit=(x_min, x_max),
        valfmt="%.3f",
    )
    ch1_slider = MovableRangeSlider(
        ch1_slider_axis,
        "CH1",
        ch1_min,
        ch1_max,
        valinit=(ch1_min, ch1_max),
        orientation="vertical",
        valfmt="%.0f",
    )

    point_1_axis = figure.add_axes((0.86, 0.83, 0.10, 0.045))
    point_2_axis = figure.add_axes((0.86, 0.77, 0.10, 0.045))
    point_1_button = Button(point_1_axis, "Point 1", hovercolor="#ffb3bd")
    point_2_button = Button(point_2_axis, "Point 2", hovercolor="#d8b3ff")
    cursor_colors = ("crimson", "purple")
    cursor_lines = [[], []]
    for cursor_index, color in enumerate(cursor_colors):
        for axis in axes:
            line = axis.axvline(x_min, color=color, linestyle="--", linewidth=1.4)
            line.set_visible(False)
            cursor_lines[cursor_index].append(line)

    cursor_positions = [None, None]
    cursor_state = {"active": None}
    measurement_text = figure.text(
        0.86,
        0.72,
        "Choose Point 1,\nthen click waveform.",
        ha="left",
        va="top",
        family="monospace",
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": "0.75"},
    )
    ch2_slider = MovableRangeSlider(
        ch2_slider_axis,
        "CH2",
        ch2_min,
        ch2_max,
        valinit=(ch2_min, ch2_max),
        orientation="vertical",
        valfmt="%.0f",
    )

    def update_x_limits(limits: tuple[float, float]) -> None:
        axes[1].set_xlim(*limits)
        figure.canvas.draw_idle()

    def update_ch1_limits(limits: tuple[float, float]) -> None:
        axes[0].set_ylim(*limits)
        figure.canvas.draw_idle()

    def update_ch2_limits(limits: tuple[float, float]) -> None:
        axes[1].set_ylim(*limits)
        figure.canvas.draw_idle()

    def update_measurement() -> None:
        if cursor_positions[0] is None or cursor_positions[1] is None:
            selected = cursor_state["active"]
            instruction = f"Point {selected + 1} armed.\nClick on either waveform." if selected is not None else "Select a point button."
            point_1_value = "--" if cursor_positions[0] is None else f"{cursor_positions[0]:.3f}"
            point_2_value = "--" if cursor_positions[1] is None else f"{cursor_positions[1]:.3f}"
            measurement_text.set_text(
                f"{instruction}\n\nPoint 1: {point_1_value}\nPoint 2: {point_2_value}"
            )
            figure.canvas.draw_idle()
            return

        start, end = sorted(cursor_positions)
        first_index = bisect_left(times, start)
        last_index = bisect_right(times, end)
        selected_ch1 = channel_1[first_index:last_index]
        selected_ch2 = channel_2[first_index:last_index]
        if not selected_ch1:
            measurement_text.set_text("Measurement\nNo samples selected")
        else:
            ch1_low, ch1_high = min(selected_ch1), max(selected_ch1)
            ch2_low, ch2_high = min(selected_ch2), max(selected_ch2)
            time_unit = "s" if x_label == "Time (s)" else "samples"
            measurement_text.set_text(
                "Measurement\n"
                f"Point 1: {cursor_positions[0]:.3f}\n"
                f"Point 2: {cursor_positions[1]:.3f}\n"
                f"Delta: {end - start:.3f} {time_unit}\n\n"
                f"CH1 max:  {ch1_high:.0f}\n"
                f"CH1 min:  {ch1_low:.0f}\n"
                f"CH1 diff: {ch1_high - ch1_low:.0f}\n\n"
                f"CH2 max:  {ch2_high:.0f}\n"
                f"CH2 min:  {ch2_low:.0f}\n"
                f"CH2 diff: {ch2_high - ch2_low:.0f}"
            )
        figure.canvas.draw_idle()

    def activate_cursor(cursor_index: int) -> None:
        cursor_state["active"] = cursor_index
        point_1_axis.set_facecolor("#ffd6dc" if cursor_index == 0 else "0.85")
        point_2_axis.set_facecolor("#e8d6ff" if cursor_index == 1 else "0.85")
        update_measurement()

    def place_cursor(event) -> None:
        cursor_index = cursor_state["active"]
        if cursor_index is None or event.inaxes not in axes or event.xdata is None:
            return

        sample_index = nearest_index(times, event.xdata)
        position = times[sample_index]
        cursor_positions[cursor_index] = position
        for line in cursor_lines[cursor_index]:
            line.set_xdata([position, position])
            line.set_visible(True)
        update_measurement()

    x_slider.on_changed(update_x_limits)
    ch1_slider.on_changed(update_ch1_limits)
    ch2_slider.on_changed(update_ch2_limits)
    point_1_button.on_clicked(lambda event: activate_cursor(0))
    point_2_button.on_clicked(lambda event: activate_cursor(1))
    figure.canvas.mpl_connect("button_press_event", place_cursor)
    figure._ecg_controls = (
        x_slider,
        ch1_slider,
        ch2_slider,
        point_1_button,
        point_2_button,
    )

    if output_path:
        figure.savefig(output_path, dpi=150)
        plt.close(figure)
    else:
        plt.show()


def padded_limits(values: list[float]) -> tuple[float, float]:
    """Return usable slider limits, including for a constant signal."""
    lower = min(values)
    upper = max(values)
    if lower == upper:
        padding = max(abs(lower) * 0.05, 1.0)
        return lower - padding, upper + padding
    return lower, upper


def nearest_index(values: list[float], target: float) -> int:
    """Return the index of the sample nearest to the requested position."""
    index = bisect_left(values, target)
    if index <= 0:
        return 0
    if index >= len(values):
        return len(values) - 1
    return index if target - values[index - 1] > values[index] - target else index - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot raw CH1 and CH2 from an ECG CSV file.")
    parser.add_argument("csv_file", nargs="?", type=Path, help="CSV file; omit to use a file picker")
    parser.add_argument("--save", type=Path, metavar="IMAGE", help="Save the plot instead of opening a window")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = args.csv_file or choose_csv()
    if csv_path is None:
        return 0
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    plot_channels(csv_path, args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
