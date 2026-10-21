# pages/p6_bus.py - 工业总线收发联动 (CAN/TWAI 直连 TJA1051，RS-485 自动流控)
import p4
import config as cfg

class PageBus:
    def __init__(self):
        self.initialized = False
        self.can_tx_count = 0
        self.rs485_tx_count = 0

    def start(self):
        if not self.initialized:
            # CAN: TX 22 / RX 21, 500kbps (避开背光 GPIO 32)
            p4.can_init(baud=500000, tx=cfg.PIN_CAN_TX, rx=cfg.PIN_CAN_RX)
            # RS-485: TX 26 / RX 27, 115200bps
            p4.rs485_init(baud=115200, tx=cfg.PIN_RS485_TX, rx=cfg.PIN_RS485_RX)
            self.initialized = True

    def update(self):
        self.start()
        # 向 CAN 总线推入标准遥测测试帧
        if p4.can_send(id=0x123, data=b"\x11\x22\x33\x44"):
            self.can_tx_count += 1
            
        # 向 RS-485 发送心跳包
        p4.rs485_write(b"RS485-POLL-OK\n")
        self.rs485_tx_count += 1
        
        return self.can_tx_count >= 5

    def render(self):
        p4.text(f"TWAI / CAN 端子 : TXD: GPIO {cfg.PIN_CAN_TX}, RXD: GPIO {cfg.PIN_CAN_RX} (直连板载 TJA1051 收发器)", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text(f"RS-485 工业端子 : TXD: GPIO {cfg.PIN_RS485_TX}, RXD: GPIO {cfg.PIN_RS485_RX} (官方硬件自动流控电路)", 65, 135, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        p4.text(f"外部 I2C 端子   : SDA: GPIO {cfg.PIN_I2C_SDA}, SCL: GPIO {cfg.PIN_I2C_SCL} (共享 I2C0 物理总线)", 65, 160, color=cfg.C_WHITE, font=p4.FONT_DOT, size=16)
        
        p4.fill_rect(x=65, y=200, w=890, h=315, color=cfg.C_BLACK)
        p4.text(f"CAN 队列推流统计 : {self.can_tx_count} 帧推入控制器 FIFO (目标: 5 帧)", 90, 230, color=cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        p4.text(f"RS-485 广播状态  : 已推发 {self.rs485_tx_count} 组自动流控心跳报文", 90, 270, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        p4.text("冲突排除说明     : CAN 引脚严格对齐原理图，完全解除与背光 GPIO 32 的冲突", 90, 310, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        
        if self.can_tx_count >= 5:
            p4.text("工业通信总线自检通过！请点击【下一项】", 90, 360, color=cfg.C_GREEN, font=p4.FONT_YAHEI, size=24)
