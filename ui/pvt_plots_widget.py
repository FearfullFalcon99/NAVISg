from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy


class PVTPlotsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(14, 10), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.subplots(3, 3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.figure.patch.set_facecolor('#ffffff')
        self._style_axes()
        self.clear()

    def _style_axes(self):
        for axis in self.axes.flat:
            axis.set_facecolor('#ffffff')
            axis.grid(True, linestyle='--', linewidth=0.4, color='#d5e4f3', alpha=0.9)
            axis.tick_params(labelsize=7, colors='#12324f')
            for spine in axis.spines.values():
                spine.set_color('#b8d4ee')

    def clear(self):
        titles = [
            ("R_s", "scf/STB"),
            ("B_oil", "RB/STB"),
            ("μ_oil", "cP"),
            ("Z Factor", "-"),
            ("B_gas", "RB/scf"),
            ("μ_gas", "cP"),
            ("ρ_water", "lb/ft³"),
            ("B_water", "RB/STB"),
            ("μ_water", "cP"),
        ]

        for axis, (title, ylabel) in zip(self.axes.flat, titles):
            axis.cla()
            axis.set_title(title, fontsize=9, fontweight='bold', color='#12324f')
            axis.set_xlabel("Pressure, psia", fontsize=8, color='#12324f')
            axis.set_ylabel(ylabel, fontsize=8, color='#12324f')
            axis.grid(True, linestyle='--', linewidth=0.4, color='#d5e4f3', alpha=0.9)
            axis.tick_params(labelsize=7, colors='#12324f')
            for spine in axis.spines.values():
                spine.set_color('#b8d4ee')

        self.axes[0, 0].text(
            0.5,
            0.5,
            "Run analysis to generate PVT plots",
            transform=self.axes[0, 0].transAxes,
            ha='center',
            va='center',
            fontsize=10,
            color='#2068b1',
            fontweight='semibold',
        )
        self.canvas.draw_idle()

    def set_data(self, plot_data: dict | None):
        if not plot_data:
            self.clear()
            return

        pressures = np.asarray(plot_data.get('pressures', []), dtype=float)
        if pressures.size == 0:
            self.clear()
            return

        series = [
            ('Rs', 'R_s', 'scf/STB'),
            ('Bo', 'B_oil', 'RB/STB'),
            ('mu_o', 'μ_oil', 'cP'),
            ('Z', 'Z Factor', '-'),
            ('Bg', 'B_gas', 'RB/scf'),
            ('mu_g', 'μ_gas', 'cP'),
            ('rho_w', 'ρ_water', 'lb/ft³'),
            ('Bw', 'B_water', 'RB/STB'),
            ('mu_w', 'μ_water', 'cP'),
        ]

        self._style_axes()

        for axis, (key, title, ylabel) in zip(self.axes.flat, series):
            values = np.asarray(plot_data.get(key, []), dtype=float)
            axis.cla()
            axis.set_title(title, fontsize=9, fontweight='bold', color='#12324f')
            axis.set_xlabel("Pressure, psia", fontsize=8, color='#12324f')
            axis.set_ylabel(ylabel, fontsize=8, color='#12324f')
            axis.grid(True, linestyle='--', linewidth=0.4, color='#d5e4f3', alpha=0.9)
            axis.tick_params(labelsize=7, colors='#12324f')
            for spine in axis.spines.values():
                spine.set_color('#b8d4ee')
            if values.size:
                axis.plot(pressures, values, color='#5a9edc', linewidth=1.6)
                axis.set_xlim(float(np.min(pressures)), float(np.max(pressures)))

        self.canvas.draw_idle()
