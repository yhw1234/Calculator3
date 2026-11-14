# -*- coding: utf-8 -*-
"""
calc_engine.py — 文本计算器核心计算引擎
安全表达式求值：使用 ast 模块解析，禁止任意代码执行。
"""
import ast
import math
import re
import cmath
import random
from fractions import Fraction

# ---------------- 常量 ----------------
PI = math.pi
E = math.e
PHI = (1 + math.sqrt(5)) / 2  # 黄金分割
INF = float('inf')
NAN = float('nan')

# 角度模式
DEG = 'DEG'
RAD = 'RAD'
GRAD = 'GRAD'


class CalcError(Exception):
    """计算错误（用户可读）"""
    pass


# ---------------- 数学函数（安全白名单） ----------------
def _fact(n):
    """阶乘：支持整数与半整数(如 5.5!)"""
    if isinstance(n, bool):
        n = int(n)
    if n < 0:
        raise CalcError("阶乘参数不能为负数")
    if float(n) == int(n):
        return math.factorial(int(n))
    # 半整数阶乘 (2k+1)!! 通过 gamma
    return math.gamma(n + 1)


def _perm(n, k):
    n = int(n); k = int(k)
    if k < 0 or n < 0 or k > n:
        raise CalcError("排列参数错误")
    return math.factorial(n) // math.factorial(n - k)


def _comb(n, k):
    n = int(n); k = int(k)
    if k < 0 or n < 0 or k > n:
        raise CalcError("组合参数错误")
    return math.comb(n, k)


def _gcd(*args):
    vals = [int(a) for a in args]
    if len(vals) == 1 and isinstance(vals[0], (list, tuple)):
        vals = [int(x) for x in vals[0]]
    if not vals:
        raise CalcError("gcd 至少需要一个参数")
    r = vals[0]
    for v in vals[1:]:
        r = math.gcd(r, v)
    return r


def _lcm(*args):
    vals = [int(a) for a in args]
    if len(vals) == 1 and isinstance(vals[0], (list, tuple)):
        vals = [int(x) for x in vals[0]]
    if not vals:
        raise CalcError("lcm 至少需要一个参数")
    r = vals[0]
    for v in vals[1:]:
        if r == 0 or v == 0:
            return 0
        r = abs(r * v) // math.gcd(r, v)
    return r


def _log(x, base=10):
    if x <= 0:
        raise CalcError("对数参数必须为正数")
    return math.log(x, base)


def _ln(x):
    if x <= 0:
        raise CalcError("ln 参数必须为正数")
    return math.log(x)


def _lg(x):
    if x <= 0:
        raise CalcError("lg 参数必须为正数")
    return math.log10(x)


def _lb(x):
    if x <= 0:
        raise CalcError("lb 参数必须为正数")
    return math.log2(x)


def _sqrt(x):
    if x < 0:
        return complex(0, math.sqrt(-x))
    return math.sqrt(x)


def _cbrt(x):
    if x < 0:
        return -math.pow(-x, 1 / 3)
    return math.pow(x, 1 / 3)


def _root(x, n):
    if n == 0:
        raise CalcError("根指数不能为0")
    if x < 0 and int(n) % 2 == 1:
        return -math.pow(-x, 1.0 / n)
    if x < 0:
        return cmath.exp(cmath.log(x) / n)
    return math.pow(x, 1.0 / n)


def _mod(a, b):
    if b == 0:
        raise CalcError("除数不能为0")
    return a % b


def _round(x, ndigits=None):
    if ndigits is None:
        return round(x)
    return round(x, int(ndigits))


def _int(x):
    return int(x)


def _floor(x):
    return math.floor(x)


def _ceil(x):
    return math.ceil(x)


def _trunc(x):
    return math.trunc(x)


def _sign(x):
    if x > 0: return 1
    if x < 0: return -1
    return 0


def _abs(x):
    return abs(x)


