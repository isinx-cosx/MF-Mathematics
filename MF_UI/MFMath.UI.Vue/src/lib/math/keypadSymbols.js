/**
 * keypadSymbols.js — 数学键盘的键位表（移植自 v1 `MF_UI/math_keyboard.py` 的 SYMBOLS）
 *
 * 三个刻意的修正（v1 的做法在 MathLive 输入框里是坏的或半坏的）：
 *
 * 1. **插入值是 LaTeX，不再是 Unicode**。
 *    v1 的 `_on_key_clicked` 是 `text = char.replace("▢",""); focused.insert(text)`，
 *    所以 126 键里只有「常用模板」那 11 键是 LaTeX，其余 115 键插的是 `∫` `α` `x̄`
 *    这类**显示用 Unicode**。MathLive 里它们要么显示成奇怪的变量字母（如 `arcsin`
 *    会被当成 6 个变量相乘），要么根本排不出正确字形。这里每个键都给
 *    「键面 label」+「插入 latex」，label 保留 v1 原字样以维持肌肉记忆。
 *
 * 2. **占位符不再被剥掉**。
 *    v1 把 `▢` 直接 replace 掉，于是 `\frac{▢}{▢}` 变成 `\frac{}{}`、
 *    `\sqrt[▢]{▢}` 变成 `\sqrt[]{}`——插进去后**光标无处可落**，只能手动补。
 *    这里改用 MathLive 的占位符语法：`#0` 是插入后光标停的位置，`#?` 是后续
 *    可 Tab 跳转的位置（与既有 `ExpressionList.vue` 的符号面板同一套约定）。
 *
 * 3. **矩阵模板补全**。
 *    v1 的 `\begin{pmatrix}` 只有开头没有 `\end`，插进去就是一段残缺 LaTeX。
 *    这里给出完整的 2×2 环境。
 *
 * 键面文字与「6 个分类的名称与顺序」都和 v1 完全一致（`SYMBOLS` 是 dict，
 * Python 3.7+ 有序，所以顺序就是这个顺序），不顺手"规范化"——那是用户的肌肉记忆。
 *
 * ⚠ **一处有意的偏离**（2026-10，按用户要求）：模板类键的**键面**不再画 v1 的 `▢` 空位，
 * 改用真字母（`\frac{a}{b}` / `\sqrt[n]{a}` / `e^{x}` / `x^{n}` / `a_{n}` /
 * `∫_{a}^{b}` / `∑_{i}^{n}` / `lim_{x→a}`，矩阵键面给一个真的 2×2）。
 * 理由：`▢` 画出来是个小方块，而 `\frac{a}{b}` 一眼就是分数。
 * **只改了键面**：第 2 个元素（插入值）仍是 `#0`/`#?`，插入行为一个字没变 ——
 * 千万别顺手把插入值也"美化"了，那会退回 v1「`\frac{}{}`、光标无处可落」的老毛病。
 *
 * 条目格式：字符串 = 键面即插入值；数组 = [键面, 插入值, 搜索关键词]
 *
 * ⚠ 键面的**显示**不在这里：模板类键的 label 本身就是 LaTeX（`\frac{▢}{▢}`、`\begin{pmatrix}`），
 * 直接画出来用户看不懂。显示逻辑在 `src/lib/math/keyFace.js` + `components/math/KeyFace.vue`
 * （按数学排版，排不了的换成可读文本）。**不要为了"好看"改这里的 label** ——
 * 那是 v1 用户的肌肉记忆，改了位置/字样都会让人找不到键。
 */

const C = (id, name, rows) => ({ id, name, rows });

