import json
import uuid

import httpx


def _register_and_login(base: str) -> str:
    username = f"rtuser_{uuid.uuid4().hex[:8]}"
    password = "rtpassword123!"
    email = f"{username}@example.com"

    try:
        httpx.post(
            f"{base}/api/auth/register",
            json={"username": username, "email": email, "password": password},
            timeout=10.0,
        )
    except Exception:
        pass

    r = httpx.post(
        f"{base}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10.0,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("登录失败：未返回 access_token")
    return token


def _create_session(base: str, token: str) -> str:
    r = httpx.post(
        f"{base}/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "rt-sse-test"},
        timeout=30.0,
    )
    r.raise_for_status()
    session_id = r.json().get("data", {}).get("session_id")
    if not session_id:
        raise RuntimeError("创建会话失败：未返回 session_id")
    return session_id


def main() -> None:
    base = "http://127.0.0.1:8000"
    token = _register_and_login(base)
    session_id = _create_session(base, token)

    big = "A" * 6000
    question = (
        "请务必调用 writing_assist 工具，action=polish，并把 content 设置为下面这段文本。"
        "不要跳过工具，先调用工具再回答。"
        f"文本开始：{big} 文本结束。"
        "工具返回后，请用200字总结你做了哪些改动。"
    )

    body = {
        "question": question,
        "session_id": session_id,
        "stream": True,
        "enable_tools": True,
        "enable_context_injection": True,
        "max_iterations": 5,
        "temperature": 0.2,
    }

    print(json.dumps({"session_id": session_id}, ensure_ascii=False))

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
    }

    with httpx.Client(timeout=None) as client:
        with client.stream("POST", f"{base}/api/v1/session/chat", headers=headers, json=body) as resp:
            print("http_status=", resp.status_code)
            resp.raise_for_status()

            seen = 0
            for line in resp.iter_lines():
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue

                payload = line[6:]
                evt = json.loads(payload)
                typ = evt.get("type")

                if typ == "tool_result":
                    d = evt.get("data", {}) or {}
                    out = d.get("result")
                    out_len = len(json.dumps(out, ensure_ascii=False)) if out is not None else 0
                    print(
                        "event=tool_result",
                        "success=",
                        d.get("success"),
                        "tool_id=",
                        d.get("tool_id"),
                        "result_chars=",
                        out_len,
                    )
                else:
                    print("event=", typ)

                seen += 1
                if typ in ("stream_complete", "error") or seen > 400:
                    break


if __name__ == "__main__":
    main()

