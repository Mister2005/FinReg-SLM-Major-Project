// ==========================================================================
// FinReg-AI Client Application Logic
// ==========================================================================

let activeRegulator = "ALL";

document.addEventListener("DOMContentLoaded", () => {
  const queryForm = document.getElementById("queryForm");
  const userInput = document.getElementById("userInput");
  const asOfDateInput = document.getElementById("asOfDateInput");
  const chatContainer = document.getElementById("chatContainer");
  const clearChatBtn = document.getElementById("clearChatBtn");
  const regulatorPills = document.querySelectorAll("#regulatorFilters .pill");
  const sampleBtns = document.querySelectorAll(".sample-btn");
  
  const docDrawer = document.getElementById("docDrawer");
  const closeDrawerBtn = document.getElementById("closeDrawerBtn");

  // Filter selection
  regulatorPills.forEach(pill => {
    pill.addEventListener("click", () => {
      regulatorPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeRegulator = pill.getAttribute("data-reg");
    });
  });

  // Pre-built sample queries
  sampleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query");
      userInput.value = q;
      userInput.focus();
    });
  });

  // Clear chat
  clearChatBtn.addEventListener("click", () => {
    chatContainer.innerHTML = `
      <div class="welcome-card" id="welcomeCard">
        <div class="welcome-icon">⚡</div>
        <h3>Welcome to FinReg-AI</h3>
        <p>This system uses a specialized <strong>DeepSeek-R1-Distill-Qwen-7B</strong> model aligned with <strong>Direct Preference Optimization (DPO)</strong> to provide zero-hallucination, strictly cited Indian regulatory compliance analysis.</p>
        <div class="welcome-features">
          <div class="feat-box">
            <span class="feat-icon">📌</span>
            <strong>Exact Citations</strong>
            <span>Every claim cited with <code>[doc_id / provision]</code></span>
          </div>
          <div class="feat-box">
            <span class="feat-icon">⏳</span>
            <strong>Temporal Pre-Filtering</strong>
            <span>Filters out amended or repealed rules as of date</span>
          </div>
          <div class="feat-box">
            <span class="feat-icon">🛡️</span>
            <strong>Calibrated Abstention</strong>
            <span>Explicitly refuses when context is insufficient</span>
          </div>
        </div>
      </div>
    `;
  });

  // Drawer handlers
  closeDrawerBtn.addEventListener("click", () => {
    docDrawer.classList.remove("open");
  });

  // Form submit
  queryForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    const asOfDate = asOfDateInput.value || "2026-06-01";
    userInput.value = "";

    // Remove welcome card if present
    const welcomeCard = document.getElementById("welcomeCard");
    if (welcomeCard) welcomeCard.remove();

    // 1. Append User Message
    appendUserMessage(query, asOfDate, activeRegulator);

    // 2. Append Loading AI Message
    const aiMsgId = "ai-msg-" + Date.now();
    appendLoadingMessage(aiMsgId);
    scrollToBottom();

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          as_of_date: asOfDate,
          regulator: activeRegulator,
          max_chunks: 4
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();
      renderAIResponse(aiMsgId, data);
    } catch (err) {
      console.error(err);
      renderErrorMessage(aiMsgId, err.message);
    }

    scrollToBottom();
  });
});

function appendUserMessage(text, asOfDate, reg) {
  const chat = document.getElementById("chatContainer");
  const row = document.createElement("div");
  row.className = "msg-row user-msg";
  row.innerHTML = `
    <div class="msg-avatar">U</div>
    <div class="msg-bubble">
      <div style="font-weight: 500;">${escapeHtml(text)}</div>
      <div class="msg-meta-bar" style="justify-content: flex-end;">
        <span class="msg-meta-item">📅 As-Of: ${asOfDate}</span>
        <span class="msg-meta-item">🏛️ ${reg}</span>
      </div>
    </div>
  `;
  chat.appendChild(row);
}

function appendLoadingMessage(msgId) {
  const chat = document.getElementById("chatContainer");
  const row = document.createElement("div");
  row.className = "msg-row ai-msg";
  row.id = msgId;
  row.innerHTML = `
    <div class="msg-avatar">⚖️</div>
    <div class="msg-bubble">
      <div style="display: flex; align-items: center; gap: 10px; color: var(--text-secondary);">
        <div class="status-dot pulse"></div>
        <span>Retrieving regulatory provisions & generating reasoning chain...</span>
      </div>
    </div>
  `;
  chat.appendChild(row);
}

