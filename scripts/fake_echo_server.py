# Fake echo WebSocket server for the throwaway Flutter spike (Part 14.1: "Weeks
# 3-4: Throwaway Flutter spike ... Connects to fake echo WebSocket server ...
# Renders streamed tokens in Dart ... Tests async stream handling ... DISCARDED
# after - de-risks Dart before Phase 8").
#
# Deliberately NOT the real backend - no pipeline, no DB, no LLM. It exists so
# the Dart client can be exercised against the real Part 14.3 wire shape
# (stage_hint -> token* -> done, or -> error) without needing the whole PIP
# backend running. Splits the echoed message into words and streams them back
# one at a time with a small delay, so the Flutter side actually has to handle
# tokens arriving asynchronously over time - a fixed single "here's your whole
# reply" frame would not exercise the thing this spike exists to de-risk.
#
# Standalone script, not part of the pytest suite or the real backend - run
# directly: python scripts/fake_echo_server.py [--port 8766]

import argparse
import asyncio
import json

import websockets


async def handle_connection(websocket):
    async for raw in websocket:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send(json.dumps({"type": "error", "data": "invalid JSON"}))
            continue

        message = (data or {}).get("message", "")
        if not message:
            await websocket.send(json.dumps({"type": "error", "data": "message is required"}))
            continue

        await websocket.send(json.dumps({
            "type": "stage_hint",
            "data": {
                "decision_log_hit": False,
                "web_search_used": False,
                "cache_hit": False,
                "model_loading": False,
            },
        }))

        for word in message.split():
            await websocket.send(json.dumps({"type": "token", "data": word + " "}))
            await asyncio.sleep(0.15)

        await websocket.send(json.dumps({"type": "done", "data": None}))


async def main(port: int) -> None:
    async with websockets.serve(handle_connection, "127.0.0.1", port):
        print(f"Fake echo WS server listening on ws://127.0.0.1:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    asyncio.run(main(args.port))
