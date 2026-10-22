# Waveshare ESP32-P4 7-inch LCD Full Hardware Showcase
import p4
import time
import os
import gc

# 1. 硬件点火
p4.display_init()
p4.backlight(90)
p4.rtc_init()
p4.touch_init()

IMAGE_FILE = "bing_today.jpg"
has_wallpaper = False
raw_surf = None
scale_ratio = 1.0
t_dec_ms = 0

# 2. 检查并解码本地图片
if IMAGE_FILE in os.listdir():
    try:
        with open(IMAGE_FILE, "rb") as f:
            jpg_bytes = f.read()
        raw_surf = p4.create_surface(1920, 1080)
        t0 = time.ticks_ms()
        real_w, real_h = p4.decode_jpeg_mem(jpg_bytes, raw_surf)
        t_dec_ms = time.ticks_diff(time.ticks_ms(), t0)
        scale_ratio = 600.0 / real_h
        has_wallpaper = True
        del jpg_bytes
        gc.collect()
        print(f"[+] JPGD 解码成功: {real_w}x{real_h}, 耗时: {t_dec_ms} ms")
    except Exception as e:
        print("[-] 图像解码跳过:", e)

offset_x = (1024 - int(1920 * scale_ratio)) // 2 if has_wallpaper else 0

def render(show_bar=True):
    if has_wallpaper:
        p4.blit(src=raw_surf, src_w=1920, src_h=1080, dst_x=offset_x, dst_y=0, scale=scale_ratio, key=-1)
    else:
        p4.fill_rect(0, 0, 1024, 600, 0x0841)
    
    if show_bar:
        p4.fill_rect(40, 470, 944, 95, 0x10A2)
        p4.fill_rect(40, 470, 944, 3, 0x03B9)
        p4.text("《高清壁纸硬件展示》 【全屏满铺·无黑边】", 60, 485, color=0xFFFF, font=p4.FONT_YAHEI, size=24)
        
        cur_temp = p4.temperature()
        try:
            _, _, _, hh, mm, ss = p4.rtc_get_time()
            time_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
        except:
            time_str = "--:--:--"
        p4.text(f"规格：1920x1080 ；硬解：{t_dec_ms}ms ；温感：{cur_temp:.1f}℃ ；走时：{time_str} 。", 60, 525, color=0x07E0, font=p4.FONT_YAHEI, size=24)

# 写入双缓冲
for _ in range(2):
    render(True)
    p4.flip()

print("[+] 启动完成！轻触屏幕可切换底部状态栏显示/隐藏。")

bar_visible = True
touch_released = True

try:
    while True:
        touches = p4.touch_read()
        if touches and len(touches) > 0:
            if touch_released:
                touch_released = False
                bar_visible = not bar_visible
                render(bar_visible)
                p4.flip()
        else:
            touch_released = True
        time.sleep_ms(20)
except KeyboardInterrupt:
    print("\n[*] 退出。")
