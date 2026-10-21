# pages/p3_touch.py - 原生 5 指多点触控与涂鸦划线画板
import p4
import config as cfg

class PageTouch:
    def __init__(self):
        self.touch_trails = []
        self.peak_points = 0

    def handle_touch(self, pts):
        if len(pts) > 0:
            self.peak_points = max(self.peak_points, len(pts))
            for pt in pts:
                tx, ty = pt
                # 仅捕获画板区域内的轨迹坐标
                if 65 <= tx <= 955 and 190 <= ty <= 520:
                    self.touch_trails.append((tx, ty))
                    if len(self.touch_trails) > 300:
                        self.touch_trails.pop(0)

    def is_passed(self):
        # 涂鸦有效轨迹点累计达 60 即可通过
        return len(self.touch_trails) >= 60

    def render(self):
        p4.text("触控芯片 : GT911 硬件 I2C0 总线 (SDA: GPIO 7, SCL: GPIO 8)", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("硬件特性 : 支持最高 5 指同时多点输入 | 180° 装配对齐", 65, 135, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        
        status_txt = f"测试要求 : 在下方黑色画板划线涂鸦 (当前峰值: {self.peak_points} 指, 轨迹点: {len(self.touch_trails)}/60)"
        p4.text(status_txt, 65, 160, color=cfg.C_GREEN if self.is_passed() else cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        
        # 黑色画板卡片区域 (65, 190, 890, 330)
        p4.fill_rect(x=65, y=190, w=890, h=330, color=cfg.C_BLACK)
        p4.text("多指划线画板区 (触控轨迹点满 60 即可通过)", 80, 205, color=cfg.C_GRAY, font=p4.FONT_DOT, size=16)
        
        # 渲染捕获的连线与笔迹点
        for pt in self.touch_trails:
            p4.fill_rect(x=pt[0] - 2, y=pt[1] - 2, w=5, h=5, color=cfg.C_CYAN)
