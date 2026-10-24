/* 盐选收藏 · 交互层（零依赖，配合 style.css 设计系统）
   - 主题/字号持久化、移动端抽屉、阅读进度、返回顶部
   - 文章页：从 GitHub raw 直链按需拉取全文并渲染（jsDelivr 备用线路）
   - 浏览区：标题即时筛选 + 拼音首字母分组（数据来自 articles_index.json）
   - Pagefind 搜索兜底（中文分词不对齐时给简化关键词建议）
   */
(function () {
  "use strict";

  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return [].slice.call((el || document).querySelectorAll(s)); };

  /* ---------- 主题 ---------- */
  var themeBtn = $("#theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var pref = localStorage.getItem("theme") || "auto";
      var next = pref === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      document.documentElement.dataset.theme = next;
    });
  }

  /* ---------- 字号（FAB 簇） ---------- */
  var clamp = function (v) { return Math.min(22, Math.max(15, v)); };
  function applyFont(v) {
    document.documentElement.style.setProperty("--read-scale", v / 18);
    localStorage.setItem("font-size", v);
  }
  document.documentElement.style.setProperty(
    "--read-scale", (parseInt(localStorage.getItem("font-size") || "18", 10)) / 18);
  [["font-minus", -1], ["font-plus", 1], ["font-reset", 0]].forEach(function (pair) {
    var el = document.getElementById(pair[0]);
    if (!el) return;
    el.addEventListener("click", function () {
      var cur = parseInt(localStorage.getItem("font-size") || "18", 10);
      applyFont(pair[1] === 0 ? 18 : clamp(cur + pair[1]));
    });
  });

  /* ---------- 移动端抽屉 ---------- */
  var drawer = $("#drawer"), backdrop = $("#drawer-backdrop"), navToggle = $("#nav-toggle");
  function closeDrawer() {
    if (drawer) drawer.classList.remove("open");
    if (backdrop) backdrop.classList.remove("open");
  }
  if (navToggle && drawer) {
    navToggle.addEventListener("click", function () {
      drawer.classList.add("open");
      if (backdrop) backdrop.classList.add("open");
    });
  }
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  /* ---------- 阅读进度条 + FAB 显隐 ---------- */
  var progress = $("#read-progress"), fabs = $("#fabs");
  function onScroll() {
    var st = window.scrollY;
    if (progress) {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      progress.style.width = (h > 0 ? Math.min(100, st / h * 100) : 0) + "%";
    }
    if (fabs) fabs.classList.toggle("show", st > 500);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  var toTop = $("#back-top");
  if (toTop) toTop.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  /* ---------- 首页统计数字滚动 ---------- */
  $$("[data-countup]").forEach(function (el) {
    var target = parseInt(el.dataset.countup, 10) || 0;
    var t0 = null, dur = 900;
    function tick(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString("zh-Hans-CN");
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });

  /* ---------- 文章页：GitHub 直链按需全文 ----------
     页面只内建开头 1500 字摘要（同时是 Pagefind 索引窗口），
     全文在阅读时从 raw.githubusercontent.com 拉取，jsDelivr 兜底。 */
  var reader = $("#full-reader");
  if (reader && window.marked) {
    var mdPath = reader.dataset.md;           // 仓库内相对路径，如 我不是盐神/xxx.md
    var owner = reader.dataset.owner, repo = reader.dataset.repo, branch = reader.dataset.branch;
    var encoded = mdPath.split("/").map(encodeURIComponent).join("/");
    var sources = [
      "https://raw.githubusercontent.com/" + owner + "/" + repo + "/" + branch + "/" + encoded,
      "https://cdn.jsdelivr.net/gh/" + owner + "/" + repo + "@" + branch + "/" + encoded
    ];
    var blobUrl = "https://github.com/" + owner + "/" + repo + "/blob/" + branch + "/" + encoded;

    var loading = document.createElement("div");
    loading.className = "read-loading";
    loading.innerHTML = '<span class="spinner"></span>正在从 GitHub 拉取全文…';
    reader.appendChild(loading);

    function renderFail(first) {
      loading.remove();
      var err = document.createElement("div");
      err.className = "read-error";
      err.innerHTML = (first ? "全文拉取失败（两条线路均未成功），先看上面的开头部分。" : "") +
        '<button type="button" id="read-retry">重试</button>' +
        '<a class="btn" href="' + blobUrl + '" target="_blank" rel="noopener">在 GitHub 查看</a>';
      reader.appendChild(err);
      var rb = $("#read-retry");
      if (rb) rb.addEventListener("click", function () { err.remove(); load(0); });
    }

    function load(i) {
      if (i >= sources.length) { renderFail(true); return; }
      loading.style.display = "";
      fetch(sources[i], { mode: "cors" })
        .then(function (r) {
          if (!r.ok) throw new Error(r.status);
          return r.text();
        })
        .then(function (text) {
          // 去掉 front matter，防止渲染成正文
          text = text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "");
          // 防御性转义游离的标签（源文件本身经清洗，理论上不含 HTML）
          text = text.replace(/<(?=[a-zA-Z!/])/g, "&lt;");
          loading.remove();
          reader.innerHTML = marked.parse(text);
          onScroll();
        })
        .catch(function () { load(i + 1); });
    }
    load(0);
  }

  /* ---------- 浏览区：标题即时筛选 + 拼音首字母 ---------- */
  var browser = $("#browser");
  if (browser) {
    var url = browser.dataset.index;
    var onlySource = browser.dataset.source || "";
    var PAGE = 60, state = { q: "", letter: "全部", shown: PAGE };
    var collator = null;
    try { collator = new Intl.Collator("zh-Hans-CN", { numeric: true }); } catch (e) {}

    var SRC_COLORS = {
      "我不是盐神": "var(--src-yanshen)",
      "盐选文库": "var(--src-yanxuanwk)",
      "知乎搬运工": "var(--src-zhbyg)",
      "语雀盐选库": "var(--src-yuque)"
    };

    browser.innerHTML = '<div class="browse-skeleton">' +
      '<div class="sk"></div>'.repeat(6) + "</div>";

    fetch(url).then(function (r) { return r.json(); }).then(function (data) {
      var arts = data.articles || [];
      if (onlySource) arts = arts.filter(function (a) { return a.s === onlySource; });
      if (collator) {
        arts.sort(function (a, b) { return collator.compare(a.t, b.t); });
      }
      var letters = ["全部"].concat(
        [].map.call(arts, function (a) { return a.i === "0" ? "#" : a.i; })
          .filter(function (v, i, arr) { return arr.indexOf(v) === i && v !== "0"; })
          .sort());
      mount(arts, letters);
    }).catch(function () {
      browser.innerHTML = '<div class="read-error">索引加载失败，' +
        '可刷新重试或前往 <a class="btn" href="' +
        (browser.dataset.repoUrl || "#") + '">GitHub 仓库</a> 浏览目录。</div>';
    });

    function normLetter(a) { return a.i === "0" ? "#" : a.i; }

    function filtered(arts) {
      var q = state.q.toLowerCase();
      return arts.filter(function (a) {
        if (state.letter !== "全部" && normLetter(a) !== state.letter) return false;
        if (!q) return true;
        if (a.t.toLowerCase().indexOf(q) >= 0) return true;
        return a.c && a.c.toLowerCase().indexOf(q) >= 0;
      });
    }

    function esc(s) {
      return String(s).replace(/[&<>"]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
      });
    }

    function hi(title) {
      var q = state.q.trim();
      if (!q) return esc(title);
      var i = title.toLowerCase().indexOf(q.toLowerCase());
      if (i < 0) return esc(title);
      return esc(title.slice(0, i)) + "<mark>" + esc(title.slice(i, i + q.length)) + "</mark>" +
        esc(title.slice(i + q.length));
    }

    function hrefOf(a) {
      // 索引里的 l 是「源/Hugo slug/」永久链接（与站点 URL 完全一致）
      if (a.l) return (browser.dataset.base || "/") +
        a.l.split("/").map(encodeURIComponent).join("/");
      var segs = a.p.replace(/\.md$/, "").split("/").map(encodeURIComponent);
      return (browser.dataset.base || "/") + segs.join("/") + "/";
    }

    function mount(arts, letters) {
      browser.innerHTML =
        '<div class="browse-bar">' +
        '<input class="browse-filter" type="search" placeholder="输入标题关键词，即时筛选" autocomplete="off">' +
        '<div class="browse-letters" role="tablist">' +
        letters.map(function (L) {
          return '<button type="button" role="tab" data-l="' + L + '"' +
            (L === "全部" ? ' class="on"' : "") + ">" + L + "</button>";
        }).join("") +
        "</div></div>" +
        '<div class="browse-meta"></div>' +
        '<ul class="browse-list"></ul>' +
        '<button type="button" class="browse-more" hidden>加载更多</button>';

      var input = $(".browse-filter", browser);
      var meta = $(".browse-meta", browser);
      var list = $(".browse-list", browser);
      var more = $(".browse-more", browser);
      var deb = null;

      input.addEventListener("input", function () {
        clearTimeout(deb);
        var v = input.value;
        deb = setTimeout(function () { state.q = v.trim(); state.shown = PAGE; render(); }, 120);
      });
      $$(".browse-letters button", browser).forEach(function (b) {
        b.addEventListener("click", function () {
          $$(".browse-letters button", browser).forEach(function (x) { x.classList.remove("on"); });
          b.classList.add("on");
          state.letter = b.dataset.l;
          state.shown = PAGE;
          render();
        });
      });
      more.addEventListener("click", function () {
        state.shown += PAGE;
        render(true);
      });

      function render(append) {
        var rows = filtered(arts);
        var view = rows.slice(0, state.shown);
        meta.textContent = "共 " + rows.length.toLocaleString("zh-Hans-CN") + " 篇" +
          (rows.length > view.length ? " · 已显示 " + view.length : "") +
          (state.q ? " · 关键词「" + state.q + "」" : "");
        list.innerHTML = view.map(function (a) {
          return "<li><a href='" + hrefOf(a) + "'>" +
            "<span class='bl-letter'>" + esc(normLetter(a)) + "</span>" +
            "<span class='bl-title'>" + hi(a.t) + "</span>" +
            (a.c ? "<span class='bl-col'>《" + esc(a.c) + "》</span>" : "") +
            (onlySource ? "" :
              "<span class='bl-src' style='--sc:" + (SRC_COLORS[a.s] || "var(--accent)") + "'>" +
              esc(a.s) + "</span>") +
            "</a></li>";
        }).join("");
        more.hidden = rows.length <= view.length;
        if (rows.length === 0) {
          list.innerHTML = "<li><a style='pointer-events:none;color:var(--muted)'>" +
            "没有匹配的文章，换个关键词试试</a></li>";
        }
      }
      render();
    }
  }

  /* ---------- Pagefind 搜索兜底（中文分词错位时给建议） ---------- */
  async function initSearchFallback() {
    var box = document.querySelector("#search");
    if (!box || box.dataset.fallbackBound) return;
    box.dataset.fallbackBound = "1";
    var pfPath = box.dataset.pagefind || "pagefind/pagefind.js";
    var pf = null;
    try { pf = await import(pfPath); } catch (e) { return; }

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
  initSearchFallback();
})();
