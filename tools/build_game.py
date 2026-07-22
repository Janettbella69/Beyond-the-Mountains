#!/usr/bin/env python3
"""build_game.py — 增量1：BP_VNGameMode（BeginPlay 挂 WBP_VN）+ 关卡 GameMode 绑定。

跑完 build_logic.py 后执行。世界设置绑定走 8003 bridge（MCP 没暴露 WorldSettings）。
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_mcp import Client

GM = "/Game/PL/Core/BP_VNGameMode"
GM_REF = {"refPath": GM + ".BP_VNGameMode"}
BT = "editor_toolset.toolsets.blueprint.BlueprintTools"
AT = "editor_toolset.toolsets.asset.AssetTools"

cli = Client()
cli.init()


def call(toolset, tool, args, ok_fail=False):
    text, err = cli.tool("call_tool", {"toolset_name": toolset, "tool_name": tool, "arguments": args})
    if err and not ok_fail:
        raise SystemExit(f"FAIL {tool}: {text[:900]}")
    try:
        return json.loads(text), err
    except json.JSONDecodeError:
        return text, err


def bridge(code):
    req = urllib.request.Request("http://127.0.0.1:8003/exec",
                                 data=json.dumps({"code": code, "timeout": 120}).encode(),
                                 headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=130).read())
    if not out.get("ok"):
        raise SystemExit("BRIDGE FAIL: " + out.get("out", "")[:800])
    return out.get("out", "")


# ---------- 1) 建 GameMode 蓝图 ----------
call(AT, "create_folder", {"folder_path": "/Game/PL/Core"}, ok_fail=True)
ex, _ = call(AT, "exists", {"path": GM}, ok_fail=True)
if not (isinstance(ex, dict) and ex.get("returnValue")):
    r, _ = call(BT, "create", {"folder_path": "/Game/PL/Core", "asset_name": "BP_VNGameMode",
                               "asset_type": {"refPath": "/Script/Engine.GameModeBase"}})
    print("created GM:", json.dumps(r)[:200])
else:
    print("GM exists")

# ---------- 2) 发现节点 & BeginPlay ----------
graphs, _ = call(BT, "list_graphs", {"blueprint": GM_REF})
eg = None
for g in graphs.get("returnValue", []):
    ref = g["refPath"] if isinstance(g, dict) else g
    if "EventGraph" in ref:
        eg = ref
print("event graph:", eg)


def find_types(f):
    r, _ = call(BT, "find_node_types", {"graph": {"refPath": eg}, "type_id_filter": f,
                                        "context_pins": []})
    rv = r.get("returnValue", r)
    if isinstance(rv, list):
        return [i for i in rv if isinstance(i, str)]
    if isinstance(rv, str):
        return [l.strip() for l in rv.splitlines() if "|" in l]
    return []


def resolve(f, *prefer):
    ids = find_types(f)
    for p in prefer:
        for i in ids:
            if p.lower() in i.lower():
                return i
    if ids:
        return ids[0]
    raise SystemExit(f"cannot resolve: {f}")


create_widget = resolve("CreateWidget", "CreateWidget")
add_viewport = resolve("AddtoViewport", "AddtoViewport")
get_pc = resolve("GetPlayerController", "Game|GetPlayerController")
show_cursor = resolve("ShowMouseCursor", "SetShowMouseCursor")
print("nodes:", create_widget, "|", add_viewport, "|", get_pc, "|", show_cursor)
for tid in (create_widget, show_cursor):
    pins, _ = call(BT, "get_node_type_pins", {"graph": {"refPath": eg}, "type_id": tid})
    print("pins:", tid, "=>", json.dumps(pins)[:400])

BEGIN = f"""
(event EventBeginPlay
  (bind pc ({get_pc} :PlayerIndex 0))
  ({show_cursor} :self pc :bShowMouseCursor true)
  (bind w ({create_widget} :Class "/Game/PL/UI/WBP_VN.WBP_VN_C" :OwningPlayer pc))
  ({add_viewport} :self w))
"""
r, _ = call(BT, "write_graph_dsl", {"graph": {"refPath": eg}, "code": BEGIN})
print("BeginPlay write:", json.dumps(r)[:400])
r, _ = call(BT, "compile_blueprint", {"blueprint": GM_REF})
print("compile:", json.dumps(r)[:300])
r, _ = call(AT, "save_assets", {"asset_paths": [GM]})
print("saved:", json.dumps(r)[:150])

# ---------- 3) 关卡绑定 GameMode + 存盘（bridge） ----------
out = bridge(r"""
import unreal
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
cur = les.get_current_level().get_outer().get_name()
if cur != 'L_WenJinGate':
    les.load_level('/Game/PL/Maps/L_WenJinGate')
gm = unreal.load_asset('/Game/PL/Core/BP_VNGameMode')
gmc = gm.generated_class()
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ws = [a for a in sub.get_all_level_actors_of_class(unreal.WorldSettings)]
if not ws:
    ws = [a for a in sub.get_all_level_actors() if isinstance(a, unreal.WorldSettings)]
print('world settings actors:', len(ws))
for a in ws:
    a.set_editor_property('default_game_mode', gmc)
    print('bound GameMode on', a.get_name())
print('saved level:', les.save_current_level())
""")
print(out)
print("DONE game")
