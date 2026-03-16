import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.session.loop import SessionLoop, SessionConfig


async def main() -> None:
    load_dotenv()
    loop = SessionLoop(session_id="test", user_id=1, config=SessionConfig(max_iterations=2))
    await loop.initialize()
    loop.set_system_prompt("你是助手。需要时调用工具。")
    async for ev in loop.run_stream("你好，给我一句话建议"):
        d = ev.data or {}
        if ev.type in {
            "agent_progress",
            "llm_chunk",
            "llm_response",
            "tool_call",
            "tool_executing",
            "tool_result",
            "doom_loop_detected",
            "iteration_limit_reached",
            "tool_limit_reached",
            "session_complete",
            "error",
        }:
            print(ev.type, "thinking" in d, "reasoning" in d)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
