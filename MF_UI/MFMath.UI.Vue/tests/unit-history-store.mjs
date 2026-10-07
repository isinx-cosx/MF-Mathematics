// history/store.js 单元测试 —— 不依赖宿主窗口，用假桥（内存 KV）替换 sys 桥
//
// 为什么要单独做一个：这条竞态**从界面上几乎点不出来**（要在 250ms 的写盘窗口内恰好按到
// "重新加载"），但后果是**静默丢数据** —— `docs/FRONTEND-FIXES.md` §5 当年只标了"未验证"。
// 用假桥就能把那个 250ms 窗口稳定复现出来。
//
// 判据（三条，前两条在修复前会失败）：
//   ① record() 之后立刻 reload()：刚记的条目**必须还在**（修复前会被旧文件覆盖、并被写回盘）
//   ② clearAll() 之后立刻 reload()：**必须还是空的**（修复前被清掉的条目会复活）
//   ③ 合并写仍然生效：短时间内多次 record 只落一次盘（不能为了修①把去抖搞坏）
//
// 用法: node tests/unit-history-store.mjs

const K = {};                    // 假存储：内存 KV
let writes = 0;                  // 落盘次数（用来验"合并写"）
const readRaw = () => JSON.parse(JSON.stringify(K));

globalThis.window = {
  chrome: {
    webview: {
      hostObjects: {
        sync: {
          sys: {
            StoreRead(name) {
              const v = K[name];
              return JSON.stringify(v === undefined
                ? { ok: true, exists: false, json: "" }
                : { ok: true, exists: true, json: v });
            },
            StoreWrite(name, json) {
              writes++;
              JSON.parse(json);          // 与真实宿主同样的校验
              K[name] = json;
              return JSON.stringify({ ok: true });
            },
          },
        },
      },
    },
  },
  addEventListener() { /* pagehide 注册：这里不需要真的触发 */ },
};

/* 预置一条旧记录（模拟"上次会话留下的历史"） */
K.history = JSON.stringify({ version: 1, entries: [{ id: "old", ts: 1, route: "/calc/algebra", mode: "化简", expr: "旧记录", summary: "1", ok: true }] });

/* ⚠ reload 不是顶层导出，它只是 useHistory() 返回的一个便捷函数（内部就是 loadHistory(true)）。
 * 测试直接调 loadHistory(true)，与设置页那条"重新加载"走的是同一条路。 */
const { entries, record, clearAll, loadHistory, useHistory } = await import("../src/lib/history/store.js");
const reload = () => loadHistory(true);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

useHistory();
console.log(`起始：内存 ${entries.value.length} 条，盘上 ${readRaw().history ? JSON.parse(K.history).entries.length : 0} 条`);

/* ① record 之后立刻 reload —— 这是会丢数据的那个顺序 */
record({ route: "/calc/algebra", mode: "化简", expr: "新记录A", summary: "2", ok: true });
reload();                                  // 不等那 250ms
const hasA = entries.value.some((e) => e.expr === "新记录A");
check("① record 后立刻 reload：新条目仍在内存里", hasA,
  hasA ? "" : `内存=${JSON.stringify(entries.value.map((e) => e.expr))}`);
const diskAfterA = JSON.parse(K.history).entries.map((e) => e.expr);
check("① 新条目也确实落到了盘上（不是只活在内存）", diskAfterA.includes("新记录A"),
  `盘上=${JSON.stringify(diskAfterA)}`);

/* ② clearAll 之后立刻 reload —— 清空不该复活 */
clearAll();
reload();
check("② clearAll 后立刻 reload：仍然是空的（没有复活）", entries.value.length === 0,
  `内存=${entries.value.length} 条；盘上=${JSON.parse(K.history).entries.length} 条`);

/* ③ 去抖仍然合并写：短时间内连记 5 次，只应落一次盘 */
const before = writes;
for (let i = 0; i < 5; i++) record({ route: "/calc/algebra", mode: "化简", expr: "连点" + i, summary: "x", ok: true });
await new Promise((r) => setTimeout(r, 400));      // 等过 250ms 去抖窗口
const delta = writes - before;
check("③ 5 次连记只落一次盘（去抖没被修坏）", delta === 1, `实际落盘 ${delta} 次`);
check("③ 且盘上是最新的那一批（5 条都在）", JSON.parse(K.history).entries.length === 5,
  `盘上 ${JSON.parse(K.history).entries.length} 条`);

console.log(`\n═══ history/store：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|unit-history-store|${pass}|${fail}`);
process.exit(fail ? 1 : 0);
