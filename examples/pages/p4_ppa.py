import p4
import framebuf
import config as cfg

class PagePPA:
    def __init__(self):
        self.WIN_W, self.WIN_H = 320, 220
        self.surf = p4.create_surface(self.WIN_W, self.WIN_H)
        fb = framebuf.FrameBuffer(self.surf, self.WIN_W, self.WIN_H, framebuf.RGB565)
        fb.fill(cfg.C_PANEL)
        fb.fill_rect(0, 0, self.WIN_W, 26, cfg.C_ACCENT)
        fb.rect(0, 0, self.WIN_W, self.WIN_H, cfg.C_WHITE)
        fb.text("PPA Hardware Surface", 10, 8, cfg.C_WHITE)
        fb.fill_rect(15, 38, self.WIN_W - 30, 75, cfg.C_BLACK)
        fb.text("PPA Hardware Blit OK", 25, 50, cfg.C_GREEN)
        fb.text("Drag to Pass Test", 25, 75, cfg.C_CYAN)
        cx, cy = self.WIN_W // 2, 160
        fb.line(cx - 25, cy, cx + 25, cy, cfg.C_RED)
        fb.line(cx, cy - 25, cx, cy + 25, cfg.C_RED)
        fb.rect(cx - 12, cy - 12, 24, 24, cfg.C_WHITE)

        self.win_x, self.win_y = 600, 160
        self.prev_pos = [(self.win_x, self.win_y), (self.win_x, self.win_y)]
        self.win_drag = False
        self.off_x, self.off_y = 0, 0
        self.drag_dist = 0

    def handle_touch(self, pts):
        if len(pts) > 0:
            tx, ty = pts[0]
            if self.win_drag:
                new_x = max(50, min(tx - self.off_x, 974 - self.WIN_W))
                new_y = max(95, min(ty - self.off_y, 530 - self.WIN_H))
                self.drag_dist += abs(new_x - self.win_x) + abs(new_y - self.win_y)
                self.win_x, self.win_y = new_x, new_y
            else:
                if self.win_x <= tx <= self.win_x + self.WIN_W and self.win_y <= ty <= self.win_y + 35:
                    self.win_drag = True
                    self.off_x = tx - self.win_x
                    self.off_y = ty - self.win_y
        else:
            self.win_drag = False

    def render_fast_drag(self, buf_idx):
        old_x, old_y = self.prev_pos[buf_idx]
        p4.fill_rect(x=old_x, y=old_y, w=self.WIN_W, h=self.WIN_H, color=cfg.C_DARK)
        p4.blit(src=self.surf, src_w=self.WIN_W, src_h=self.WIN_H, dst_x=self.win_x, dst_y=self.win_y)
        self.prev_pos[buf_idx] = (self.win_x, self.win_y)

    def render_static(self, passed):
        p4.text("PPA 硬件引擎 : 片上 2D 独立 DMA 高速搬运 (Zero CPU Load)", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("显存架构     : 双缓冲物理内存对齐，无撕裂无残影", 65, 135, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        txt = f"测试要求     : 手指拖动右侧窗口 (位移: {self.drag_dist}/200 px)"
        p4.text(txt, 65, 165, color=cfg.C_GREEN if passed else cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        p4.blit(src=self.surf, src_w=self.WIN_W, src_h=self.WIN_H, dst_x=self.win_x, dst_y=self.win_y)
