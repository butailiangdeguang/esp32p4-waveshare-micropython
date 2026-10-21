# Waveshare ESP32-P4-WIFI6-Touch-LCD-7B-C MicroPython BSP

专为 **微雪 (Waveshare) ESP32-P4-WIFI6-Touch-LCD-7B-C** 评估套件定制的高性能 MicroPython C 扩展驱动与固件。

---

> ⚠️ **已知硬件问题说明 (Hardware Known Issue)**
> 
> * **板载「USB TO UART」接口由于未知原因当前无法使用**（接入后会导致系统总线异常、死锁或无法建立稳定握手）。
> * **烧录与调试方案**：
>   1. 请统一连接板载的 **「Type-C USB1.1 FS 直出接口」**（ESP32-P4 原生 USB-Serial-JTAG 端口）进行供电、固件烧录、REPL 终端交互与 Thonny 连接；
>   2. 外部设备串口通信请使用 **PH2.0 4PIN 独立 UART1 端子**（TX: GPIO 35 / RX: GPIO 36），切勿使用板载 USB 转串口桥接芯片。

---

## 核心特性

- **显示与硬件双缓冲**：1024×600 MIPI-DSI (EK79007)，基于 32MB PSRAM 的物理双缓冲显存，对齐硬件 VSYNC 刷新。
- **2D 硬件加速**：片上 PPA 引擎直灌，支持非阻塞 DMA 图像搬运、色彩穿透与实时缩放。
- **中文字库引擎**：内置 ASCII 符号全集与常用 GB2312 汉字字模库，原生支持 UTF-8 解析与 16/24 点阵渲染。
- **工业控制端子**：已验证的 CAN/TWAI (TJA1051)、RS-485 自动半双工流控、独立 UART1 及 I2C 通道。
- **音频与双麦降噪**：ES8311 音频 Codec、NS4150B 扬声器功放 (GPIO 53) 及 ES7210 AEC 双麦阵列。
- **无线协处理器**：ESP32-C6 (Wi-Fi 6 / BLE 5.0)，通过高速 SDIO 2.0 专线互联。

---

## 严格验证的引脚定义 (Pinout Mapping)

| 功能模块 | 对应 GPIO | 避坑与硬件冲突说明 |
| :--- | :--- | :--- |
| **独立通用 UART1 端子** | **TX: GPIO 35 / RX: GPIO 36** | **严禁动用 GPIO 14~19**（属于 C6 协处理器 SDIO 总线，碰触会导致总线死锁）。 |
| **CAN / TWAI 端子** | **TX: GPIO 22 / RX: GPIO 21** | 直连板载 TJA1051 收发器。**绝对不能配置为 GPIO 32**（GPIO 32 为屏幕背光控制引脚）。 |
| **RS-485 工业端子** | **TX: GPIO 26 / RX: GPIO 27** | 板载硬件自动收发半双工流控电路，无需外部流控引脚。 |
| **共享 I2C0 总线** | **SDA: GPIO 7 / SCL: GPIO 8** | 挂载 GT911 触控、PCF8563 RTC、ES8311、ES7210 及 PH2.0 I2C 端子。 |
| **音频 I2S 与功放使能** | **SCLK: 12, MCLK: 13, LRCK: 10, DOUT: 9, DSIN: 11, PA: 53** | 开启扬声器输出前必须拉高 GPIO 53 (`BSP_POWER_AMP_IO`)。 |
| **屏幕物理背光与复位** | **背光: GPIO 32 / 复位: GPIO 33** | 背光支持硬件 PWM 调光控制 (0~100 级调节)。 |
| **Micro SD 卡槽** | **GPIO 39 ~ GPIO 44** | 板载 4-wire SDIO 3.0 接口。 |

---

## 快速使用 (Quick Start)

### 1. 固件刷写 (通过原生 Type-C USB1.1 FS 直出接口)

```powershell
python -m esptool --chip esp32p4 -p <PORT> --no-stub -b 115200 write_flash \
    --flash_mode dio --flash_size 32MB --flash_freq 80m --no-compress \
    0x2000 firmware/bootloader.bin \
    0x8000 firmware/partition-table.bin \
    0x10000 firmware/micropython.bin

```

## 2. 基础调用范例

```python
import p4

# 初始化屏幕并开启背光
p4.display_init()
p4.backlight(85)

# 使用宋体渲染文本
p4.text("南乡子·登京口北固亭有怀", 120, 80, color=0xFFE0, font=p4.FONT_SONG, size=24)
p4.flip()

```
