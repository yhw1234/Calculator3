# -*- coding: utf-8 -*-
"""
文本计算器主程序 — PyQt6 GUI
功能：
- 多行文本工作区，逐行计算
- 支持：+ - * / ^ ** % // 括号、函数、常量、变量、单位、阶乘、百分号、隐式乘法
- 设置：小数位、保存结果、复制结果、复制到剪贴板、笔记本用户、*/替换成×÷、窗口前置、字体大小颜色、角度模式
- 帮助对话框
- 自动保存/加载上次计算结果与窗口位置
"""
import sys
import os
import json
import re
import math
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QToolBar, QPushButton, QDialog, QFormLayout,
    QSpinBox, QCheckBox, QLabel, QFontComboBox, QSpinBox as QFontSizeSpin,
    QColorDialog, QComboBox, QMessageBox, QGridLayout, QFrame, QScrollArea,
    QSizePolicy, QTextEdit, QToolButton, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QSettings, QPoint, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QKeySequence, QTextCursor, QPalette

# 导入计算引擎
import calc_engine
from calc_engine import (
    evaluate, format_result, SafeEvaluator, CalcError,
    DEG, RAD, GRAD, FUNCTIONS
)

APP_NAME = "文本计算器 V5.0"
ORG_NAME = "WorkBuddy"

# 数字键盘按钮
NUMPAD_KEYS = [
    ['7', '8', '9', '÷', 'C'],
    ['4', '5', '6', '×', '⌫'],
    ['1', '2', '3', '-', '('],
    ['0', '.', '%', '+', ')'],
    ['sin(', 'cos(', 'tan(', '√(', '='],
    ['π', '^', 'e', 'ln(', '^2'],
]

FUNC_LIST = [
    "sin( ", "cos( ", "tan( ", "ctg( ", "asin( ", "acos( ", "atan( ",
    "sinh( ", "cosh( ", "tanh( ", "ln( ", "lg( ", "log( ", "exp( ",
    "sqrt( ", "cbrt( ", "abs( ", "round( ", "floor( ", "ceil( ",
    "fact( ", "gcd( ", "lcm( ", "mod( ", "min( ", "max( ", "avg( ",
    "hypot( ", "comb( ", "perm( ", "deg( ", "rad( ", "clamp( ",
]


