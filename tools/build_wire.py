#!/usr/bin/env python3
"""build_wire.py — 增量1：把 4 个按钮 OnClicked 事件节点连到对应函数调用。

BindToEventProperty 只造事件节点不带身体；本脚本 find_nodes 定位事件 →
create_node 造 CallFunction → connect_pins 连 exec。随后清孤儿探针节点、编译、存盘。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_mcp import Client

WBP = "/Game/PL/UI/WBP_VN"
BP_REF = {"refPath": WBP + ".WBP_VN"}
EG = {"refPath": WBP + ".WBP_VN:EventGraph"}
BT = "editor_toolset.toolsets.blueprint.BlueprintTools"
AT = "editor_toolset.toolsets.asset.AssetTools"

cli = Client()
cli.init()


def call(tool, args, ok_fail=False):
    text, err = cli.tool("call_tool", {"toolset_name": BT, "tool_name": tool, "arguments": args})
    if err and not ok_fail:
        raise SystemExit(f"FAIL {tool}: {text[:900]}")
    try:
        return json.loads(text), err
    except json.JSONDecodeError:
        return text, err


def node_infos(refs):
    r, _ = call("get_node_infos", {"nodes": [{"refPath": x} for x in refs]})
    return r["returnValue"]


# ---------- 1) 定位 4 个事件节点（入口节点里的 ComponentBoundEvent） ----------
r, _ = call("find_nodes", {"graph": EG, "title": "", "entry_points_only": True})
ev_refs = sorted({o["refPath"] for o in r["returnValue"]
                  if isinstance(o, dict) and "ComponentBoundEvent" in o.get("refPath", "")})
print("event nodes:", ev_refs)

infos = node_infos(ev_refs)
print("titles:", [(i.get("title"), i.get("node", {}).get("refPath", "?")) for i in infos] if isinstance(infos, list) else json.dumps(infos)[:500])

MAP = {"AdvanceCatcher": "Advance", "ChoiceBtnA": "PickA", "ChoiceBtnB": "PickB", "ChoiceBtnC": "PickC"}


def exec_out_pin(info):
    for p in info.get("output_pins", []):
        if p.get("type_id") == "Exec":
            return p["pin_id"]
    return None


def exec_in_pin(info):
    for p in info.get("input_pins", []):
        if p.get("type_id") == "Exec":
            return p["pin_id"]
    return None


wired = 0
if isinstance(infos, list):
    for info in infos:
        title = info.get("type_id", "")  # 形如 AddEvent|OnClicked(AdvanceCatcher)
        ref = info.get("node", {}).get("refPath")
        target_fn = None
        for widget, fn in MAP.items():
            if widget in title:
                target_fn = fn
        if not target_fn:
            print(f"  ? 匹配不到函数: title={title} ref={ref}")
            continue
        out_pin = exec_out_pin(info)
        if not out_pin:
            print(f"  ? 事件无 Exec 出脚: {title}")
            continue
        if any(p.get("connected_pins") for p in info.get("output_pins", [])):
            print(f"  = 已接线 skip: {title}")
            continue
        # 造函数调用节点
        y = 200 * wired
        rn, _ = call("create_node", {"graph": EG, "type_id": f"CallFunction|{target_fn}",
                                     "pos": {"x": 1400, "y": y}})
        call_ref = None
        def pickref(o):
            global call_ref
            if isinstance(o, dict):
                if "refPath" in o and isinstance(o["refPath"], str) and "K2Node" in o["refPath"]:
                    call_ref = call_ref or o["refPath"]
                for v in o.values():
                    pickref(v)
            elif isinstance(o, list):
                for v in o:
                    pickref(v)
        pickref(rn)
        if not call_ref:
            print(f"  ! create_node 无 ref: {json.dumps(rn)[:300]}")
            continue
        ci = node_infos([call_ref])[0]
        in_pin = exec_in_pin(ci)
        if not in_pin:
            print(f"  ! 调用节点无 Exec 入脚: {call_ref}")
            continue
        r2, err = call("connect_pins", {"output_pin": out_pin, "input_pin": in_pin}, ok_fail=True)
        print(f"  {'ERR' if err else '->'} {title} => {target_fn}: {json.dumps(r2)[:150]}")
        if not err:
            wired += 1
print(f"wired {wired}/4")

# ---------- 2) 清孤儿探针节点（全部引脚无连接的 CallFunction/GetArrayItem） ----------
r, _ = call("find_nodes", {"graph": EG, "title": ""}, ok_fail=True)
all_refs = []
collect_target = all_refs
def collect2(o):
    if isinstance(o, dict):
        if "refPath" in o and isinstance(o["refPath"], str):
            collect_target.append(o["refPath"])
        for v in o.values():
            collect2(v)
    elif isinstance(o, list):
        for v in o:
            collect2(v)
collect2(r)
all_refs = sorted(set(all_refs))
removed = 0
if all_refs:
    for info in node_infos(all_refs):
        pins = info.get("output_pins", []) + info.get("input_pins", [])
        ref = None
        for p in pins:
            ref = p.get("pin_id", {}).get("node", {}).get("refPath")
            if ref:
                break
        if not ref or ("K2Node_CallFunction" not in ref and "K2Node_GetArrayItem" not in ref):
            continue
        if pins and all(not p.get("connected_pins") for p in pins):
            _, err = call("delete_node", {"node": {"refPath": ref}}, ok_fail=True)
            removed += 0 if err else 1
print(f"orphans removed: {removed}")

# ---------- 3) 编译 + 存 ----------
r, _ = call("compile_blueprint", {"blueprint": BP_REF})
print("compile:", json.dumps(r)[:300])
text, err = cli.tool("call_tool", {"toolset_name": AT, "tool_name": "save_assets",
                                   "arguments": {"asset_paths": [WBP]}})
print("saved:", text[:150], "err" if err else "")
print("DONE wire")
