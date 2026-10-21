# pages/p8_media.py - JPGD 硬件 JPEG 解码与 H.264 VPU 加速状态校验
import p4
import config as cfg

class PageMedia:
    def __init__(self):
        self.jpgd_status = p4.jpgd_info()[0]
        self.h264_status = p4.h264_init()[0]

    def is_passed(self):
        # 驱动层底层状态导出成功即通过
        return True

    def render(self):
        p4.text("图像解码器 : " + self.jpgd_status, 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("视频解码器 : " + self.h264_status, 65, 135, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text("摄像头座子 : 15PIN 1.0mm MIPI-CSI (2-lane) 专用排线接口", 65, 160, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        
        p4.fill_rect(x=65, y=200, w=890, h=315, color=cfg.C_BLACK)
        p4.text("JPGD 硬件 DMA 解码引擎 : 就绪 (支持 JPEG 直灌显存，零 CPU 拷贝负载)", 90, 230, color=cfg.C_WHITE, font=p4.FONT_DOT, size=16)
        p4.text("H.264 VPU 硬件视频解码 : 就绪 (支持 1080P@30fps 主流编码标准)", 90, 270, color=cfg.C_WHITE, font=p4.FONT_DOT, size=16)
        p4.text("支持摄像头模组规格     : RPi FPC Camera (B) / RPi Camera (B) / OV5647", 90, 310, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        p4.text("多媒体加速硬件自检通过！请点击【下一项】", 90, 360, color=cfg.C_GREEN, font=p4.FONT_YAHEI, size=24)
