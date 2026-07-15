#!/usr/bin/env python3
"""build_logic.py — 增量1：给 WBP_VN 写 VN 推进逻辑（图 DSL）+ 灌剧本数据。

五步：①函数图 ShowRow ②编译后发现自函数调用节点 ③Advance/PickA/B/C
④Construct 事件 + 按钮 OnClicked 绑定 ⑤CDO 灌 script_flat.json 并行数组。
节点 type_id 全部运行时发现（find_node_types），不硬编码猜测。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_mcp import Client

WBP = "/Game/PL/UI/WBP_VN"
BP_REF = {"refPath": WBP + ".WBP_VN"}
FLAT = "/private/tmp/claude-501/-Users-isabella/ef722424-a629-4b08-86c6-12918f2b3446/scratchpad/script_flat.json"

BT = "editor_toolset.toolsets.blueprint.BlueprintTools"
OT = "editor_toolset.toolsets.object.ObjectTools"
AT = "editor_toolset.toolsets.asset.AssetTools"
UMG = "UMGToolSet.UMGToolSet"

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


# ---------- 0) 图清单 ----------
graphs, _ = call(BT, "list_graphs", {"blueprint": BP_REF})
gmap = {}
for g in graphs.get("returnValue", []):
    ref = g["refPath"] if isinstance(g, dict) else g
    gmap[ref.split(".")[-1].split(":")[-1]] = ref
print("graphs:", list(gmap.keys()))
event_graph = None
for k, v in gmap.items():
    if "EventGraph" in k:
        event_graph = v
if not event_graph:
    raise SystemExit("no EventGraph found: " + json.dumps(gmap))


def ensure_fn_graph(name):
    for k, v in gmap.items():
        if k == name:
            return v
    r, _ = call(BT, "add_function_graph", {"blueprint": BP_REF, "graph_name": name})
    ref = None
    def pick(o):
        nonlocal ref
        if isinstance(o, dict):
            for v in o.values():
                pick(v)
            if "refPath" in o and isinstance(o["refPath"], str):
                ref = ref or o["refPath"]
        elif isinstance(o, list):
            for v in o:
                pick(v)
    pick(r)
    if not ref:
        raise SystemExit(f"add_function_graph {name}: no ref in {json.dumps(r)[:400]}")
    gmap[name] = ref
    return ref


# ---------- 1) 节点类型发现 ----------
def find_types(filter_s, graph=None):
    r, _ = call(BT, "find_node_types", {"graph": {"refPath": graph or event_graph},
                                        "type_id_filter": filter_s})
    rv = r.get("returnValue", r)
    ids = []
    def pick(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "type_id" and isinstance(v, str):
                    ids.append(v)
                else:
                    pick(v)
        elif isinstance(o, list):
            for v in o:
                pick(v)
    pick(rv)
    if not ids and isinstance(rv, str):
        ids = [l.strip() for l in rv.splitlines() if "|" in l]
    return ids


def resolve(filter_s, *prefer, required=True):
    ids = find_types(filter_s)
    for p in prefer:
        for i in ids:
            if p.lower() in i.lower():
                return i
    if ids:
        return ids[0]
    if required:
        raise SystemExit(f"cannot resolve node type: {filter_s} (got {ids})")
    return None


NODE = {}
NODE["arr_get"] = resolve("Array|Get", "Utilities|Array|Get")
NODE["settext"] = resolve("SetText", "TextBlock|SetText")
NODE["setvis"] = resolve("SetVisibility", "Widget|SetVisibility")
NODE["strlen"] = resolve("Len", "String|Len")
NODE["str2text"] = resolve("ToText", "String")
NODE["int2text"] = resolve("Conv_IntToText", "Int", required=False) or resolve("ToText(int", "int")
print("resolved nodes:", json.dumps(NODE, indent=1))
for k in NODE:
    pins, _ = call(BT, "get_node_type_pins", {"graph": {"refPath": event_graph}, "type_id": NODE[k]})
    print(f"  pins[{k}]:", json.dumps(pins)[:300])


# ---------- 2) DSL 源 ----------
def gv(name):  # get variable
    return f"(Variables|Default|Get{name})"


def sv(name, expr):  # set variable
    return f"(Variables|Default|Set{name} {expr})"


def arr(name, idx):
    return f"({NODE['arr_get']} {gv(name)} {idx})"


def settext(widget, text_expr):
    return f"({NODE['settext']} :self {gv(widget)} :InText {text_expr})"


def s2t(expr):
    return f"({NODE['str2text']} {expr})"


def i2t(expr):
    return f"({NODE['int2text']} {expr})"


def setvis(widget, vis):
    return f"({NODE['setvis']} :self {gv(widget)} :InVisibility \"{vis}\")"


SHOWROW = f"""
(fn ShowRow ()
  (bind i {gv('Idx')})
  (bind t {arr('RowType', 'i')})
  {setvis('TitleText', 'Collapsed')}
  {setvis('InsightPanel', 'Collapsed')}
  {setvis('ChoiceBox', 'Collapsed')}
  {setvis('DialogPanel', 'SelfHitTestInvisible')}
  {settext('BeliefValue', i2t(gv('Belief')))}
  (switch int t
    (:0
      {settext('SpeakerText', s2t(arr('RowSpeaker', 'i')))}
      {settext('BodyText', s2t(arr('RowText', 'i')))})
    (:1
      {setvis('DialogPanel', 'Collapsed')}
      {settext('TitleText', s2t(arr('RowText', 'i')))}
      {setvis('TitleText', 'HitTestInvisible')})
    (:2
      {settext('SpeakerText', s2t('""'))}
      {settext('BodyText', s2t(arr('RowText', 'i')))}
      {settext('ChoiceTextA', s2t(arr('AText', 'i')))}
      (bind bt {arr('BText', 'i')})
      (if (> ({NODE['strlen']} bt) 0)
        {settext('ChoiceTextB', s2t('bt'))}
        (Class|Widget|SetVisibility :self {gv('ChoiceBtnB')} :InVisibility "Visible")
        (else
          (Class|Widget|SetVisibility :self {gv('ChoiceBtnB')} :InVisibility "Collapsed")))
      (bind ct {arr('CText', 'i')})
      (if (> ({NODE['strlen']} ct) 0)
        {settext('ChoiceTextC', s2t('ct'))}
        (Class|Widget|SetVisibility :self {gv('ChoiceBtnC')} :InVisibility "Visible")
        (else
          (Class|Widget|SetVisibility :self {gv('ChoiceBtnC')} :InVisibility "Collapsed")))
      {setvis('ChoiceBox', 'Visible')})
    (:3
      {setvis('DialogPanel', 'Collapsed')}
      {settext('InsightText', s2t(arr('RowText', 'i')))}
      {setvis('InsightPanel', 'HitTestInvisible')})
    (:4
      {settext('SpeakerText', s2t('""'))}
      {settext('BodyText', s2t('"—— 楔子 · 终 ——　（点击重新开始）"'))})))
