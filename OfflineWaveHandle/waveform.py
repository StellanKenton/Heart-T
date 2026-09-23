"""Interactive display for raw CH2 and filtered CH4 ECG waveforms."""

from pathlib import Path
from tkinter import Tk, filedialog

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, RangeSlider

from data import EcgData


class MovableRangeSlider(RangeSlider):
    """Allow dragging the selected range without changing its width."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._drag_start = None
        self._drag_values = None

    def _update(self, event):
        if self.ignore(event) or event.button != 1:
            return
        if event.name == "button_press_event" and self.ax.contains(event)[0]:
            position = self.ax.transData.inverted().transform((event.x, event.y))[0 if self.orientation == "horizontal" else 1]
            if self.val[0] < position < self.val[1]:
                pointer = event.x if self.orientation == "horizontal" else event.y
                handle_pixels = []
                for value in self.val:
                    point = (value, 0.5) if self.orientation == "horizontal" else (0.5, value)
                    pixel = self.ax.transData.transform(point)
                    handle_pixels.append(pixel[0 if self.orientation == "horizontal" else 1])
                if min(abs(pointer - pixel) for pixel in handle_pixels) > 12:
                    self._drag_start = position
                    self._drag_values = tuple(self.val)
                    event.canvas.grab_mouse(self.ax)
                    return
        if self._drag_start is not None:
            if event.name == "button_release_event":
                self._drag_start = None
                self._drag_values = None
                event.canvas.release_mouse(self.ax)
                return
            if event.name == "motion_notify_event":
                position = self.ax.transData.inverted().transform((event.x, event.y))[0 if self.orientation == "horizontal" else 1]
                low, high = self._drag_values
                width = high - low
                new_low = min(max(low + position - self._drag_start, self.valmin), self.valmax - width)
                self.set_val((new_low, new_low + width))
                return
        super()._update(event)


def _save_path(source: Path) -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.asksaveasfilename(
        title="Export CH2 and CH4", initialdir=source.parent,
        initialfile=f"{source.stem}_ch2_ch4.csv", defaultextension=".csv",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
    )
    root.destroy()
    return Path(selected) if selected else None


def show_waveforms(data: EcgData, source: Path, output: Path | None = None) -> None:
    """Display or save the ECG and filtered beat-to-beat heart rate."""
    figure, axes = plt.subplots(3, 1, sharex=True, figsize=(14, 9))
    figure.canvas.manager.set_window_title(f"ECG waveform - {source.name}")
    figure.subplots_adjust(left=0.09, right=0.78, bottom=0.15, top=0.96, hspace=0.18)
    first, last = float(data.times[0]), float(data.times[-1])
    if first == last:
        last = first + 1 / 500
    lines = []
    for axis, values, label, color in zip(
        axes[:2], (data.ch2, data.ch4), ("Raw CH2", "Filtered CH4"), ("tab:orange", "tab:red")
    ):
        line, = axis.plot([], [], color=color, linewidth=0.8)
        lines.append(line)
        axis.set_ylabel(label)
        axis.set_ylim(*data.limits(values))
        axis.set_xlim(first, last)
        axis.grid(True, alpha=0.3)
        axis.margins(x=0)
    rate_axis = axes[2]
    valid_rates = data.instantaneous_hr[np.isfinite(data.instantaneous_hr)]
    if valid_rates.size:
        low, high = float(np.min(valid_rates)), float(np.max(valid_rates))
        padding = max((high - low) * 0.1, 5.0)
        rate_axis.set_ylim(low - padding, high + padding)
    else:
        rate_axis.set_ylim(40, 180)
    rate_axis.set_xlim(first, last)
    rate_axis.set_ylabel("Heart rate (bpm)")
    rate_axis.set_xlabel("Time (s)")
    rate_axis.grid(True, alpha=0.3)
    rate_axis.margins(x=0)
    rate_line, = rate_axis.plot([], [], color="tab:blue", linewidth=1.1, marker=".", markersize=3)
    if not valid_rates.size:
        rate_axis.text(0.5, 0.5, "No valid RR intervals", ha="center", va="center", transform=rate_axis.transAxes)
    peaks_artist = axes[1].scatter([], [], color="tab:blue", marker="x", s=28, linewidths=1.2, label="R peak", zorder=3)
    if data.r_peaks.size:
        axes[1].legend(loc="upper right")

    def refresh() -> None:
        start, end = axes[-1].get_xlim()
        point_budget = max(int(axes[-1].bbox.width * 2), 500)
        for line, (times, values) in zip(lines, data.visible(start, end, point_budget)):
            line.set_data(times, values)
        peaks_artist.set_offsets(data.visible_peaks(start, end))
        rate_line.set_data(*data.visible_heart_rates(start, end))
        figure.canvas.draw_idle()

    # Coalesce successive slider events into one waveform refresh per short interval.
    refresh_timer = figure.canvas.new_timer(interval=35)
    refresh_timer.single_shot = True
    refresh_timer.add_callback(refresh)

    def queue_refresh(_axis):
        refresh_timer.stop()
        refresh_timer.start()

    axes[-1].callbacks.connect("xlim_changed", queue_refresh)

    x_slider_axis = figure.add_axes((0.14, 0.055, 0.57, 0.025))
    x_slider = MovableRangeSlider(x_slider_axis, "X range", first, last, valinit=(first, last), valfmt="%.3f")

    def update_x(limits):
        axes[-1].set_xlim(*limits)

    x_slider.on_changed(update_x)
    y_sliders = []
    for axis, label in zip(axes, ("R", "F", "HR")):
        box = axis.get_position()
        slider_axis = figure.add_axes((0.80, box.y0, 0.012, box.height))
        low, high = axis.get_ylim()
        slider = MovableRangeSlider(slider_axis, label, low, high, valinit=(low, high), orientation="vertical", valfmt="%.0f")
        slider.valtext.set_visible(False)
        slider.on_changed(lambda limits, target=axis: (target.set_ylim(*limits), figure.canvas.draw_idle()))
        y_sliders.append(slider)

    export_axis = figure.add_axes((0.84, 0.91, 0.13, 0.045))
    point_1_axis = figure.add_axes((0.84, 0.85, 0.13, 0.045))
    point_2_axis = figure.add_axes((0.84, 0.79, 0.13, 0.045))
    export_button = Button(export_axis, "Export CH2/CH4")
    point_1_button = Button(point_1_axis, "Point 1")
    point_2_button = Button(point_2_axis, "Point 2")
    status = figure.text(0.84, 0.765, "", ha="left", va="top", fontsize=8)
    rate = "N/A" if data.heart_rate is None else f"{data.heart_rate:.1f} bpm"
    accepted = int(np.count_nonzero(np.isfinite(data.instantaneous_hr)))
    figure.text(0.84, 0.69, f"Heart rate\n{rate}\nR peaks: {data.r_peaks.size}\nValid RR: {accepted}/{data.rr_intervals.size}", ha="left", va="top", fontsize=10, weight="bold")
    beat_text = figure.text(0.84, 0.57, "Click near a QRS\non either waveform.", ha="left", va="top", fontsize=9)
    beat_axis = figure.add_axes((0.84, 0.24, 0.14, 0.15))
    beat_axis.set_title("Single beat (CH4)", fontsize=9)
    beat_axis.tick_params(labelsize=7)
    beat_axis.grid(True, alpha=0.3)
    beat_line, = beat_axis.plot([], [], color="tab:red", linewidth=1)
    measurement = figure.text(0.84, 0.21, "Choose Point 1,\nthen click waveform.", ha="left", va="top", family="monospace", fontsize=8)
    beat_span = axes[1].axvspan(first, first, color="tab:green", alpha=0.09, visible=False)
    marker_specs = (("QRS start", "qrs_onset", "tab:green"), ("Q end", "q_end", "tab:green"),
                    ("R", "r", "tab:blue"), ("S start", "s_onset", "tab:purple"),
                    ("S end", "s_end", "tab:purple"))
    beat_markers = []
    for label, _, color in marker_specs:
        main_line = axes[1].axvline(first, color=color, linestyle="--", linewidth=1, visible=False)
        main_label = axes[1].text(first, 0.98, label, color=color, fontsize=7, rotation=90,
                                  va="top", transform=axes[1].get_xaxis_transform(), visible=False)
        detail_line = beat_axis.axvline(first, color=color, linestyle="--", linewidth=0.8, visible=False)
        beat_markers.append((main_line, main_label, detail_line))
    cursors = [[axis.axvline(first, color=color, linestyle="--", linewidth=1.4, visible=False) for axis in axes]
               for color in ("crimson", "purple")]
    positions = [None, None]
    active = [None]

    def update_measurement():
        if None in positions:
            selected = active[0]
            instruction = f"Point {selected + 1} armed.\nClick waveform." if selected is not None else "Select a point button."
            measurement.set_text(f"{instruction}\n\nPoint 1: {positions[0] if positions[0] is not None else '--'}\nPoint 2: {positions[1] if positions[1] is not None else '--'}")
        else:
            measurement.set_text(data.measurement(*positions))
        figure.canvas.draw_idle()

    def activate(index):
        active[0] = index
        update_measurement()

    def show_beat(beat):
        times = data.times
        segment = data.ch4[beat.start:beat.stop]
        beat_line.set_data(times[beat.start:beat.stop], segment)
        beat_axis.set_xlim(float(times[beat.start]), float(times[beat.stop - 1]))
        beat_axis.set_ylim(*data.limits(segment))
        lower, upper = data.limits(segment)
        padding = max((upper - lower) * 0.1, 1)
        filter_slider = y_sliders[1]
        filter_slider.set_val((max(filter_slider.valmin, lower - padding),
                               min(filter_slider.valmax, upper + padding)))
        beat_span.set_x(float(times[beat.start]))
        beat_span.set_width(float(times[beat.stop - 1] - times[beat.start]))
        beat_span.set_visible(True)
        for (label, field, _), (main_line, main_label, detail_line) in zip(marker_specs, beat_markers):
            index = getattr(beat, field)
            if field == "qrs_onset" and index is None:
                index = beat.q_onset
            visible = index is not None
            for artist in (main_line, main_label, detail_line):
                artist.set_visible(visible)
            if visible:
                position = float(times[index])
                main_line.set_xdata([position, position])
                main_label.set_x(position)
                main_label.set_text("Q/QRS start" if field == "qrs_onset" and beat.qrs_onset is not None and beat.q_onset is not None
                                    else "Q start" if field == "qrs_onset" and beat.q_onset is not None
                                    else "S/QRS end" if field == "s_end" and beat.qrs_end is not None else label)
                detail_line.set_xdata([position, position])

        def duration(start, end):
            return f"{(times[end] - times[start]) * 1000:.0f} ms" if start is not None and end is not None else "N/A"

        beat_text.set_text(f"R: {times[beat.r]:.3f} s\n"
                           f"Q width: {duration(beat.q_onset, beat.q_end)}\n"
                           f"S width: {duration(beat.s_onset, beat.s_end)}\n"
                           f"QRS width: {duration(beat.qrs_onset, beat.qrs_end)}")
        figure.canvas.draw_idle()

    def place(event):
        if event.inaxes not in axes or event.xdata is None:
            return
        if active[0] is None:
            if event.inaxes in axes[:2]:
                beat = data.beat_near(event.xdata)
                if beat is not None:
                    show_beat(beat)
            return
        position = data.nearest_time(event.xdata)
        positions[active[0]] = position
        for cursor in cursors[active[0]]:
            cursor.set_xdata([position, position])
            cursor.set_visible(True)
        active[0] = None
        update_measurement()

    def export(_event):
        path = _save_path(source)
        if path is None:
            return
        try:
            data.export(path)
        except OSError as error:
            status.set_text(f"Export failed:\n{error}")
        else:
            status.set_text(f"Saved:\n{path.name}")
        figure.canvas.draw_idle()

    export_button.on_clicked(export)
    point_1_button.on_clicked(lambda event: activate(0))
    point_2_button.on_clicked(lambda event: activate(1))
    figure.canvas.mpl_connect("button_press_event", place)
    figure._ecg_controls = (x_slider, *y_sliders, export_button, point_1_button, point_2_button, refresh_timer)
    refresh()
    if output:
        figure.savefig(output, dpi=150)
        plt.close(figure)
    else:
        plt.show()
