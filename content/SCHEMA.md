# 相遇数据 Schema v0.1

> 这是 UE 表现层与叙事引擎之间的**契约**。增量1 用硬编码 JSON 喂 UE 壳；
> 增量2 的 Mastra 引擎输出**同一形状**；增量3 只是把"读文件"换成"读 HTTP/WS"。
> 字段对齐设计 spec §5 约束/校验层（角色、情境、命题、选项、后果、状态影响、领悟）。

## 顶层

```jsonc
{
  "schema_version": "0.1",
  "encounter": {
    "id": "anchor_call_gatekeeper",   // 唯一 id；anchor_* = 手写锚点
    "type": "anchor",                 // anchor | generated（AI 动态生成）
    "node": "call",                   // 主线节点: call|trial|oasis|dark|epiphany|return
    "pillar": "courage",              // 支柱: courage(恐惧/勇气)|vocation(志业/热爱)|bond(爱/羁绊)|faith(信念/诱惑)
    "location_name": "问津门",
    "background": "BG_WenJinGate",    // 表现层背景资产 key
    "characters": [
      {"id": "gatekeeper", "name": "守门老人", "archetype": "mentor"}
    ]
  },
  "beats": [ /* 顺序播放的节拍，见下 */ ]
}
```

## beat 类型

```jsonc
// 章节题卡（全屏居中，点击继续）
{"type": "title", "text": "楔子 · 问津门"}

// 一行台词/旁白。speaker="旁白" 走旁白样式；tags 供引擎/结局回扣用
{"type": "line", "speaker": "守门老人", "text": "……", "tags": ["mirror_anchor"]}

// 抉择：无对错，选择即价值观。选项落定后先播 reaction，再回主序列
{"type": "choice", "id": "c_step_out", "prompt": "现在，你还走吗？",
 "options": [
   {"id": "a", "text": "跨出去",
    "belief_delta": 2,                 // 信念值增减（可为负）
    "value_tag": "courage.forward",    // 价值观刻痕：结局《你的天命之书》的原料
    "reaction": [ {"speaker": "守门老人", "text": "……"} ],
    "insight": "原来怕和走，可以是同一件事。"   // 领悟：高亮沉淀，一句话
   }
 ]}

// 领悟单独成拍（不挂在选项上时用）：高亮样式
{"type": "insight", "text": "……"}
```

## 表现层消费规则（增量1）

- 依序播 beats；`line`/`title` 点击推进；`choice` 出选项按钮、点选后播 `reaction` → 高亮 `insight` → 继续。
- `belief_delta` 实时改信念值 HUD（初始 3）。
- `value_tag` 与带 `tags` 的行要落进玩家档案（增量1 先打 log，记忆层是增量2 的事）。
- `mirror_anchor` 标记首尾同景的锚点行：镜子结局要回放同一背景并回扣这段文字。

## 版权自检（写内容前必读 spec §7）

自创地名体系（云岫山/问津门/溪尾村…），不用《山海经》专名；只用公有领域母题
（预兆/天命/宝藏在出发地）；无原著专名、情节链、台词。
