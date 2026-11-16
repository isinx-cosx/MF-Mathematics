/**
 * 关掉可能开着的浮层（AI 助手面板 / 外观弹层），把画布让出来。
 *
 * 为什么每支绘图用例都需要它：`cdp-ai` 跑完会把 AI 面板**留在打开状态**，
 * 而 `AiPanel` 是 `position: fixed` 的抽屉，正好盖在绘图画布上 ——
 * 于是拖拽/点击全打在 `DIV.ai-body` 上，用例只看到"像素没变"（实测签名一模一样）。
 * 这类失败看起来像产品回归，其实是**上一条用例没收拾干净**。
 */
export async function closeOverlays(evalJs) {
  return await evalJs(`(function(){
    const out = [];
    const aiClose = document.querySelector('[data-ai="close"]');
    if (aiClose) { aiClose.click(); out.push('ai'); }
    const ap = document.querySelector('.appearance-pop');
    if (ap) {
      const x = ap.querySelector('.ap-close');
      if (x) x.click();
      out.push('appearance');
    }
    return out.join(',') || 'none';
  })()`);
}

/** 断言浮层真的关掉了（否则后面的像素/拖拽断言没有意义） */
export async function overlaysClosed(evalJs) {
  return (await evalJs(`!document.querySelector('.ai-panel') && !document.querySelector('.appearance-pop')`)) === true;
}
