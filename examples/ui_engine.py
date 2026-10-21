# ui_engine.py - 统一框架绘制与防抖触控状态机
import p4
import config as cfg

class UIEngine:
    def __init__(self):
        self.touch_pressed = False
        self.touch_peak = 0

    def draw_framework(self, cur_page, page_passed):
        # 顶部导航步骤栏
        p4.fill_rect(x=0, y=0, w=cfg.SCR_W, h=42, color=0x0861)
        btn_w = cfg.SCR_W // len(cfg.PAGE_NAMES)
        for i, name in enumerate(cfg.PAGE_NAMES):
            bx = i * btn_w
            is_cur = (cur_page == i)
            is_pass = page_passed[i]
            
            bg_col = cfg.C_ACCENT if is_cur else (0x0280 if is_pass else 0x10A2)
            txt_col = cfg.C_WHITE if is_cur else (cfg.C_GREEN if is_pass else cfg.C_GRAY)
            
            p4.fill_rect(x=bx, y=0, w=btn_w - 2, h=40, color=bg_col)
            if is_cur:
                p4.fill_rect(x=bx, y=38, w=btn_w - 2, h=4, color=cfg.C_YELLOW)
            elif is_pass:
                p4.fill_rect(x=bx, y=38, w=btn_w - 2, h=4, color=cfg.C_GREEN)
                
            tag = "[V] " if is_pass else f"{i+1}."
            p4.text(f"{tag}{name.split('.')[1]}", bx + 6, 12, color=txt_col, font=p4.FONT_DOT, size=16)

        # 底部控制栏
        p4.fill_rect(x=0, y=550, w=cfg.SCR_W, h=50, color=cfg.C_BLACK)
        
        # 按钮 1: 跳过
        p4.fill_rect(x=700, y=555, w=130, h=38, color=0x4208)
        p4.text("跳过此项 >>", 715, 566, color=cfg.C_ORANGE, font=p4.FONT_DOT, size=16)
        
        # 按钮 2: 下一项
        pass_col = cfg.C_GREEN if page_passed[cur_page] else cfg.C_DGRAY
        p4.fill_rect(x=850, y=555, w=150, h=38, color=pass_col)
        btn_txt = "下一项 >>" if cur_page < len(cfg.PAGE_NAMES) - 1 else "验收完成"
        p4.text(btn_txt, 875, 566, color=cfg.C_WHITE if page_passed[cur_page] else cfg.C_GRAY, font=p4.FONT_DOT, size=16)

        info = "测试达标后点绿色前进，或点黄色直接跳过" if not page_passed[cur_page] else "本项已达标！请点击【下一项】进入下一步"
        p4.text(info, 50, 566, color=cfg.C_WHITE if not page_passed[cur_page] else cfg.C_GREEN, font=p4.FONT_DOT, size=16)

        # 底部 RTC 时间
        try:
            _, _, _, hh, mm, ss = p4.rtc_get_time()
            t_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
        except:
            t_str = "--:--:--"
        p4.fill_rect(x=550, y=560, w=120, h=30, color=cfg.C_BLACK)
        p4.text(t_str, 560, 566, color=cfg.C_WHITE, font=p4.FONT_DOT, size=16)

    def draw_card_base(self, cur_page):
        p4.fill_rect(x=40, y=56, w=944, h=488, color=cfg.C_DARK)
        p4.fill_rect(x=42, y=58, w=940, h=34, color=cfg.C_PANEL)
        p4.text(f"检测步骤 {cur_page+1}/{len(cfg.PAGE_NAMES)}: {cfg.PAGE_NAMES[cur_page]}", 55, 66, color=cfg.C_WHITE, font=p4.FONT_YAHEI, size=24)

    def check_navigation(self, pts, cur_page, page_passed):
        """处理底部前进与跳过按钮的边沿触发"""
        if len(pts) > 0:
            tx, ty = pts[0]
            if not self.touch_pressed and ty >= 545:
                # 跳过
                if 700 <= tx <= 830:
                    self.touch_pressed = True
                    return "skip"
                # 下一项
                elif 850 <= tx <= 1000:
                    if page_passed[cur_page]:
                        self.touch_pressed = True
                        return "next"
        else:
            self.touch_pressed = False
        return None
