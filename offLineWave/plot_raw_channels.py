"""Open an ECG CSV file and plot its two raw channels."""

import argparse
from bisect import bisect_left, bisect_right
from pathlib import Path
from tkinter import Tk, filedialog

import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RangeSlider

from csv_data import export_processed_channels, load_show_plot_data


DEFAULT_DATA_DIR = Path(r"C:\Users\senki\Desktop\ECGDATA")


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


def choose_export_csv(source_path: Path) -> Path | None:
    """Choose where to export the processed CH3 and CH4 samples."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.asksaveasfilename(
        title="Export processed CH3 and CH4",
        initialdir=source_path.parent,
        initialfile=f"{source_path.stem}_ch3_ch4.csv",
        defaultextension=".csv",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
    )
    root.destroy()
    return Path(selected) if selected else None


def plot_channels(csv_path: Path, output_path: Path | None = None) -> None:
    """Plot raw and 50 Hz notch-filtered channels with interactive controls."""
    showPlotData = load_show_plot_data(csv_path)
    times = showPlotData.times
    x_label = showPlotData.xLabel
    showPlotSeries = (
        (showPlotData.showPlotCh1, "Raw CH1", "tab:blue"),
        (showPlotData.showPlotCh2, "Raw CH2", "tab:orange"),
        (showPlotData.showPlotCh3, "CH1 - 50 Hz notch", "tab:green"),
        (showPlotData.showPlotCh4, "CH2 - 50 Hz notch", "tab:red"),
    )

    figure, axes = plt.subplots(4, 1, sharex=True, figsize=(14, 8))
    figure.canvas.manager.set_window_title(f"ECG raw waveform - {csv_path.name}")
    figure.subplots_adjust(left=0.07, right=0.78, bottom=0.13, top=0.98, hspace=0.13)

    for axis, (values, label, color) in zip(axes, showPlotSeries):
        axis.plot(times, values, color=color, linewidth=0.8)
        axis.set_ylabel(label)
        axis.grid(True, alpha=0.3)
        axis.margins(x=0)
    axes[-1].set_xlabel(x_label)

    x_min, x_max = min(times), max(times)
    x_slider_axis = figure.add_axes((0.13, 0.045, 0.58, 0.025))
    x_slider = MovableRangeSlider(
        x_slider_axis,
        "X range",
        x_min,
        x_max,
        valinit=(x_min, x_max),
        valfmt="%.3f",
    )

    y_sliders = []
    slider_labels = ("R1", "R2", "F1", "F2")
    for axis, (values, _, _), slider_label in zip(
        axes, showPlotSeries, slider_labels
    ):
        lower, upper = padded_limits(values)
        axis.set_ylim(lower, upper)
        axis_position = axis.get_position()
        slider_axis = figure.add_axes((0.80, axis_position.y0, 0.012, axis_position.height))
        slider = MovableRangeSlider(
            slider_axis,
            slider_label,
            lower,
            upper,
            valinit=(lower, upper),
            orientation="vertical",
            valfmt="%.0f",
        )
        slider.valtext.set_visible(False)

        def update_y_limits(limits: tuple[float, float], target_axis=axis) -> None:
            target_axis.set_ylim(*limits)
            figure.canvas.draw_idle()

        slider.on_changed(update_y_limits)
        y_sliders.append(slider)

    export_axis = figure.add_axes((0.85, 0.93, 0.11, 0.04))
    point_1_axis = figure.add_axes((0.85, 0.88, 0.11, 0.04))
    point_2_axis = figure.add_axes((0.85, 0.83, 0.11, 0.04))
    export_button = Button(export_axis, "Export CH3/CH4", hovercolor="#bde5c8")
    point_1_button = Button(point_1_axis, "Point 1", hovercolor="#ffb3bd")
    point_2_button = Button(point_2_axis, "Point 2", hovercolor="#d8b3ff")
    export_status_text = figure.text(0.85, 0.815, "", ha="left", va="top", fontsize=8)
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
        0.84,
        0.78,
        "Choose Point 1,\nthen click waveform.",
        ha="left",
        va="top",
        family="monospace",
        fontsize=8.5,
        bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": "0.75"},
    )

    def update_x_limits(limits: tuple[float, float]) -> None:
        axes[-1].set_xlim(*limits)
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
        selected_series = [
            values[first_index:last_index] for values, _, _ in showPlotSeries
        ]
        if not selected_series[0]:
            measurement_text.set_text("Measurement\nNo samples selected")
        else:
            result_lines = [
                "Measurement\n"
                f"Point 1: {cursor_positions[0]:.3f}\n"
                f"Point 2: {cursor_positions[1]:.3f}\n"
                f"Delta: {end - start:.3f} s"
            ]
            for selected_values, (_, label, _) in zip(
                selected_series, showPlotSeries
            ):
                low, high = min(selected_values), max(selected_values)
                result_lines.append(
                    f"\n\n{label}\n"
                    f"max:  {high:.0f}\n"
                    f"min:  {low:.0f}\n"
                    f"diff: {high - low:.0f}"
                )
            measurement_text.set_text("".join(result_lines))
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

    def export_channels(event) -> None:
        export_path = choose_export_csv(csv_path)
        if export_path is None:
            return
        try:
            export_processed_channels(
                export_path, showPlotData.showPlotCh3, showPlotData.showPlotCh4
            )
        except OSError as error:
            export_status_text.set_text(f"Export failed:\n{error}")
        else:
            export_status_text.set_text(f"Saved:\n{export_path.name}")
        figure.canvas.draw_idle()

    x_slider.on_changed(update_x_limits)
    export_button.on_clicked(export_channels)
    point_1_button.on_clicked(lambda event: activate_cursor(0))
    point_2_button.on_clicked(lambda event: activate_cursor(1))
    figure.canvas.mpl_connect("button_press_event", place_cursor)
    figure._ecg_controls = (
        x_slider,
        *y_sliders,
        export_button,
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
