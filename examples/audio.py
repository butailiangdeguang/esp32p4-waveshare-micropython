# audio.py - Waveshare ESP32-P4 v1.2.0 音频子系统综合测试
import p4
import time
import struct
import math

# 1. 硬件外设拉起与安全配置
p4.display_init()
p4.display_backlight(95)
p4.touch_init()

p4.audio_init()
p4.audio_pa(True)

current_volume = 20
p4.audio_volume(current_volume)  # 默认 20% 安全音量，防止自激啸叫

# 调用新增的麦克风采样配置函数：16kHz, 立体声双通道, 16-bit
p4.audio_mic_config(16000, 2, 16)
p4.audio_mic_gain(85)            # 设置适度增益

# 2. 生成一段 3 秒的五音阶测试音频缓存 (16kHz 立体声 PCM)
def generate_music_buffer():
    rate = 16000
    duration_sec = 3
    total_samples = rate * duration_sec
    buf = bytearray(total_samples * 4)  # 16-bit stereo: 4 字节/采样点
    
    notes = [261.63, 329.63, 392.00, 440.00, 523.25, 392.00]
    note_duration = total_samples // len(notes)
    
    for i in range(total_samples):
        note_idx = min(len(notes) - 1, i // note_duration)
        freq = notes[note_idx]
        val = int(math.sin(2 * math.pi * freq * (i / rate)) * 8000)
        struct.pack_into('<hh', buf, i * 4, val, val)
    return buf

music_buf = generate_music_buffer()
# 载入缓存并开启后台循环播放
p4.audio_load_buf(music_buf, 16000, True)

# 3. UI 界面布局与配色
C_BG            = 0x0821
C_PANEL         = 0x18C3
C_TITLEBAR      = 0x000F
C_GRID_LINE     = 0x11A4
C_GRID_CENTER   = 0x2287
C_MIC1_COLOR    = 0x07FF  # CH1 (左麦) 亮青色
C_MIC2_COLOR    = 0xFFE0  # CH2 (右麦) 亮黄色
C_TEXT_WHITE    = 0xFFFF
C_TEXT_MUTED    = 0x8C71
C_SLIDER_BG     = 0x2124
C_SLIDER_FILL   = 0x04DF  # 进度条亮蓝
C_BTN_GREEN     = 0x0D04
C_BTN_RED       = 0xA080
C_BTN_GRAY      = 0x39E7
C_ACCENT_GREEN  = 0x07E0

OSC_X, OSC_Y, OSC_W, OSC_H = 40, 70, 680, 460
MID_Y = OSC_Y + (OSC_H // 2)

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 740, 70, 250, 460
SLIDER_X, SLIDER_Y, SLIDER_W, SLIDER_H = 760, 160, 210, 32

BTN_PLAY_X, BTN_PLAY_Y, BTN_W, BTN_H = 760, 240, 210, 60
BTN_STOP_X, BTN_STOP_Y                = 760, 320

def draw_static_ui():
    p4.fill_rect(0, 0, 1024, 600, C_BG)
    p4.fill_rect(0, 0, 1024, 42, C_TITLEBAR)
    p4.text("ESP32-P4 Audio System: Mic Config & Buffered Stream Control", 20, 12, color=C_TEXT_WHITE)
    p4.text("v1.2.0 Firmware Ready", 800, 12, color=C_TEXT_MUTED)
    
    # 示波器视口外框
    p4.fill_rect(OSC_X - 4, OSC_Y - 4, OSC_W + 8, OSC_H + 8, C_PANEL)
    p4.fill_rect(OSC_X, OSC_Y, OSC_W, OSC_H, 0x0000)
    
    # 右侧控制面板
    p4.fill_rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H, C_PANEL)
    p4.text("AUDIO CONTROLLER", PANEL_X + 25, 95, color=C_TEXT_WHITE)
    p4.text("--------------------", PANEL_X + 25, 115, color=C_TEXT_MUTED)
    p4.text("Master Volume", SLIDER_X, 138, color=C_TEXT_MUTED)
    
    p4.fill_rect(0, 560, 1024, 40, C_TITLEBAR)
    p4.text("Drag slider (Default 20%) | Tap [Play/Pause] to toggle music playback", 20, 572, color=C_TEXT_MUTED)

def draw_slider(vol):
    p4.fill_rect(SLIDER_X, SLIDER_Y, SLIDER_W, SLIDER_H, C_SLIDER_BG)
    fill_w = int((vol / 100.0) * SLIDER_W)
    if fill_w > 0:
        p4.fill_rect(SLIDER_X, SLIDER_Y, fill_w, SLIDER_H, C_SLIDER_FILL)
    
    handle_x = SLIDER_X + fill_w - 4
    if handle_x < SLIDER_X: handle_x = SLIDER_X
    if handle_x > SLIDER_X + SLIDER_W - 8: handle_x = SLIDER_X + SLIDER_W - 8
    p4.fill_rect(handle_x, SLIDER_Y - 4, 8, SLIDER_H + 8, C_TEXT_WHITE)
    
    p4.fill_rect(SLIDER_X + 130, 138, 80, 20, C_PANEL)
    p4.text(f"{vol}%", SLIDER_X + 140, 138, color=C_ACCENT_GREEN)

def draw_play_button(is_playing):
    col = C_BTN_GREEN if is_playing else C_BTN_GRAY
    txt = "[ PAUSE MUSIC ]" if is_playing else "[ RESUME MUSIC ]"
    p4.fill_rect(BTN_PLAY_X, BTN_PLAY_Y, BTN_W, BTN_H, col)
    p4.fill_rect(BTN_PLAY_X, BTN_PLAY_Y, BTN_W, 2, C_TEXT_WHITE)
    p4.fill_rect(BTN_PLAY_X, BTN_PLAY_Y, 2, BTN_H, C_TEXT_WHITE)
    p4.text(txt, BTN_PLAY_X + 25, BTN_PLAY_Y + 22, color=C_TEXT_WHITE)

def draw_stop_button():
    p4.fill_rect(BTN_STOP_X, BTN_STOP_Y, BTN_W, BTN_H, C_BTN_RED)
    p4.fill_rect(BTN_STOP_X, BTN_STOP_Y, BTN_W, 2, C_TEXT_WHITE)
    p4.fill_rect(BTN_STOP_X, BTN_STOP_Y, 2, BTN_H, C_TEXT_WHITE)
    p4.text("[ RESTART MUSIC ]", BTN_STOP_X + 20, BTN_STOP_Y + 22, color=C_TEXT_WHITE)

def draw_scope_grid():
    for x in range(OSC_X, OSC_X + OSC_W, 85):
        p4.fill_rect(x, OSC_Y, 1, OSC_H, C_GRID_LINE)
    for y in range(OSC_Y, OSC_Y + OSC_H, 57):
        p4.fill_rect(OSC_X, y, OSC_W, 1, C_GRID_LINE)
    for x in range(OSC_X, OSC_X + OSC_W, 12):
        p4.fill_rect(x, MID_Y, 6, 1, C_GRID_CENTER)

def parse_touch(t):
    if not t: return None
    try:
        if isinstance(t, (list, tuple)) and len(t) > 0:
            first = t[0]
            if isinstance(first, (list, tuple)): return first[0], first[1]
            elif isinstance(first, int) and len(t) >= 2: return t[0], t[1]
    except Exception:
        pass
    return None

# 双缓冲预热：连续两次绘制对齐显存
is_music_active = True
for _ in range(2):
    draw_static_ui()
    draw_slider(current_volume)
    draw_play_button(is_music_active)
    draw_stop_button()
    draw_scope_grid()
    p4.display_flip()

CHUNK_SAMPLES = 256
audio_chunk = bytearray(CHUNK_SAMPLES * 4)
last_touch_btn = False
STEP_PIXELS = 3

print("[+] audio.py 运行中：麦克风配置、音乐缓冲播放与滑块流控就绪。")

try:
    while True:
        # 1. 触摸轮询与按键/滑块判定
        touch_point = parse_touch(p4.touch_read())
        if touch_point:
            tx, ty = touch_point
            
            # 音量滑块滑动判定
            if (SLIDER_X - 15) <= tx <= (SLIDER_X + SLIDER_W + 15) and (SLIDER_Y - 20) <= ty <= (SLIDER_Y + SLIDER_H + 20):
                new_vol = int(((tx - SLIDER_X) / float(SLIDER_W)) * 100)
                if new_vol < 0: new_vol = 0
                if new_vol > 100: new_vol = 100
                if new_vol != current_volume:
                    current_volume = new_vol
                    p4.audio_volume(current_volume)
                    for _ in range(2):
                        draw_slider(current_volume)
                        p4.display_flip()

            # 暂停 / 继续按键判定
            elif BTN_PLAY_X <= tx <= (BTN_PLAY_X + BTN_W) and BTN_PLAY_Y <= ty <= (BTN_PLAY_Y + BTN_H):
                if not last_touch_btn:
                    if p4.audio_is_playing():
                        p4.audio_pause()
                        is_music_active = False
                    else:
                        p4.audio_resume()
                        is_music_active = True
                    for _ in range(2):
                        draw_play_button(is_music_active)
                        p4.display_flip()
                    last_touch_btn = True

            # 重新载入/播放按键判定
            elif BTN_STOP_X <= tx <= (BTN_STOP_X + BTN_W) and BTN_STOP_Y <= ty <= (BTN_STOP_Y + BTN_H):
                if not last_touch_btn:
                    p4.audio_load_buf(music_buf, 16000, True)
                    is_music_active = True
                    for _ in range(2):
                        draw_play_button(is_music_active)
                        p4.display_flip()
                    last_touch_btn = True
        else:
            last_touch_btn = False

        # 2. ES7210 麦克风数据采集
        n_bytes = p4.audio_record(audio_chunk)

        # 3. 示波器离屏刷新
        if n_bytes >= 4:
            p4.fill_rect(OSC_X, OSC_Y, OSC_W, OSC_H, 0x0000)
            draw_scope_grid()

            num_frames = n_bytes // 4
            stride = num_frames / (OSC_W / STEP_PIXELS)
            last_py_l = MID_Y
            last_py_r = MID_Y
            max_amp_l = 0
            max_amp_r = 0

            for col in range(0, OSC_W, STEP_PIXELS):
                f_idx = int((col / STEP_PIXELS) * stride)
                if f_idx < num_frames:
                    b_idx = f_idx * 4
                    val_l, val_r = struct.unpack_from('<hh', audio_chunk, b_idx)
                    val_l -= 130  # 扣除麦克风硬件直流偏置

                    if abs(val_l) > max_amp_l: max_amp_l = abs(val_l)
                    if abs(val_r) > max_amp_r: max_amp_r = abs(val_r)

                    off_l = int((val_l / 16384.0) * (OSC_H // 2 - 25))
                    cur_y_l = MID_Y - off_l
                    if cur_y_l < OSC_Y + 2: cur_y_l = OSC_Y + 2
                    if cur_y_l > OSC_Y + OSC_H - 2: cur_y_l = OSC_Y + OSC_H - 2

                    off_r = int((val_r / 16384.0) * (OSC_H // 2 - 25))
                    cur_y_r = MID_Y - off_r
                    if cur_y_r < OSC_Y + 2: cur_y_r = OSC_Y + 2
                    if cur_y_r > OSC_Y + OSC_H - 2: cur_y_r = OSC_Y + OSC_H - 2

                    cur_x = OSC_X + col

                    # 绘制 MIC1 (亮青) 与 MIC2 (亮黄)
                    h_l = abs(cur_y_l - last_py_l) + 1
                    top_l = min(cur_y_l, last_py_l)
                    p4.fill_rect(cur_x, top_l, STEP_PIXELS, h_l, C_MIC1_COLOR)

                    h_r = abs(cur_y_r - last_py_r) + 1
                    top_r = min(cur_y_r, last_py_r)
                    p4.fill_rect(cur_x, top_r, STEP_PIXELS, h_r, C_MIC2_COLOR)

                    last_py_l = cur_y_l
                    last_py_r = cur_y_r

            vpp_l_mv = int((max_amp_l / 32768.0) * 3300)
            vpp_r_mv = int((max_amp_r / 32768.0) * 3300)
            status_txt = "MUSIC PLAYING" if is_music_active else "MUSIC PAUSED"
            p4.fill_rect(OSC_X + 10, OSC_Y + 10, 360, 24, 0x0000)
            p4.text(f"CH1(L): {vpp_l_mv}mV | CH2(R): {vpp_r_mv}mV | {status_txt}", OSC_X + 14, OSC_Y + 14, color=C_ACCENT_GREEN)

        # 4. 调用已有的双缓冲垂直同步翻转
        p4.display_flip()
        time.sleep_ms(2)

except KeyboardInterrupt:
    p4.audio_stop()
    p4.audio_pa(False)
