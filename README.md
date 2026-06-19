# ⚙️ DevOpsGPT — AI DevOps Assistant

A modern, dark-themed, streaming chatbot for DevOps engineers. Built with **Python 3.12 + Flask + OpenAI**, vanilla **HTML/CSS/JS** on the frontend.

Get fast, practical answers about **Linux, Docker, Kubernetes, Jenkins, Git, GitHub Actions, Terraform, AWS, Azure, CI/CD, monitoring,** and **troubleshooting**.

---

## ✨ Features

- 🌙 Modern dark theme, mobile responsive
- 💬 Streaming chat (Server-Sent Events)
- 🧠 Last-5-messages context window (token-efficient)
- 💾 LocalStorage chat history persistence
- 🗑️ Clear chat button
- 📋 Copy response button
- 🎨 Markdown rendering + syntax highlighting (highlight.js)
- ⏳ Loading / typing indicator
- 🛡️ DOMPurify XSS protection
- ❤️ `/health` endpoint
- 🔐 `.env` based configuration

---

## 🗂️ Project structure

```
devops-gpt/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

---

## 🚀 Quick start

### 1. Clone & enter the project
```bash
git clone <your-repo-url> devops-gpt
cd devops-gpt
```

### 2. Create a virtual environment (Python 3.12)
```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 5. Run (development)
```bash
python app.py
```

Open <http://localhost:5000>.

### 6. Run (production)
```bash
gunicorn -w 2 -k gthread --threads 8 -b 0.0.0.0:5000 app:app
```

> Streaming requires a worker that supports request streaming. `gthread` works well; for `gunicorn` + nginx, disable proxy buffering (`proxy_buffering off;`).

---

## 🔧 Configuration (.env)

| Variable             | Default        | Purpose                                  |
| -------------------- | -------------- | ---------------------------------------- |
| `OPENAI_API_KEY`     | _(required)_   | Your OpenAI API key                      |
| `OPENAI_MODEL`       | `gpt-4.1-mini` | Chat model                               |
| `OPENAI_TEMPERATURE` | `0.2`          | Response randomness                      |
| `OPENAI_MAX_TOKENS`  | `400`          | Max tokens in a single answer            |
| `MAX_HISTORY`        | `5`            | Last N messages sent to the model        |
| `FLASK_ENV`          | `production`   | `development` enables debug mode         |
| `HOST`               | `0.0.0.0`      | Bind host                                |
| `PORT`               | `5000`         | Bind port                                |

---

## 🔌 API

### `POST /api/chat`
Streams the response as Server-Sent Events.

**Request body**
```json
{
  "message": "How do I list all pods in a namespace?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**Stream events**
```
data: {"token": "kubectl"}
data: {"token": " get"}
data: {"token": " pods"}
data: {"done": true}
```

### `GET /health`
```json
{
  "status": "ok",
  "model": "gpt-4.1-mini",
  "api_key_configured": true
}
```

---

## 🛡️ Security notes

- API key is loaded from `.env` and **never exposed** to the browser.
- Input is length-limited (4 KB) and JSON-validated.
- Request body capped at 1 MB.
- All rendered Markdown is sanitized with **DOMPurify** to prevent XSS.
- Run behind HTTPS in production (nginx / Caddy / Cloudflare).

---

## 🐳 Docker (optional)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-k", "gthread", "--threads", "8", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t devops-gpt .
docker run -p 5000:5000 --env-file .env devops-gpt
```

---

## 📜 License

MIT — use it, fork it, ship it. 🚀