class CalcEdit(QPlainTextEdit):
    """多行文本编辑区，逐行计算"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(4)
        # 等宽字体
        font = QFont("Consolas")
        font.setPointSize(11)
        self.setFont(font)


class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        # 分组框
        from PyQt6.QtWidgets import QGroupBox
        gbox = QGroupBox("功能选项设置")
        form = QFormLayout(gbox)

        # 小数位数
        self.dec_spin = QSpinBox()
        self.dec_spin.setRange(0, 15)
        self.dec_spin.setValue(settings.get("precision", 6))
        form.addRow("计算结果中小数点位数", self.dec_spin)

        # 角度模式
        self.angle_combo = QComboBox()
        self.angle_combo.addItems(["角度 (DEG)", "弧度 (RAD)", "百分度 (GRAD)"])
        am = settings.get("angle_mode", DEG)
        idx = {DEG: 0, RAD: 1, GRAD: 2}.get(am, 0)
        self.angle_combo.setCurrentIndex(idx)
        form.addRow("角度模式", self.angle_combo)

        # 保存计算结果
        self.save_check = QCheckBox("保存计算结果")
        self.save_check.setChecked(settings.get("save_result", True))
        form.addRow("", self.save_check)

        # 复制计算结果
        self.copy_check = QCheckBox("复制计算结果")
        self.copy_check.setChecked(settings.get("copy_result", True))
        form.addRow("", self.copy_check)

        # 复制到剪贴板
        self.clipboard_check = QCheckBox("复制到剪贴板")
        self.clipboard_check.setChecked(settings.get("clipboard", False))
        form.addRow("", self.clipboard_check)

        # 笔记本用户
        self.notebook_check = QCheckBox("笔记本用户")
        self.notebook_check.setChecked(settings.get("notebook", False))
        form.addRow("", self.notebook_check)

        # */替换成×÷
        self.sym_replace_check = QCheckBox("*/替换成×÷")
        self.sym_replace_check.setChecked(settings.get("sym_replace", True))
        form.addRow("", self.sym_replace_check)

        # 窗口前置
        self.topmost_check = QCheckBox("窗口前置")
        self.topmost_check.setChecked(settings.get("topmost", False))
        form.addRow("", self.topmost_check)

        # 自动计算
        self.auto_check = QCheckBox("自动计算（输入即算）")
        self.auto_check.setChecked(settings.get("auto_calc", False))
        form.addRow("", self.auto_check)

        layout.addWidget(gbox)

        # 字体设置
        font_box = QGroupBox("字体大小和颜色")
        font_layout = QHBoxLayout(font_box)

        font_label = QLabel("字体:")
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(settings.get("font_family", "Consolas")))
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_combo, 1)

        size_label = QLabel("字号:")
        self.size_spin = QFontSizeSpin()
        self.size_spin.setRange(8, 40)
        self.size_spin.setValue(settings.get("font_size", 11))
        font_layout.addWidget(size_label)
        font_layout.addWidget(self.size_spin)

        layout.addWidget(font_box)

        # 颜色按钮
        color_row = QHBoxLayout()
        self.fg_color_btn = QPushButton("前景颜色…")
        self.fg_color_btn.clicked.connect(self.pick_fg_color)
        self.bg_color_btn = QPushButton("背景颜色…")
        self.bg_color_btn.clicked.connect(self.pick_bg_color)
        color_row.addWidget(self.fg_color_btn)
        color_row.addWidget(self.bg_color_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def pick_fg_color(self):
        color = QColorDialog.getColor(QColor(self.settings.get("fg_color", "#000000")), self)
        if color.isValid():
            self.settings["fg_color"] = color.name()
            self.fg_color_btn.setStyleSheet(f"background-color:{color.name()}")

    def pick_bg_color(self):
        color = QColorDialog.getColor(QColor(self.settings.get("bg_color", "#FFFFFF")), self)
        if color.isValid():
            self.settings["bg_color"] = color.name()
            self.bg_color_btn.setStyleSheet(f"background-color:{color.name()}")

    def get_settings(self):
        s = dict(self.settings)
        s["precision"] = self.dec_spin.value()
        am_idx = self.angle_combo.currentIndex()
        s["angle_mode"] = {0: DEG, 1: RAD, 2: GRAD}[am_idx]
        s["save_result"] = self.save_check.isChecked()
        s["copy_result"] = self.copy_check.isChecked()
        s["clipboard"] = self.clipboard_check.isChecked()
        s["notebook"] = self.notebook_check.isChecked()
        s["sym_replace"] = self.sym_replace_check.isChecked()
        s["topmost"] = self.topmost_check.isChecked()
        s["auto_calc"] = self.auto_check.isChecked()
        s["font_family"] = self.font_combo.currentFont().family()
        s["font_size"] = self.size_spin.value()
        return s


class HelpDialog(QDialog):
    """帮助对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助")
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("background-color:#FFFDE7; font-family:'Microsoft YaHei'; font-size:12pt;")
        help_html = """
        <h2>文本计算器说明</h2>
        <h3>一、用法</h3>
        <ol>
        <li>文本计算器具有关闭时是否保存计算结果的功能、计算结果的小数位选择功能。</li>
        <li>文本计算器打开时，可以自动加载上次的计算结果以及上次关闭时窗口位置。</li>
        <li>双击计算器的文本框可打开数字键盘，方便笔记本用户使用。</li>
        <li>输入数学表达式后，按回车键，自动计算结果。</li>
        <li>一个表达式必须在一行内全部输入。</li>
        <li>表达式不输入内容时直接回车，不再出现错误提示。</li>
        <li>需要当记事本用时，在本行最前面加入 <b>:</b> 号，可不出现错误提示。</li>
        <li>表达式可以是加+、减-、乘*、除/、乘方^、括号()，以及数学函数组合。</li>
        <li>支持隐式乘法：2(3+4)、3π、2sin(30)、(1+2)(3+4)。</li>
        <li>支持变量：先输入 <b>x=5</b> 定义变量，再输入 <b>2x+1</b> 计算结果。</li>
        <li>支持单位换算：1km+500m、2kg*3、10min+30s。</li>
        <li>支持后缀阶乘：5!、3!+2。</li>
        <li>支持百分号：50% 表示 0.5。</li>
        </ol>
        <h3>二、支持的数学函数</h3>
        <p>sin、cos、tan、ctg/cot、asin、acos、atan、actg/acot、sinh/sh、cosh/ch、tanh/th、coth/cth、<br>
        ln、lg、lb、log、exp、sqrt、cbrt、root、abs、sign、floor、ceil、trunc、int、round、frac、<br>
        gcd、lcm、mod、min、max、avg/mean、sum、hypot、clamp、fact/factorial、perm、comb、<br>
        deg、rad、heaviside、sinc、rand、randint。</p>
        <p>常量：π(pi)、e、τ(tau)、φ(phi)、∞(inf)。</p>
        <p>示例：1+sin(30)（其中30为角度，按回车键后显示 1+sin(30)=1.5）。</p>
        <h3>三、其它说明</h3>
        <p>本程序基于 Python + PyQt6 开发，支持 Windows 双击 bat 启动。</p>
        """
        text.setHtml(help_html)
        layout.addWidget(text)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn.rejected.connect(self.reject)
        btn.clicked.connect(self.reject)
        layout.addWidget(btn)


