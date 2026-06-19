/* =========================================================
   SupportMate AI – Frontend Logic
   ========================================================= */

const chatWindow   = document.getElementById('chatWindow');
const userInput    = document.getElementById('userInput');
const sendBtn      = document.getElementById('sendBtn');
const clearBtn     = document.getElementById('clearBtn');
const statusDot    = document.getElementById('statusDot');
const statusText   = document.getElementById('statusText');
const welcomeCard  = document.getElementById('welcomeCard');

let chatHistory = [];   // [{role, content}, ...]
let isStreaming = false;

// ── Chip suggestions ─────────────────────────────────────
document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        const msg = chip.dataset.msg;
        if (msg) sendMessage(msg);
    });
});

// ── Clear button ─────────────────────────────────────────
clearBtn.addEventListener('click', () => {
    chatHistory = [];
    // Remove all messages except welcome card
    const msgs = chatWindow.querySelectorAll('.message');
    msgs.forEach(m => m.remove());
    if (!welcomeCard.parentElement) chatWindow.prepend(welcomeCard);
    welcomeCard.style.display = '';
});

// ── Health check ─────────────────────────────────────────
async function checkHealth() {
    try {
        const res = await fetch('/health');
        const data = await res.json();
        if (data.status === 'ok' && data.api_key_configured) {
            setStatus('online', '🟢 Online · ' + (data.model || 'AI'));
        } else {
            setStatus('offline', '⚠️ API key missing');
        }
    } catch {
        setStatus('offline', '❌ Server offline');
    }
}

function setStatus(state, label) {
    statusDot.className = 'status-dot ' + state;
    statusText.textContent = label;
}

// ── Textarea auto-resize + send on Enter ─────────────────
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 140) + 'px';
    sendBtn.disabled = !userInput.value.trim() || isStreaming;
});

userInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) sendMessage(userInput.value.trim());
    }
});

sendBtn.addEventListener('click', () => {
    const text = userInput.value.trim();
    if (text && !isStreaming) sendMessage(text);
});

// ── Main send function ────────────────────────────────────
async function sendMessage(text) {
    if (isStreaming) return;

    // Hide welcome card on first message
    if (welcomeCard.style.display !== 'none') {
        welcomeCard.style.display = 'none';
    }

    // Append user bubble
    appendMessage('user', text);
    chatHistory.push({ role: 'user', content: text });

    // Clear input
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.disabled = true;
    isStreaming = true;

    // Show typing indicator
    const typingEl = appendTyping();

    // Create bot bubble (will fill with streamed tokens)
    let botBubble = null;
    let fullResponse = '';

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, history: chatHistory.slice(0, -1) }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
            removeEl(typingEl);
            appendMessage('bot', '⚠️ ' + (err.error || 'Request failed'), true);
            finishStreaming();
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line

            for (const line of lines) {
                if (!line.startsWith('data:')) continue;
                const raw = line.slice(5).trim();
                if (!raw) continue;

                try {
                    const evt = JSON.parse(raw);

                    if (evt.error) {
                        removeEl(typingEl);
                        appendMessage('bot', '⚠️ ' + evt.error, true);
                        finishStreaming();
                        return;
                    }

                    if (evt.token) {
                        if (!botBubble) {
                            removeEl(typingEl);
                            botBubble = appendMessage('bot', '', false, true);
                        }
                        fullResponse += evt.token;
                        botBubble.innerHTML = formatText(fullResponse);
                        scrollBottom();
                    }

                    if (evt.done) {
                        chatHistory.push({ role: 'assistant', content: fullResponse });
                        finishStreaming();
                        return;
                    }
                } catch { /* skip bad JSON */ }
            }
        }

        // Stream ended without [DONE]
        if (fullResponse) {
            chatHistory.push({ role: 'assistant', content: fullResponse });
        }
    } catch (err) {
        removeEl(typingEl);
        appendMessage('bot', '⚠️ Network error: ' + err.message, true);
    } finally {
        finishStreaming();
    }
}

// ── UI helpers ────────────────────────────────────────────
function appendMessage(role, text, isError = false, returnBubble = false) {
    const wrapper = document.createElement('div');
    wrapper.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = role === 'user' ? '🧑' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'bubble' + (isError ? ' error' : '');
    bubble.innerHTML = text ? formatText(text) : '';

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    chatWindow.appendChild(wrapper);
    scrollBottom();

    if (returnBubble) return bubble;
}

function appendTyping() {
    const wrapper = document.createElement('div');
    wrapper.className = 'message bot';
    wrapper.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const typing = document.createElement('div');
    typing.className = 'typing-indicator';
    typing.innerHTML = '<span></span><span></span><span></span>';

    bubble.appendChild(typing);
    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    chatWindow.appendChild(wrapper);
    scrollBottom();
    return wrapper;
}

function removeEl(el) {
    if (el && el.parentElement) el.parentElement.removeChild(el);
}

function scrollBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function finishStreaming() {
    isStreaming = false;
    sendBtn.disabled = !userInput.value.trim();
    sendBtn.classList.remove('loading');
}

// ── Basic text formatter (bold, code, newlines) ───────────
function formatText(text) {
    // Escape HTML first
    let escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Code blocks ```...```
    escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    // Inline code `...`
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold **...**
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic *...*
    escaped = escaped.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Newlines
    escaped = escaped.replace(/\n/g, '<br>');

    return escaped;
}

// ── Init ──────────────────────────────────────────────────
checkHealth();
userInput.focus();
