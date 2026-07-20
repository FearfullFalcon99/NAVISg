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
        self.ax.set_facecolor("#FFFFFF")
        self.figure.patch.set_facecolor('#FFFFFF')
        self.ax.set_xlabel('Liquid Rate [STB/d]', fontsize=9, fontweight='semibold')
        self.ax.set_ylabel('FBHP [psia]', fontsize=9, fontweight='semibold')
        self.ax.set_title('IPR / VLP — Nodal Analysis', fontsize=11, fontweight='bold')
        
        # Gridlines removed per instructions
        self.ax.grid(False) 
        
        self.ax.tick_params(labelsize=8, colors='#2D1E1E')
        self.ax.xaxis.label.set_color('#2D1E1E')
        self.ax.yaxis.label.set_color('#2D1E1E')
        self.ax.title.set_color('#8B1E1E')
        for spine in self.ax.spines.values():
            spine.set_color('#D4C3C3')

        # Create annotation for hover
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(15,15),
                                     textcoords="offset points",
                                     bbox=dict(boxstyle="round,pad=0.6", fc="#FFFFFF", ec="#8B1E1E", lw=1.5, alpha=0.97),
                                     arrowprops=dict(arrowstyle="-|>", connectionstyle="arc3,rad=0.1", color="#8B1E1E"),
                                     fontsize=11, fontweight='semibold', color='#2D1E1E', zorder=10) # Increased fontsize from 8 to 11
        self.annot.set_visible(False)

        # Create hover dot
        self.hover_dot, = self.ax.plot([], [], 'o', color='#8B1E1E', markersize=6, zorder=9)
        self.hover_dot.set_visible(False)

    # ui/plot_widget.py (Replace only the plot method block)-----------------------------------

    def plot(self, ipr_data=None, vlp_curves=None, op_point=None):
        self._hide_annot()  # <--- ADD THIS: Hides the tooltip before clearing axes
        self.ax.cla()
        self._style_axes()
        self.lines = []
        
        # ... (rest of your plot logic remains exactly the same)

        colors = ['#8B1E1E', '#A32B2B', '#B23A3A', '#CD5C5C', '#E9967A']
        
        # Dynamic Scaler Boundaries
        max_q = 0
        max_p = 0
        pr_val = float('inf')  # Default limit if IPR data is absent

        # Detect if this is a comparison plot (Future vs Current)
        is_comparison = any(c and 'Current IPR' in c.get('label', '') for c in (vlp_curves or []))

        if ipr_data is not None:
            rates, pwfs = ipr_data
            mask_ipr = pwfs >= 0
            if len(rates[mask_ipr]) > 0:
                max_q = max(max_q, np.max(rates[mask_ipr]))
                max_p = max(max_p, np.max(pwfs[mask_ipr]))
                # The highest pressure in the IPR curve is the Avg. Reservoir Pressure
                pr_val = np.max(pwfs[mask_ipr])
                
            # Shift Future IPR to theme red during comparison, otherwise keep base blackish brown
            ipr_label = 'Future IPR' if is_comparison else 'IPR (Inflow performance curve)'
            ipr_color = '#8B1E1E' if is_comparison else '#2D1E1E'
                
            line, = self.ax.plot(rates[mask_ipr], pwfs[mask_ipr], color=ipr_color, linewidth=2.5, linestyle='-', label=ipr_label)
            self.lines.append((line, ipr_label))

        if vlp_curves:
            # Extended fallback palette
            colors = ['#8B1E1E', '#A32B2B', '#B23A3A', '#CD5C5C', '#E9967A']
            
            for i, curve in enumerate(vlp_curves):
                if curve is None: continue 
                
                label = curve.get('label', '')
                
                # Apply high-contrast overrides for comparison curves
                if 'Current IPR' in label:
                    color = '#12324f'  # Deep Blue
                    linestyle = '--'
                    linewidth = 2.5
                elif 'Current VLP' in label:
                    color = '#4682B4'  # Steel Blue
                    linestyle = '-.'
                    linewidth = 2.0
                else:
                    color = colors[i % len(colors)]
                    linestyle = '-'
                    linewidth = 2.0
                
                v_rates = np.array(curve['rates'])
                v_bhps = np.array(curve['bhps'])
                
                # --- Filter points so FBHP doesn't exceed Avg. Reservoir Pressure ---
                # Bypass the clipping filter if the curve is a comparison 'IPR'
                if 'IPR' in label:
                    mask_vlp = np.ones_like(v_bhps, dtype=bool)
                else:
                    mask_vlp = v_bhps <= pr_val
                # ------------------------------------------------------------------------
                
                v_rates_filtered = v_rates[mask_vlp]
                v_bhps_filtered = v_bhps[mask_vlp]
                
                if len(v_rates_filtered) > 0:
                    max_q = max(max_q, np.max(v_rates_filtered))
                    max_p = max(max_p, np.max(v_bhps_filtered))
                    
                line, = self.ax.plot(v_rates_filtered, v_bhps_filtered, color=color, linewidth=linewidth, linestyle=linestyle, label=label)
                self.lines.append((line, label))

        if op_point and op_point[0] is not None:
            q_op, p_op = op_point
            self.ax.plot(q_op, p_op, 'o', color='#D4C3C3', markeredgecolor='#8B1E1E', markersize=8, zorder=5, label=f'Op. point  Q={q_op:.0f} STB/d  Pwf={p_op:.0f} psia')
            self.ax.axvline(x=q_op, color='#A32B2B', linewidth=1, linestyle='--')
            self.ax.axhline(y=p_op, color='#A32B2B', linewidth=1, linestyle='--')
            self.ax.annotate(f'  Q = {q_op:.0f}\n  Pwf = {p_op:.0f}', xy=(q_op, p_op), xytext=(q_op + (max_q*0.02), p_op + (max_p*0.02)), fontsize=8, color='#2D1E1E')

        # Prevent Scaling Failure if there's completely blank / zero data
        if max_q == 0: max_q = 1000
        if max_p == 0: max_p = 1000

        # Enforce intervals strictly at 250 units without gridlines
        max_q_scaled = int(np.ceil(max_q / 250.0)) * 250
        max_p_scaled = int(np.ceil(max_p / 250.0)) * 250 + 250  # Add extra 250 to ensure visibility of topmost data point
        
        # Lower bound protection to maintain interval visibility
        max_q_scaled = max(500, max_q_scaled)
        max_p_scaled = max(500, max_p_scaled)

        self.ax.set_xlim(0, max_q_scaled)
        self.ax.set_ylim(0, max_p_scaled)
        self.ax.set_xticks(np.arange(0, max_q_scaled + 1, 250))
        self.ax.set_yticks(np.arange(0, max_p_scaled + 1, 250))

        legend = self.ax.legend(fontsize=10, loc='upper right') 
        if legend:
            legend.get_frame().set_facecolor('#FFFFFF')
            legend.get_frame().set_edgecolor('#D4C3C3')
            for text in legend.get_texts():
                text.set_color('#2D1E1E')
                
        self.canvas.draw()

    def clear(self):
        self._hide_annot()  # <--- ADD THIS HERE TOO
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


