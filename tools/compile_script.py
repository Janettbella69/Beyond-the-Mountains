#!/usr/bin/env python3
"""compile_script.py — 把富 encounter JSON（content/SCHEMA.md）编译成 UE 壳消费的扁平行数组。

为什么扁平：UE5.8 MCP 的 DataTableTools 需要已存在的 RowStruct（无法凭空造
UserDefinedStruct），所以增量1 把剧本烤成 Widget 蓝图 CDO 上的**并行数组**变量
（Type/Speaker/Text/Next + 选项列），蓝图逻辑按索引走行、按 next 跳转。
增量3 换 HTTP 喂同样形状的行数组即可。

行模型（并行数组，等长）:
  Type:    0=line 1=title 2=choice 3=insight 4=end
  Speaker: 说话人（line 用；旁白=旁白）
  Text:    正文 / 题卡 / 选择 prompt / 领悟
  Next:    下一行索引（choice 行不用；end=-1）
  AText/BText/CText:       选项文案（"" = 该槽位无选项）
  ADelta/BDelta/CDelta:    信念增减
  ATag/BTag/CTag:          value_tag（增量1 只打 log）
  ANext/BNext/CNext:       选中后跳转行（进 reaction 链，链尾回汇合点）

用法: compile_script.py <encounter.json> <out.json> [--trace]
"""
import json
import sys

SLOT = "ABC"


def compile_beats(beats):
    rows = []

    def add(row):
        rows.append(row)
        return len(rows) - 1

    def blank(t, speaker="", text="", nxt=-1):
        r = {"Type": t, "Speaker": speaker, "Text": text, "Next": nxt}
        for s in SLOT:
            r[f"{s}Text"] = ""
            r[f"{s}Delta"] = 0
            r[f"{s}Tag"] = ""
            r[f"{s}Next"] = -1
        return r

    for beat in beats:
        bt = beat["type"]
        if bt == "line":
            add(blank(0, beat.get("speaker", "旁白"), beat["text"]))
        elif bt == "title":
            add(blank(1, "", beat["text"]))
        elif bt == "insight":
            add(blank(3, "", beat["text"]))
        elif bt == "end":
            add(blank(4))
        elif bt == "choice":
            opts = beat.get("options", [])
            if not 1 <= len(opts) <= 3:
                raise ValueError(f"choice {beat.get('id')} 选项数 {len(opts)} 不在 1..3")
            ci = add(blank(2, "", beat.get("prompt", "")))
            tails = []  # 各选项链尾行，待补 Next=汇合点
            for k, opt in enumerate(opts):
                s = SLOT[k]
                rows[ci][f"{s}Text"] = opt["text"]
                rows[ci][f"{s}Delta"] = int(opt.get("belief_delta", 0))
                rows[ci][f"{s}Tag"] = opt.get("value_tag", "")
                first = None
                last = None
                for r in opt.get("reaction", []):
                    i = add(blank(0, r.get("speaker", "旁白"), r["text"]))
                    first = first if first is not None else i
                    last = i
                if opt.get("insight"):
                    i = add(blank(3, "", opt["insight"]))
                    first = first if first is not None else i
                    last = i
                rows[ci][f"{s}Next"] = first if first is not None else -2
                if last is not None:
                    tails.append(last)
            cont = len(rows)  # 下一个源 beat 将落在这里 = 汇合点
            for t in tails:
                rows[t]["Next"] = cont
            for s in SLOT:
                if rows[ci][f"{s}Next"] == -2:
                    rows[ci][f"{s}Next"] = cont
        else:
            raise ValueError(f"未知 beat type: {bt}")

    # 补顺序 Next（简单行指向下一行；end 保持 -1）
    for i, r in enumerate(rows):
        if r["Type"] in (0, 1, 3) and r["Next"] == -1:
            r["Next"] = i + 1
    # 校验
    n = len(rows)
    assert rows[-1]["Type"] == 4, "最后一行必须是 end"
    for i, r in enumerate(rows):
        links = [r["Next"]] if r["Type"] != 2 else [r[f"{s}Next"] for s in SLOT if r[f"{s}Text"]]
        for j in links:
            if r["Type"] == 4:
                continue
            assert 0 <= j < n, f"行 {i} 跳转越界: {j}"
    return rows


def to_arrays(rows):
    keys = list(rows[0].keys())
    return {k: [r[k] for r in rows] for k in keys}


def trace(rows):
    tn = {0: "line", 1: "TITLE", 2: "CHOICE", 3: "*insight*", 4: "END"}
    for i, r in enumerate(rows):
        if r["Type"] == 2:
            print(f"[{i:02d}] CHOICE {r['Text']}")
            for s in SLOT:
                if r[f"{s}Text"]:
                    print(f"      {s}: {r[f'{s}Text']}  (Δ{r[f'{s}Delta']:+d} {r[f'{s}Tag']}) -> {r[f'{s}Next']}")
        else:
            sp = f"{r['Speaker']}: " if r["Speaker"] else ""
            print(f"[{i:02d}] {tn[r['Type']]:9s} {sp}{r['Text'][:46]}{'…' if len(r['Text'])>46 else ''} -> {r['Next']}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    data = json.load(open(sys.argv[1]))
    rows = compile_beats(data["beats"])
    out = {
        "encounter_id": data["encounter"]["id"],
        "background": data["encounter"]["background"],
        "belief_initial": 3,
        "row_count": len(rows),
        "arrays": to_arrays(rows),
    }
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(f"OK: {len(rows)} rows -> {sys.argv[2]}")
    if "--trace" in sys.argv:
        trace(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