function renderAIResponse(msgId, data) {
  const row = document.getElementById(msgId);
  if (!row) return;

  const bubble = row.querySelector(".msg-bubble");
  
  // Format citations into clickable pills
  let formattedAnswer = escapeHtml(data.answer);
  formattedAnswer = formattedAnswer.replace(/\[(.*?)\]/g, (match, p1) => {
    const trimmed = p1.trim();
    if (trimmed.includes('/') || trimmed.includes(':') || trimmed.toLowerCase().includes('para') || trimmed.toLowerCase().includes('section')) {
      const docIdMatch = trimmed.split('/')[0].trim();
      return `<span class="cit-pill" onclick="inspectDocument('${escapeHtml(docIdMatch)}')">📌 [${escapeHtml(trimmed)}]</span>`;
    }
    return match;
  });

  let reasoningHtml = "";
  if (data.reasoning) {
    reasoningHtml = `
      <div class="reasoning-box" id="reasoning-${msgId}">
        <div class="reasoning-header" onclick="toggleReasoning('reasoning-${msgId}')">
          <span class="reasoning-title">🧠 DeepSeek-R1 Reasoning Chain</span>
          <span class="reasoning-arrow">▼</span>
        </div>
        <div class="reasoning-content">${escapeHtml(data.reasoning)}</div>
      </div>
    `;
  }

  let abstentionBadge = "";
  if (data.is_abstained) {
    abstentionBadge = `<span style="background: rgba(244, 63, 94, 0.15); color: #f43f5e; font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 700; margin-left: 8px;">CALIBRATED ABSTENTION</span>`;
  }

  bubble.innerHTML = `
    ${reasoningHtml}
    <div class="answer-text" style="color: var(--text-primary);">
      ${formattedAnswer}
    </div>
    <div class="msg-meta-bar">
      <span class="msg-meta-item">⚡ Latency: ${data.latency_seconds}s</span>
      <span class="msg-meta-item">📑 Chunks: ${data.retrieved_chunks.length}</span>
      <span class="msg-meta-item">📌 Citations: ${data.citations.length}</span>
      ${abstentionBadge}
    </div>
  `;
}

function renderErrorMessage(msgId, errText) {
  const row = document.getElementById(msgId);
  if (!row) return;
  const bubble = row.querySelector(".msg-bubble");
  bubble.innerHTML = `
    <div style="color: var(--accent-rose);">
      <strong>Error:</strong> Failed to execute query: ${escapeHtml(errText)}
    </div>
  `;
}

function toggleReasoning(boxId) {
  const box = document.getElementById(boxId);
  if (box) {
    box.classList.toggle("open");
  }
}

async function inspectDocument(docId) {
  const drawer = document.getElementById("docDrawer");
  const drawerDocId = document.getElementById("drawerDocId");
  const drawerRegulator = document.getElementById("drawerRegulator");
  const drawerTitle = document.getElementById("drawerTitle");
  const drawerStatus = document.getElementById("drawerStatus");
  const drawerInForceFrom = document.getElementById("drawerInForceFrom");
  const drawerInForceTo = document.getElementById("drawerInForceTo");
  const drawerBody = document.getElementById("drawerBody");

  drawerDocId.innerText = docId;
  drawerRegulator.innerText = "SEARCHING";
  drawerTitle.innerText = "Loading circular metadata...";
  drawerStatus.innerText = "-";
  drawerInForceFrom.innerText = "-";
  drawerInForceTo.innerText = "-";
  drawerBody.innerText = "Querying SQLite manifest.db for circular text...";
  drawer.classList.add("open");

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}`);
    if (!res.ok) throw new Error(`Document '${docId}' not found in manifest database.`);
    const data = await res.json();

    drawerDocId.innerText = data.doc_id || docId;
    drawerRegulator.innerText = (data.regulator || "REGULATOR").toUpperCase();
    drawerTitle.innerText = data.title || "Untitled Circular";
    drawerStatus.innerText = (data.status || "active").toUpperCase();
    drawerInForceFrom.innerText = data.in_force_from || "2020-01-01";
    drawerInForceTo.innerText = data.in_force_to || "PRESENT";
    drawerBody.innerText = data.body || "No text content stored for this provision.";
  } catch (e) {
    drawerRegulator.innerText = "NOT FOUND";
    drawerTitle.innerText = "Provision Not In Corpus Database";
    drawerStatus.innerText = "UNAVAILABLE";
    drawerInForceFrom.innerText = "N/A";
    drawerInForceTo.innerText = "N/A";
    drawerBody.innerText = `⚠️ Document reference '${docId}' is not indexed in the local SQLite database.\n\nDetails: ${e.message}\n\nNote: In strict RAG systems, references must match real circulars stored in manifest.db.`;
  }
}

function scrollToBottom() {
  const chat = document.getElementById("chatContainer");
  chat.scrollTop = chat.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
