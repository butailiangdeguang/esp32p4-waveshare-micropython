# pages/p7_audio.py - ES8311 放音 + NS4150B 功放 (GPIO 53) + ES7210 双麦波形
import p4
import config as cfg

class PageAudio:
    def __init__(self):
        self.initialized = False
        self.mic_levels = [0] * 24

    def start(self):
        if not self.initialized:
            p4.audio_init()          # 拉高 GPIO 53 使能功放，拉起 I2S 通道
            p4.audio_volume(80)
            p4.mic_init(mode=0)      # 0: AEC 回声消除与双麦降噪混合模式
            self.initialized = True

    def update(self):
        self.start()
        # 录制 128 采样点原始 PCM 音频流
        pcm_chunk = p4.mic_record(samples=128)
        if len(pcm_chunk) >= 48:
            self.mic_levels.pop(0)
            # 计算音频能量振幅
            energy = sum(abs(b - 128) for b in pcm_chunk[:48]) // 48
            self.mic_levels.append(energy)
        
        # 只要麦克风拾取到环境音或说话能量即判定通过
        return any(v > 5 for v in self.mic_levels)

    def render(self):
        p4.text("音频输出芯片 : ES8311 Codec (I2S0: GPIO 9-13)", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("扬声器功放   : NS4150B (PH2.0 喇叭座, GPIO 53 PA使能激活)", 65, 135, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("ES7210 AEC   : 贴片双硅麦阵列降噪拾音与回声消除 (AEC 硬件模式)", 65, 160, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        
        p4.fill_rect(x=65, y=200, w=890, h=315, color=cfg.C_BLACK)
        p4.text("实时双麦拾音音频能量图谱 (请对着板载贴片麦克风吹气或说话):", 90, 220, color=cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        
        # 动态绘制 24 根拾音能量柱
        for i in range(24):
            val = self.mic_levels[i]
            bar_h = min(int(val * 1.8), 170)
            bx = 100 + i * 35
            by = 480 - bar_h
            p4.fill_rect(x=bx, y=by, w=22, h=bar_h, color=cfg.C_GREEN if bar_h < 120 else cfg.C_RED)
        
        if any(v > 5 for v in self.mic_levels):
            p4.text("双麦拾音阵列响应正常！请点击【下一项】", 90, 260, color=cfg.C_GREEN, font=p4.FONT_YAHEI, size=24)
        else:
            p4.text("等待拾音信号... 请对麦克风发出声音", 90, 260, color=cfg.C_GRAY, font=p4.FONT_DOT, size=16)