"""

# ---------- 3) 写 ShowRow / 编译 / 发现自函数调用 ----------
show_g = ensure_fn_graph("ShowRow")
r, _ = call(BT, "write_graph_dsl", {"graph": {"refPath": show_g}, "code": SHOWROW})
print("ShowRow write:", json.dumps(r)[:400])
r, _ = call(BT, "compile_blueprint", {"blueprint": BP_REF})
print("compile1:", json.dumps(r)[:400])

callshow_id = resolve("ShowRow", "ShowRow")
print("ShowRow call node:", callshow_id)
CALLSHOW = f"({callshow_id} :self self)"

ADVANCE = f"""
(fn Advance ()
  (bind i {gv('Idx')})
  (bind t {arr('RowType', 'i')})
  (if (== t 2)
    (return))
  (if (== t 4)
    {sv('Idx', '0')}
    {sv('Belief', '3')}
    {CALLSHOW}
    (return))
  {sv('Idx', arr('RowNext', 'i'))}
  {CALLSHOW})
"""


def pick_fn(slot):
    return f"""
(fn Pick{slot} ()
  (bind i {gv('Idx')})
  {sv('Belief', f"(+ {gv('Belief')} {arr(slot + 'Delta', 'i')})")}
  (Development|PrintString :InString {arr(slot + 'Tag', 'i')})
  {sv('Idx', arr(slot + 'Next', 'i'))}
  {CALLSHOW})
