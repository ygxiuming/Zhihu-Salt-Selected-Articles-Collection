/* 搜索兜底：Pagefind 中文分词与查询分词偶有不对齐（如含「我的」的
   长词组会 0 结果），此时自动用简化关键词重搜并给出建议按钮 */
async function initSearchFallback() {
  var box = document.querySelector("#search");
  if (!box || box.dataset.fallbackBound) return;
  box.dataset.fallbackBound = "1";
  var pfPath = box.dataset.pagefind || "pagefind/pagefind.js";
  var pf = null;
  try {
    pf = await import(pfPath);
  } catch (e) { return; }

  var STOP = /(我的|你的|他的|她的|什么|怎么|这样|那样|一个|一下|已经|就是|不是|有没有|可以|这个|那个|真的|现在|时候)/g;

  async function count(q) {
    try { return (await pf.search(q)).results.length; }
    catch (e) { return 0; }
  }

  var input = box.querySelector(".pagefind-ui__search-input");
  if (!input) return;
  var deb = null;
  input.addEventListener("input", function () {
    clearTimeout(deb);
    deb = setTimeout(check, 900);
  });

  async function check() {
    var old = box.querySelector(".search-fallback");
    if (old) old.remove();
    var q = input.value.trim();
    if (!q || (await count(q)) > 0) return;

    var cleaned = q.replace(STOP, "").trim();
    var cands = [];
    var n0 = (cleaned && cleaned !== q) ? await count(cleaned) : 0;
    if (n0 > 0) cands.push([cleaned, n0]);
    if (!cands.length && cleaned.replace(/\s/g, "").length >= 4) {
      var flat = cleaned.replace(/\s/g, "");
      for (var i = 0; i + 3 <= flat.length && cands.length < 4; i += 3) {
        var w = flat.substr(i, 3);
        if (w && cands.every(function (c) { return c[0] !== w; })) {
          var n = await count(w);
          if (n > 0) cands.push([w, n]);
        }
      }
    }
    if (!cands.length) return;

    var wrap = document.createElement("div");
    wrap.className = "search-fallback";
    wrap.textContent = "「" + q + "」没有直接命中，试试：";
    cands.forEach(function (c) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = c[0] + "（" + c[1] + " 条）";
      b.addEventListener("click", function () {
        input.value = c[0];
        input.dispatchEvent(new Event("input", { bubbles: true }));
        wrap.remove();
      });
      wrap.appendChild(b);
    });
    box.appendChild(wrap);
  }
}

/* 主题切换 / 字号调节（localStorage 持久化） */
(function () {
  var root = document.documentElement;

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var pref = localStorage.getItem("theme") || "auto";
      var next = pref === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      root.dataset.theme = next;
    });
  }

  var clamp = function (v) { return Math.min(24, Math.max(14, v)); };
  var apply = function (v) {
    root.style.fontSize = v + "px";
    localStorage.setItem("font-size", v);
  };
  var current = function () {
    return parseInt(localStorage.getItem("font-size") || "18", 10);
  };
  [["font-minus", -1], ["font-plus", 1], ["font-reset", 0]].forEach(function (pair) {
    var el = document.getElementById(pair[0]);
    if (!el) return;
    el.addEventListener("click", function () {
      if (pair[1] === 0) apply(18);
      else apply(clamp(current() + pair[1]));
    });
  });

  initSearchFallback();
})();
