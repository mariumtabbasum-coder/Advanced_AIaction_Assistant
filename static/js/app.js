const $ = (s) => document.querySelector(s);
const KEY = "actionai_chat_v1";

let state = load();
let controller = null;

function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function newSession(id) { return { id, title: "New chat", system: "", messages: [] }; }
function load() {
  try { const s = JSON.parse(localStorage.getItem(KEY)); if (s && s.sessions && s.sessions.length) return s; } catch (e) {}
  const id = uid();
  return { activeId: id, sessions: [newSession(id)] };
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function active() { return state.sessions.find((s) => s.id === state.activeId) || state.sessions[0]; }

function esc(t) { return t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function renderMarkdown(text) {
  if (window.marked && window.DOMPurify) {
    const html = DOMPurify.sanitize(marked.parse(text, { breaks: true }));
    const d = document.createElement("div"); d.innerHTML = html;
    d.querySelectorAll("a").forEach((a) => { a.target = "_blank"; a.rel = "noopener noreferrer"; });
    return d.innerHTML;
  }
  return esc(text).replace(/\n/g, "<br>");
}

/* ---------- Sidebar / history ---------- */
function renderHistory() {
  const ul = $("#history"); ul.innerHTML = "";
  const list = state.sessions.filter((s) => s.messages.length);
  if (!list.length) { ul.innerHTML = '<li class="empty">No conversations yet</li>'; return; }
  list.forEach((s) => {
    const li = document.createElement("li");
    if (s.id === state.activeId) li.className = "active";
    li.innerHTML = '<span></span><button class="del" aria-label="Delete chat">✕</button>';
    li.querySelector("span").textContent = s.title;
    li.onclick = () => { if (controller) return; state.activeId = s.id; save(); renderAll(); closeSide(); };
    li.querySelector(".del").onclick = (e) => { e.stopPropagation(); if (!controller) deleteSession(s.id); };
    ul.appendChild(li);
  });
}
function deleteSession(id) {
  state.sessions = state.sessions.filter((s) => s.id !== id);
  if (!state.sessions.length) state.sessions.push(newSession(uid()));
  if (!state.sessions.some((s) => s.id === state.activeId)) state.activeId = state.sessions[0].id;
  save(); renderAll();
}
function newChat() {
  if (controller) controller.abort();
  const cur = active();
  if (cur && !cur.messages.length) { renderAll(); closeSide(); $("#input").focus(); return; } // reuse empty chat
  const id = uid();
  state.sessions.unshift(newSession(id)); state.activeId = id;
  save(); renderAll(); closeSide(); $("#input").focus();
}
function openSide() { document.body.classList.add("side-open"); }
function closeSide() { document.body.classList.remove("side-open"); }

/* ---------- Messages ---------- */
function chipsHTML(tools) {
  return (tools || []).map((t) => `<span class="tool-chip ${t.status}">${esc(t.label)}${t.status === "fail" ? " – failed" : ""}</span>`).join("");
}
function buildRow(role, content, tools) {
  const row = document.createElement("div");
  row.className = "row " + role;
  const avatar = role === "user" ? "You" : "✦";
  row.innerHTML = `<div class="avatar">${avatar}</div><div class="body"></div>`;
  const body = row.querySelector(".body");
  if (role === "assistant") {
    const chips = document.createElement("div"); chips.className = "tool-chips"; chips.innerHTML = chipsHTML(tools);
    if (!tools || !tools.length) chips.hidden = true;
    const bubble = document.createElement("div"); bubble.className = "bubble";
    bubble.innerHTML = content ? renderMarkdown(content) : typingHTML();
    const actions = document.createElement("div"); actions.className = "actions";
    actions.innerHTML = '<button class="act copy">Copy</button>';
    actions.hidden = !content;
    body.append(chips, bubble, actions);
  } else {
    const bubble = document.createElement("div"); bubble.className = "bubble"; bubble.textContent = content;
    body.append(bubble);
  }
  return row;
}
function typingHTML(label = "ActionAI is thinking…") {
  return `<span class="typing"><i></i><i></i><i></i><span class="typing-label">${label}</span></span>`;
}
function renderMessages() {
  const box = $("#messages"); box.innerHTML = "";
  const s = active();
  $("#welcome").hidden = s.messages.length > 0;
  s.messages.forEach((m) => box.appendChild(buildRow(m.role, m.content, m.tools)));
  markLatest();
  scrollDown(true);
}
function markLatest() {
  document.querySelectorAll(".row.latest").forEach((r) => r.classList.remove("latest"));
  const rows = document.querySelectorAll(".row.assistant");
  if (rows.length) rows[rows.length - 1].classList.add("latest");
}
function scrollDown(force) {
  const sc = $("#scroll");
  const near = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 160;
  if (force || near) sc.scrollTop = sc.scrollHeight;
}
function renderAll() { renderHistory(); renderMessages(); hideError(); }

function showError(msg) { const e = $("#errorBox"); e.textContent = msg; e.hidden = false; }
function hideError() { $("#errorBox").hidden = true; }

function setBusy(busy) {
  $("#sendBtn").hidden = busy;
  $("#stopBtn").hidden = !busy;
  $("#input").disabled = busy;
  if (!busy) $("#input").focus();
}
function autoGrow() { const t = $("#input"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 140) + "px"; }

/* ---------- Send ---------- */
async function send() {
  const input = $("#input");
  const text = input.value.trim();
  if (!text || controller) return;
  const s = active();
  hideError();
  s.messages.push({ role: "user", content: text });
  if (s.messages.length === 1) s.title = text.slice(0, 42);
  input.value = ""; autoGrow();
  save(); renderHistory();
  $("#welcome").hidden = true;
  $("#messages").appendChild(buildRow("user", text));

  const row = buildRow("assistant", "", []);
  $("#messages").appendChild(row);
  markLatest(); scrollDown(true);
  const chipsEl = row.querySelector(".tool-chips");
  const bubble = row.querySelector(".bubble");
  const actions = row.querySelector(".actions");

  let reply = ""; let tools = [];
  controller = new AbortController();
  const myController = controller;
  setBusy(true);

  const payload = s.messages.map((m) => ({ role: m.role, content: m.content }));
  try {
    const res = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system: s.system, messages: payload }), signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Server error (" + res.status + ").");
    }
    const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n"); buf = lines.pop();
      for (const ln of lines) {
        if (!ln.trim()) continue;
        const d = JSON.parse(ln);
        if (d.error) throw new Error(d.error);
        if (d.reset) { reply = ""; tools = []; chipsEl.hidden = true; chipsEl.innerHTML = ""; bubble.innerHTML = typingHTML(); continue; }
        if (d.tool_start) {
          tools.push({ name: d.tool_start, label: d.label, status: "run" });
          chipsEl.hidden = false; chipsEl.innerHTML = chipsHTML(tools);
          if (!reply) bubble.innerHTML = typingHTML("Using " + d.label + "…");
        } else if (d.tool_done) {
          const t = [...tools].reverse().find((x) => x.name === d.tool_done && x.status === "run");
          if (t) t.status = d.ok ? "ok" : "fail";
          chipsEl.innerHTML = chipsHTML(tools);
          if (!reply) bubble.innerHTML = typingHTML("Preparing the answer…");
        } else if (d.text) {
          reply += d.text; bubble.innerHTML = renderMarkdown(reply);
        }
        scrollDown();
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      showError(err.message || "Network error. Check your connection and try again.");
      if (reply) { reply += "\n\n*(reply interrupted)*"; bubble.innerHTML = renderMarkdown(reply); }
    }
  } finally {
    const stillHere = state.sessions.includes(s);
    tools.forEach((t) => { if (t.status === "run") t.status = "fail"; });
    if (stillHere) {
      if (reply) {
        s.messages.push({ role: "assistant", content: reply, tools });
      } else {
        // failed/stopped before any reply: undo the question so a retry does not duplicate it
        if (s.messages.at(-1)?.role === "user") s.messages.pop();
        if (state.activeId === s.id) input.value = text;
        if (!s.messages.length) s.title = "New chat";
      }
    }
    if (controller === myController) controller = null;
    setBusy(false); save(); renderAll(); autoGrow();
  }
}

