from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
from datetime import datetime

app = FastAPI(title="LAN Chat")

clients = []
history = []


def now_str():
    return datetime.now().strftime("%H:%M:%S")


HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
  <title>LAN Chat</title>
  <style>
    * {
      box-sizing: border-box;
    }

    html, body {
      margin: 0;
      padding: 0;
      height: 100%;
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }

    body {
      display: flex;
      flex-direction: column;
      min-height: 100dvh;
    }

    header {
      padding: 14px 16px;
      background: #111827;
      border-bottom: 1px solid #334155;
      font-size: 18px;
      font-weight: bold;
      position: sticky;
      top: 0;
      z-index: 10;
    }

    #chat {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
      padding-bottom: 90px;
    }

    .msg {
      background: #1e293b;
      padding: 10px 12px;
      border-radius: 14px;
      margin-bottom: 10px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .meta {
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 6px;
    }

    #status {
      font-size: 12px;
      color: #94a3b8;
      padding: 8px 12px 0;
    }

    form {
      position: sticky;
      bottom: 0;
      display: flex;
      gap: 8px;
      padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
      border-top: 1px solid #334155;
      background: #111827;
    }

    input, button {
      min-height: 48px;
      border-radius: 12px;
      border: none;
      font-size: 16px;
    }

    #text {
      flex: 1;
      background: #1e293b;
      color: white;
      padding: 0 14px;
      outline: none;
    }

    button {
      background: #2563eb;
      color: white;
      cursor: pointer;
      padding: 0 16px;
      font-weight: 600;
      flex-shrink: 0;
    }

    button:hover {
      background: #1d4ed8;
    }

    @media (max-width: 640px) {
      header {
        font-size: 16px;
      }

      #chat {
        padding: 10px;
      }

      form {
        gap: 6px;
        padding: 8px 10px calc(8px + env(safe-area-inset-bottom));
      }

      button {
        min-width: 92px;
      }
    }
  </style>
</head>
<body>
  <header>Локальная общалка</header>
  <div id="chat"></div>
  <div id="status"></div>

  <form id="form">
    <input id="text" autocomplete="off" placeholder="Введите сообщение..." />
    <button type="submit">Отправить</button>
  </form>

  <script>
    const username = prompt("Ваше имя:", "Пользователь") || "Пользователь";
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/ws?username=${encodeURIComponent(username)}`);

    const chat = document.getElementById("chat");
    const form = document.getElementById("form");
    const text = document.getElementById("text");
    const status = document.getElementById("status");

    function addMessage(item) {
      const div = document.createElement("div");
      div.className = "msg";

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${item.time} • ${item.username}`;

      const body = document.createElement("div");
      body.textContent = item.text;

      div.appendChild(meta);
      div.appendChild(body);
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    ws.onopen = () => {
      status.textContent = "Подключено";
    };

    ws.onclose = () => {
      status.textContent = "Соединение потеряно";
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "history") {
        chat.innerHTML = "";
        data.items.forEach(addMessage);
      } else if (data.type === "message") {
        addMessage(data.item);
      } else if (data.type === "system") {
        addMessage({
          username: "Система",
          text: data.text,
          time: data.time
        });
      }
    };

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const value = text.value.trim();
      if (!value) return;

      ws.send(JSON.stringify({ text: value }));
      text.value = "";
      text.focus();
    });
  </script>
</body>
</html>
"""


@app.get("/")
async def home():
    return HTMLResponse(HTML)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    username = websocket.query_params.get("username", "Пользователь")
    await websocket.accept()
    clients.append(websocket)

    await websocket.send_text(json.dumps({
        "type": "history",
        "items": history[-100:]
    }, ensure_ascii=False))

    join_text = {
        "type": "system",
        "text": f"{username} вошёл в чат",
        "time": now_str()
    }

    for client in clients[:]:
        try:
            await client.send_text(json.dumps(join_text, ensure_ascii=False))
        except Exception:
            if client in clients:
                clients.remove(client)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            item = {
                "username": username,
                "text": payload.get("text", ""),
                "time": now_str()
            }

            history.append(item)
            history[:] = history[-200:]

            message = {
                "type": "message",
                "item": item
            }

            for client in clients[:]:
                try:
                    await client.send_text(json.dumps(message, ensure_ascii=False))
                except Exception:
                    if client in clients:
                        clients.remove(client)

    except WebSocketDisconnect:
        if websocket in clients:
            clients.remove(websocket)

        leave_text = {
            "type": "system",
            "text": f"{username} вышел из чата",
            "time": now_str()
        }

        for client in clients[:]:
            try:
                await client.send_text(json.dumps(leave_text, ensure_ascii=False))
            except Exception:
                if client in clients:
                    clients.remove(client)
