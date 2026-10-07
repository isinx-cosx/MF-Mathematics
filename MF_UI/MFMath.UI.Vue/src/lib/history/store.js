/**
 * history/store.js — 计算历史（跨会话持久化）
 *
 * 为什么单独一个 store：v1 有独立的历史对话框 + 编辑菜单"清空历史"，而 v2.0 之前
 * 只有基础运算页里 8 条内存记录（刷新即失、不跨页）——顶栏那个「历史」按钮点了没反应。
 *
 * 存放位置：宿主 `sys` 桥的键值存储 → `%LOCALAPPDATA%\MFMath\settings\history.json`。
 * 无宿主（浏览器预览）时由 lib/settings/bridge.js 自动降级到 localStorage，
 * 功能照样点得通，只是不落文件。
 *
 * 宿主那侧已经具备写入保障（SettingsBridge.StoreWrite）：先校验 JSON、再备份旧文件、
 * 最后原子替换。v1 的 `workspace_save.json` 是直接 `open(path,"w")`，写一半崩溃后
 * 下次读必定 JSONDecodeError —— 这里不重犯。
 */
import { computed, ref } from "vue";
import { storeRead, storeWrite } from "../settings/bridge.js";

const NAME = "history";

/** 保留条数上限。超出的从尾部丢（历史越久越没用），200 条约几十 KB。 */
export const MAX = 200;

/** 新 → 旧。整个应用共享这一份，历史面板与页面里的"最近"都读它。 */
export const entries = ref([]);

let loaded = false;
let saveTimer = null;
const errorText = ref("");

function mkId() {
  return "h" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

/** 只接受结构完整的条目：坏数据不该把面板搞崩 */
function usable(x) {
  return x && typeof x === "object" && typeof x.expr === "string" && typeof x.ts === "number";
}

/** 首次调用时从存储读入；force=true 强制重读（设置页"重新加载"用） */
export function loadHistory(force = false) {
  if (loaded && !force) return entries.value;
  /* ⚠ 强制重读之前**必须**先把待写内容落盘：否则 reload 会用旧文件覆盖内存、
   * 随后那个待触发的定时器再把旧内容写回，刚记的条目就永久没了（详见 flush 的说明）。
   * 顺序不能反 —— 先读后写等于把内存里的新状态直接丢掉。 */
  if (force) flush();
  loaded = true;
  errorText.value = "";
  const r = storeRead(NAME);
  if (r && r.ok === false) {
    errorText.value = r.corrupt
      ? "历史文件已损坏，已保留原文件并从未开始：" + (r.error || "")
      : (r.error || "读取历史失败");
    return entries.value;
  }
  if (r?.exists && r.json) {
    try {
      const d = JSON.parse(r.json);
      const list = Array.isArray(d) ? d : d?.entries;
      if (Array.isArray(list)) entries.value = list.filter(usable).slice(0, MAX);
    } catch (e) {
      errorText.value = "历史文件内容无法解析：" + (e?.message || e);
    }
  }
  return entries.value;
}

/**
 * 立刻把待写内容落盘（并取消定时器）；没有待写内容时是空操作。
 *
 * 为什么必须有它（这原先是**静默丢数据**的竞态，`docs/FRONTEND-FIXES.md` §5 只标了"未验证"）：
 * 写盘是**延后 250ms** 的，而 `loadHistory(true)`（设置页"重新加载"）会**从磁盘读入并覆盖内存**。
 * 两者撞在一起时：
 *   · `record()` 之后 250ms 内 reload：reload 先用**旧文件**覆盖内存，随后待触发的定时器
 *     又把这份旧内容写回盘 ⇒ 刚记的那条**永久消失**（内存与磁盘都没有了）；
 *   · `clearAll()` 之后 250ms 内 reload：被清掉的条目**复活**并被写回盘 ⇒"清空历史"失效。
 * 所以规矩是：**重新读之前先把待写内容落盘**，让"盘上"与"内存"先一致。
 *
 * 顺带解决另一处：关窗时那 250ms 内的改动会丢。桥是**同步**宿主调用
 * （`hostObjects.sync.sys`），所以 `pagehide` 里写是来得及的（无宿主时走 localStorage，同样来得及）。
 */
function flush() {
  if (!saveTimer) return;
  clearTimeout(saveTimer);
  saveTimer = null;
  const r = storeWrite(NAME, { version: 1, entries: entries.value.slice(0, MAX) });
  if (r && r.ok === false) errorText.value = r.error || "写入历史失败";
}

/** 合并写入：250ms 内多次记录只落一次盘，避免连点计算时频繁写文件 */
function persist() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, 250);
}

/* 关窗/切页前补一次落盘（见 flush 的说明）。模块级只挂一次。 */
if (typeof window !== "undefined") {
  window.addEventListener("pagehide", flush);
}

/**
 * 记一条。
 * @param {{route?:string, mode?:string, expr:string, summary?:string, ok?:boolean}} e
 * @returns 写入的条目（expr 为空且没有 mode 时返回 null，不记）
 */
export function record(e) {
  const expr = String(e?.expr ?? "").trim();
  const mode = String(e?.mode ?? "").trim();
  if (!expr && !mode) return null;
  loadHistory();
  const entry = {
    id: mkId(),
    ts: Date.now(),
    route: String(e?.route ?? ""),
    mode,
    expr,
    summary: String(e?.summary ?? "").slice(0, 300),
    ok: e?.ok !== false,
  };
  // 同一页、同一模式、同一表达式：只更新时间并置顶。
  // 否则"算一次 → 改个参数再算回来"会堆出一串一模一样的记录。
  const dup = entries.value.findIndex(
    (x) => x.route === entry.route && x.mode === entry.mode && x.expr === entry.expr
  );
  if (dup >= 0) {
    entry.id = entries.value[dup].id;
    entry.ts = entries.value[dup].ts;   // 保留首次时间，便于"我什么时候第一次算的"
    entries.value.splice(dup, 1);
  }
  entries.value = [entry, ...entries.value].slice(0, MAX);
  persist();
  return entry;
}

export function removeEntry(id) {
  loadHistory();
  entries.value = entries.value.filter((x) => x.id !== id);
  persist();
}

export function clearAll() {
  loadHistory();
  entries.value = [];
  persist();
}

/** 只清某一页的历史（基础运算页的"清空"用它） */
export function clearRoute(route) {
  loadHistory();
  entries.value = entries.value.filter((x) => x.route !== route);
  persist();
}

export function listByRoute(route, limit = 0) {
  loadHistory();
  const out = entries.value.filter((x) => x.route === route);
  return limit > 0 ? out.slice(0, limit) : out;
}

/** 关键词过滤：表达式、结果摘要、模式名都参与匹配（空格分词，全部命中才算） */
export function searchEntries(query, source = entries.value) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return source;
  const terms = q.split(/\s+/).filter(Boolean);
  return source.filter((e) => {
    const hay = `${e.expr} ${e.summary} ${e.mode}`.toLowerCase();
    return terms.every((t) => hay.includes(t));
  });
}

export function historyError() {
  loadHistory();
  return errorText.value;
}

/** 组合式入口：组件里 `const { entries, count, record, ... } = useHistory()` */
export function useHistory() {
  loadHistory();
  return {
    entries,
    count: computed(() => entries.value.length),
    error: computed(() => errorText.value),
    record,
    removeEntry,
    clearAll,
    clearRoute,
    listByRoute,
    searchEntries,
    reload: () => loadHistory(true),
    MAX,
  };
}
