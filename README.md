# Waveshare ESP32-P4-WIFI6-Touch-LCD-7B-C MicroPython BSP

专为 **微雪 (Waveshare) ESP32-P4-WIFI6-Touch-LCD-7B-C** 评估套件深度定制的高性能 MicroPython C 扩展驱动与整机测试系统。

本项目利用 ESP32-P4 的高性能多媒体管线与双核 RISC-V 400MHz 算力，打通了 1024×600 MIPI-DSI 双显存 Framebuffer、片上 2D 硬件加速引擎 (PPA)、GT911 原生电容触控、全字库中文字模引擎、ES8311 音频编解码输出、ES7210 四通道双麦 AEC 回声消除与降噪拾音，以及工业现场通信总线（CAN/TWAI、RS-485、独立安全 UART1、I2C）。

---

> ### ⚠️ 重要硬件已知问题说明 (Hardware Known Issue)
> 
> * **板载「USB TO UART」接口由于未知原因当前无法使用**（接入后会导致系统总线异常、死锁或无法建立稳定握手）。
> * **推荐烧录与调试方案**：
>   1. 请统一连接板载的 **「Type-C USB1.1 FS 直出接口」**（ESP32-P4 原生 USB-Serial-JTAG 端口）进行供电、固件烧录、REPL 终端交互与 Thonny 连接；
>   2. 外部设备串口通信请使用 **PH2.0 4PIN 独立 UART1 端子**（TX: GPIO 35 / RX: GPIO 36），切勿使用板载 USB 转串口桥接芯片。

---

## 一、 硬件规格与系统拓扑

* **主控核心**：ESP32-P4NRW32X，双核 32 位 RISC-V 处理器，锁频 400MHz。
* **物理内存拓扑**：
  * **片外 PSRAM**：32MB Hex-SPI 高速物理显存池（160MHz 双沿采样，实测带宽超 800MB/s）。
  * **片外 Flash**：32MB Nor Flash（8MB 固件内核与字库分区 + 24MB VFS 存储）。
* **显示子系统**：
  * 7 英寸 IPS 工业级电容液晶屏，分辨率 1024×600。
  * 2-Lane MIPI-DSI 硬件物理通道（EK79007 驱动 IC）。
  * 底层启用双缓冲 Framebuffer（每个缓冲区 1024×600×2 = 1,228,800 字节），对齐硬件 VSYNC 刷新与 D-Cache (`esp_cache_msync`) 物理内存同步。
* **电容触控**：GT911 原生 5 点多点触控（挂载 I2C0，180° 旋转对齐，读取后自动复位状态寄存器 `0x814E` 防止硬件 Buffer 粘滞）。
* **2D 硬件加速器 (PPA)**：Pixel Processing Accelerator，独立非阻塞 DMA 传输，支持 2D 像素块直灌、色彩穿透（Color Keying）、平滑缩放与旋转。
* **多媒体硬解**：片上集成硬件 JPEG 解码器 (JPGD) 与 H.264 VPU 硬件视频解码引擎。
* **无线协处理器**：ESP32-C6-MINI-1 芯片，通过板载 SDIO 2.0 高速总线直连主控，提供原生 Wi-Fi 6 (802.11ax) 与 BLE 5.0 Radio。
* **音频子系统**：
  * **输出**：ES8311 低功耗音频 Codec（I2S 接口）+ NS4150B 扬声器功放（GPIO 53 硬件使能）。
  * **输入**：ES7210 四通道音频 ADC + 板载贴片双数字硅麦矩阵，支持硬件 AEC 回声消除与降噪算法。

---

## 二、 严格验证的引脚映射与冲突规避表

