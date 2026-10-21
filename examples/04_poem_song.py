import p4
import time

# 1. 初始化显示与背光
p4.display_init()
p4.backlight(85)

# 2. 颜色方案
C_BG       = 0x0841  # 墨黑背景
C_CARD     = 0x10A2  # 雅灰卡片底衬
C_BORDER   = 0x39E7  # 边框线
C_TITLE    = 0xFFE0  # 琥珀金标题
C_AUTHOR   = 0x7BEF  # 浅灰作者署名
C_BODY     = 0xFFFF  # 纯白正文诗句
C_LINE     = 0x03B9  # 装饰点缀线

# 3. 诗词内容
title = "南乡子·登京口北固亭有怀"
author = "[宋] 辛弃疾"
lines = [
    "何处望神州？满眼风光北固楼。",
    "千古兴亡多少事？悠悠。不尽长江滚滚流。",
    "年少万双兜鍪，坐断东南战未休。",
    "天下英雄谁敌手？曹刘。生子当如孙仲谋。"
]

# 4. 绘制双缓冲背景与居中画框 (两帧同步，保证绝不闪烁)
def draw_poem():
    # 纯黑底色
    p4.fill_rect(x=0, y=0, w=1024, h=600, color=C_BG)

    # 居中雅致主画框 (100, 40, 824, 520)
    p4.fill_rect(x=100, y=40, w=824, h=520, color=C_CARD)
    
    # 装饰线框
    p4.fill_rect(x=102, y=42, w=820, h=2, color=C_BORDER)
    p4.fill_rect(x=102, y=556, w=820, h=2, color=C_BORDER)
    p4.fill_rect(x=102, y=42, w=2, h=516, color=C_BORDER)
    p4.fill_rect(x=920, y=42, w=2, h=516, color=C_BORDER)

    # 顶部装饰分割线
    p4.fill_rect(x=140, y=145, w=744, h=2, color=C_LINE)

    # 标题 (宋体 24 点阵，字宽约 24px)
    title_w = len(title) * 24
    title_x = 100 + (824 - title_w) // 2
    p4.text(title, title_x, 75, color=C_TITLE, font=p4.FONT_SONG, size=24)

    # 作者朝代
    author_w = len(author) * 24
    author_x = 100 + (824 - author_w) // 2
    p4.text(author, author_x, 112, color=C_AUTHOR, font=p4.FONT_SONG, size=24)

    # 正文逐行排版 (行高 68px)
    start_y = 180
    line_spacing = 68
    for i, line_text in enumerate(lines):
        line_w = len(line_text) * 24
        line_x = 100 + (824 - line_w) // 2
        line_y = start_y + i * line_spacing
        p4.text(line_text, line_x, line_y, color=C_BODY, font=p4.FONT_SONG, size=24)

    # 底部题注
    p4.text("@butailiangdeguang  不太亮的光", 360, 515, color=C_AUTHOR, font=p4.FONT_DOT, size=16)

# 写入双缓冲显存并翻转呈现
for _ in range(2):
    draw_poem()
    p4.flip()

print("宋体诗词渲染完成。")
