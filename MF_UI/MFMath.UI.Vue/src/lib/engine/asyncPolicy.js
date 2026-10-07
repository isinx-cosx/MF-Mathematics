/**
 * asyncPolicy.js —— 哪些引擎调用该走**异步通道**（`engineCallAsync`）
 *
 * 分界线是一条实测出来的线，不是拍脑袋：
 *   · 同步 `engineCall` 会占住渲染进程主线程 ⇒ 只适合"毫秒级"的活；
 *   · 超过几百毫秒的活必须走异步，否则界面白屏 + 系统判定"未响应"。
 *
 * 实测（本机，Rust 宿主，C++ 引擎）：
 *   mandelbrot 600×600×256 = 9.2e7 次迭代 → 248 ms
 *   ⇒ 约 3.7e8 次迭代/秒，所以 1.5e8 ≈ 400 ms 是"还能忍"的上限。
 *
 * ⚠ 用途限定：**只给"用户明确发起的一次重活"用** ——
 *   分形页重绘、复平面页求网格、工具箱跑一条 action。
 *   绘图页里"每条曲线一次"的采样/极值标记**保持同步**：那些是毫秒级，
 *   而且一条曲线一个 await 会把采样时序拆碎，得不偿失。
 */

/** 规模可判的一族：按参数算出"工作量"，超过阈值才异步 */
const BY_SIZE = {
  mandelbrot: (a) => num(a.width) * num(a.height) * num(a.max_iter, 256),
  complex_grid: (a) => num(a.nx) * num(a.ny),
  expr_eval_grid: (a) => (Array.isArray(a.xs) ? a.xs.length : num(a.nx)) * (Array.isArray(a.ys) ? a.ys.length : num(a.ny)),
  matrix_multiply: (a) => num(a.n) * num(a.n) * num(a.n),
};

/** 阈值：超过就走异步（单位 = 上面那个"工作量"） */
const LIMIT = {
  mandelbrot: 1.5e8,      // ≈400 ms
  complex_grid: 2.5e5,    // 500×500
  expr_eval_grid: 2.5e5,
  matrix_multiply: 2e6,
};

/**
 * **没有上界**的动作：只要用户点了就跑异步。
 * 这些是符号/数值重活，规模没法从参数估（表达式有多难只有引擎知道）：
 * 一个 factor_integer 可能 1 ms，也可能几十秒。
 */
const ALWAYS_ASYNC = new Set([
  // 积分 / 求和 / 级数
  "integrate", "integrate_numeric", "integrate_double", "integrate_triple", "integrate_complex",
  "darboux_sum", "series_sum", "taylor_series", "taylor_remainder", "infinite_product",
  "arithmetic_sum", "geometric_sum", "divisor_sum", "euler_product", "poisson_summation",
  // 符号求解 / 化简
  "solve_sym", "extrema_sym", "simplify", "factor", "expand", "limit",
  "limit_comparison_test", "limit_epsilon_delta", "sequence_limit",
  // 数论 / 矩阵
  "factor_integer", "is_prime", "matrix_inverse", "matrix_determinant",
]);

function num(v, d = 0) {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : d;
}

/** 估算这次调用的工作量；`null` 表示"估不了"（AI 无关，仅诊断用） */
export function estimateWork(name, args = {}) {
  const f = BY_SIZE[name];
  if (!f) return null;
  try { return f(args || {}); } catch { return null; }
}

/**
 * 该不该走异步？
 * @param {string} name 引擎 action
 * @param {object} args 参数
 * @param {{force?:boolean}} [opt] force=true 时无条件异步（工具箱的"后台运行"勾选）
 */
export function shouldRunAsync(name, args = {}, opt = {}) {
  if (opt.force) return true;
  if (ALWAYS_ASYNC.has(name)) return true;
  const f = BY_SIZE[name];
  if (!f) return false;
  const work = estimateWork(name, args);
  if (work == null) return false;
  return work > (LIMIT[name] ?? Infinity);
}

/** 给界面用的一句话说明（"计算中 · 引擎 1200×1200×1024"） */
export function describeWork(name, args = {}) {
  if (name === "mandelbrot") {
    return `引擎 mandelbrot ${num(args.width)}×${num(args.height)}×${num(args.max_iter, 256)}`;
  }
  const w = estimateWork(name, args);
  return w ? `引擎 ${name} · 规模 ${Math.round(w)}` : `引擎 ${name}`;
}