| 硬件功能模块 | 对应引脚 (GPIO) | 说明与避坑规范 |
| :--- | :--- | :--- |
| **独立通用 UART1 端子** | **TX: GPIO 35<br>RX: GPIO 36** | **严禁动用 GPIO 14~19**（属于 C6 协处理器 SDIO 总线，碰触会导致总线死锁与串口中断）。 |
| **CAN / TWAI 工业端子** | **TX: GPIO 22<br>RX: GPIO 21** | 硬件直连板载 **TJA1051** CAN 收发芯片。**绝对不能配置为 GPIO 32**（GPIO 32 为屏幕物理背光控制引脚）。 |
| **RS-485 工业端子** | **TX: GPIO 26<br>RX: GPIO 27** | 板载硬件自动收发半双工流控电路，无需软件翻转 RTS/DE 即可自收发。 |
| **原生/外部 I2C 总线** | **SDA: GPIO 7<br>SCL: GPIO 8** | 共享原生 I2C0 总线，挂载 GT911、PCF8563 RTC、ES8311、ES7210 及 PH2.0 I2C 端子。 |
| **音频 I2S 与功放使能** | **SCLK: 12, MCLK: 13, LRCK: 10<br>DOUT: 9, DSIN: 11, PA使能: 53** | 扬声器放音前必须拉高 GPIO 53 (`BSP_POWER_AMP_IO`) 开启功放供电。 |
| **屏幕物理背光与复位** | **背光: GPIO 32<br>复位: GPIO 33** | 背光支持硬件 PWM 调光控制（0~100 级无级调光）。 |
| **Micro SD (TF 卡槽)** | **GPIO 39 ~ GPIO 44** | 板载 4-wire SDIO 3.0 接口。 |

---

## 三、 C 模块 `p4` 核心 API 手册

### 1. 显存与屏幕显示控制

```python
import p4

# 初始化 MIPI-DSI 总线及底层双显存 (分配 2.4MB PSRAM)
p4.display_init()

# 设置屏幕背光 (0~100)
p4.backlight(85)

# 设定旋转方向 (默认 180 对齐微雪外壳装配)
p4.rotation(180)

# 快速填充实心矩形 (RGB565 格式)
p4.fill_rect(x=0, y=0, w=1024, h=600, color=0x0841)

# 提交显存翻转 (等待 PPA 信号量，执行 esp_cache_msync 刷新物理内存并对齐 VSYNC)
p4.flip()

# 查询显存池信息: (硬件显存字节数, 自定义 Surface 显存字节数, 剩余可用 PSRAM)
hw_vram, surf_vram, free_psram = p4.get_vram_info()
```

### 2. 离屏 Surface 与 PPA 2D 硬件加速

```python
import framebuf

# 从 32MB PSRAM 中申请一块 64 字节对齐的离屏画布
WIN_W, WIN_H = 320, 240
surf = p4.create_surface(WIN_W, WIN_H)

# 绑定 MicroPython 原生 framebuf 库
fb = framebuf.FrameBuffer(surf, WIN_W, WIN_H, framebuf.RGB565)
fb.fill(0x18C3)
fb.rect(0, 0, WIN_W, WIN_H, 0xFFFF)
fb.text("PPA Hardware Surface", 10, 10, 0xFFFF)

# 使用 PPA 硬件 2D DMA 直灌显存 (无需 CPU 参与逐像素拷贝，支持透明色穿透与缩放)
# scale: 缩放比例 (浮点数)；key: 透明色彩键 (-1 表示不透明直刷)
p4.blit(src=surf, src_w=WIN_W, src_h=WIN_H, dst_x=100, dst_y=50, scale=1.0, key=-1)
p4.flip()
```

### 3. 多字库原生中文字符渲染系统

内置 95 个 ASCII 字符与 6763 个常用 GB2312 中文字模库，支持 UTF-8 编码原生解析与二分法高速检索：

```python
# 常量定义: p4.FONT_DOT (0: 16点阵等宽), p4.FONT_YAHEI (1: 24点阵雅黑), p4.FONT_SONG (2: 24点阵宋体)

# 16 点阵标准等宽工业字模
p4.text("系统动力: 双核 RISC-V 400MHz", 50, 100, color=0x07E0, font=p4.FONT_DOT, size=16)

# 24 点阵微软雅黑平滑抗锯齿字模
p4.text("微雪 ESP32-P4 高性能物联网控制中心", 50, 140, color=0xFFFF, font=p4.FONT_YAHEI, size=24)

# 24 点阵经典宋体字模 (适合古典诗词与排版)
p4.text("天下英雄谁敌手？曹刘。生子当如孙仲谋。", 50, 180, color=0xFFE0, font=p4.FONT_SONG, size=24)
```

### 4. 电容触控 (GT911)

底层驱动在每次采样后自动向 GT911 寄存器 `0x814E` 写入 `0x00`，彻底防止硬件状态缓冲粘连：