# New Traverse Plot ----------------------------------------------------------------

class TraversePlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(6, 5), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self._style_axes()
        
    def _style_axes(self):
        self.ax.set_facecolor("#FFFFFF")
        self.figure.patch.set_facecolor('#FFFFFF')
        self.ax.set_xlabel('Pressure [psia]', fontsize=10, fontweight='semibold')
        self.ax.set_ylabel('Measured Depth [ft]', fontsize=10, fontweight='semibold')
        
        # Requirement: Pressure at the top of the plot, Depth at left (inverted)
        self.ax.xaxis.tick_top()
        self.ax.xaxis.set_label_position('top')
        self.ax.invert_yaxis()
        
        self.ax.grid(True, linestyle='--', alpha=0.6, color='#D4C3C3')
        self.ax.tick_params(labelsize=9, colors='#2D1E1E')
        self.ax.xaxis.label.set_color('#2D1E1E')
        self.ax.yaxis.label.set_color('#2D1E1E')
        for spine in self.ax.spines.values():
            spine.set_color('#D4C3C3')
            
    def plot_traverse(self, traverse_tubing, traverse_casing, inj_depth, op_point=None):
        self.ax.cla()
        self._style_axes()
        
        if traverse_casing:
            deps_c = [pt[0] for pt in traverse_casing]
            pres_c = [pt[1] for pt in traverse_casing]
            self.ax.plot(pres_c, deps_c, color='#A32B2B', linestyle='--', linewidth=2, label='Casing Gas Pressure')
            
        if traverse_tubing:
            deps_t = [pt[0] for pt in traverse_tubing]
            pres_t = [pt[1] for pt in traverse_tubing]
            self.ax.plot(pres_t, deps_t, color='#12324f', linestyle='-', linewidth=2.5, label='Tubing Traverse')
            
        if inj_depth:
            self.ax.axhline(y=inj_depth, color='#8B1E1E', linestyle=':', linewidth=1.5)
            self.ax.text(
                min(pres_c if traverse_casing else [0]) + 50, inj_depth - 50, 
                f"Injection @ {inj_depth:.0f} ft", color='#8B1E1E', fontsize=9, fontweight='bold'
            )
            
        self.ax.set_xlim(left=0)
        self.ax.set_ylim(bottom=max([pt[0] for pt in traverse_tubing] if traverse_tubing else [10000]), top=0)
        
        legend = self.ax.legend(fontsize=9, loc='lower left')
        if legend:
            legend.get_frame().set_facecolor('#FFFFFF')
            legend.get_frame().set_edgecolor('#D4C3C3')
            for text in legend.get_texts(): text.set_color('#2D1E1E')
            
        self.canvas.draw()
        
    def clear(self):
        self.ax.cla()
        self._style_axes()
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
        
# --------------------------------------------------------------------------------------------------