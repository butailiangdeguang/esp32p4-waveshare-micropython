# main.py - 主调度入口
import p4
import time
import gc

import config as cfg
from ui_engine import UIEngine

# 导入拆分的分页模块
from pages.p1_system import PageSystem
from pages.p4_ppa import PagePPA
from pages.p5_uart import PageUART

# 硬件总线点火
p4.display_init()
p4.touch_init()
p4.backlight(85)
p4.rtc_init()

ui = UIEngine()
page_sys = PageSystem()
page_ppa = PagePPA()
page_uart = PageUART()

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

    # 1. 底部换页与跳过判定 (边沿触发)
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

    # 2. 专属页面触控处理
    if cur_page == 3:  # P4 PPA
        page_ppa.handle_touch(pts)
        if page_ppa.drag_dist >= 200:
            page_passed[3] = True

    # 3. 换页全量刷新处理
    if page_changed:
        for _ in range(2):
            p4.fill_rect(0, 0, cfg.SCR_W, cfg.SCR_H, cfg.C_BLACK)
            ui.draw_framework(cur_page, page_passed)
            ui.draw_card_base(cur_page)
            if cur_page == 0:
                page_sys.render(cur_temp)
            elif cur_page == 3:
                page_ppa.render_static(page_passed[3])
            elif cur_page == 4:
                page_uart.render()
            p4.flip()
        page_changed = False
        continue

    # 4. P4 极速局部无重影拖拽 (锁定 60 FPS)
    if cur_page == 3 and page_ppa.win_drag:
        if time.ticks_diff(now, last_drag) >= 16:
            page_ppa.render_fast_drag(buf_idx)
            p4.flip()
            buf_idx = 1 - buf_idx
            last_drag = now
        continue

    # 5. 后台常规轮询 (150ms)
    if time.ticks_diff(now, last_poll) >= 150:
        if cur_page == 0:
            if page_sys.update():
                page_passed[0] = True
        elif cur_page == 4:
            if page_uart.update():
                page_passed[4] = True

        # 平稳刷新当前页
        ui.draw_framework(cur_page, page_passed)
        ui.draw_card_base(cur_page)
        if cur_page == 0:
            page_sys.render(cur_temp)
        elif cur_page == 3:
            page_ppa.render_static(page_passed[3])
        elif cur_page == 4:
            page_uart.render()
        p4.flip()
        buf_idx = 1 - buf_idx

        last_poll = now
    else:
        time.sleep_ms(2)
