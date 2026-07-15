#!/usr/bin/env python3
"""gen_bg.py — 光遇系（Sky-like）氛围背景生成器：渐变暮空 + 云海 + 剪影。

档位 A 占位美术：借光遇的**氛围语言**（大渐变天空、云海暖光、被风景衬小的
斗篷旅人剪影），造型全部原创（中式牌坊山门、提灯守门老人），不复刻任何
光遇具体设计。正式美术后续走批量生成 + 人工定稿，本工具保证先有可玩的脸面。

用法: gen_bg.py <scene_key> <out.png>   （场景参数见 SCENES）
"""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080
RNG = np.random.default_rng(7)


# ---------- 基础 ----------
def smoothstep(t):
    return t * t * (3 - 2 * t)


def vgrad(stops):
    """垂直渐变底图。stops: [(y_frac, (r,g,b)), ...] 自上而下。"""
    ys = np.linspace(0, 1, H)
    cols = np.zeros((H, 3), np.float32)
    cols[ys <= stops[0][0]] = stops[0][1]
    cols[ys >= stops[-1][0]] = stops[-1][1]
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        m = (ys >= y0) & (ys < y1)
        t = smoothstep((ys[m] - y0) / max(y1 - y0, 1e-6))
        cols[m] = np.outer(1 - t, np.array(c0, np.float32)) + np.outer(t, np.array(c1, np.float32))
    return np.repeat(cols[:, None, :], W, axis=1)