class NumpadDialog(QDialog):
    """数字键盘对话框（笔记本用户）"""
    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.setWindowTitle("数字键盘")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(320, 260)

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(4)

        for r, row in enumerate(NUMPAD_KEYS):
            for c, key in enumerate(row):
                btn = QPushButton(key)
                btn.setFixedSize(56, 36)
                btn.clicked.connect(lambda checked, k=key: self.on_key(k))
                grid.addWidget(btn, r, c)
        layout.addLayout(grid)

    def on_key(self, key):
        if self.callback:
            self.callback(key)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(820, 600)

        # 设置
        self.settings = self.load_settings()
        self.variables = {}   # 用户变量

        # 中央部件：垂直布局 = 函数快捷栏 + 编辑器
        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 函数快捷输入栏（可滚动）
        self.func_bar = self.build_func_bar()
        vbox.addWidget(self.func_bar)

        # 主编辑区
        self.editor = CalcEdit(self)
        vbox.addWidget(self.editor, 1)

        self.setCentralWidget(central)

        # 应用设置
        self.apply_settings()

        # 工具栏
        self.setup_toolbar()

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 恢复窗口位置
        self.restore_geometry()

        # 自动加载上次计算结果
        self.load_previous()

        # 回车计算
        self.editor.installEventFilter(self)

    # ---------- 函数快捷栏 ----------
    def build_func_bar(self):
        """在编辑区上方构建函数点击输入栏，多行（3-4行）显示。
        点击按钮即在光标处插入对应函数文本。
        """
        # 可滚动容器（多行显示，固定高度足以容纳全部行，默认不滚动即可看全）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # 高度 = 5行×26px + 4×4px间距 + 8px边距 + 边框/滚动条余量
        scroll.setFixedHeight(176)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea{border:1px solid #cccccc; background:#f5f5f5;}")

        inner = QWidget()
        inner.setStyleSheet("background:#f5f5f5;")
        vbox = QVBoxLayout(inner)
        vbox.setContentsMargins(6, 4, 6, 4)
        vbox.setSpacing(4)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 按钮组：函数 + 常量 + 运算符，按行分组（每组一行）
        row_groups = [
            # 第1行：三角/反三角/双曲
            [
                ("sin(", "sin("), ("cos(", "cos("), ("tan(", "tan("),
                ("ctg(", "ctg("), ("asin(", "asin("), ("acos(", "acos("),
                ("atan(", "atan("), ("actg(", "actg("),
                ("sinh(", "sinh("), ("cosh(", "cosh("), ("tanh(", "tanh("),
                ("coth(", "coth("),
            ],
            # 第2行：对数/指数/根式
            [
                ("ln(", "ln("), ("lg(", "lg("), ("lb(", "lb("), ("log(", "log("),
                ("exp(", "exp("), ("√(", "sqrt("), ("∛(", "cbrt("),
                ("abs(", "abs("), ("sign(", "sign("), ("round(", "round("),
                ("floor(", "floor("), ("ceil(", "ceil("), ("trunc(", "trunc("),
            ],
            # 第3行：阶乘/数论/统计
            [
                ("fact(", "fact("), ("n!", "fact("),
                ("gcd(", "gcd("), ("lcm(", "lcm("), ("mod(", "mod("),
                ("min(", "min("), ("max(", "max("), ("avg(", "avg("),
                ("sum(", "sum("), ("hypot(", "hypot("), ("clamp(", "clamp("),
                ("comb(", "comb("), ("perm(", "perm("),
                ("deg(", "deg("), ("rad(", "rad("),
            ],
            # 第4行：其它函数/常量/运算符/快捷操作
            [
                ("heaviside(", "heaviside("), ("sinc(", "sinc("),
                ("π", "π"), ("e", "e"), ("τ", "tau"), ("φ", "phi"), ("∞", "inf"),
                ("^", "^"), ("%", "%"), ("//", "//"), ("!", "!"),
                ("(", "("), (")", ")"), (",", ","), ("=", "="),
            ],
        ]

        # 普通按钮样式
        normal_style = (
            "QPushButton{background:#ffffff;border:1px solid #c0c0c0;"
            "border-radius:4px;padding:2px 8px;font-size:12px;}"
            "QPushButton:hover{background:#e8f0fe;border-color:#7baaf7;}"
            "QPushButton:pressed{background:#d2e3fc;}"
        )

        for row_items in row_groups:
            hrow = QHBoxLayout()
            hrow.setSpacing(4)
            hrow.setContentsMargins(0, 0, 0, 0)
            hrow.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for label, insert in row_items:
                btn = QPushButton(label)
                btn.setFixedHeight(26)
                btn.setStyleSheet(normal_style)
                btn.clicked.connect(lambda checked, t=insert: self.insert_func_text(t))
                hrow.addWidget(btn)
            vbox.addLayout(hrow)

        # 快捷操作行（单独一行，放最下面）
        hrow = QHBoxLayout()
        hrow.setSpacing(4)
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setAlignment(Qt.AlignmentFlag.AlignLeft)
        quick = [
            ("清除", "clear"), ("退格", "backspace"), ("计算", "calc"),
        ]
        for label, act in quick:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                "QPushButton{background:#fff8e1;border:1px solid #e0c060;"
                "border-radius:4px;padding:2px 12px;font-size:12px;font-weight:bold;}"
                "QPushButton:hover{background:#fff3c4;}"
            )
            btn.clicked.connect(lambda checked, a=act: self.func_quick_action(a))
            hrow.addWidget(btn)
        hrow.addStretch()
        vbox.addLayout(hrow)

        scroll.setWidget(inner)
        return scroll

    def insert_func_text(self, text):
        """在光标处插入函数文本"""
        self.editor.insertPlainText(text)
        self.editor.setFocus()

    def func_quick_action(self, action):
        """快捷操作：清除 / 退格 / 计算"""
        if action == "clear":
            self.editor.clear()
        elif action == "backspace":
            cursor = self.editor.textCursor()
            cursor.deletePreviousChar()
        elif action == "calc":
            self.calculate_line()
        self.editor.setFocus()

    # ---------- 设置持久化 ----------
    def settings_path(self):
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "settings.json")

    def load_settings(self):
        default = {
            "precision": 6,
            "angle_mode": DEG,
            "save_result": True,
            "copy_result": True,
            "clipboard": False,
            "notebook": False,
            "sym_replace": True,
            "topmost": False,
            "auto_calc": False,
            "font_family": "Consolas",
            "font_size": 11,
            "fg_color": "#000000",
            "bg_color": "#FFFFFF",
        }
        try:
            with open(self.settings_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
        except Exception:
            pass
        return default

    def save_settings(self):
        try:
            with open(self.settings_path(), "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存设置失败:", e)

    def apply_settings(self):
        # 字体
        font = QFont(self.settings["font_family"], self.settings["font_size"])
        self.editor.setFont(font)
        # 颜色
        fg = QColor(self.settings.get("fg_color", "#000000"))
        bg = QColor(self.settings.get("bg_color", "#FFFFFF"))
        self.editor.setStyleSheet(f"QPlainTextEdit{{background-color:{bg.name()};color:{fg.name()};}}")
        # 窗口前置
        if self.settings.get("topmost", False):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        # 注意：不在 apply_settings 里 show()，由 main 统一 show

    # ---------- 工具栏 ----------
    def setup_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        # 计算按钮
        act_calc = QAction("计算", self)
        act_calc.triggered.connect(self.calculate_all)
        tb.addAction(act_calc)

        # 设置按钮
        act_set = QAction("设置", self)
        act_set.triggered.connect(self.open_settings)
        tb.addAction(act_set)

        # 帮助按钮
        act_help = QAction("帮助", self)
        act_help.triggered.connect(self.open_help)
        tb.addAction(act_help)

        tb.addSeparator()

        # 退出按钮
        act_exit = QAction("退出", self)
        act_exit.triggered.connect(self.close)
        tb.addAction(act_exit)

        # 清空
        act_clear = QAction("清空", self)
        act_clear.triggered.connect(self.editor.clear)
        tb.addAction(act_clear)

    # ---------- 事件 ----------
    def eventFilter(self, obj, event):
        if obj is self.editor and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.calculate_line()
                return True
            if event.key() == Qt.Key.Key_F9:
                self.calculate_all()
                return True
        return super().eventFilter(obj, event)

    # ---------- 计算 ----------
    def get_evaluator(self):
        return SafeEvaluator(
            variables=self.variables,
            angle_mode=self.settings.get("angle_mode", DEG),
            precision=self.settings.get("precision", 6),
        )

    def calculate_line(self):
        """计算当前光标所在行"""
        cursor = self.editor.textCursor()
        doc = self.editor.document()
        block = cursor.block()
        line_text = block.text().rstrip()
        line_num = block.blockNumber()

        if not line_text.strip():
            # 空行，不报错
            return
        # 记事本模式
        if line_text.strip().startswith(":"):
            return

        # 变量定义: x=5
        if self.try_define_variable(line_text):
            return

        result, err = evaluate(
            line_text,
            variables=self.variables,
            angle_mode=self.settings.get("angle_mode", DEG),
            precision=self.settings.get("precision", 6),
        )
        if err:
            # 错误输出到下一行
            self.append_line(f"错误: {err}", error=True)
            return

        # 结果格式化
        res_str = format_result(result, self.settings.get("precision", 6))

        # 替换显示
        new_line = f"{line_text}={res_str}"
        if self.settings.get("sym_replace", True):
            new_line = new_line.replace('*', '×').replace('/', '÷')

        # 替换当前行
        self.replace_line(line_num, new_line)

        # 追加结果行
        self.append_line(res_str)

        # 复制到剪贴板
        if self.settings.get("clipboard", False):
            QApplication.clipboard().setText(res_str)

        # 保存结果
        if self.settings.get("save_result", True):
            self.save_current(self.editor.toPlainText())

    def try_define_variable(self, line):
        """尝试解析 x=5 形式的变量定义"""
        m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$', line)
        if m:
            name = m.group(1)
            expr = m.group(2)
            # 避免把函数名当变量
            if name in ("e", "pi", "tau", "phi") or name.lower() in FUNCTIONS:
                return False
            val, err = evaluate(expr, variables=self.variables,
                                angle_mode=self.settings.get("angle_mode", DEG),
                                precision=self.settings.get("precision", 6))
            if not err:
                self.variables[name] = val
                res = format_result(val, self.settings.get("precision", 6))
                new_line = f"{line}  →  {res}"
                if self.settings.get("sym_replace", True):
                    new_line = new_line.replace('*', '×').replace('/', '÷')
                self.replace_line(self.editor.textCursor().block().blockNumber(), new_line)
                return True
        return False

    def calculate_all(self):
        """计算所有行"""
        text = self.editor.toPlainText()
        lines = text.split('\n')
        output_lines = []
        evaluator = self.get_evaluator()
        prec = self.settings.get("precision", 6)
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(":"):
                output_lines.append(line)
                continue
            # 变量定义
            if self.try_define_variable_line(line, evaluator):
                output_lines.append(line)
                continue
            val, err = evaluate(line, variables=self.variables,
                                angle_mode=self.settings.get("angle_mode", DEG),
                                precision=prec)
            if err:
                output_lines.append(f"{line}  →  错误: {err}")
            else:
                res = format_result(val, prec)
                output_lines.append(f"{line}={res}")
                output_lines.append(res)
        self.editor.setPlainText('\n'.join(output_lines))

    def try_define_variable_line(self, line, evaluator):
        m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$', line)
        if m:
            name = m.group(1)
            expr = m.group(2)
            if name in ("e", "pi", "tau", "phi") or name.lower() in FUNCTIONS:
                return False
            val, err = evaluate(expr, variables=self.variables,
                                angle_mode=self.settings.get("angle_mode", DEG),
                                precision=self.settings.get("precision", 6))
            if not err:
                self.variables[name] = val
                return True
        return False

    def append_line(self, text, error=False):
        """在文档末尾追加一行"""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # 确保前面有换行
        doc_text = self.editor.toPlainText()
        if doc_text and not doc_text.endswith('\n'):
            cursor.insertText('\n')
        cursor.insertText(text + "\n")

    def replace_line(self, line_num, text):
        """替换指定行文本（保留换行符）。line_num 从 0 开始。"""
        doc = self.editor.document()
        block = doc.findBlockByNumber(line_num)
        if block is None:
            return
        cursor = QTextCursor(block)
        # 选中块内全部文本（不含块分隔符/换行）
        cursor.setPosition(block.position())
        cursor.setPosition(block.position() + block.length() - 1,
                           QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)

    # ---------- 对话框 ----------
    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings = dlg.get_settings()
            self.apply_settings()
            self.save_settings()
            self.statusBar().showMessage("设置已保存")

    def open_help(self):
        dlg = HelpDialog(self)
        dlg.exec()

    def open_numpad(self):
        dlg = NumpadDialog(self, callback=self.numpad_key)
        dlg.exec()

    def numpad_key(self, key):
        if key == 'C':
            self.editor.clear()
        elif key == '⌫':
            cursor = self.editor.textCursor()
            cursor.deletePreviousChar()
        elif key == '=':
            self.calculate_line()
        else:
            # 映射 × ÷
            k = key
            if k == '×':
                k = '*'
            elif k == '÷':
                k = '/'
            self.editor.insertPlainText(k)

    # ---------- 持久化 ----------
    def save_current(self, text):
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "last.txt"),
                      "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    def load_previous(self):
        try:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last.txt")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    self.editor.setPlainText(f.read())
        except Exception:
            pass

    def restore_geometry(self):
        # 简单恢复窗口位置（用 settings 文件存）
        try:
            geo = self.settings.get("window_geo")
            if geo:
                x, y, w, h = geo
                self.setGeometry(x, y, w, h)
        except Exception:
            pass

    def closeEvent(self, event):
        # 保存窗口几何
        try:
            geo = self.geometry()
            self.settings["window_geo"] = [geo.x(), geo.y(), geo.width(), geo.height()]
            if self.settings.get("save_result", True):
                self.save_current(self.editor.toPlainText())
            self.save_settings()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
