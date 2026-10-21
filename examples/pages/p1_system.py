import p4
import config as cfg

class PageSystem:
    def __init__(self):
        self.temp_history = [35.0] * 32
        self.pwm_duty = 0
        self.pwm_step = 2048
        self.pwm_freq = 1000

    def update(self):
        cur_temp = p4.temperature()
        self.temp_history.pop(0)
        self.temp_history.append(cur_temp)
        
        self.pwm_duty += self.pwm_step
        if self.pwm_duty >= 65535 or self.pwm_duty <= 0:
            self.pwm_step = -self.pwm_step
        p4.pwm(cfg.PIN_PWM, freq=self.pwm_freq, duty=self.pwm_duty, channel=0)
        
        # 温度在合理区间且采样满 8 次即通过
        passed = (len(self.temp_history) >= 8 and 20.0 <= cur_temp <= 80.0)
        return passed

    def render(self, cur_temp):
        p4.text("处理器核心 : 双核 RISC-V 400MHz 锁频 | 算力浮点单元激活", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("片上高频内存 : Hex-SPI 160MHz 32MB 物理 PSRAM", 65, 135, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text(f"芯片核心温感 : {cur_temp:.2f} °C", 65, 160, color=cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        p4.text(f"PWM 通道 0  : GPIO {cfg.PIN_PWM} | 频率: {self.pwm_freq}Hz | 占空比: {int(self.pwm_duty/65535*100)}%", 65, 185, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        
        # 温度曲线
        p4.fill_rect(x=65, y=225, w=890, h=290, color=cfg.C_BLACK)
        p4.text("片上硬件真实温度动态走势 (200ms采样):", 80, 235, color=cfg.C_GRAY, font=p4.FONT_DOT, size=16)
        for i in range(len(self.temp_history) - 1):
            t1 = self.temp_history[i]
            t2 = self.temp_history[i + 1]
            y1 = 490 - int((t1 - 25.0) / 35.0 * 220)
            y2 = 490 - int((t2 - 25.0) / 35.0 * 220)
            x1 = 80 + int(i * (850 / len(self.temp_history)))
            x2 = 80 + int((i + 1) * (850 / len(self.temp_history)))
            p4.fill_rect(x=x1, y=min(y1, y2), w=max(x2 - x1, 1), h=max(abs(y2 - y1), 2), color=cfg.C_RED)
