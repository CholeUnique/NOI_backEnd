import os
import json

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()

    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")

    if not base_url or not api_key or not model:
        raise RuntimeError("缺少 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 环境变量")

    client = OpenAI(api_key=api_key, base_url=base_url)

    tool = {
        "type": "function",
        "function": {
            "name": "writing_assist",
            "description": "提供科研写作辅助，包括模板、润色和检查",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["template", "polish", "generate", "check"],
                    },
                    "section": {"type": "string"},
                    "content": {"type": "string"},
                    "context": {"type": "string"},
                    "style": {"type": "string", "enum": ["academic", "formal", "casual"]},
                },
                "required": ["action"],
            },
        },
    }

    prompt = '请调用 writing_assist，action=polish，content="hello"。不要直接回答。'
    messages = [{"role": "user", "content": prompt}]

    cases = [
        ("auto", "auto"),
        ("forced", {"type": "function", "function": {"name": "writing_assist"}}),
    ]

    for name, tool_choice in cases:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[tool],
            tool_choice=tool_choice,
            temperature=0,
            stream=True,
        )

        saw_tool_calls = False
        saw_content = False
        tool_calls_count = 0

        for i, chunk in enumerate(stream):
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            content = getattr(delta, "content", None)
            tool_calls = getattr(delta, "tool_calls", None)

            if content:
                saw_content = True
            if tool_calls:
                saw_tool_calls = True
                try:
                    tool_calls_count += len(tool_calls)
                except Exception:
                    tool_calls_count += 1

            if i >= 80:
                break

        print(
            json.dumps(
                {
                    "case": name,
                    "saw_content": saw_content,
                    "saw_tool_calls": saw_tool_calls,
                    "tool_calls_count_est": tool_calls_count,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()