```python
p4.touch_init()

# 轮询读取当前触控点 (返回元组: ((x1, y1), (x2, y2), ...)，无触摸返回空元组)
pts = p4.touch_read()
if len(pts) > 0:
    for i, pt in enumerate(pts):
        print(f"触控点 #{i+1}: X={pt[0]}, Y={pt[1]}")
```

### 5. 工业总线与安全端子通信

```python
# 1. 独立 UART1 端子 (安全通用引脚 35/36，带零等待非阻塞防护)
p4.uart_init(baud=115200, tx=35, rx=36)
p4.uart_write(b"DEVICE_READY\n")
data = p4.uart_read(len=64, timeout=0) # 0 等待，无数据立即返回 b''，绝不死锁

# 2. CAN / TWAI 控制器 (直连板载 TJA1051)
p4.can_init(tx=22, rx=21, baud=500000)
p4.can_send(id=0x123, data=b"\x01\x02\x03\x04", ext=False)
p4.can_deinit()

# 3. RS-485 工业半双工通信
p4.rs485_init(tx=26, rx=27, baud=115200)
p4.rs485_write(b"MODBUS_QUERY\n")

# 4. 共享 I2C0 外部设备通道
p4.ext_i2c_init()
```

### 6. 音频、双麦 AEC 降噪与片上外设

```python
# 1. 音频输出与扬声器功放使能 (GPIO 53)
p4.audio_init()
p4.audio_volume(85) # 硬件音量 (0~100)

# 2. ES7210 AEC 双麦克风采集与降噪 (0: 降噪混合, 1: 左麦, 2: 右麦, 3: 立体声)
p4.mic_init(mode=0)
pcm_data = p4.mic_record(samples=256) # 读取原始 PCM 音频流

# 3. 片上温度传感器
temp_c = p4.temperature()
print("芯片核心温度:", temp_c)

# 4. PCF8563 硬件 RTC
p4.rtc_init()
year, month, day, hour, minute, second = p4.rtc_get_time()

# 5. 硬件 LEDC PWM 输出 (14-bit 分辨率, duty 0~65535)
p4.pwm(pin=20, freq=1000, duty=32768, channel=0)
p4.pwm_deinit(channel=0)

# 6. BTLDG 物联网协议引擎快速打包
p4.bld_init(token="btldg_iot_token_2026", node_id=101)
pkt = p4.bld_pack(type="TELEMETRY", val1=temp_c, val2=100.0)
# 输出: BLD:101:TELEMETRY:35.20:100.00:btldg_iot_token_2026
```

---

## 四、 项目工程目录与模块化设计

项目采用了完全解耦的模块化设计，每个硬件功能独占一个独立页面文件：

```text
esp32p4-waveshare-micropython/
├── README.md               # 项目主说明文档
├── .gitignore              # Git 忽略配置
├── config.py               # 硬件引脚分配、全局颜色常量、阈值配置
├── ui_engine.py            # 双缓冲管理、标题栏/任务栏公共绘制、边沿防抖触控状态机
├── main.py                 # 主程序入口：流水线调度、切页与主事件循环
├── pages/                  # 独立测试页面（每个页面独占一个文件）
│   ├── __init__.py         # 模块包聚合导出
│   ├── p1_system.py        # 关卡 1：系统动力、温感、PWM、RTC
│   ├── p2_display.py       # 关卡 2：屏幕全色域坏点检测
│   ├── p3_touch.py         # 关卡 3：GT911 5 指多点触控与涂鸦画板
│   ├── p4_ppa.py           # 关卡 4：PPA 2D 硬件 DMA 窗口拖拽 (60 FPS 无残影)
│   ├── p5_uart.py          # 关卡 5：独立端子 UART1 回环测试
│   ├── p6_bus.py           # 关卡 6：CAN (TWAI) 与 RS-485 工业总线
│   ├── p7_audio.py         # 关卡 7：ES8311 放音与 ES7210 双麦波形
│   ├── p8_media.py         # 关卡 8：JPGD 与 H.264 VPU 加速状态
│   └── p9_wifi.py          # 关卡 9：C6 Wi-Fi 6 扫描与 BTLDG 网关协议
├── src/
│   ├── modwaveshare_p4.c   # MicroPython 原生 C 驱动扩展核心
└── firmware/
    ├── bootloader.bin      # 编译生成的二级引导程序
    ├── partition-table.bin # 32MB 分区表
    └── micropython.bin     # 包含 p4 C 驱动的 MicroPython 运行时全量固件
```