export const CATEGORIES = [
  C("basic", "基础运算", [
    ["7", "8", "9", "/", ["√", "\\sqrt{#0}", "根号 平方根 sqrt root"]],
    ["4", "5", "6", "*", ["^", "^", "幂 次方 power"]],
    ["1", "2", "3", "-", ["_", "_", "下标 subscript"]],
    ["0", ".", "=", "+", ["|x|", "\\left|#0\\right|", "绝对值 模 abs"]],
    ["(", ")", "[", "]", ["{", "{", "花括号 brace"], ["}", "}", "花括号 brace"]],
  ]),
  C("calculus", "微积分", [
    [["∫", "\\int", "积分 不定积分 integral"],
     ["∬", "\\iint", "二重积分 double integral"],
     ["∂", "\\partial", "偏导 partial"],
     ["∇", "\\nabla", "梯度 散度 旋度 nabla"],
     ["lim", "\\lim_{#0\\to#1}", "极限 limit"]],
    [["d/dx", "d/dx", "导数 微分 derivative"],
     ["∞", "\\infty", "无穷 infinity"],
     ["Δ", "\\Delta", "增量 delta"],
     ["∑", "\\sum_{#0}^{#1}", "求和 级数 sum"],
     ["∏", "\\prod_{#0}^{#1}", "连乘 积 product"]],
    [["sin", "\\sin", "正弦"], ["cos", "\\cos", "余弦"], ["tan", "\\tan", "正切"],
     ["log", "\\log", "对数"], ["ln", "\\ln", "自然对数"]],
    [["arcsin", "\\arcsin", "反正弦"], ["arccos", "\\arccos", "反余弦"], ["arctan", "\\arctan", "反正切"],
     ["exp", "\\exp", "指数函数"], ["abs", "\\left|#0\\right|", "绝对值"]],
  ]),
  C("linalg", "线性代数", [
    [["det", "\\det", "行列式 determinant"], ["tr", "\\operatorname{tr}", "迹 trace"],
     ["rank", "\\operatorname{rank}", "秩"], ["·", "\\cdot", "点乘 dot"],
     ["×", "\\times", "叉乘 乘号 times"]],
    [["∥v∥", "\\left\\lVert#0\\right\\rVert", "范数 模长 norm"],
     ["⟨u,v⟩", "\\left\\langle#0,#1\\right\\rangle", "内积 inner product"],
     ["⊥", "\\perp", "垂直 正交 perpendicular"],
     ["A⁻¹", "A^{-1}", "逆矩阵 inverse"],
     ["Aᵀ", "A^{T}", "转置 transpose"]],
    [["I_n", "I_{#0}", "单位矩阵 identity"],
     ["0_{m×n}", "0_{#0\\times#1}", "零矩阵 zero matrix"],
     ["⊕", "\\oplus", "直和 异或 oplus"],
     ["⊗", "\\otimes", "张量积 tensor"],
     ["⊤", "\\top", "转置符号 top"]],
  ]),
  C("greek", "希腊字母", [
    [["α", "\\alpha", "阿尔法 alpha"], ["β", "\\beta", "贝塔 beta"], ["γ", "\\gamma", "伽马 gamma"],
     ["δ", "\\delta", "德尔塔 delta"], ["ε", "\\varepsilon", "伊普西龙 epsilon"], ["ζ", "\\zeta", "泽塔 zeta"]],
    [["η", "\\eta", "伊塔 eta"], ["θ", "\\theta", "西塔 theta"], ["ι", "\\iota", "约塔 iota"],
     ["κ", "\\kappa", "卡帕 kappa"], ["λ", "\\lambda", "兰姆达 lambda"], ["μ", "\\mu", "缪 mu"]],
    [["ν", "\\nu", "纽 nu"], ["ξ", "\\xi", "克西 xi"], ["ο", "o", "奥密克戎 omicron"],
     ["π", "\\pi", "派 pi 圆周率"], ["ρ", "\\rho", "柔 rho"], ["σ", "\\sigma", "西格玛 sigma"]],
    [["τ", "\\tau", "套 tau"], ["υ", "\\upsilon", "宇普西龙 upsilon"], ["φ", "\\varphi", "斐 phi"],
     ["χ", "\\chi", "卡伊 chi"], ["ψ", "\\psi", "普西 psi"], ["ω", "\\omega", "欧米伽 omega"]],
    [["Γ", "\\Gamma", "大写伽马"], ["Δ", "\\Delta", "大写德尔塔"], ["Θ", "\\Theta", "大写西塔"],
     ["Λ", "\\Lambda", "大写兰姆达"], ["Ξ", "\\Xi", "大写克西"], ["Π", "\\Pi", "大写派"]],
    [["Σ", "\\Sigma", "大写西格玛"], ["Φ", "\\Phi", "大写斐"], ["Ψ", "\\Psi", "大写普西"], ["Ω", "\\Omega", "大写欧米伽"]],
  ]),
  C("stats", "概率统计", [
    [["P(A)", "P(A)", "概率 probability"], ["E(X)", "E(X)", "期望 expectation"],
     ["Var(X)", "\\operatorname{Var}(X)", "方差 variance"], ["σ(X)", "\\sigma(X)", "标准差"],
     ["Cov", "\\operatorname{Cov}", "协方差 covariance"]],
    [["N(μ,σ²)", "N(\\mu,\\sigma^{2})", "正态分布 normal"],
     ["Bin(n,p)", "\\operatorname{Bin}(n,p)", "二项分布 binomial"],
     ["Pois(λ)", "\\operatorname{Pois}(\\lambda)", "泊松分布 poisson"],
     ["Exp(λ)", "\\operatorname{Exp}(\\lambda)", "指数分布 exponential"],
     ["U(a,b)", "U(a,b)", "均匀分布 uniform"]],
    [["≤", "\\le", "小于等于 le"], ["≥", "\\ge", "大于等于 ge"], ["≠", "\\ne", "不等于 ne"],
     ["≈", "\\approx", "约等于 approx"], ["±", "\\pm", "正负 plusminus"]],
    [["x̄", "\\bar{x}", "样本均值 xbar"], ["ŷ", "\\bar{y}", "预测值 ybar"],
     ["p̂", "\\hat{p}", "样本比例 phat"], ["μ̂", "\\hat{\\mu}", "均值估计 muhat"],
     ["σ̂", "\\hat{\\sigma}", "标准差估计"]],
  ]),
  C("templates", "常用模板", [
    // 键面用**真字母**（a/b、n/a、x/n…）而不是 v1 的 ▢ 空位 —— 按用户要求改的：
    // 空位画出来是一个小方块，而 \frac{a}{b} 一眼就是分数。**只改键面**，
    // 第 2 个元素（插入值）仍是 #0/#? 占位符，一个字都没动。
    [["\\frac{a}{b}", "\\frac{#0}{#?}", "分数 分式 fraction"],
     ["\\sqrt[n]{a}", "\\sqrt[#0]{#?}", "n 次根 root"],
     ["e^{x}", "e^{#0}", "指数 exp"],
     ["x^{n}", "#0^{#?}", "幂 power"],
     ["a_{n}", "#0_{#?}", "下标"]],
    [["∫_{a}^{b}", "\\int_{#0}^{#1}", "定积分 definite"],
     ["∑_{i}^{n}", "\\sum_{#0}^{#1}", "求和"],
     ["lim_{x→a}", "\\lim_{#0\\to#1}", "极限"]],
    [["\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}", "\\begin{pmatrix}#0 & #? \\\\ #? & #? \\end{pmatrix}", "矩阵 圆括号 pmatrix"],
     ["\\begin{bmatrix}a&b\\\\c&d\\end{bmatrix}", "\\begin{bmatrix}#0 & #? \\\\ #? & #? \\end{bmatrix}", "矩阵 方括号 bmatrix"],
     ["\\begin{vmatrix}a&b\\\\c&d\\end{vmatrix}", "\\begin{vmatrix}#0 & #? \\\\ #? & #? \\end{vmatrix}", "行列式 竖线 vmatrix"]],
  ]),
];

/** 统一成 {label, latex, tip, cat, catName} 的扁平结构 */
function flatten() {
  const out = [];
  for (const c of CATEGORIES) {
    for (const row of c.rows) {
      for (const k of row) {
        if (typeof k === "string") out.push({ label: k, latex: k, tip: "", cat: c.id, catName: c.name });
        else out.push({ label: k[0], latex: k[1], tip: k[2] || "", cat: c.id, catName: c.name });
      }
    }
  }
  return out;
}

export const ALL_KEYS = flatten();
export const KEY_COUNT = ALL_KEYS.length;

/** v1 的键数（用于校验：多一个少一个都要能发现） */
export const V1_KEY_COUNT = 126;

export function searchKeys(query, limit = 24) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return [];
  return ALL_KEYS.filter((k) =>
    k.label.toLowerCase().includes(q) || k.latex.toLowerCase().includes(q) || k.tip.includes(q)
  ).slice(0, limit);
}

/** 常用键（放"最近"为空时的兜底，避免面板一开就是空的） */
export const DEFAULT_RECENT = ["\\frac{#0}{#?}", "\\sqrt{#0}", "\\int_{#0}^{#1}", "^", "\\pi", "\\le"];
