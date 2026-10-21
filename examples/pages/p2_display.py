# pages/p2_display.py - 屏幕全色域坏点校准与色阶检测
import p4
import config as cfg

class PageDisplay:
    def __init__(self):
        self.color_patterns = [
            ("纯红色检测 (Red)", cfg.C_RED),
            ("纯绿色检测 (Green)", cfg.C_GREEN),
            ("纯蓝色检测 (Blue)", cfg.C_BLUE),
            ("纯白色检测 (White)", cfg.C_WHITE),
            ("纯黑暗场检测 (Black)", cfg.C_BLACK),
        ]
        self.color_idx = 0
        self.tested_flags = [False] * len(self.color_patterns)

    def handle_touch(self, pts):
        """点击屏幕区域单次循环切换色彩"""
        if len(pts) > 0:
            self.tested_flags[self.color_idx] = True
            self.color_idx = (self.color_idx + 1) % len(self.color_patterns)
            return True
        return False

    def is_passed(self):
        # 切换核验过至少 3 种纯色即可通过
        return sum(self.tested_flags) >= 3

    def render(self):
        c_title, c_val = self.color_patterns[self.color_idx]
        # 铺满工作区进行纯色坏点肉眼筛查
        p4.fill_rect(x=40, y=56, w=944, h=488, color=c_val)
        
        # 浮动提示卡片
        p4.fill_rect(x=60, y=70, w=540, h=65, color=cfg.C_BLACK)
        p4.text(f"屏幕坏点检测: {c_title}", 75, 80, color=cfg.C_WHITE, font=p4.FONT_YAHEI, size=24)
        p4.text(f"点击屏幕区域切换色彩 (已检测: {sum(self.tested_flags)}/{len(self.color_patterns)} 色)", 75, 112, color=cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