/* ---------- Events ---------- */
$("#chatForm").addEventListener("submit", (e) => { e.preventDefault(); send(); });
$("#input").addEventListener("input", autoGrow);
$("#input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
$("#stopBtn").onclick = () => controller && controller.abort();
$("#newChat").onclick = newChat;
$("#newChatTop").onclick = newChat;
$("#openSide").onclick = openSide;
$("#closeSide").onclick = closeSide;
$("#overlay").onclick = closeSide;

$("#messages").addEventListener("click", async (e) => {
  const btn = e.target.closest(".copy"); if (!btn) return;
  const text = btn.closest(".body").querySelector(".bubble").innerText;
  try { await navigator.clipboard.writeText(text); }
  catch (_) { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
  btn.textContent = "Copied ✓"; setTimeout(() => (btn.textContent = "Copy"), 1500);
});

$("#openSettings").onclick = () => { $("#systemInput").value = active().system || ""; $("#settingsModal").hidden = false; closeSide(); };
$("#closeSettings").onclick = () => ($("#settingsModal").hidden = true);
$("#saveSettings").onclick = () => { active().system = $("#systemInput").value.trim(); save(); $("#settingsModal").hidden = true; };
$("#settingsModal").addEventListener("click", (e) => { if (e.target.id === "settingsModal") e.target.hidden = true; });
$("#clearAll").onclick = () => {
  if (!confirm("Delete all chats? This cannot be undone.")) return;
  if (controller) controller.abort();
  const id = uid(); state = { activeId: id, sessions: [newSession(id)] };
  save(); $("#settingsModal").hidden = true; renderAll();
};
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeSide(); $("#settingsModal").hidden = true; } });

renderAll();
