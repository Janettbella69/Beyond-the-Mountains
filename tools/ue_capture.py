#!/usr/bin/env python3
"""ue_capture.py — 抓整个编辑器窗口画面（含 PIE 视口与 UMG）存 PNG。

用法: ue_capture.py <out.png>
走 MCP EditorAppToolset.CaptureEditorImage，解 base64 图像内容落盘。
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_mcp import Client


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    out = sys.argv[1]
    tool = sys.argv[2] if len(sys.argv) > 2 else "CaptureEditorImage"  # or CaptureViewport
    cli = Client()
    cli.init()
    res = cli.rpc("tools/call", {"name": "call_tool", "arguments": {
        "toolset_name": "EditorToolset.EditorAppToolset",
        "tool_name": tool, "arguments": {}}})
    for c in res.get("content", []):
        if c.get("type") == "image" and c.get("data"):
            open(out, "wb").write(base64.b64decode(c["data"]))
            print(f"OK {out} ({os.path.getsize(out)} bytes, {c.get('mimeType')})")
            return 0
        if c.get("type") == "text":
            try:
                rv = json.loads(c["text"]).get("returnValue", {})
            except json.JSONDecodeError:
                continue
            if isinstance(rv, dict) and rv.get("data"):
                open(out, "wb").write(base64.b64decode(rv["data"]))
                print(f"OK {out} ({os.path.getsize(out)} bytes, {rv.get('mimeType')})")
                return 0
    print("no image content; isError:", res.get("isError"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
