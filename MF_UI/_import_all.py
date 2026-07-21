"""PyInstaller analysis helper — 强制导入所有子模块确保被打包收集。"""
# plot submodules
import plot.fractal.workspace      # noqa
import plot.basic.workspace        # noqa
import plot.basic.function_box     # noqa
import plot.basic.plot_canvas      # noqa
import plot.basic.slider_function_box  # noqa
import plot.complex.workspace      # noqa
import plot.vector_field.workspace # noqa
import plot.plot_3d.workspace      # noqa
import plot.plot_3d.canvas         # noqa
import plot.plot_3d.function_box   # noqa
import plot.arbitrary.workspace    # noqa
import plot.arbitrary.geometry_canvas  # noqa
import plot.arbitrary.shapes       # noqa
import plot.arbitrary.undo_manager # noqa
import plot.mpl_setup              # noqa
import plot.plot_colors            # noqa
import plot.grid_renderer          # noqa

# calc submodules
import calc.basic_arithmetic.workspace  # noqa
import calc.basic_arithmetic.calculator # noqa
import calc.algebra.workspace      # noqa
import calc.algebra.calc_block     # noqa
import calc.algebraic_topology.workspace  # noqa
import calc.algebraic_topology.calc_block # noqa
import calc.analytic_geometry.workspace  # noqa
import calc.analytic_geometry.calc_block # noqa
import calc.calculus.workspace     # noqa
import calc.calculus.calc_block    # noqa
import calc.complex_analysis.workspace  # noqa
import calc.complex_analysis.calc_block # noqa
import calc.functional_analysis.workspace  # noqa
import calc.functional_analysis.calc_block # noqa
import calc.linear_algebra.workspace  # noqa
import calc.linear_algebra.calc_block # noqa
import calc.measure_theory.workspace  # noqa
import calc.measure_theory.calc_block # noqa
import calc.number_theory.workspace   # noqa
import calc.number_theory.calc_block  # noqa
import calc.numerical.workspace    # noqa
import calc.numerical.calc_block   # noqa
import calc.probability.workspace  # noqa
import calc.probability.calc_block # noqa
import calc.real_analysis.workspace    # noqa
import calc.real_analysis.calc_block   # noqa
import calc.sequences.workspace    # noqa
import calc.sequences.calc_block   # noqa
import calc.base_calc_block        # noqa
import calc.base_workspace         # noqa
import calc.math_display           # noqa
import calc.numerical_estimation   # noqa
import calc.step_viewer            # noqa

# root-level modules
import calc_engine                 # noqa
import compute_worker              # noqa
import math_keyboard               # noqa

# components
import components.custom_title_bar # noqa
import components.dialog_style     # noqa
import components.mf_dialog        # noqa

# dialogs
import dialogs.about_dialog        # noqa
import dialogs.ai_config_prompt    # noqa
import dialogs.ai_dialog           # noqa
import dialogs.history_dialog      # noqa
import dialogs.search_panel        # noqa
import dialogs.settings_dialog     # noqa

# MF_User — 用户认证系统
import MF_User.auth_service        # noqa
import MF_User.auth_worker         # noqa
import MF_User.api_client          # noqa
import MF_User.login_dialog        # noqa

# utils
import utils.math_guard            # noqa
import utils.math_guard_ui         # noqa
import utils.translator            # noqa
