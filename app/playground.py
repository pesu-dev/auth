"""HTML for the interactive PESUAuth API Explorer."""

PLAYGROUND_HTML = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta name="description" content="Explore and test the PESUAuth API." />
    <meta name="color-scheme" content="light dark" />
    <title>PESUAuth API Explorer</title>
    <script>
      (() => {
        const saved = localStorage.getItem("pesuauth-theme") || "system";
        const dark =
          saved === "dark" ||
          (saved === "system" &&
            matchMedia("(prefers-color-scheme:dark)").matches);
        document.documentElement.dataset.theme = dark ? "dark" : "light";
        document.documentElement.dataset.preference = saved;
      })();
    </script>
    <style>
      :root {
        color-scheme: light;
        --bg: #f7f7f5;
        --surface: #fff;
        --surface-soft: #efefec;
        --line: #d8d8d2;
        --line-strong: #a9aaa4;
        --text: #171816;
        --muted: #6f716b;
        --soft: #444740;
        --button: #171816;
        --button-text: #fff;
        --get: #2563a8;
        --post: #a45d13;
        --danger: #b63e34;
        --code: #f0f0ec;
        --shadow: 0 10px 35px rgba(30, 31, 28, 0.06);
      }
      :root[data-theme="dark"] {
        color-scheme: dark;
        --bg: #090a09;
        --surface: #101110;
        --surface-soft: #191a19;
        --line: #292b29;
        --line-strong: #515451;
        --text: #f1f1ed;
        --muted: #969a94;
        --soft: #c7cac4;
        --button: #f1f1ed;
        --button-text: #101110;
        --get: #75a7e5;
        --post: #d6a466;
        --danger: #e48c84;
        --code: #141514;
        --shadow: 0 14px 40px rgba(0, 0, 0, 0.18);
      }
      * {
        box-sizing: border-box;
      }
      html,
      body {
        margin: 0;
        min-height: 100%;
        background-color: var(--bg);
        color: var(--text);
        font-family: Arial, Helvetica, sans-serif;
      }
      button,
      input,
      textarea,
      select {
        font: inherit;
      }
      button {
        color: inherit;
      }
      .shell {
        position: relative;
        z-index: 1;
        min-height: 100vh;
      }
      #dotGrid {
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
      }
      .topbar {
        height: 62px;
        border-bottom: 1px solid var(--line);
        display: flex;
        align-items: center;
        padding: 0 max(18px, calc((100vw - 1380px) / 2));
        gap: 28px;
        background: color-mix(in srgb, var(--bg) 94%, transparent);
        position: sticky;
        top: 0;
        z-index: 10;
        backdrop-filter: blur(16px);
      }
      .brand {
        font:
          22px Georgia,
          "Times New Roman",
          serif;
        white-space: nowrap;
      }
      .brand small {
        font:
          10px "SFMono-Regular",
          Consolas,
          monospace;
        color: var(--muted);
        margin-left: 8px;
      }
      .topnav {
        display: flex;
        gap: 22px;
        font:
          10px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
        color: var(--muted);
      }
      .topnav a {
        color: var(--muted);
        display: grid;
        place-items: center;
        transition: color 0.15s;
      }
      .topnav a:hover {
        color: var(--text);
      }
      .topnav a svg {
        width: 24px;
        height: 24px;
        display: block;
      }
      .theme-wrap {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .theme-label {
        font:
          9px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
        color: var(--muted);
      }
      .theme-switcher {
        display: flex;
        padding: 3px;
        border: 1px solid var(--line);
        border-radius: 99px;
        background: var(--surface);
        box-shadow: var(--shadow);
      }
      .theme-option,
      .icon-button {
        border: 0;
        background: transparent;
        display: grid;
        place-items: center;
        cursor: pointer;
      }
      .theme-option {
        position: relative;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        color: var(--muted);
      }
      .theme-option:hover {
        color: var(--text);
      }
      .theme-option.active {
        color: var(--text);
        background: var(--surface-soft);
        box-shadow: inset 0 0 0 1px var(--line-strong);
      }
      .theme-option svg,
      .icon-button svg {
        width: 15px;
        height: 15px;
      }
      .theme-option:focus-visible,
      .icon-button:focus-visible,
      .endpoint:focus-visible,
      .action:focus-visible,
      .copy:focus-visible {
        outline: 2px solid var(--text);
        outline-offset: 2px;
      }
      .workspace {
        display: grid;
        grid-template-columns: 220px minmax(420px, 1fr) minmax(340px, 0.75fr);
        max-width: 1380px;
        margin: auto;
        min-height: calc(100vh - 62px);
        background: var(--bg);
      }
      .sidebar {
        border-right: 1px solid var(--line);
        padding: 28px 16px;
        background: var(--surface);
      }
      .main {
        padding: 38px clamp(25px, 4vw, 56px);
      }
      .request-panel {
        border-left: 1px solid var(--line);
        padding: 28px 24px;
        background: var(--surface);
      }
      .section-title,
      .eyebrow {
        font:
          10px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
        color: var(--muted);
      }
      .endpoint-list {
        display: grid;
        gap: 6px;
        margin-top: 16px;
      }
      .endpoint {
        width: 100%;
        display: grid;
        grid-template-columns: 44px 1fr;
        gap: 8px;
        align-items: center;
        border: 1px solid transparent;
        background: transparent;
        text-align: left;
        padding: 10px;
        border-radius: 6px;
        cursor: pointer;
      }
      .endpoint:hover {
        background: var(--surface-soft);
      }
      .endpoint.active {
        background: var(--surface-soft);
        border-color: var(--line-strong);
      }
      .method {
        font:
          700 9px "SFMono-Regular",
          Consolas,
          monospace;
      }
      .method.get {
        color: var(--get);
      }
      .method.post {
        color: var(--post);
      }
      .path {
        font:
          11px "SFMono-Regular",
          Consolas,
          monospace;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .sidebar-links {
        border-top: 1px solid var(--line);
        margin-top: 24px;
        padding-top: 16px;
        display: grid;
        gap: 10px;
      }
      .sidebar-links a {
        font:
          11px "SFMono-Regular",
          Consolas,
          monospace;
        color: var(--muted);
        text-decoration: none;
      }
      .sidebar-links a:hover {
        color: var(--text);
      }
      .eyebrow {
        display: flex;
        align-items: center;
      }
      h1 {
        font:
          44px/1.04 Georgia,
          "Times New Roman",
          serif;
        font-weight: 400;
        margin: 16px 0 12px;
      }
      p {
        color: var(--soft);
        line-height: 1.65;
      }
      .intro {
        font-size: 14px;
        max-width: 680px;
        margin: 0;
      }
      .intro p {
        margin: 0;
      }
      .intro p + p {
        margin-top: 8px;
      }
      .endpoint-heading {
        display: flex;
        gap: 12px;
        align-items: center;
        margin-top: 30px;
      }
      .method-pill {
        font:
          700 10px "SFMono-Regular",
          Consolas,
          monospace;
        padding: 6px 8px;
        border: 1px solid var(--line-strong);
        border-radius: 4px;
      }
      .method-pill.get {
        color: var(--get);
      }
      .method-pill.post {
        color: var(--post);
      }
      h2 {
        font:
          27px Georgia,
          "Times New Roman",
          serif;
        font-weight: 400;
        margin: 0;
      }
      .rule {
        border: 0;
        border-top: 1px solid var(--line);
        margin: 26px 0;
      }
      .fields {
        display: grid;
        gap: 0;
        margin-top: 10px;
      }
      .field-row {
        display: grid;
        grid-template-columns: 135px 72px 1fr;
        gap: 15px;
        padding: 13px 0;
        border-bottom: 1px solid var(--line);
        font-size: 12px;
      }
      .field-row code {
        font-family: "SFMono-Regular", Consolas, monospace;
      }
      .field-row span {
        color: var(--muted);
      }
      .field-row p {
        margin: 0;
        font-size: 12px;
        line-height: 1.5;
      }
      .schema {
        margin: 8px 0 0;
        font-size: 12px;
        white-space: pre;
        overflow-x: auto;
      }
      details.response-code summary {
        cursor: pointer;
      }
      .responses {
        display: flex;
        gap: 7px;
        flex-wrap: wrap;
        margin-top: 13px;
      }
      .response-code {
        border: 1px solid var(--line);
        border-radius: 4px;
        padding: 7px 9px;
        font:
          10px "SFMono-Regular",
          Consolas,
          monospace;
        color: var(--soft);
      }
      .explanation {
        margin-top: 12px;
        font-size: 13px;
        color: var(--soft);
      }
      .explanation h3 {
        font:
          16px Georgia,
          "Times New Roman",
          serif;
        color: var(--text);
        font-weight: 400;
        margin: 20px 0 7px;
      }
      .explanation p {
        margin: 0 0 9px;
      }
      .explanation code {
        font:
          11px "SFMono-Regular",
          Consolas,
          monospace;
        background: var(--code);
        border: 1px solid var(--line);
        padding: 2px 4px;
        border-radius: 3px;
      }
      .explanation pre {
        overflow: auto;
        background: var(--code);
        border: 1px solid var(--line);
        padding: 14px;
        border-radius: 6px;
      }
      .explanation pre code {
        padding: 0;
        border: 0;
        background: transparent;
        line-height: 1.6;
      }
      .panel-head,
      .result-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .panel-head {
        margin-bottom: 16px;
      }
      .panel-head strong {
        font:
          11px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
      }
      .icon-button {
        width: 32px;
        height: 32px;
        border: 1px solid var(--line);
        border-radius: 5px;
        color: var(--muted);
      }
      .icon-button:hover {
        color: var(--text);
        border-color: var(--line-strong);
      }
      .icon-button.is-loading svg {
        animation: spin 0.7s linear infinite;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      label {
        display: block;
        font:
          9px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
        color: var(--muted);
        margin: 14px 0 7px;
      }
      .control,
      textarea,
      select {
        width: 100%;
        border: 1px solid var(--line);
        background: var(--bg);
        color: var(--text);
        border-radius: 5px;
        outline: none;
      }
      .control,
      select {
        height: 40px;
        padding: 0 11px;
      }
      textarea {
        min-height: 150px;
        padding: 12px;
        font:
          12px/1.55 "SFMono-Regular",
          Consolas,
          monospace;
        resize: vertical;
      }
      .control:focus,
      textarea:focus,
      select:focus {
        border-color: var(--text);
      }
      .action {
        width: 100%;
        border: 1px solid var(--button);
        border-radius: 5px;
        background: var(--button);
        color: var(--button-text);
        cursor: pointer;
        padding: 12px;
        margin-top: 15px;
        font:
          700 10px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
      }
      .action:disabled {
        opacity: 0.55;
        cursor: wait;
      }
      .result {
        margin-top: 22px;
        border-top: 1px solid var(--line);
        padding-top: 18px;
      }
      .copy {
        border: 1px solid var(--line);
        border-radius: 5px;
        background: transparent;
        color: var(--muted);
        padding: 6px 8px;
        cursor: pointer;
        font:
          9px "SFMono-Regular",
          Consolas,
          monospace;
        text-transform: uppercase;
      }
      .copy:hover {
        color: var(--text);
        border-color: var(--line-strong);
      }
      .output {
        min-height: 130px;
        max-height: 350px;
        overflow: auto;
        margin: 10px 0 0;
        border: 1px solid var(--line);
        border-radius: 6px;
        background: var(--bg);
        padding: 14px;
        white-space: pre-wrap;
        word-break: break-word;
        font:
          11px/1.65 "SFMono-Regular",
          Consolas,
          monospace;
        color: var(--soft);
      }
      .output.error {
        color: var(--danger);
      }
      .empty {
        color: var(--muted);
        font-size: 12px;
      }
      .toast {
        position: fixed;
        right: 20px;
        bottom: 20px;
        z-index: 100;
        background: var(--text);
        color: var(--bg);
        padding: 9px 12px;
        border-radius: 5px;
        font:
          10px "SFMono-Regular",
          Consolas,
          monospace;
        opacity: 0;
        transform: translateY(8px);
        pointer-events: none;
        transition: 0.18s;
      }
      .toast.show {
        opacity: 1;
        transform: none;
      }
      @media (prefers-reduced-motion: reduce) {
        * {
          scroll-behavior: auto !important;
          transition: none !important;
        }
      }
      @media (max-width: 1040px) {
        .workspace {
          grid-template-columns: 210px 1fr;
        }
        .request-panel {
          grid-column: 1/-1;
          border-left: 0;
          border-top: 1px solid var(--line);
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 24px;
        }
        .result {
          margin-top: 0;
          border-top: 0;
          padding-top: 0;
        }
      }
      @media (max-width: 700px) {
        .topbar {
          padding: 0 14px;
          gap: 14px;
        }
        .topnav,
        .theme-label {
          display: none;
        }
        .brand {
          font-size: 19px;
        }
        .workspace {
          display: block;
        }
        .sidebar {
          border-right: 0;
          border-bottom: 1px solid var(--line);
          padding: 16px 14px;
        }
        .endpoint-list {
          display: flex;
          overflow: auto;
        }
        .endpoint {
          min-width: 145px;
        }
        .sidebar-links {
          display: none;
        }
        .main {
          padding: 28px 18px;
        }
        .request-panel {
          display: block;
          padding: 24px 18px;
        }
        .result {
          margin-top: 22px;
          border-top: 1px solid var(--line);
          padding-top: 18px;
        }
        .field-row {
          grid-template-columns: 105px 58px 1fr;
        }
        h1 {
          font-size: 36px;
        }
        .theme-wrap {
          margin-left: auto;
        }
      }
    </style>
  </head>
  <body>
    <canvas id="dotGrid" aria-hidden="true"></canvas>
    <div class="shell">
      <header class="topbar">
        <div class="brand">PESU<small>AUTH / API</small></div>
        <nav class="topnav">
          <a
            href="https://github.com/pesu-dev/auth"
            rel="noreferrer"
            aria-label="GitHub repository"
            title="GitHub"
            ><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path
                d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.55
                  0-.27-.01-1.17-.02-2.12-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7
                  1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.69 1.25
                  3.35.96.1-.75.4-1.25.72-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28
                  1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.8
                  0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0
                  4.41-2.69 5.38-5.26 5.67.41.35.78 1.05.78 2.12 0 1.53-.01 2.76-.01 3.14 0
                  .3.2.66.8.55A11.51 11.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z"
              /></svg
          ></a>
        </nav>
        <div class="theme-wrap">
          <span class="theme-label">Theme</span>
          <div class="theme-switcher" role="radiogroup" aria-label="Theme">
            <button
              class="theme-option"
              data-theme-value="system"
              role="radio"
              aria-label="Use system theme"
              title="System theme"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <rect x="3" y="4" width="18" height="12" rx="2" />
                <path d="M8 20h8M12 16v4" />
              </svg>
            </button>
            <button
              class="theme-option"
              data-theme-value="light"
              role="radio"
              aria-label="Use light theme"
              title="Light theme"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="12" cy="12" r="4" />
                <path
                  d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93
                    19.07l1.42-1.42M17.66 6.34l1.41-1.41"
                />
              </svg>
            </button>
            <button
              class="theme-option"
              data-theme-value="dark"
              role="radio"
              aria-label="Use dark theme"
              title="Dark theme"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            </button>
          </div>
        </div>
      </header>
      <div class="workspace">
        <aside class="sidebar">
          <div class="section-title">Endpoints</div>
          <div id="endpoints" class="endpoint-list">
            <div class="empty">Loading...</div>
          </div>
        </aside>
        <main class="main">
          <div class="eyebrow" id="tag">API reference</div>
          <h1 id="title">Choose an endpoint</h1>
          <div id="description" class="intro">
            Select an endpoint to inspect and test it.
          </div>
          <div class="endpoint-heading">
            <span id="methodPill" class="method-pill">API</span>
            <h2 id="pathTitle">/</h2>
          </div>
          <hr class="rule" />
          <section>
            <div class="section-title">Parameters</div>
            <div id="fields" class="fields">
              <p class="empty">No endpoint selected.</p>
            </div>
          </section>
          <hr class="rule" />
          <section>
            <div class="section-title">Responses</div>
            <div id="responses" class="responses"></div>
          </section>
          <hr class="rule" />
          <section>
            <div class="section-title">Example request</div>
            <article id="explanation" class="explanation"></article>
          </section>
        </main>
        <aside class="request-panel">
          <div>
            <div class="panel-head">
              <strong>Request</strong
              ><button
                id="reloadBtn"
                class="icon-button"
                type="button"
                aria-label="Reload endpoints"
                title="Reload endpoints"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M20 12a8 8 0 0 0-14.93-4" />
                  <path d="M4 4v4h4" />
                  <path d="M4 12a8 8 0 0 0 14.93 4" />
                  <path d="M20 20v-4h-4" />
                </svg>
              </button>
            </div>
            <div id="queryFields"></div>
            <div id="authWrap">
              <label for="auth">Bearer token</label
              ><input
                id="auth"
                class="control"
                type="password"
                autocomplete="off"
                placeholder="Token"
              />
            </div>
            <p id="noAuth" class="empty">No authentication required.</p>
            <label for="body">Request body</label
            ><textarea id="body" spellcheck="false" aria-label="Request body">
{}</textarea
            ><button id="sendBtn" class="action" type="button">
              Send request
            </button>
          </div>
          <div class="result">
            <div class="result-toolbar">
              <span class="section-title">Response</span
              ><button id="copyBtn" class="copy" type="button">Copy</button>
            </div>
            <pre id="output" class="output">No response yet.</pre>
          </div>
        </aside>
      </div>
    </div>
    <div id="toast" class="toast" role="status"></div>
    <script>
      const state = {
        spec: null,
        path: null,
        method: null,
        operation: null,
        selectedIndex: 0,
      };
      const $ = (id) => document.getElementById(id);
      const esc = (s) =>
        String(s ?? "").replace(
          /[&<>"']/g,
          (c) =>
            ({
              "&": "&amp;",
              "<": "&lt;",
              ">": "&gt;",
              '"': "&quot;",
              "'": "&#39;",
            })[c],
        );
      function toast(message) {
        $("toast").textContent = message;
        $("toast").classList.add("show");
        setTimeout(() => $("toast").classList.remove("show"), 1300);
      }
      function applyTheme(value) {
        localStorage.setItem("pesuauth-theme", value);
        document.documentElement.dataset.preference = value;
        const dark =
          value === "dark" ||
          (value === "system" &&
            matchMedia("(prefers-color-scheme:dark)").matches);
        document.documentElement.dataset.theme = dark ? "dark" : "light";
        document.querySelectorAll("[data-theme-value]").forEach((b) => {
          const active = b.dataset.themeValue === value;
          b.classList.toggle("active", active);
          b.setAttribute("aria-checked", String(active));
        });
        if (window.grid) window.grid.draw();
      }
      document
        .querySelectorAll("[data-theme-value]")
        .forEach((b) => (b.onclick = () => applyTheme(b.dataset.themeValue)));
      applyTheme(document.documentElement.dataset.preference || "system");
      matchMedia("(prefers-color-scheme:dark)").addEventListener(
        "change",
        () => {
          if (document.documentElement.dataset.preference === "system")
            applyTheme("system");
        },
      );
      function schemaType(s = {}) {
        if (s.type === "array") return `array<${schemaType(s.items || {})}>`;
        return s.type || s.$ref?.split("/").pop() || "object";
      }
      function resolveSchema(s = {}, depth = 0) {
        while (s && s.$ref && depth < 10) {
          const name = s.$ref.split("/").pop();
          const next = state.spec?.components?.schemas?.[name];
          if (!next) break;
          s = { title: name, ...next };
          depth++;
        }
        return s || {};
      }
      function needsAuth(op) {
        return (op.security || state.spec?.security || []).length > 0;
      }
      function schemaTree(schema, indent = "  ", depth = 0) {
        const s = resolveSchema(schema);
        const variants = s.anyOf || s.oneOf;
        if (variants) {
          const real = variants.filter((v) => v.type !== "null");
          if (real.length === 1) return schemaTree(real[0], indent, depth);
        }
        if (s.type === "array")
          return `array<${schemaTree(s.items || {}, indent, depth)}>`;
        if (!s.properties || depth > 3) return s.format || s.type || s.title || "any";
        const req = s.required || [];
        const pad = indent.repeat(depth + 1);
        const lines = Object.entries(s.properties).map(
          ([k, v]) =>
            `${pad}${k}${req.includes(k) ? "" : "?"}: ${schemaTree(v, indent, depth + 1)}`,
        );
        return `{\n${lines.join("\n")}\n${indent.repeat(depth)}}`;
      }
      function responseSchema(r) {
        return r?.content?.["application/json"]?.schema || null;
      }
      function exampleForSchema(schema = {}) {
        schema = resolveSchema(schema);
        if (schema.example !== undefined) return schema.example;
        if (schema.default !== undefined) return schema.default;
        if (schema.enum) return schema.enum[0];
        if (schema.type === "object" || schema.properties) {
          const o = {};
          for (const [k, v] of Object.entries(schema.properties || {}))
            o[k] = exampleForSchema(v);
          return o;
        }
        if (schema.type === "array")
          return [exampleForSchema(schema.items || {})];
        if (schema.type === "boolean") return false;
        if (schema.type === "integer" || schema.type === "number") return 0;
        return `<${schema.title || schema.type || "value"}>`;
      }
      function requestSchema(op) {
        return op.requestBody?.content?.["application/json"]?.schema || null;
      }
      function requestExample(op) {
        const content = op.requestBody?.content?.["application/json"];
        const examples = content?.examples;
        if (examples) {
          const first = Object.values(examples)[0];
          if (first?.value) return first.value;
        }
        if (content?.example) return content.example;
        return content?.schema ? exampleForSchema(content.schema) : null;
      }
      function renderFields(op) {
        const rows = [];
        (op.parameters || []).forEach((p) =>
          rows.push({
            name: p.name,
            type: schemaType(p.schema),
            required: p.required,
            description: p.description || `${p.in} parameter`,
          }),
        );
        const schema = requestSchema(op);
        const bodySchema = schema ? resolveSchema(schema) : null;
        for (const [name, s] of Object.entries(bodySchema?.properties || {}))
          rows.push({
            name,
            type: schemaType(s),
            required: (bodySchema.required || []).includes(name),
            description: s.description || "Request body field",
          });
        $("fields").innerHTML = rows.length
          ? rows
              .map(
                (r) =>
                  `<div class="field-row"><code>${esc(r.name)}</code>` +
                  `<span>${esc(r.type)}${r.required ? " *" : ""}</span>` +
                  `<p>${esc(r.description)}</p></div>`,
              )
              .join("")
          : '<p class="empty">No input parameters.</p>';
      }
      function curlExample(path, method, op) {
        const example = requestExample(op);
        const query = (op.parameters || [])
          .filter((p) => p.in === "query")
          .map(
            (p, i) =>
              `${encodeURIComponent(p.name)}=` +
              encodeURIComponent(
                p.schema?.default ?? p.schema?.enum?.[0] ?? `value${i + 1}`,
              ),
          )
          .join("&");
        const url = `${location.origin}${path}${query ? "?" + query : ""}`;
        let curl = `curl -X ${method.toUpperCase()} '${url}'`;
        if (needsAuth(op))
          curl += ` \\\n  -H 'Authorization: Bearer <token>'`;
        if (example !== null)
          curl += ` \\\n  -H 'Content-Type: application/json' \\\n  -d '${JSON.stringify(example)}'`;
        return curl;
      }
      function markdownFor(path, method, op) {
        return [
          "### Authentication",
          needsAuth(op) ? "Bearer token, when the server requires one." : "None required.",
          "### Example request",
          "```bash",
          curlExample(path, method, op),
          "```",
        ].join("\n");
      }
      function renderMarkdown(md) {
        let html = "",
          inCode = false,
          code = [];
        const flush = () => {
          if (code.length) {
            html += `<pre><code>${esc(code.join("\n"))}</code></pre>`;
            code = [];
          }
        };
        for (const line of md.split("\n")) {
          if (line.startsWith("```")) {
            if (inCode) {
              flush();
              inCode = false;
            } else inCode = true;
            continue;
          }
          if (inCode) {
            code.push(line);
            continue;
          }
          if (line.startsWith("### ")) {
            html += `<h3>${esc(line.slice(4))}</h3>`;
            continue;
          }
          if (line.startsWith("- ")) {
            html += `<p>• ${inline(line.slice(2))}</p>`;
            continue;
          }
          if (line.trim()) html += `<p>${inline(line)}</p>`;
        }
        flush();
        return html;
      }
      function inline(s) {
        return esc(s)
          .replace(/`([^`]+)`/g, "<code>$1</code>")
          .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      }
      function renderQuery(op) {
        const params = (op.parameters || []).filter((p) => p.in === "query");
        $("queryFields").innerHTML = params
          .map(
            (p) =>
              `<label for="q-${esc(p.name)}">${esc(p.name)}${p.required ? " *" : ""}</label>` +
              `<input id="q-${esc(p.name)}" data-query="${esc(p.name)}" class="control" ` +
              `placeholder="${esc(p.schema?.default ?? p.schema?.enum?.[0] ?? "")}">`,
          )
          .join("");
      }
      function selectEndpoint(path, method, op, button, index) {
        state.path = path;
        state.method = method;
        state.operation = op;
        state.selectedIndex = index;
        document
          .querySelectorAll(".endpoint")
          .forEach((x) => x.classList.remove("active"));
        button.classList.add("active");
        $("tag").textContent = (op.tags || ["API reference"])[0];
        $("title").textContent =
          op.summary || `${method.toUpperCase()} ${path}`;
        const desc = (op.description || "")
          .split(/\n\n(?:Request body|Query) parameters:/i)[0]
          .trim();
        $("description").innerHTML = desc
          ? renderMarkdown(desc)
          : "<p>No description supplied.</p>";
        $("methodPill").textContent = method.toUpperCase();
        $("methodPill").className = `method-pill ${method}`;
        $("pathTitle").textContent = path;
        renderFields(op);
        $("responses").innerHTML = Object.entries(op.responses || {})
          .map(([code, r]) => {
            const label = `${esc(code)} · ${esc(r.description || "Response")}`;
            const schema = responseSchema(r);
            if (!schema) return `<span class="response-code">${label}</span>`;
            const name = resolveSchema(schema).title || "Response";
            return (
              `<details class="response-code"><summary>${label}</summary>` +
              `<pre class="schema">${esc(name)} ${esc(schemaTree(schema))}</pre></details>`
            );
          })
          .join("");
        const auth = needsAuth(op);
        $("authWrap").hidden = !auth;
        $("noAuth").hidden = auth;
        $("explanation").innerHTML = renderMarkdown(
          markdownFor(path, method, op),
        );
        const example = requestExample(op);
        $("body").value =
          example === null ? "" : JSON.stringify(example, null, 2);
        $("body").disabled = !requestSchema(op);
        renderQuery(op);
        $("output").className = "output";
        $("output").textContent = "Ready to send.";
      }
      async function load(showToast = false) {
        const reload = $("reloadBtn");
        reload.disabled = true;
        reload.classList.add("is-loading");
        try {
          const r = await fetch("/openapi.json", { cache: "no-store" });
          if (!r.ok) throw new Error("Specification unavailable");
          state.spec = await r.json();
          const orderOf = (p) => {
            const i = [
              "/authenticate",
              "/readme",
              "/health",
              "/metrics",
            ].indexOf(p);
            return i < 0 ? 99 : i;
          };
          const endpoints = [];
          for (const [path, methods] of Object.entries(state.spec.paths || {}))
            for (const [method, op] of Object.entries(methods))
              if (["get", "post", "put", "patch", "delete"].includes(method))
                endpoints.push({ path, method, op });
          endpoints.sort((a, b) => orderOf(a.path) - orderOf(b.path));
          $("endpoints").innerHTML = "";
          endpoints.forEach((e, i) => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "endpoint";
            b.innerHTML =
              `<span class="method ${e.method}">${e.method.toUpperCase()}</span>` +
              `<span class="path">${esc(e.path)}</span>`;
            b.onclick = () => selectEndpoint(e.path, e.method, e.op, b, i);
            $("endpoints").appendChild(b);
            if (i === Math.min(state.selectedIndex, endpoints.length - 1))
              b.click();
          });
          if (showToast) toast("API reloaded");
        } catch (e) {
          $("endpoints").innerHTML =
            '<div class="empty">Could not load the API specification.</div>';
          toast("Reload failed");
        } finally {
          reload.disabled = false;
          reload.classList.remove("is-loading");
        }
      }
      $("reloadBtn").onclick = () => load(true);
      $("sendBtn").onclick = async () => {
        if (!state.path) return;
        const btn = $("sendBtn"),
          out = $("output");
        btn.disabled = true;
        btn.textContent = "Sending...";
        out.className = "output";
        out.textContent = "Waiting for response...";
        try {
          const url = new URL(state.path, location.origin);
          document.querySelectorAll("[data-query]").forEach((el) => {
            if (el.value) url.searchParams.set(el.dataset.query, el.value);
          });
          const headers = {};
          if (needsAuth(state.operation) && $("auth").value)
            headers.Authorization = `Bearer ${$("auth").value}`;
          const opts = { method: state.method.toUpperCase(), headers };
          if (
            !["GET", "HEAD"].includes(opts.method) &&
            $("body").value.trim()
          ) {
            headers["Content-Type"] = "application/json";
            JSON.parse($("body").value);
            opts.body = $("body").value;
          }
          const started = performance.now();
          const r = await fetch(url, opts);
          const text = await r.text();
          let shown = text;
          try {
            shown = JSON.stringify(JSON.parse(text), null, 2);
          } catch {}
          out.textContent = `${r.status} ${r.statusText} · ${Math.round(performance.now() - started)}ms\n\n${shown}`;
        } catch (e) {
          out.className = "output error";
          out.textContent =
            e instanceof SyntaxError
              ? "Request body is not valid JSON."
              : String(e);
        } finally {
          btn.disabled = false;
          btn.textContent = "Send request";
        }
      };
      $("copyBtn").onclick = async () => {
        await navigator.clipboard.writeText($("output").textContent);
        toast("Response copied");
      };
      const grid = {
        c: $("dotGrid"),
        ctx: null,
        w: 0,
        h: 0,
        mx: -9999,
        my: -9999,
        active: false,
        frame: null,
        colors: {
          light: { dot: "rgba(0,0,0,0.08)", active: "rgba(0,0,0,0.16)" },
          dark: {
            dot: "rgba(255,255,255,0.06)",
            active: "rgba(255,255,255,0.12)",
          },
        },
        spacing: 22,
        baseRadius: 1,
        activeRadius: 2,
        radius: 140,
        minAlpha: 0.5,
        palette() {
          return this.colors[
            document.documentElement.dataset.theme === "dark" ? "dark" : "light"
          ];
        },
        resize() {
          const dpr = window.devicePixelRatio || 1;
          this.w = innerWidth;
          this.h = innerHeight;
          if (!this.w || !this.h) return;
          this.c.width = this.w * dpr;
          this.c.height = this.h * dpr;
          this.c.style.width = this.w + "px";
          this.c.style.height = this.h + "px";
          this.ctx = this.c.getContext("2d");
          this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          this.draw();
        },
        draw() {
          if (!this.ctx) return;
          const t = this.palette();
          this.ctx.clearRect(0, 0, this.w, this.h);
          const ox = (this.w % this.spacing) / 2,
            oy = (this.h % this.spacing) / 2;
          for (let x = ox; x <= this.w; x += this.spacing) {
            for (let y = oy; y <= this.h; y += this.spacing) {
              const dx = x - this.mx,
                dy = y - this.my,
                d = Math.sqrt(dx * dx + dy * dy);
              let r = this.baseRadius,
                color = t.dot,
                alpha = 1;
              if (this.active && d < this.radius) {
                const f = 1 - d / this.radius;
                r = this.baseRadius + (this.activeRadius - this.baseRadius) * f;
                color = t.active;
                alpha = this.minAlpha + (1 - this.minAlpha) * f;
              }
              this.ctx.globalAlpha = alpha;
              this.ctx.beginPath();
              this.ctx.arc(x, y, r, 0, Math.PI * 2);
              this.ctx.fillStyle = color;
              this.ctx.fill();
            }
          }
          this.ctx.globalAlpha = 1;
        },
        queue() {
          if (this.frame === null)
            this.frame = requestAnimationFrame(() => {
              this.frame = null;
              this.draw();
            });
        },
      };
      window.grid = grid;
      addEventListener("resize", () => grid.resize());
      addEventListener("mousemove", (e) => {
        grid.mx = e.clientX;
        grid.my = e.clientY;
        grid.active = true;
        grid.queue();
      });
      document.addEventListener("mouseleave", () => {
        grid.active = false;
        grid.queue();
      });
      grid.resize();
      load();
    </script>
  </body>
</html>"""
