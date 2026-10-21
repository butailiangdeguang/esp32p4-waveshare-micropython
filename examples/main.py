# main.py - 完整模块化主程序入口
import p4
import time
import gc

import config as cfg
from ui_engine import UIEngine

# 导入所有 9 个独立页面
from pages.p1_system import PageSystem
from pages.p2_display import PageDisplay
from pages.p3_touch import PageTouch
from pages.p4_ppa import PagePPA
from pages.p5_uart import PageUART
from pages.p6_bus import PageBus
from pages.p7_audio import PageAudio
from pages.p8_media import PageMedia
from pages.p9_wifi import PageWiFi

# 硬件总线底层点火
p4.display_init()
p4.touch_init()
p4.backlight(85)
p4.rtc_init()
p4.bld_init(token="btldg_iot_token_2026", node_id=101)

ui = UIEngine()

# 实例化所有页面对象
pages = [
    PageSystem(),
    PageDisplay(),
    PageTouch(),
    PagePPA(),
    PageUART(),
    PageBus(),
    PageAudio(),
    PageMedia(),
    PageWiFi(),
]

cur_page = 0
page_changed = True
page_passed = [False] * len(cfg.PAGE_NAMES)
buf_idx = 0

last_poll = 0
last_drag = 0

# 初始双缓冲同步清屏
for _ in range(2):
    p4.fill_rect(0, 0, cfg.SCR_W, cfg.SCR_H, cfg.C_BLACK)
    ui.draw_framework(cur_page, page_passed)
    p4.flip()

while True:
    now = time.ticks_ms()
    cur_temp = p4.temperature()
    pts = p4.touch_read()

    # 1. 底部通用导航判定 (跳过 / 下一项，边沿防抖)
    act = ui.check_navigation(pts, cur_page, page_passed)
    if act == "skip":
        page_passed[cur_page] = True
        if cur_page < len(cfg.PAGE_NAMES) - 1:
            cur_page += 1
        page_changed = True
    elif act == "next":
        if cur_page < len(cfg.PAGE_NAMES) - 1:
            cur_page += 1
        page_changed = True

    # 2. 当前页面的专属触控事件分发
    if not ui.touch_pressed:
        if cur_page == 1:    # P2: 屏幕坏点切色
            if pages[1].handle_touch(pts):
                ui.touch_pressed = True
                page_changed = True
        elif cur_page == 2:  # P3: 画板划线
            pages[2].handle_touch(pts)
            if pages[2].is_passed():
                page_passed[2] = True
        elif cur_page == 3:  # P4: PPA 窗口拖拽
            pages[3].handle_touch(pts)
            if pages[3].drag_dist >= 200:
                page_passed[3] = True

    # 3. 换页全量刷新 (双显存彻底擦除)
    if page_changed:
        for _ in range(2):
            p4.fill_rect(0, 0, cfg.SCR_W, cfg.SCR_H, cfg.C_BLACK)
            ui.draw_framework(cur_page, page_passed)
            if cur_page != 1:
                ui.draw_card_base(cur_page)
            
            # 静态渲染当前页内容
            if cur_page == 0:
                pages[0].render(cur_temp)
            elif cur_page == 1:
                pages[1].render()
            elif cur_page == 2:
                pages[2].render()
            elif cur_page == 3:
                pages[3].render_static(page_passed[3])
            elif cur_page == 4:
                pages[4].render()
            elif cur_page == 5:
                pages[5].render()
            elif cur_page == 6:
                pages[6].render()
            elif cur_page == 7:
                pages[7].render()
            elif cur_page == 8:
                pages[8].render(cur_temp)
            p4.flip()
        page_changed = False
        continue

    # 4. P4 专属 60FPS 极速局部无重影拖拽通道
    if cur_page == 3 and pages[3].win_drag:
        if time.ticks_diff(now, last_drag) >= 16:
            pages[3].render_fast_drag(buf_idx)
            p4.flip()
            buf_idx = 1 - buf_idx
            last_drag = now
        continue

    # 5. 常规业务轮询 (150ms 周期)
    if time.ticks_diff(now, last_poll) >= 150:
        if cur_page == 0:
            if pages[0].update():
                page_passed[0] = True
        elif cur_page == 4:
            if pages[4].update():
                page_passed[4] = True
        elif cur_page == 5:
            if pages[5].update():
                page_passed[5] = True
        elif cur_page == 6:
            if pages[6].update():
                page_passed[6] = True
        elif cur_page == 7:
            if pages[7].is_passed():
                page_passed[7] = True
        elif cur_page == 8:
            if pages[8].update():
                page_passed[8] = True

        # 平稳刷新当前页
        ui.draw_framework(cur_page, page_passed)
        if cur_page != 1:
            ui.draw_card_base(cur_page)

        if cur_page == 0:
            pages[0].render(cur_temp)
        elif cur_page == 1:
            pages[1].render()
        elif cur_page == 2:
            pages[2].render()
        elif cur_page == 3:
            pages[3].render_static(page_passed[3])
        elif cur_page == 4:
            pages[4].render()
        elif cur_page == 5:
            pages[5].render()
        elif cur_page == 6:
            pages[6].render()
        elif cur_page == 7:
            pages[7].render()
        elif cur_page == 8:
            pages[8].render(cur_temp)

        p4.flip()
        buf_idx = 1 - buf_idx
        last_poll = now
    else:
        time.sleep_ms(2)
