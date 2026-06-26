import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget, QVBoxLayout


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure  = Figure(figsize=(6, 5), tight_layout=True)
        self.canvas  = FigureCanvas(self.figure)
        self.ax      = self.figure.add_subplot(111)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.lines = []
        self._style_axes()
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)

    def _style_axes(self):
        self.ax.set_facecolor('#d9e8f5')
        self.figure.patch.set_facecolor('#ffffff')
        self.ax.set_xlabel('Oil Rate  [STB/d]', fontsize=9)
        self.ax.set_ylabel('Flowing BHP  [psia]', fontsize=9)
        self.ax.set_title('IPR / VLP — Nodal Analysis', fontsize=10, fontweight='bold')
        self.ax.grid(True, linestyle='--', linewidth=0.45, color='#b8d4ee', alpha=0.75)
        self.ax.tick_params(labelsize=8, colors='#12324f')
        self.ax.xaxis.label.set_color('#12324f')
        self.ax.yaxis.label.set_color('#12324f')
        self.ax.title.set_color('#12324f')
        for spine in self.ax.spines.values():
            spine.set_color('#78ade0')

        # Create annotation for hover
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(15,15),
                                     textcoords="offset points",
                                     bbox=dict(boxstyle="round,pad=0.5", fc="#f5fbff", ec="#2068b1", lw=1.5, alpha=0.97),
                                     arrowprops=dict(arrowstyle="-|>", connectionstyle="arc3,rad=0.1", color="#2068b1"),
                                     fontsize=8, fontweight='semibold', color='#12324f', zorder=10)
        self.annot.set_visible(False)

        # Create hover dot
        self.hover_dot, = self.ax.plot([], [], 'o', color='#2068b1', markersize=6, zorder=9)
        self.hover_dot.set_visible(False)

    def plot(self, ipr_data=None, vlp_curves=None, op_point=None):
        """
        ipr_data   : (rates, pwfs)  numpy arrays
        vlp_curves : list of dicts  {rates, bhps, label}
        op_point   : (q, pwf)  or None
        """
        self.ax.cla()
        self._style_axes()
        self.lines = []

        colors = ['#2068b1', '#3c8eda', '#78ade0', '#185f9d', '#5a9edc']

        if ipr_data is not None:
            rates, pwfs = ipr_data
            mask = pwfs >= 0
            line, = self.ax.plot(rates[mask], pwfs[mask],
                         color='#c0392b', linewidth=2,
                         linestyle='--', label='IPR')
            self.lines.append((line, 'IPR (Inflow performance curve)'))

        if vlp_curves:
            for i, curve in enumerate(vlp_curves):
                color = colors[i % len(colors)]
                line, = self.ax.plot(curve['rates'], curve['bhps'],
                             color=color, linewidth=2,
                             label=curve['label'])
                self.lines.append((line, f"VLP ({curve['label']})"))

        if op_point and op_point[0] is not None:
            q_op, p_op = op_point
            self.ax.plot(q_op, p_op, 'o',
                         color='#12324f', markersize=7, zorder=5,
                         label=f'Op. point  Q={q_op:.0f} STB/d  Pwf={p_op:.0f} psia')
            self.ax.axvline(x=q_op, color='#78ade0', linewidth=0.8, linestyle=':')
            self.ax.axhline(y=p_op, color='#78ade0', linewidth=0.8, linestyle=':')
            self.ax.annotate(f'  Q = {q_op:.0f}\n  Pwf = {p_op:.0f}',
                             xy=(q_op, p_op),
                             xytext=(q_op + 30, p_op + 50),
                             fontsize=8, color='#12324f')

        legend = self.ax.legend(fontsize=8, loc='upper right')
        if legend:
            legend.get_frame().set_facecolor('#f5fbff')
            legend.get_frame().set_edgecolor('#b8d4ee')
            for text in legend.get_texts():
                text.set_color('#12324f')
        self.ax.set_xlim(left=0)
        self.ax.set_ylim(bottom=0)
        self.canvas.draw()

    def clear(self):
        self.ax.cla()
        self._style_axes()
        self.lines = []
        self.canvas.draw()

    def on_hover(self, event):
        if event.inaxes != self.ax or not self.lines:
            self._hide_annot()
            return
        
        closest_line = None
        closest_dist = float('inf')
        closest_point = None
        closest_label = ""

        # Find the closest point among all plotted lines
        for line, label in self.lines:
            xdata = line.get_xdata()
            ydata = line.get_ydata()
            if len(xdata) == 0:
                continue

            # Convert line data points and mouse position to screen coordinates (pixels)
            xy_disp = self.ax.transData.transform(np.column_stack((xdata, ydata)))
            mouse_x, mouse_y = event.x, event.y

            # Calculate Euclidean distance
            dists = np.hypot(xy_disp[:, 0] - mouse_x, xy_disp[:, 1] - mouse_y)
            min_idx = np.argmin(dists)
            min_dist = dists[min_idx]

            if min_dist < closest_dist:
                closest_dist = min_dist
                closest_point = (xdata[min_idx], ydata[min_idx])
                closest_line = line
                closest_label = label

        # Display tooltip if cursor is close to the line (within 20 pixels)
        if closest_dist < 20 and closest_point is not None:
            x_val, y_val = closest_point
            text = f"{closest_label}:\nQ = {x_val:.1f} STB/d at P = {y_val:.1f} psia"
            
            self.annot.xy = closest_point
            self.annot.set_text(text)
            
            # Prevent tooltip from clipping/contracting the graph when near the right edge
            xlim = self.ax.get_xlim()
            x_mid = (xlim[0] + xlim[1]) / 2.0
            if x_val > x_mid:
                self.annot.set_position((-15, 15))
                self.annot.set_ha('right')
            else:
                self.annot.set_position((15, 15))
                self.annot.set_ha('left')
            
            line_color = closest_line.get_color()
            self.annot.get_bbox_patch().set_edgecolor(line_color)
            self.annot.get_bbox_patch().set_facecolor('#f5fbff')
            
            # Match the arrow color to the line color
            if hasattr(self.annot, 'arrow_patch') and self.annot.arrow_patch is not None:
                self.annot.arrow_patch.set_color(line_color)
                self.annot.arrow_patch.set_edgecolor(line_color)
                self.annot.arrow_patch.set_facecolor(line_color)
            
            self.hover_dot.set_data([x_val], [y_val])
            self.hover_dot.set_color(line_color)
            
            self.annot.set_visible(True)
            self.hover_dot.set_visible(True)
            self.canvas.draw_idle()
        else:
            self._hide_annot()

    def _hide_annot(self):
        if self.annot.get_visible() or self.hover_dot.get_visible():
            self.annot.set_visible(False)
            self.hover_dot.set_visible(False)
            self.canvas.draw_idle()
