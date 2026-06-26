# Nodal Analysis UI Package (ui/)

This package implements the graphical user interface for the Nodal Analysis application using **PySide6** and **Matplotlib**. It provides a desktop workspace to configure reservoir/wellbore parameters, run background computations, perform sensitivity analyses, and visualize inflow/outflow curves.

---

## Component Architecture

The interface is structured into three main modules cooperating under a Model-View-Presenter/Controller style:

```
                  ┌─────────────────────────────────┐
                  │           MainWindow            │
                  │       (ui/main_window.py)       │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌──────────────────┐                               ┌──────────────────┐
│    InputPanel    │                               │    PlotWidget    │
│(ui/input_panel.py)│                               │(ui/plot_widget.py)│
└──────────────────┘                               └──────────────────┘
```

### 1. MainWindow (`ui/main_window.py`)
The primary application window that manages layouts, layout resizing (`QSplitter`), the status bar, and multithreading.
*   **Background Worker (`Worker` & `QThread`)**: Performs heavy numerical calculations (reservoir IPR points and wellbore pressure traverses) in a separate thread. This prevents the UI from freezing or stuttering during calculations.
*   **Consistency Checks**: Includes validation rules (e.g., verifying user-entered bubblepoint pressures against calculated thermodynamics from Standing's correlation).
*   **Status Bar**: Displays live run diagnostics, including operating flow rate ($Q_o$), flowing bottomhole pressure ($P_{wf}$), Absolute Open Flow (AOF/Qmax), Productivity Index ($J$), and recovery efficiency.

### 2. InputPanel (`ui/input_panel.py`)
A scrollable, form-based sidebar hosting user inputs. Numerical values utilize bounded `QDoubleSpinBox` fields with custom unit suffixes.
*   **Reservoir (IPR)**: Model selection (Vogel or Composite), average reservoir pressure ($P_r$), bubblepoint ($P_b$), and well test point data.
*   **Fluid Properties**: Specific gravities, API gravity, GOR, and WOR.
*   **Well & Tubing (VLP)**: Selected correlation (e.g., Hagedorn-Brown), well depth (TVD), tubing ID, wellhead pressure (WHP), surface/bottomhole temperatures, and pipe roughness.
*   **Sensitivity (VLP)**: Lets users select a parameter (WHP, GOR, or Tubing ID) to vary across a min/max range in a specified number of steps.
*   **Run Button**: Triggers the analysis workflow by gathering all widget values into a configuration dictionary.

### 3. PlotWidget (`ui/plot_widget.py`)
An interactive plotting canvas wrapping a Matplotlib figure widget.
*   **IPR curve**: Plots reservoir inflow capacity.
*   **VLP curves**: Plots wellbore tubing outflow performance (including multiple curves if sensitivity analysis is active).
*   **Operating Point**: Computes and highlights the intersection of inflow and outflow curves, labeling the coordinate directly on the canvas.

---

## Application Workflow

```
1. User adjusts inputs in InputPanel & clicks "Run Analysis"
                       │
                       ▼
2. MainWindow gathers parameter dict & spins up Worker thread
                       │
                       ▼
3. Worker thread runs vogel_ipr(...) and compute_vlp_curve(...)
                       │
                       ▼
4. Worker emits finished(result) ──► MainWindow stops thread
                       │
                       ▼
5. MainWindow updates Status Bar & PlotWidget draws curves
```

---

## Sensitivity Analysis Capabilities
The UI supports live parameter sweeps to evaluate well performance under different operating conditions:
1.  **WHP (Wellhead Pressure)**: Simulates the effect of changing choke sizes or flowline backpressures.
2.  **GOR (Gas-Oil Ratio)**: Analyzes well behavior during gas breakthrough or simulates gas-lift optimization.
3.  **Tubing ID**: Helps size production tubing diameters during completion design.
