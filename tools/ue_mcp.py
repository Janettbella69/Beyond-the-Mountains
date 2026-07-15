#!/usr/bin/env python3
"""ue_mcp.py — 极简 raw-HTTP 客户端，驱动 UE5.8 内置 MCP server（streamable HTTP）。

为什么存在：让任意 shell（含 Claude Code 会话）不依赖 MCP 客户端配置就能驱动编辑器。
只走小结果；大载荷（截图等）让编辑器直接落盘（HighResShot / take_high_res_screenshot），
不要经 MCP 传 base64（raw HTTP 对大结果会丢，见 unreal-agent-harness BUILD-LOG §3）。

用法:
  ue_mcp.py toolsets                       # 列出所有 toolset
  ue_mcp.py describe <toolset>             # 看某 toolset 的工具与参数
  ue_mcp.py call <toolset> <tool> ['<json-args>']   # 调工具
  ue_mcp.py py '<python 代码>'             # 在编辑器内跑 Python（PythonToolset 快捷方式）
  ue_mcp.py pyfile <path>                  # 同上，代码从文件读
环境变量: UE_MCP_URL (默认 http://127.0.0.1:8002/mcp), UE_MCP_TIMEOUT (默认 180s)
退出码: 0 成功；1 工具报错(isError)；2 连接/协议失败
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("UE_MCP_URL", "http://127.0.0.1:8002/mcp")
TIMEOUT = float(os.environ.get("UE_MCP_TIMEOUT", "180"))


class Client:
    def __init__(self):
        self.sid = None
        self._id = 0

    def _post(self, payload, want_headers=False):
        req = urllib.request.Request(
            URL,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        if self.sid:
            req.add_header("Mcp-Session-Id", self.sid)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        body = resp.read().decode("utf-8", "replace")
        # 兼容 SSE 帧（data: 行）与纯 JSON 两种响应
        if body.startswith("event:") or body.startswith("data:") or "\ndata:" in body:
            datas = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
            if datas:
                body = datas[-1]
        return (body, dict(resp.headers)) if want_headers else body

    def init(self):
        body, headers = self._post(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "ue_mcp.py", "version": "1.0"},
                },
            },
            want_headers=True,
        )
        for k, v in headers.items():
            if k.lower() == "mcp-session-id":
                self.sid = v
        json.loads(body)  # 握手响应必须是合法 JSON
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def rpc(self, method, params):
        self._id += 1
        body = self._post(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        )
        msg = json.loads(body)
        if "error" in msg:
            raise RuntimeError(f"jsonrpc error: {msg['error']}")
        return msg["result"]

    def tool(self, name, arguments):
        """调顶层工具，返回 (text, is_error)。"""
        res = self.rpc("tools/call", {"name": name, "arguments": arguments})
        parts = []
        for c in res.get("content", []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            else:
                parts.append(f"[{c.get('type')} content]")
        return "\n".join(parts), bool(res.get("isError"))


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    cli = Client()
    try:
        cli.init()
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"[ue_mcp] cannot reach MCP server at {URL}: {e}", file=sys.stderr)
        print("[ue_mcp] editor 没开或 server 没启？编辑器控制台: ModelContextProtocol.StartServer 8002", file=sys.stderr)
        return 2

    if cmd == "toolsets":
        text, err = cli.tool("list_toolsets", {})
    elif cmd == "describe" and len(argv) >= 3:
        text, err = cli.tool("describe_toolset", {"toolset_name": argv[2]})
    elif cmd == "call" and len(argv) >= 4:
        args = json.loads(argv[4]) if len(argv) >= 5 else {}
        text, err = cli.tool(
            "call_tool",
            {"toolset_name": argv[2], "tool_name": argv[3], "arguments": args},
        )
    elif cmd in ("py", "pyfile") and len(argv) >= 3:
        code = open(argv[2]).read() if cmd == "pyfile" else argv[2]
        # PythonToolset 的工具名在不同版本可能叫 execute_python / run_python —
        # 先试常见名，失败再让调用方 describe PythonToolset 自查
        last = None
        for ts, tn, key in (
            ("PythonToolset", "execute_python", "code"),
            ("PythonToolset", "run_python", "code"),
            ("PythonToolset", "execute", "code"),
        ):
            try:
                text, err = cli.tool(
                    "call_tool",
                    {"toolset_name": ts, "tool_name": tn, "arguments": {key: code}},
                )
                if not err or "Unknown tool" not in text:
                    break
            except RuntimeError as e:
                last = e
                continue
        else:
            print(f"[ue_mcp] python 工具名探测失败: {last}", file=sys.stderr)
            return 2
    else:
        print(__doc__)
        return 1

    print(text)
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
