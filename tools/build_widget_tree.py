#!/usr/bin/env python3
"""build_widget_tree.py — 增量1：经 MCP 搭 WBP_VN 控件树 + 属性 + 变量。

树结构（CanvasPanel 根）:
  BGImage(全屏背景) / AdvanceCatcher(全屏透明推进钮) / DialogPanel(底部对话框:
  SpeakerText+BodyText) / ChoiceBox(3 选项钮) / InsightPanel(领悟卡) /
  TitleText(题卡) / BeliefHUD(信念值)
之后 build_logic.py 再写图逻辑。可重复运行（存在即跳过创建）。
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_mcp import Client

WBP = "/Game/PL/UI/WBP_VN"
FONT = "/Game/PL/Fonts/F_CJK.F_CJK"
BG = "/Game/PL/Art/BG_WenJinGate.BG_WenJinGate"

IVORY = {"R": 0.93, "G": 0.94, "B": 0.97, "A": 1.0}
GOLD = {"R": 0.95, "G": 0.78, "B": 0.55, "A": 1.0}
GOLD_HI = {"R": 1.0, "G": 0.85, "B": 0.55, "A": 1.0}

cli = Client()
cli.init()


def call(tool, args, toolset="UMGToolSet.UMGToolSet"):
    text, err = cli.tool("call_tool", {"toolset_name": toolset, "tool_name": tool, "arguments": args})
    if err:
        raise SystemExit(f"FAIL {tool}: {text[:800]}")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def set_props(ref, values):
    return call("set_properties", {"instance": {"refPath": ref}, "values": json.dumps(values)},
                toolset="editor_toolset.toolsets.object.ObjectTools")


# ---------- 1) 创建 WBP ----------
exists = call("exists", {"path": WBP}, toolset="editor_toolset.toolsets.asset.AssetTools")
if not (isinstance(exists, dict) and exists.get("returnValue")):
    r = call("CreateWidgetBlueprint", {
        "folderPath": "/Game/PL/UI", "assetName": "WBP_VN",
        "parentClass": {"refPath": "/Script/UMG.UserWidget"}})
    print("created WBP:", json.dumps(r)[:200])
else:
    print("WBP exists")

bp_ref = {"refPath": WBP + ".WBP_VN"}

# ---------- 2) 控件树 ----------
def widgets_by_name():
    r = call("GetWidgets", {"widgetBlueprint": bp_ref})
    out = {}
    for w in r["returnValue"]["widgets"]:
        slot = w.get("slot")
        out[w["widgetName"]] = {
            "widget": w["widget"]["refPath"],
            "slot": slot["refPath"] if isinstance(slot, dict) else None,
        }
    return out

have = widgets_by_name()
print("existing widgets:", sorted(have.keys()) or "(none)")

slots = {}   # name -> slot refPath
refs = {}    # name -> widget refPath


def addw(cls, name, parent_ref):
    """AddWidget，返回 (widget_ref, slot_ref)。已存在则查询返回。"""
    if name in have:
        return (have[name]["widget"], have[name]["slot"])
    args = {"widgetBlueprint": bp_ref,
            "widgetClass": {"refPath": f"/Script/UMG.{cls}"},
            "widgetDisplayName": name}
    if parent_ref:
        args["parentWidget"] = {"refPath": parent_ref}
    r = call("AddWidget", args)
    txt = json.dumps(r)
    w_ref = s_ref = None
    def pick(o):
        nonlocal w_ref, s_ref
        if isinstance(o, dict):
            if "refPath" in o and isinstance(o["refPath"], str):
                p = o["refPath"]
                if ":" in p and (".WidgetTree." in p or p.endswith(name)) and "Slot" not in p.split(".")[-1]:
                    w_ref = w_ref or p
                if "Slot" in p.split(".")[-1] or "slot" in p.split(".")[-1].lower():
                    s_ref = s_ref or p
            for v in o.values():
                pick(v)
        elif isinstance(o, list):
            for v in o:
                pick(v)
    pick(r)
    if not w_ref:
        raise SystemExit(f"AddWidget {name}: cannot find widget ref in: {txt[:600]}")
    return (w_ref, s_ref)


root_ref, _ = addw("CanvasPanel", "RootCanvas", None)
refs["RootCanvas"] = root_ref

tree = [
    # (class, name, parent, canvas-layout or None)
    ("Image", "BGImage", "RootCanvas",
     {"Anchors": ((0, 0), (1, 1)), "Offsets": (0, 0, 0, 0), "Align": (0, 0), "Auto": False}),
    ("Button", "AdvanceCatcher", "RootCanvas",
     {"Anchors": ((0, 0), (1, 1)), "Offsets": (0, 0, 0, 0), "Align": (0, 0), "Auto": False}),
    ("Border", "DialogPanel", "RootCanvas",
     {"Anchors": ((0, 1), (1, 1)), "Offsets": (140, -286, 140, 242), "Align": (0, 0), "Auto": False, "Z": 5}),
    ("VerticalBox", "DialogVBox", "DialogPanel", None),
    ("TextBlock", "SpeakerText", "DialogVBox", None),
    ("TextBlock", "BodyText", "DialogVBox", None),
    ("VerticalBox", "ChoiceBox", "RootCanvas",
     {"Anchors": ((0.5, 0.58), (0.5, 0.58)), "Offsets": (0, 0, 0, 0), "Align": (0.5, 0.5), "Auto": True, "Z": 6}),
    ("Button", "ChoiceBtnA", "ChoiceBox", None),
    ("TextBlock", "ChoiceTextA", "ChoiceBtnA", None),
    ("Button", "ChoiceBtnB", "ChoiceBox", None),
    ("TextBlock", "ChoiceTextB", "ChoiceBtnB", None),
    ("Button", "ChoiceBtnC", "ChoiceBox", None),
    ("TextBlock", "ChoiceTextC", "ChoiceBtnC", None),
    ("Border", "InsightPanel", "RootCanvas",
     {"Anchors": ((0.5, 0.38), (0.5, 0.38)), "Offsets": (0, 0, 0, 0), "Align": (0.5, 0.5), "Auto": True, "Z": 7}),
    ("TextBlock", "InsightText", "InsightPanel", None),
    ("TextBlock", "TitleText", "RootCanvas",
     {"Anchors": ((0.5, 0.42), (0.5, 0.42)), "Offsets": (0, 0, 0, 0), "Align": (0.5, 0.5), "Auto": True, "Z": 8}),
    ("HorizontalBox", "BeliefHUD", "RootCanvas",
     {"Anchors": ((1, 0), (1, 0)), "Offsets": (-44, 34, 0, 0), "Align": (1, 0), "Auto": True, "Z": 9}),
    ("TextBlock", "BeliefLabel", "BeliefHUD", None),
    ("TextBlock", "BeliefValue", "BeliefHUD", None),
]

for cls, name, parent, layout in tree:
    w, s = addw(cls, name, refs[parent])
    refs[name] = w
    if s:
        slots[name] = s
    print(f"  + {name} ({cls})")
    if layout and s:
        (amin, amax), off, al = layout["Anchors"], layout["Offsets"], layout["Align"]
        v = {"LayoutData": {
                "Anchors": {"Minimum": {"X": amin[0], "Y": amin[1]}, "Maximum": {"X": amax[0], "Y": amax[1]}},
                "Offsets": {"Left": off[0], "Top": off[1], "Right": off[2], "Bottom": off[3]},
                "Alignment": {"X": al[0], "Y": al[1]}},
             "bAutoSize": layout["Auto"]}
        if "Z" in layout:
            v["ZOrder"] = layout["Z"]
        set_props(s, v)

# ---------- 3) 控件属性 ----------
def font(size):
    return {"FontObject": FONT, "TypefaceFontName": "Regular", "Size": size}

props = {
    "BGImage": {"Brush": {"ResourceObject": BG}},
    "AdvanceCatcher": {"RenderOpacity": 0.0},
    "DialogPanel": {"BrushColor": {"R": 0.012, "G": 0.016, "B": 0.05, "A": 0.78},
                    "Padding": {"Left": 30, "Top": 20, "Right": 30, "Bottom": 20}},
    "SpeakerText": {"Font": font(21), "ColorAndOpacity": {"SpecifiedColor": GOLD},
                    "Text": "守门老人"},
    "BodyText": {"Font": font(27), "ColorAndOpacity": {"SpecifiedColor": IVORY},
                 "AutoWrapText": True, "Text": "……"},
    "ChoiceBtnA": {"BackgroundColor": {"R": 0.03, "G": 0.04, "B": 0.10, "A": 0.85}},
    "ChoiceBtnB": {"BackgroundColor": {"R": 0.03, "G": 0.04, "B": 0.10, "A": 0.85}},
    "ChoiceBtnC": {"BackgroundColor": {"R": 0.03, "G": 0.04, "B": 0.10, "A": 0.85}},
    "ChoiceTextA": {"Font": font(24), "ColorAndOpacity": {"SpecifiedColor": IVORY}, "Text": "A"},
    "ChoiceTextB": {"Font": font(24), "ColorAndOpacity": {"SpecifiedColor": IVORY}, "Text": "B"},
    "ChoiceTextC": {"Font": font(24), "ColorAndOpacity": {"SpecifiedColor": IVORY}, "Text": "C"},
    "InsightPanel": {"BrushColor": {"R": 0.06, "G": 0.05, "B": 0.02, "A": 0.85},
                     "Padding": {"Left": 34, "Top": 22, "Right": 34, "Bottom": 22},
                     "Visibility": "Collapsed"},
    "InsightText": {"Font": font(30), "ColorAndOpacity": {"SpecifiedColor": GOLD_HI}, "Text": "领悟"},
    "TitleText": {"Font": font(50), "ColorAndOpacity": {"SpecifiedColor": IVORY},
                  "Text": "楔子 · 问津门", "Visibility": "Collapsed"},
    "ChoiceBox": {"Visibility": "Collapsed"},
    "BeliefLabel": {"Font": font(22), "ColorAndOpacity": {"SpecifiedColor": GOLD}, "Text": "信念 "},
    "BeliefValue": {"Font": font(22), "ColorAndOpacity": {"SpecifiedColor": IVORY}, "Text": "3"},
}
for name, v in props.items():
    set_props(refs[name], v)
    print(f"  ~ props {name}")

# 关键控件设为蓝图变量（图里要引用）
for name in ["BGImage", "SpeakerText", "BodyText", "ChoiceBox", "ChoiceBtnA", "ChoiceBtnB",
             "ChoiceBtnC", "ChoiceTextA", "ChoiceTextB", "ChoiceTextC", "InsightPanel",
             "InsightText", "TitleText", "DialogPanel", "BeliefValue", "AdvanceCatcher"]:
    call("ToggleWidgetAsVariable", {"widgetBlueprint": bp_ref,
                                    "widget": {"refPath": refs[name]}, "bIsVariable": True})
print("widget variables toggled")

# ---------- 4) 剧本/状态变量 ----------
def add_var(name, type_name, container=None):
    args = {"blueprint": bp_ref, "name": name, "type_name": type_name}
    if container:
        args["container_type"] = container
    text, err = cli.tool("call_tool", {"toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
                                       "tool_name": "add_variable", "arguments": args})
    print(f"  var {name}: {'ERR ' + text[:120] if err else 'ok'}")
    return not err

for v in ["RowType", "RowNext", "ADelta", "ANext", "BDelta", "BNext", "CDelta", "CNext"]:
    add_var(v, "int", "ARRAY")
for v in ["RowSpeaker", "RowText", "AText", "ATag", "BText", "BTag", "CText", "CTag"]:
    add_var(v, "string", "ARRAY")
add_var("Idx", "int")
add_var("Belief", "int")

# ---------- 5) 编译 + 存 ----------
r = call("CompileWidgetBlueprint", {"widgetBlueprint": bp_ref})
print("compile:", json.dumps(r)[:300])
r = call("save_assets", {"assets": [{"refPath": WBP + ".WBP_VN"}]},
         toolset="editor_toolset.toolsets.asset.AssetTools")
print("saved:", json.dumps(r)[:200])
print("DONE tree")
