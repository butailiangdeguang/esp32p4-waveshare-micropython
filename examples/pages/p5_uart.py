import p4
import config as cfg

class PageUART:
    def __init__(self):
        self.initialized = False
        self.seq = 0
        self.passed_frames = 0
        self.lost_frames = 0

    def start(self):
        if not self.initialized:
            p4.uart_init(baud=115200, tx=cfg.PIN_UART1_TX, rx=cfg.PIN_UART1_RX)
            self.initialized = True

    def update(self):
        self.start()
        self.seq += 1
        pkt = f"UART-P5:{self.seq:05d}\n".encode()
        p4.uart_write(pkt)
        rx = p4.uart_read(len=32, timeout=0)
        if rx == pkt:
            self.passed_frames += 1
        else:
            self.lost_frames += 1
        return self.passed_frames >= 3

    def render(self):
        p4.text(f"端子定义 : 独立 UART1 (TX: GPIO {cfg.PIN_UART1_TX}, RX: GPIO {cfg.PIN_UART1_RX})", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("硬件隔离 : 避开 C6 SDIO (14-19)，保护原生调试串口稳定", 65, 135, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("测试要求 : 短接 35 与 36 排针自发自收，成功 >= 3 帧即通过：", 65, 160, color=cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        
        p4.fill_rect(x=65, y=200, w=890, h=315, color=cfg.C_BLACK)
        ok = (self.passed_frames >= 3)
        p4.text(f"自测状态 : {'回环通过 (PASS)' if ok else '未闭环 (请短接 35 与 36)'}", 90, 230, color=cfg.C_GREEN if ok else cfg.C_RED, font=p4.FONT_YAHEI, size=24)
        p4.text(f"成功发送并校验 : {self.passed_frames} 帧 (目标: 3 帧)", 90, 280, color=cfg.C_WHITE, font=p4.FONT_DOT, size=16)
        p4.text(f"丢失/未接收帧数 : {self.lost_frames} 帧", 90, 320, color=cfg.C_GRAY, font=p4.FONT_DOT, size=16)