"""

for name, code in [("Advance", ADVANCE), ("PickA", pick_fn("A")), ("PickB", pick_fn("B")), ("PickC", pick_fn("C"))]:
    g = ensure_fn_graph(name)
    r, _ = call(BT, "write_graph_dsl", {"graph": {"refPath": g}, "code": code})
    print(f"{name} write:", json.dumps(r)[:250])

r, _ = call(BT, "compile_blueprint", {"blueprint": BP_REF})
print("compile2:", json.dumps(r)[:400])

# ---------- 4) Construct + 按钮绑定 ----------
CONSTRUCT = f"""
(event Construct
  {sv('Idx', '0')}
  {sv('Belief', '3')}
  {CALLSHOW})
"""
r, err = call(BT, "write_graph_dsl", {"graph": {"refPath": event_graph}, "code": CONSTRUCT}, ok_fail=True)
print("Construct write:", ("ERR " if err else "") + json.dumps(r)[:400])

bind_map = [("AdvanceCatcher", "Advance"), ("ChoiceBtnA", "PickA"),
            ("ChoiceBtnB", "PickB"), ("ChoiceBtnC", "PickC")]
for widget_var, fn in bind_map:
    r, err = call(UMG, "BindToEventProperty", {
        "widgetBlueprint": BP_REF, "eventName": "OnClicked",
        "propertyName": widget_var,
        "propertyClass": {"refPath": "/Script/UMG.Button"}}, ok_fail=True)
    print(f"bind {widget_var}.OnClicked:", ("ERR " if err else "") + json.dumps(r)[:300])
    fn_id = resolve(fn, fn)
    code = f"(event OnClicked_{widget_var} ({fn_id} :self self))"
    r, err = call(BT, "write_graph_dsl", {"graph": {"refPath": event_graph}, "code": code}, ok_fail=True)
    print(f"  handler via DSL OnClicked_{widget_var}:", ("ERR " if err else "ok ") + json.dumps(r)[:250])

r, _ = call(BT, "compile_blueprint", {"blueprint": BP_REF})
print("compile3:", json.dumps(r)[:400])

# ---------- 5) CDO 灌数据 ----------
flat = json.load(open(FLAT))
arrs = flat["arrays"]
cdo, _ = call(BT, "get_default_object", {"blueprint": BP_REF})
cdo_ref = None
def pickref(o):
    global cdo_ref
    if isinstance(o, dict):
        for v in o.values():
            pickref(v)
        if "refPath" in o:
            cdo_ref = cdo_ref or o["refPath"]
    elif isinstance(o, list):
        for v in o:
            pickref(v)
pickref(cdo)
print("CDO:", cdo_ref)

values = {
    "RowType": arrs["Type"], "RowSpeaker": arrs["Speaker"], "RowText": arrs["Text"],
    "RowNext": arrs["Next"],
    "AText": arrs["AText"], "ADelta": arrs["ADelta"], "ATag": arrs["ATag"], "ANext": arrs["ANext"],
    "BText": arrs["BText"], "BDelta": arrs["BDelta"], "BTag": arrs["BTag"], "BNext": arrs["BNext"],
    "CText": arrs["CText"], "CDelta": arrs["CDelta"], "CTag": arrs["CTag"], "CNext": arrs["CNext"],
    "Idx": 0, "Belief": 3,
}
r, _ = call(OT, "set_properties", {"instance": {"refPath": cdo_ref}, "values": json.dumps(values, ensure_ascii=False)})
print("CDO set:", json.dumps(r)[:200])

r, _ = call(BT, "compile_blueprint", {"blueprint": BP_REF})
print("compile4:", json.dumps(r)[:300])
r, _ = call(AT, "save_assets", {"assets": [BP_REF]})
print("saved:", json.dumps(r)[:200])
print("DONE logic")
