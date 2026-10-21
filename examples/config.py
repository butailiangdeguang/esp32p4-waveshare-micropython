# config.py - 硬件参数与公共常量

# 颜色定义 (RGB565)
C_BLACK   = 0x0000
C_WHITE   = 0xFFFF
C_CYAN    = 0x07FF
C_YELLOW  = 0xFFE0
C_GREEN   = 0x07E0
C_RED     = 0xF800
C_DARK    = 0x0841
C_PANEL   = 0x18C3
C_GRAY    = 0x7BEF
C_DGRAY   = 0x39E7
C_ACCENT  = 0x03B9
C_ORANGE  = 0xFD20
C_BLUE    = 0x001F

# 屏幕尺寸
SCR_W = 1024
SCR_H = 600

# 硬件引脚规避与固定分配
PIN_PWM       = 20
PIN_UART1_TX  = 35
PIN_UART1_RX  = 36
PIN_CAN_TX    = 22
PIN_CAN_RX    = 21
PIN_RS485_TX  = 26
PIN_RS485_RX  = 27
PIN_I2C_SDA   = 7
PIN_I2C_SCL   = 8

# 测试关卡名称
PAGE_NAMES = [
    "1.动力时钟", "2.屏幕坏点", "3.多点触控",
    "4.PPA视窗", "5.UART端子", "6.工业总线",
    "7.音频双麦", "8.多媒体硬解", "9.WiFi与BLD"
]
