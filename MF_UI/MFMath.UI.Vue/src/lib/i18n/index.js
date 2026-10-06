import { ref } from "vue";
import { EN } from "./en-US.js";
import { EN_MODES } from "./en-modes.js";
import { EN_VARS } from "./en-vars.js";
import { EN_RESULTS } from "./en-results.js";

/** 合并译文表：模式名/字段标签/结果标签打底，外壳文案（en-US）优先 */
const DICT = { ...EN_MODES, ...EN_VARS, ...EN_RESULTS, ...EN };

/**
 * 国际化（D4）—— 以**中文原文为键**的最小实现。
 *
 * 为什么用"中文当键"而不是给每条文案编 id：
 *   本项目的文案散布在数据层（`NAV_GROUPS` 的 title/name、`VIEW_CONFIGS` 的标题…）
 *   与近百个组件模板里。要给每条编 id，等于先把**整个代码库的字符串抽出来改名** ——
 *   一次做不完、做一半就是两套体系并存，比不做更乱。
 *   以中文原文为键则：数据层一行都不用改；想翻译哪一条，把那个位置包一层 `t()`；
 *   没包的地方照旧显示中文，**界面永远不会出现空白或 key**。
 *
 * 代价（明知并接受）：
 *   · 同一句中文在不同语境需要不同英文时无法区分（本项目的界面文案基本没有这种情况）；
 *   · 改了中文原文等于改了 key，译文会失效并回退成中文 —— 由下面 check-ui 的
 *     "t() 用到的键必须在 en-US 里存在"这条自检兜住（回退是显式的，不会静默乱码）。
 *
 * 当前覆盖范围：导航（分组与全部条目）、顶栏按钮与外观浮层、设置里的语言项。
 * 页面正文仍是中文 —— 迁移路径就是"哪里要英文，就在那里包一层 t()"，改完跑 `npm run check`。
 */

export const LOCALES = [
  { id: "zh-CN", label: "简体中文" },
  { id: "en-US", label: "English" },
];

const STORE_KEY = "mf.lang";
const FALLBACK = "zh-CN";

function readStored() {
  try {
    const v = localStorage.getItem(STORE_KEY) || "";
    return LOCALES.some((l) => l.id === v) ? v : FALLBACK;
  } catch {
    return FALLBACK;
  }
}

export const locale = ref(readStored());

/** 切换语言：立即生效（与本项目其它设置一致，没有"保存"按钮），并记住选择 */
export function setLocale(id) {
  if (!LOCALES.some((l) => l.id === id)) return;
  locale.value = id;
  try { localStorage.setItem(STORE_KEY, id); } catch { /* 隐私模式下忽略 */ }
  try { document.documentElement.lang = id; } catch { /* 非浏览器环境忽略 */ }
}

/**
 * 取译文。约定：
 *   · 中文环境**原样返回键**（中文就是原文，零维护）；
 *   · 英文环境查 EN，查不到就回退中文原文（而不是显示 key 或空字符串）；
 *   · `{name}` 形式的占位符用第二个参数替换。
 *
 * 在模板里直接调用即可获得响应式：函数内部读了 `locale.value`。
 */
export function t(key, params) {
  /* ⚠ 参数替换必须在**两个分支都做**：原先中文分支直接 `return key` 就跳过了替换，
   * 于是中文界面上出现过字面的 `共 {n} 键` —— 而英文界面正常，所以只跑英文探针
   * 根本发现不了（是靠给键盘截图才看出来的）。 */
  let s = locale.value === "zh-CN"
    ? key
    : (Object.prototype.hasOwnProperty.call(DICT, key) ? DICT[key] : key);
  if (params) {
    for (const [k, v] of Object.entries(params)) s = s.split("{" + k + "}").join(String(v));
  }
  return s;
}

try { document.documentElement.lang = locale.value; } catch { /* 忽略 */ }