def add_radial_glow(img, cx, cy, sigma, color, gain):
    """加法辉光（太阳/灯笼）。img: float HxWx3。"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    g = np.exp(-d2 / (2 * sigma * sigma))[:, :, None] * np.array(color, np.float32) * gain
    img += g
    return img


def paste_rgba(base_img, layer):
    return Image.alpha_composite(base_img, layer)


def ridge_layer(y_base, amp, color, blur=3, seed=0):
    """一条远山棱线剪影（随机游走山脊）。"""
    rng = np.random.default_rng(seed)
    n = 24
    xs = np.linspace(-50, W + 50, n)
    ys = y_base + np.cumsum(rng.uniform(-1, 1, n)) * amp * 0.35
    ys += rng.uniform(-0.4, 0.4, n) * amp
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    pts = list(zip(xs, ys)) + [(W + 50, H + 50), (-50, H + 50)]
    d.polygon(pts, fill=color)
    return lay.filter(ImageFilter.GaussianBlur(blur))


def cloud_band(y_center, thickness, n_blobs, color, rim_color, blur, seed):
    """一条云海带：椭圆团簇 + 上缘暖光。"""
    rng = np.random.default_rng(seed)
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    for _ in range(n_blobs):
        x = rng.uniform(-100, W + 100)
        y = y_center + rng.uniform(-thickness * 0.4, thickness * 0.4)
        rw = rng.uniform(90, 260)
        rh = rw * rng.uniform(0.28, 0.42)
        d.ellipse([x - rw, y - rh, x + rw, y + rh], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.paste(Image.new("RGBA", (W, H), color), (0, 0), mask)
    rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rim.paste(Image.new("RGBA", (W, H), rim_color), (0, -6), mask)
    rim_m = np.array(rim)[:, :, 3].astype(np.int16) - np.array(lay)[:, :, 3].astype(np.int16)
    rim_np = np.array(rim)
    rim_np[:, :, 3] = np.clip(rim_m, 0, 255).astype(np.uint8)
    return lay, Image.fromarray(rim_np)


# ---------- 剪影元素（原创造型） ----------
SIL = (14, 20, 46, 255)  # 近黑靛


def draw_gate(d):
    """中式石牌坊剪影：双柱 + 双梁 + 翘檐顶 + 柱础。中空即门洞，透出云海。"""
    cx = int(W * 0.52)
    gap = 240
    pw = 30
    top = int(H * 0.40)
    ground = int(H * 0.885) + 36  # 沉进前景坡地，别悬空
    lx, rx = cx - gap // 2, cx + gap // 2
    for x in (lx, rx):
        d.rectangle([x - pw // 2, top + 70, x + pw // 2, ground], fill=SIL)
        d.rectangle([x - pw, ground - 34, x + pw, ground], fill=SIL)  # 柱础
        d.rectangle([x - pw + 6, ground - 58, x + pw - 6, ground - 34], fill=SIL)
    beam_y = top + 118
    d.rectangle([lx - 74, beam_y, rx + 74, beam_y + 26], fill=SIL)  # 下梁（带出挑）
    d.rectangle([lx - 44, top + 64, rx + 44, top + 88], fill=SIL)  # 上梁
    d.rectangle([cx - 46, top + 88, cx + 46, beam_y], fill=SIL)  # 匾额
    d.rectangle([cx - 168, top + 50, cx + 168, top + 66], fill=SIL)  # 檐下枋（封住漏天）
    for x in range(lx - 20, rx + 21, 22):  # 斗拱点（加密）
        d.rectangle([x - 5, top + 42, x + 5, top + 52], fill=SIL)
    # 庑殿顶：短脊长檐，檐端缓缓上挑
    roof = [(cx - 246, top + 30), (cx - 196, top + 44), (cx - 116, top + 14), (cx + 116, top + 14),
            (cx + 196, top + 44), (cx + 246, top + 30), (cx + 204, top + 58),
            (cx - 204, top + 58)]
    d.polygon(roof, fill=SIL)
    d.rectangle([cx - 8, top - 2, cx + 8, top + 18], fill=SIL)  # 脊饰
    return lx, rx, ground


def draw_youth(d, x, ground):
    """斗篷少年剪影（原创）：兜帽、微前倾、背小包袱，斗篷下摆被风带起。"""
    h = 104
    top = ground - h
    d.ellipse([x - 11, top, x + 11, top + 22], fill=SIL)  # 兜帽头
    d.polygon([(x - 4, top + 6), (x + 14, top + 10), (x + 6, top + 20)], fill=SIL)  # 帽尖
    cloak = [(x - 8, top + 18), (x + 10, top + 18), (x + 16, top + 46),
             (x + 22, ground - 6), (x + 30, ground),  # 风向右带起的下摆
             (x - 14, ground), (x - 18, ground - 18), (x - 12, top + 40)]
    d.polygon(cloak, fill=SIL)
    d.ellipse([x + 4, top + 22, x + 20, top + 42], fill=SIL)  # 包袱
    d.polygon([(x - 2, ground - 2), (x + 8, ground - 2), (x + 5, ground + 4), (x + 1, ground + 4)], fill=SIL)


def draw_gatekeeper(d, x, ground):
    """守门老人剪影（原创）：坐在石墩上、佝偻、身边一杆纸灯笼。"""
    d.rectangle([x - 16, ground - 26, x + 16, ground], fill=SIL)  # 石墩
    d.ellipse([x - 15, ground - 74, x + 17, ground - 30], fill=SIL)  # 佝偻身形
    d.ellipse([x - 6, ground - 88, x + 10, ground - 70], fill=SIL)  # 头
    d.line([(x + 24, ground), (x + 30, ground - 92)], fill=SIL, width=4)  # 灯杆
    d.line([(x + 30, ground - 92), (x + 44, ground - 84)], fill=SIL, width=3)
    d.ellipse([x + 38, ground - 82, x + 52, ground - 62], fill=SIL)  # 灯笼壳（光后补）


def draw_egret(d, x, y, s=13):
    """白鹭剪影：两笔翅，一点颈。兆头。"""
    d.arc([x - s * 2, y - s, x, y + s], 200, 330, fill=(240, 244, 250, 200), width=3)
    d.arc([x, y - s, x + s * 2, y + s], 210, 340, fill=(240, 244, 250, 200), width=3)


# ---------- 场景 ----------
def build_wenjin_gate(out_path):
    # 1) 暮空（光遇黄昏调）
    sky = vgrad([
        (0.00, (24, 33, 66)),
        (0.30, (63, 76, 126)),
        (0.50, (132, 118, 152)),
        (0.615, (214, 156, 122)),
        (0.66, (243, 200, 146)),
        (0.72, (232, 178, 128)),
        (1.00, (150, 128, 138)),
    ])
    sun_x, sun_y = W * 0.545, H * 0.615
    sky = add_radial_glow(sky, sun_x, sun_y, 46, (255, 236, 200), 1.0)
    sky = add_radial_glow(sky, sun_x, sun_y, 170, (255, 208, 150), 0.55)
    sky = add_radial_glow(sky, sun_x, sun_y, 430, (255, 178, 120), 0.22)
    img = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8)).convert("RGBA")

    # 2) 远山棱线（门外世界的远方）
    img = paste_rgba(img, ridge_layer(H * 0.60, 46, (84, 88, 132, 105), blur=4, seed=11))
    img = paste_rgba(img, ridge_layer(H * 0.635, 30, (66, 72, 116, 150), blur=3, seed=23))

    # 3) 云海（四层，近大远小、近暗远亮）
    bands = [
        (H * 0.665, 46, 42, (247, 214, 168, 210), (255, 238, 205, 150), 10, 31),
        (H * 0.72, 70, 34, (226, 180, 146, 225), (255, 226, 180, 130), 13, 32),
        (H * 0.80, 110, 26, (168, 138, 138, 235), (250, 205, 160, 110), 17, 33),
        (H * 0.93, 170, 20, (108, 96, 128, 245), (222, 176, 148, 90), 22, 34),
    ]
    for yc, th, nb, col, rim, bl, sd in bands:
        lay, rim_l = cloud_band(yc, th, nb, col, rim, bl, sd)
        img = paste_rgba(paste_rgba(img, lay), rim_l)

    # 4) 神光（太阳斜射）
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for ang, ln, wd, al in [(-32, 900, 60, 16), (-18, 1050, 90, 13), (-6, 980, 70, 15),
                            (8, 1000, 84, 12), (22, 880, 58, 15), (36, 760, 46, 12)]:
        a = np.deg2rad(ang + 90)
        dx, dy = np.cos(a), -np.sin(a)
        px, py = -dy, dx
        p = [(sun_x + px * 6, sun_y + py * 6), (sun_x - px * 6, sun_y - py * 6),
             (sun_x + dx * ln - px * wd, sun_y + dy * ln - py * wd),
             (sun_x + dx * ln + px * wd, sun_y + dy * ln + py * wd)]
        rd.polygon(p, fill=(255, 224, 170, al))
    img = paste_rgba(img, rays.filter(ImageFilter.GaussianBlur(6)))

    # 5) 前景剪影：坡地 + 牌坊 + 人物
    sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sil)
    gy = int(H * 0.885)
    slope = [(0, H), (0, gy + 66)]
    xs = np.linspace(0, W, 40)
    ys = gy + 30 + 36 * smoothstep(np.abs(xs - W * 0.52) / (W * 0.55))
    slope += list(zip(xs, ys)) + [(W, H)]
    d.polygon(slope, fill=SIL)
    lx, rx, ground = draw_gate(d)
    draw_youth(d, int(W * 0.508), ground)  # 站进门洞正中，逆光
    draw_gatekeeper(d, rx + 78, ground)
    img = paste_rgba(img, sil)

    # 6) 灯笼暖光（压在剪影之上）
    arr = np.asarray(img).astype(np.float32)[:, :, :3]
    lant_x, lant_y = rx + 78 + 45, ground - 72
    arr = add_radial_glow(arr, lant_x, lant_y, 7, (255, 214, 140), 1.1)
    arr = add_radial_glow(arr, lant_x, lant_y, 46, (255, 190, 120), 0.30)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")

    # 7) 光尘 + 白鹭
    motes = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(motes)
    for _ in range(52):
        x = RNG.uniform(0, W)
        y = RNG.uniform(H * 0.30, H * 0.92)
        near_sun = np.exp(-((x - sun_x) ** 2 + (y - sun_y) ** 2) / (2 * 500 ** 2))
        r = RNG.uniform(1.2, 3.6) + 2.5 * (RNG.random() < 0.12)
        al = int(RNG.uniform(22, 70) * (0.45 + 0.8 * near_sun))
        md.ellipse([x - r, y - r, x + r, y + r], fill=(255, 218, 164, al))
    img = paste_rgba(img, motes.filter(ImageFilter.GaussianBlur(1.1)))
    eg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_egret(ImageDraw.Draw(eg), W * 0.30, H * 0.235)
    img = paste_rgba(img, eg.filter(ImageFilter.GaussianBlur(0.6)))

    # 8) 晕影 + 细颗粒
    arr = np.asarray(img).astype(np.float32)[:, :, :3]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dist = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    arr *= (1 - 0.22 * np.clip(dist - 0.55, 0, 1)[..., None] ** 1.6)
    arr += RNG.normal(0, 2.2, arr.shape)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(out_path)
    print(f"OK -> {out_path}")


SCENES = {"BG_WenJinGate": build_wenjin_gate}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in SCENES:
        print(__doc__)
        print("scenes:", ", ".join(SCENES))
        sys.exit(1)
    SCENES[sys.argv[1]](sys.argv[2])