---

## 五、 编译与刷写指南

### 1. 编译环境搭建 (Ubuntu 22.04 / 24.04 VM)

```bash
# 1. 激活 ESP-IDF v5.3+ 环境变量
. $HOME/esp/esp-idf/export.sh

# 2. 进入 MicroPython ESP32 端口目录
cd ~/micropython/ports/esp32

# 3. 编译定制固件 (C6_WIFI 变体集成 SDIO 协议栈)
rm -f build-ESP32_GENERIC_P4-C6_WIFI/frozen_content.c
make -j$(nproc) BOARD=ESP32_GENERIC_P4 BOARD_VARIANT=C6_WIFI
```

### 2. 固件刷写 (Windows PowerShell 示例)

开发板连接电脑 **「USB 1.1 FS 直出 Type-C」** 接口，在 PowerShell 中执行全量写入：

```powershell
Set-Location "$HOME\Desktop\p4_firmware"

# 同步提取虚拟机编译产物
scp butailiangdeguang@<虚拟机IP>:/home/butailiangdeguang/micropython/ports/esp32/build-ESP32_GENERIC_P4-C6_WIFI/bootloader/bootloader.bin .
scp butailiangdeguang@<虚拟机IP>:/home/butailiangdeguang/micropython/ports/esp32/build-ESP32_GENERIC_P4-C6_WIFI/partition_table/partition-table.bin .
scp butailiangdeguang@<虚拟机IP>:/home/butailiangdeguang/micropython/ports/esp32/build-ESP32_GENERIC_P4-C6_WIFI/micropython.bin .

# 全量刷写 32MB Flash (示例端口 COM84)
python -m esptool --chip esp32p4 -p COM84 --no-stub -b 115200 write_flash `
    --flash_mode dio `
    --flash_size 32MB `
    --flash_freq 80m `
    --no-compress `
    0x2000 bootloader.bin `
    0x8000 partition-table.bin `
    0x10000 micropython.bin
```

---

## 六、 常见问题与排障指南 (FAQ)

### 1. 为什么拖拽窗口会出现“重影”或“纸牌拖尾”？
* **根因**：固件启用了硬件双缓冲（Buffer 0 与 Buffer 1 轮流交替显示）。在拖拽窗口时，如果只记录了一组旧坐标，另一块显存缓冲区内的旧图形并没有被抹平，导致两块显存交替呈现时出现拖尾。
* **解决方案**：使用 `prev_pos = [(x, y), (x, y)]` 为两块显存分别维护各自上一帧的旧矩形坐标。每次绘制前，调用 `p4.fill_rect` 仅抹除当前 Buffer 对应的旧矩形，随后立即使用 PPA 贴入新窗口，严禁全屏重画。

### 2. 为什么电容触摸点按一次会跳两步（连击触发两次）？
* **根因**：物理点按时间（约 150~300ms）远大于主循环采样周期（15ms）。如果采用电平触发模式，系统在一次按压过程中会多次抓到触摸点。
* **解决方案**：引入 `touch_pressed` 状态锁实现边沿触发。只有当检测到 `len(pts) > 0` 且 `not touch_pressed` 时才响应按键事件并置位锁死；只有在检测到 `len(pts) == 0`（手指完全离开屏幕）时才释放状态锁。

### 3. 为什么通信总线会导致系统假死或 USB 调试中断？
* **根因**：误将 ESP32-C6 占用的 SDIO 引脚（GPIO 14~19）重新复用为普通 UART 或 GPIO，破坏了主控与 C6 协处理器的硬件通信握手。
* **解决方案**：所有用户级通用串口通信统一使用独立端子 **GPIO 35 (TX) / GPIO 36 (RX)**，且接收函数超时必须设为 `timeout=0`（纯非阻塞），即使未插外部设备也绝不发生总线死锁。

---

## 许可证 (License)

本项目遵循 **MIT License** 开源许可证。欢迎在保留原始版权声明的前提下进行商用、二次修改与移植开发。