def _min(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return min(args[0])
    return min(args)


def _max(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return max(args[0])
    return max(args)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _avg(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
    if not args:
        raise CalcError("avg 至少需要一个参数")
    return sum(args) / len(args)


def _sum(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return sum(args[0])
    return sum(args)


def _hypot(*args):
    return math.hypot(*args)


def _deg(x):
    return math.degrees(x)


def _rad(x):
    return math.radians(x)


def _grad_to_deg(x):
    return x * 0.9


# 双曲函数简写
def _sinh(x): return math.sinh(x)
def _cosh(x): return math.cosh(x)
def _tanh(x): return math.tanh(x)
def _asinh(x): return math.asinh(x)
def _acosh(x): return math.acosh(x)
def _atanh(x): return math.atanh(x)


def _sech(x): return 1 / math.cosh(x)
def _csch(x): return 1 / math.sinh(x)
def _coth(x): return 1 / math.tanh(x)


def _heaviside(x):
    return 0 if x < 0 else 1


def _sinc(x):
    if x == 0:
        return 1.0
    return math.sin(x) / x


def _rand():
    return random.random()


def _randint(a, b):
    return random.randint(int(a), int(b))


def _deg2(x):
    """度→弧度（角度模式转换用，内部）"""
    return math.radians(x)


def _grad2(x):
    return math.radians(x * 0.9)


# 支持的数学函数表。值可为 callable 或 (callable, is_angle_sensitive)
FUNCTIONS = {
    # 三角函数（角度模式敏感）
    'sin': (lambda x, m: _trig('sin', x, m), True),
    'cos': (lambda x, m: _trig('cos', x, m), True),
    'tan': (lambda x, m: _trig('tan', x, m), True),
    'ctg': (lambda x, m: _trig('ctg', x, m), True),
    'cot': (lambda x, m: _trig('ctg', x, m), True),
    'sec': (lambda x, m: _trig('sec', x, m), True),
    'csc': (lambda x, m: _trig('csc', x, m), True),
    'asin': (lambda x, m: _atrig('asin', x, m), True),
    'acos': (lambda x, m: _atrig('acos', x, m), True),
    'atan': (lambda x, m: _atrig('atan', x, m), True),
    'actg': (lambda x, m: _atrig('actg', x, m), True),
    'acot': (lambda x, m: _atrig('actg', x, m), True),
    'atan2': (lambda y, x, m: _atrig2(y, x, m), True),
    # 双曲
    'sinh': (_sinh, False), 'sh': (_sinh, False),
    'cosh': (_cosh, False), 'ch': (_cosh, False),
    'tanh': (_tanh, False), 'th': (_tanh, False),
    'coth': (_coth, False), 'cth': (_coth, False),
    'asinh': (_asinh, False), 'arcsinh': (_asinh, False),
    'acosh': (_acosh, False), 'arccosh': (_acosh, False),
    'atanh': (_atanh, False), 'arctanh': (_atanh, False),
    'sech': (_sech, False), 'csch': (_csch, False),
    # 对数 / 指数
    'ln': (_ln, False), 'log': (_log, False), 'lg': (_lg, False),
    'lb': (_lb, False), 'log2': (_lb, False), 'log10': (_lg, False),
    'exp': (math.exp, False), 'e': (lambda: E, False),
    'sqrt': (_sqrt, False), 'cbrt': (_cbrt, False), 'root': (_root, False),
    'abs': (_abs, False), 'fabs': (math.fabs, False),
    'sign': (_sign, False), 'sgn': (_sign, False),
    'floor': (_floor, False), 'ceil': (_ceil, False),
    'trunc': (_trunc, False), 'int': (_int, False),
    'round': (_round, False), 'frac': (lambda x: x - math.floor(x), False),
    'mod': (_mod, False), 'gcd': (_gcd, False), 'lcm': (_lcm, False),
    'min': (_min, False), 'max': (_max, False), 'avg': (_avg, False),
    'mean': (_avg, False), 'sum': (_sum, False), 'hypot': (_hypot, False),
    'clamp': (_clamp, False),
    'fact': (_fact, False), 'factorial': (_fact, False),
    'perm': (_perm, False), 'comb': (_comb, False),
    'deg': (_deg, False), 'rad': (_rad, False),
    'heaviside': (_heaviside, False), 'sinc': (_sinc, False),
    'rand': (_rand, False), 'random': (_rand, False),
    'randint': (_randint, False),
    # 常量函数（无参）
    'pi': (lambda: PI, False), 'π': (lambda: PI, False),
    'tau': (lambda: 2 * PI, False),
    'phi': (lambda: PHI, False), 'inf': (lambda: INF, False),
    'nan': (lambda: NAN, False),
}


def _trig(name, x, mode):
    x = float(x)
    if mode == DEG:
        x = math.radians(x)
    elif mode == GRAD:
        x = math.radians(x * 0.9)
    if name == 'sin': return math.sin(x)
    if name == 'cos': return math.cos(x)
    if name == 'tan':
        if abs(math.cos(x)) < 1e-15:
            raise CalcError("tan 在该点无定义")
        return math.tan(x)
    if name == 'ctg':
        if abs(math.sin(x)) < 1e-15:
            raise CalcError("ctg 在该点无定义")
        return 1 / math.tan(x)
    if name == 'sec':
        if abs(math.cos(x)) < 1e-15:
            raise CalcError("sec 在该点无定义")
        return 1 / math.cos(x)
    if name == 'csc':
        if abs(math.sin(x)) < 1e-15:
            raise CalcError("csc 在该点无定义")
        return 1 / math.sin(x)


def _atrig(name, x, mode):
    x = float(x)
    if name == 'asin':
        if not -1 <= x <= 1:
            raise CalcError("asin 参数须在[-1,1]内")
        r = math.asin(x)
    elif name == 'acos':
        if not -1 <= x <= 1:
            raise CalcError("acos 参数须在[-1,1]内")
        r = math.acos(x)
    else:  # atan
        r = math.atan(x)
    if name == 'actg':
        r = math.pi / 2 - math.atan(x)
    if mode == DEG:
        return math.degrees(r)
    if mode == GRAD:
        return math.degrees(r) / 0.9
    return r


def _atrig2(y, x, mode):
    r = math.atan2(float(y), float(x))
    if mode == DEG:
        return math.degrees(r)
    if mode == GRAD:
        return math.degrees(r) / 0.9
    return r


# ---------------- 表达式预处理 ----------------
# 单位换算表： 前缀 (m 毫=1e-3, k 千=1e3, M 兆=1e6, G=1e9)
UNIT_MAP = {
    # 长度
    'km': 1e3, 'm': 1.0, 'dm': 0.1, 'cm': 0.01, 'mm': 1e-3, 'um': 1e-6, 'μm': 1e-6,
    'nm': 1e-9, 'in': 0.0254, 'inch': 0.0254, 'ft': 0.3048, 'feet': 0.3048,
    'yd': 0.9144, 'mi': 1609.344, 'li': 500.0, 'chi': 1 / 3, 'cun': 1 / 30,
    # 面积
    'm2': 1.0, 'cm2': 1e-4, 'km2': 1e6, 'mu': 666.6667, 'mu2': 666.6667,
    # 质量
    'kg': 1.0, 'g': 1e-3, 'mg': 1e-6, 't': 1e3, 'ton': 1e3,
    'jin': 0.5, 'liang': 0.05, 'lb': 0.45359237, 'oz': 0.0283495231,
    # 时间
    's': 1.0, 'sec': 1.0, 'min': 60.0, 'h': 3600.0, 'hr': 3600.0, 'day': 86400.0,
    'week': 604800.0, 'ms': 1e-3, 'us': 1e-6,
    # 温度
    'degC': 1.0, 'degF': 1.0,
    # 速度
    'mps': 1.0, 'kmh': 1 / 3.6, 'mph': 0.44704,
    # 功率
    'w': 1.0, 'kw': 1e3, 'hp': 745.699872,
    # 能量
    'j': 1.0, 'kj': 1e3, 'cal': 4.1868, 'kcal': 4186.8, 'wh': 3600.0, 'kwh': 3.6e6,
    # 数据
    'b': 1.0, 'kb': 1e3, 'mb': 1e6, 'gb': 1e9, 'tb': 1e12,
    'kib': 1024, 'mib': 1024 ** 2, 'gib': 1024 ** 3, 'tib': 1024 ** 4,
    # 角度
    'deg2': 1.0, 'rad2': 57.2957795, 'grad2': 0.9,
    # 汇率示例（简单）
    'usd': 7.2, 'cny': 1.0, 'eur': 7.8, 'jpy': 0.048,
    # 其它
    'mol': 6.02214076e23, 'pa': 1.0, 'kpa': 1e3, 'atm': 101325.0,
}

# 前缀
UNIT_PREFIX = {
    'k': 1e3, 'm': 1e-3, 'u': 1e-6, 'n': 1e-9, 'M': 1e6, 'G': 1e9,
}

# 运算符
# 支持: + - * / ^ ** % // ( ) , 
# 隐式乘法: 2x, 2(3+4), (1+2)(3+4), 3π, 2sin(30), (2)(3)

# 替换中文/全角符号（注意：不要把 x/X 直接替换成 *，否则会破坏函数名如 max）
SYMBOL_TRANSLATE = {
    '×': '*', '÷': '/', '＋': '+', '－': '-',
    '＊': '*', '／': '/', '（': '(', '）': ')', '，': ',', '。': '.',
    '＝': '=', '％': '%',
    '＾': '**', '｛': '{', '｝': '}', '【': '[', '】': ']',
    '·': '*', '∙': '*', '．': '.',
}

# 函数名/常量名 中英文映射（帮助里提到 cos, sin, tg, ctg ...）
ALIAS_MAP = {
    'tg': 'tan', 'arctg': 'atan', 'arcctg': 'actg', 'arcsin': 'asin',
    'arccos': 'acos', 'arctan': 'atan', 'ctg': 'ctg', 'cot': 'ctg',
    'log10': 'lg', 'log2': 'lb', '√': 'sqrt', '∛': 'cbrt',
    'Γ': 'fact', 'gamma': 'fact',
    'floor': 'floor', 'ceil': 'ceil',
    'sh': 'sinh', 'ch': 'cosh', 'th': 'tanh', 'cth': 'coth',
    'arsinh': 'asinh', 'arcosh': 'acosh', 'arth': 'atanh',
    '∞': 'inf',
}


def normalize_text(text):
    """统一符号、空格、转小写（变量除外）"""
    t = text
    # 去除首尾空白
    t = t.strip()
    # 全角转半角
    for k, v in SYMBOL_TRANSLATE.items():
        t = t.replace(k, v)
    # ^ 作为幂（全角＾已在上表转成**；半角 ^ 也转成 **）
    t = t.replace('^', '**')
    return t


def _insert_implicit_mul(expr):
    """在数字与字母、( 之间插入隐式乘号。
    支持: 2x -> 2*x, 2(3) -> 2*(3), (1+2)(3+4) -> (1+2)*(3+4), 3π, 2sin(30), 3!
    注意: 函数名如 max, sin 内部的字母不被拆开；x/X 作为乘号时需前后为数字/括号。
    科学计数法如 2e3、1.5E-5 不插入乘号（e/E 后跟数字/符号）。
    """
    out = []
    n = len(expr)
    i = 0
    while i < n:
        ch = expr[i]
        out.append(ch)
        if i + 1 < n:
            nxt = expr[i + 1]
            prev = expr[i - 1] if i > 0 else ''
            # 科学计数法: 数字 后跟 e/E 且 e 后是数字或 +/- 数字
            if (ch.isdigit() or ch == '.') and nxt in 'eE' and i + 2 < n:
                after = expr[i + 2]
                if after.isdigit() or (after in '+-' and i + 3 < n and expr[i + 3].isdigit()):
                    i += 1
                    continue
            # 数字 / . / ) / % / π 后跟 ( 或 字母 或 π -> 隐式乘
            if ch.isdigit() or ch == '.' or ch == ')' or ch == '%' or ch == 'π':
                if nxt == '(' or nxt.isalpha() or nxt == 'π':
                    out.append('*')
            # ) 后跟 数字 -> 隐式乘
            if ch == ')' and (nxt.isdigit() or nxt == '.'):
                out.append('*')
            # 单字母 x/X 作为乘号: 数字x(、)x(、πx(  且前面不是字母（避免破坏函数名）
            if ch in 'xX' and nxt == '(' and not prev.isalpha() and not prev.isdigit():
                out.append('*')
            # 数字 后跟 x 作为乘号: 2x -> 2*x （x 后不能是字母数字，否则是变量如 x2）
            if (ch.isdigit() or ch == ')' or ch == '%' or ch == 'π') and nxt in 'xX' and \
               (i + 2 >= n or not (expr[i + 2].isalpha() or expr[i + 2].isdigit())):
                out.append('*')
        i += 1
    return ''.join(out)


def _handle_units(expr):
    """把「数字+单位名」转换为「数字*系数」，例如 1km -> 1*1000, 500m -> 500*1, 2kg*3 -> 2*1*3。
    要求单位名后不是字母/数字/左括号(避免误伤函数如 min(、sin()、5min 中的函数调用)。
    """
    # 单位名按长度降序，保证 km 优先于 k，m2 优先于 m
    unit_names = sorted(UNIT_MAP.keys(), key=len, reverse=True)
    # 构造正则: (数字)(单位名)(?![A-Za-z0-9_(])
    # 但注意: 单位名后紧跟左括号的情况需排除, 如 5min( 不应匹配（min 是函数）
    pattern = r'(\d+(?:\.\d+)?)(' + '|'.join(re.escape(u) for u in unit_names) + r')(?![A-Za-z0-9_])'
    # 排除 单位后紧跟 ( 的情况（函数调用）
    def repl(m):
        num = m.group(1)
        unit = m.group(2)
        # 检查 unit 后是否是左括号（函数调用），例如 5min(1,2) 中的 min(
        end = m.end()
        if end < len(expr) and expr[end] == '(':
            return m.group(0)  # 不替换，视为函数
        factor = UNIT_MAP[unit]
        return f"({num})*({factor})"
    return re.sub(pattern, repl, expr)


def _handle_factorial(expr):
    """处理后缀阶乘: N! -> fact(N), (expr)! -> fact(expr), n! -> fact(n)
    注意排除 != 运算符。
    """
    # 先处理括号表达式! : (1+2)! -> fact((1+2))
    def repl_paren(m):
        return f"fact({m.group(1)})"
    # 匹配最内层括号后跟!
    prev = None
    while prev != expr:
        prev = expr
        expr = re.sub(r'\(([^()]*)\)!', repl_paren, expr)
    # 处理 数字/标识符/π/e! (排除 != )
    expr = re.sub(r'(\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|[πe])!(?!=)', repl_paren, expr)
    return expr


# ---------------- 安全 AST 求值 ----------------
class SafeEvaluator:
    """基于 ast 的安全求值器"""

    # 允许的二元操作
    BIN_OPS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
    }
    UNARY_OPS = {
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
        ast.Not: lambda a: not a,
    }

    def __init__(self, variables=None, angle_mode=DEG, precision=10):
        self.variables = variables if variables is not None else {}
        self.angle_mode = angle_mode
        self.precision = precision

    def eval(self, expression):
        """求值表达式字符串，返回结果数值"""
        expr = expression.strip()
        if not expr:
            raise CalcError("表达式为空")

        # 先统一符号
        expr = normalize_text(expr)

        # 百分号处理：a% -> a/100  (仅当 % 后不是数字时，避免与取模冲突)
        expr = self._handle_percent(expr)

        # 单位换算：1km -> 1*1000
        expr = _handle_units(expr)

        # 阶乘处理：N! -> fact(N)
        expr = _handle_factorial(expr)

        # 隐式乘法
        expr = _insert_implicit_mul(expr)

        # 变量替换
        expr = self._substitute_vars(expr)

        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError as e:
            raise CalcError(f"语法错误: {e.msg}")

        try:
            result = self._eval_node(tree.body)
        except CalcError:
            raise
        except ZeroDivisionError:
            raise CalcError("除数不能为0")
        except OverflowError:
            raise CalcError("数值溢出")
        except Exception as e:
            raise CalcError(f"计算错误: {e}")

        # 处理复数结果
        if isinstance(result, complex):
            if abs(result.imag) < 1e-12:
                result = result.real
            else:
                return result
        return result

    def _handle_percent(self, expr):
        """百分号: 数字% -> (数字)/100，仅当 % 后不是数字/字母(否则视为取模)。
        例如 50% -> 50/100, (1+2)% -> (1+2)/100, 10%3 保留为取模。
        """
        # 匹配 数字(含小数) 后跟 % 且 % 后不是数字（避免 10%3 被拆）
        def repl(m):
            num = m.group(1)
            return f"({num})/100"
        expr = re.sub(r'(\d+(?:\.\d+)?)%(?![0-9A-Za-z_])', repl, expr)
        return expr

    def _substitute_vars(self, expr):
        """替换已知变量名为其值。同时处理函数别名。"""
        # 先把已知变量名替换
        for name in sorted(self.variables.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(name) + r'\b', expr):
                val = self.variables[name]
                # 避免替换函数名
                expr = re.sub(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])',
                              f"({val})", expr)
        return expr

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            op = self.BIN_OPS.get(type(node.op))
            if op is None:
                raise CalcError(f"不支持的运算符: {type(node.op).__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            # 幂的特殊处理
            if isinstance(node.op, ast.Pow):
                # 复数与负数处理
                try:
                    return left ** right
                except (ValueError, OverflowError):
                    return cmath.exp(right * cmath.log(left))
            return op(left, right)
        if isinstance(node, ast.UnaryOp):
            op = self.UNARY_OPS.get(type(node.op))
            if op is None:
                raise CalcError(f"不支持的运算符: {type(node.op).__name__}")
            return op(self._eval_node(node.operand))
        if isinstance(node, ast.Call):
            return self._eval_call(node)
        if isinstance(node, ast.Name):
            return self._eval_name(node)
        if isinstance(node, ast.List):
            return [self._eval_node(x) for x in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(x) for x in node.elts)
        if isinstance(node, ast.Subscript):
            val = self._eval_node(node.value)
            idx = self._eval_node(node.slice)
            return val[idx]
        if isinstance(node, ast.Compare):
            return self._eval_compare(node)
        if isinstance(node, ast.IfExp):
            cond = self._eval_node(node.test)
            return self._eval_node(node.body if cond else node.orelse)
        raise CalcError(f"不支持的表达式元素: {type(node).__name__}")

    def _eval_compare(self, node):
        left = self._eval_node(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = self._eval_node(comp)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            else:
                raise CalcError("不支持的比较运算符")
            if not ok:
                return False
            left = right
        return True

    def _eval_name(self, node):
        name = node.id
        # 常量
        lower = name.lower()
        if lower == 'pi' or name == 'π':
            return PI
        if lower == 'e' and len(name) == 1:
            return E
        if lower == 'tau':
            return 2 * PI
        if lower == 'phi':
            return PHI
        if lower == 'inf':
            return INF
        if lower == 'nan':
            return NAN
        # 变量
        if name in self.variables:
            return self.variables[name]
        raise CalcError(f"未知变量或函数: {name}")

    def _eval_call(self, node):
        if not isinstance(node.func, ast.Name):
            raise CalcError("仅支持直接函数调用")
        fname = node.func.id
        fname = ALIAS_MAP.get(fname, fname)
        # 无参数处理
        args = []
        for a in node.args:
            args.append(self._eval_node(a))
        kw = {}
        for k in node.keywords:
            if k.arg:
                kw[k.arg] = self._eval_node(k.value)

        # 查找函数
        if fname in FUNCTIONS:
            finfo = FUNCTIONS[fname]
            func = finfo[0] if callable(finfo) else finfo[0]
            is_angle = finfo[1] if not callable(finfo) else False
            try:
                if is_angle:
                    return func(*args, self.angle_mode)
                # 常量函数无参
                return func(*args, **kw)
            except CalcError:
                raise
            except TypeError as e:
                raise CalcError(f"函数 {fname} 参数错误: {e}")
            except ValueError as e:
                raise CalcError(f"函数 {fname} 计算错误: {e}")
        else:
            # 尝试作为变量？不，报错
            raise CalcError(f"未知函数: {fname}")


# ---------------- 便捷求值接口 ----------------
def evaluate(expression, variables=None, angle_mode=DEG, precision=10):
    """便捷求值。返回 (value, error_str)。error_str 为空表示成功。"""
    evaluator = SafeEvaluator(variables=variables, angle_mode=angle_mode, precision=precision)
    try:
        result = evaluator.eval(expression)
        return result, ""
    except CalcError as e:
        return None, str(e)
    except Exception as e:
        return None, f"计算错误: {e}"


def format_result(value, precision=10):
    """格式化结果字符串"""
    if isinstance(value, complex):
        r = round(value.real, precision)
        i = round(value.imag, precision)
        if abs(value.imag) < 1e-10:
            return f"{r:g}"
        return f"{r:g}{'+' if i >= 0 else ''}{i:g}i"
    if isinstance(value, bool):
        return "真" if value else "假"
    if isinstance(value, float):
        # 避免 -0
        if abs(value) < 1e-15:
            value = 0.0
        # 大数/小数用科学计数
        if abs(value) >= 1e15 or (abs(value) < 1e-9 and value != 0):
            return f"{value:.{max(4, precision)}e}"
        # 整数显示
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.{precision}g}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Fraction):
        return str(value)
    return str(value)


if __name__ == '__main__':
    # 简单自测
    tests = [
        ("2+3*4", 14),
        ("(1+2)*3", 9),
        ("10/4", 2.5),
        ("2^10", 1024),
        ("2**3", 8),
        ("sin(30)", 0.5),  # DEG 模式
        ("cos(60)", 0.5),
        ("tan(45)", 1),
        ("asin(0.5)", 30),
        ("sqrt(16)", 4),
        ("cbrt(27)", 3),
        ("root(32,5)", 2),
        ("3!+2", 8),
        ("fact(5)", 120),
        ("log(100)", 2),
        ("ln(e)", 1),
        ("lg(1000)", 3),
        ("100*0.1", 10),
        ("50%", 0.5),
        ("10%3", 1),
        ("10//3", 3),
        ("2π", 2 * math.pi),
        ("3pi", 3 * math.pi),
        ("abs(-5)", 5),
        ("sign(-3)", -1),
        ("round(3.14159, 2)", 3.14),
        ("floor(3.7)", 3),
        ("ceil(3.2)", 4),
        ("max(1,5,3)", 5),
        ("min(1,5,3)", 1),
        ("avg(1,2,3,4)", 2.5),
        ("hypot(3,4)", 5),
        ("gcd(12,18)", 6),
        ("lcm(4,6)", 12),
        ("comb(5,2)", 10),
        ("perm(5,2)", 20),
        ("sqrt(-4)", complex(0, 2)),
        # 隐式乘法
        ("2(3+4)", 14),
        ("(1+2)(3+4)", 21),
        ("3(2+1)", 9),
        ("2sin(30)", 1),
        ("2x", None),  # x 作为变量时应报错（未定义变量），不崩溃
        # 单位
        ("1km+500m", 1500),
        ("2kg*3", 6),
        # 双曲
        ("sinh(0)", 0),
        ("cosh(0)", 1),
        ("tanh(0)", 0),
        ("sh(0)", 0),
        ("ch(0)", 1),
        ("th(0)", 0),
        ("heaviside(1)", 1),
        ("sinc(0)", 1),
    ]
    for expr, expected in tests:
        val, err = evaluate(expr)
        ok = False
        if expected is None:
            ok = (err != "")  # 应报错
        else:
            try:
                if isinstance(expected, complex):
                    ok = abs(complex(val) - expected) < 1e-6
                else:
                    ok = abs(float(val) - float(expected)) < 1e-6
            except Exception:
                ok = False
        status = "OK " if ok else "FAIL"
        print(f"[{status}] {expr} = {format_result(val) if val is not None else err} (期望 {expected}) {err if err else ''}")

    # 变量测试
    print("\n变量测试:")
    val, err = evaluate("x+y", variables={"x": 3, "y": 4})
    print(f"  x+y (x=3,y=4) = {val} {err}")

    # 角度模式测试
    print("\n角度模式测试:")
    val, err = evaluate("sin(30)", angle_mode=DEG)
    print(f"  DEG sin(30) = {val} {err}")
    val, err = evaluate("sin(pi/6)", angle_mode=RAD)
    print(f"  RAD sin(pi/6) = {val} {err}")
