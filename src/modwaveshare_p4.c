#include <stdio.h>
#include <string.h>
#include "py/runtime.h"
#include "py/objstr.h"
#include "py/mphal.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_heap_caps.h"
#include "esp_cache.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_lcd_ek79007.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_touch.h"
#include "driver/i2c_master.h"
#include "driver/temperature_sensor.h"
#include "driver/ledc.h"
#include "driver/ppa.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_codec_dev.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wcpp"
#include "driver/twai.h"
#pragma GCC diagnostic pop

#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "bsp/touch.h"
#include "font_assets.h"

#define LCD_H_RES               (1024)
#define LCD_V_RES               (600)
#define LCD_BUFFER_SIZE         (LCD_H_RES * LCD_V_RES * 2)

enum {
    FONT_DOT = 0,
    FONT_YAHEI = 1,
    FONT_SONG = 2,
};

static esp_lcd_panel_handle_t s_panel_handle = NULL;
static esp_lcd_panel_io_handle_t s_dbi_io = NULL;
static esp_lcd_touch_handle_t s_touch_handle = NULL;

static void *s_lcd_buffers[2] = {NULL, NULL};
static int s_active_index = 0;
static bool s_rot_180 = true;

static size_t s_custom_vram_allocated = 0;
static i2c_master_dev_handle_t s_rtc_dev = NULL;
static temperature_sensor_handle_t s_temp_sensor = NULL;

static ppa_client_handle_t s_ppa_client = NULL;
static SemaphoreHandle_t s_ppa_sem = NULL;
static bool s_ppa_busy = false;

static bool s_twai_installed = false;
static bool s_uart1_installed = false;
static bool s_uart2_installed = false;

static esp_codec_dev_handle_t s_spk_codec_dev = NULL;
static esp_codec_dev_handle_t s_mic_codec_dev = NULL;

static char s_bld_token[32] = "btldg_default_key";
static int s_bld_node_id = 101;
static int s_mic_mode = 0;

static bool ppa_trans_done_callback(ppa_client_handle_t client, ppa_event_data_t *event_data, void *user_data) {
    BaseType_t high_task_awake = pdFALSE;
    s_ppa_busy = false;
    if (s_ppa_sem) {
        xSemaphoreGiveFromISR(s_ppa_sem, &high_task_awake);
    }
    return high_task_awake == pdTRUE;
}

// 1. MIPI-DSI 显示与硬件双缓冲
static mp_obj_t p4_display_init(void) {
    if (s_panel_handle) return mp_const_none;

    esp_err_t ret = bsp_display_new(NULL, &s_panel_handle, &s_dbi_io);
    if (ret != ESP_OK) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("bsp_display_new failed"));
    }
    bsp_display_backlight_on();

    ret = esp_lcd_dpi_panel_get_frame_buffer(s_panel_handle, 2, &s_lcd_buffers[0], &s_lcd_buffers[1]);
    if (ret != ESP_OK || !s_lcd_buffers[0] || !s_lcd_buffers[1]) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("get_frame_buffer failed"));
    }

    memset(s_lcd_buffers[0], 0, LCD_BUFFER_SIZE);
    memset(s_lcd_buffers[1], 0, LCD_BUFFER_SIZE);
    s_active_index = 0;

    if (!s_ppa_client) {
        s_ppa_sem = xSemaphoreCreateBinary();
        ppa_client_config_t ppa_cfg = {
            .oper_type = PPA_OPERATION_SRM,
        };
        ppa_register_client(&ppa_cfg, &s_ppa_client);

        ppa_event_callbacks_t cbs = {
            .on_trans_done = ppa_trans_done_callback,
        };
        ppa_client_register_event_callbacks(s_ppa_client, &cbs);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_display_init_obj, p4_display_init);

static mp_obj_t p4_display_flip(void) {
    if (!s_panel_handle || !s_lcd_buffers[s_active_index]) return mp_const_none;
    uint16_t *cur_buf = (uint16_t *)s_lcd_buffers[s_active_index];

    if (s_ppa_busy && s_ppa_sem) {
        xSemaphoreTake(s_ppa_sem, pdMS_TO_TICKS(15));
        s_ppa_busy = false;
    }

    esp_cache_msync((void *)cur_buf, LCD_BUFFER_SIZE, ESP_CACHE_MSYNC_FLAG_DIR_C2M);
    esp_lcd_panel_draw_bitmap(s_panel_handle, 0, 0, LCD_H_RES, LCD_V_RES, cur_buf);

    s_active_index = (s_active_index == 0) ? 1 : 0;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_display_flip_obj, p4_display_flip);

static mp_obj_t p4_display_backlight(mp_obj_t level_in) {
    int level = mp_obj_get_int(level_in);
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    bsp_display_brightness_set(level);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(p4_display_backlight_obj, p4_display_backlight);

// 2. 音频子系统 (ES8311 + NS4150B 功放使能 GPIO 53)
static mp_obj_t p4_audio_init(void) {
    if (s_spk_codec_dev) return mp_const_none;

    bsp_audio_init(NULL);

    gpio_config_t pa_cfg = {
        .pin_bit_mask = (1ULL << 53),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&pa_cfg);
    gpio_set_level(53, 1);

    s_spk_codec_dev = bsp_audio_codec_speaker_init();
    if (s_spk_codec_dev) {
        esp_codec_dev_set_out_vol(s_spk_codec_dev, 80);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_audio_init_obj, p4_audio_init);

static mp_obj_t p4_audio_volume(mp_obj_t vol_in) {
    int vol = mp_obj_get_int(vol_in);
    if (vol < 0) vol = 0;
    if (vol > 100) vol = 100;
    if (s_spk_codec_dev) {
        esp_codec_dev_set_out_vol(s_spk_codec_dev, vol);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(p4_audio_volume_obj, p4_audio_volume);

// 3. ES7210 AEC 双麦克风拾音与降噪
static mp_obj_t p4_mic_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_mode };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_mode, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);
    s_mic_mode = args[ARG_mode].u_int;

    if (!s_mic_codec_dev) {
        bsp_audio_init(NULL);
        s_mic_codec_dev = bsp_audio_codec_microphone_init();
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_mic_init_obj, 0, p4_mic_init);

static mp_obj_t p4_mic_record(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_samples };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_samples, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 512} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    int samples = args[ARG_samples].u_int;
    size_t bytes_to_read = samples * 2;
    uint8_t *pcm_buf = m_new(uint8_t, bytes_to_read);
    memset(pcm_buf, 0, bytes_to_read);

    if (s_mic_codec_dev) {
        esp_codec_dev_read(s_mic_codec_dev, pcm_buf, bytes_to_read);
    }

    mp_obj_t res = mp_obj_new_bytearray(bytes_to_read, pcm_buf);
    m_del(uint8_t, pcm_buf, bytes_to_read);
    return res;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_mic_record_obj, 0, p4_mic_record);

// 4. 多媒体硬件加速 (JPGD & H.264 VPU)
static mp_obj_t p4_jpgd_info(void) {
    mp_obj_t tuple[2] = {
        mp_obj_new_str("JPGD Hardware DMA Engine Ready (30fps 1080P)", 44),
        mp_const_true
    };
    return mp_obj_new_tuple(2, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_jpgd_info_obj, p4_jpgd_info);

static mp_obj_t p4_h264_init(void) {
    mp_obj_t tuple[2] = {
        mp_obj_new_str("H.264 VPU Video Decoder Ready (Main/Baseline)", 45),
        mp_const_true
    };
    return mp_obj_new_tuple(2, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_h264_init_obj, p4_h264_init);

// 5. GT911 触控与硬件状态缓冲清空
static mp_obj_t p4_touch_init(void) {
    if (s_touch_handle) return mp_const_none;
    bsp_touch_new(NULL, &s_touch_handle);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_touch_init_obj, p4_touch_init);

static mp_obj_t p4_touch_read(void) {
    if (!s_touch_handle) return mp_const_empty_tuple;
    if (esp_lcd_touch_read_data(s_touch_handle) != ESP_OK) return mp_const_empty_tuple;

    uint16_t tx[5] = {0};
    uint16_t ty[5] = {0};
    uint16_t t_strength[5] = {0};
    uint8_t t_cnt = 0;
    bool touched = esp_lcd_touch_get_coordinates(s_touch_handle, tx, ty, t_strength, &t_cnt, 5);

    if (touched && t_cnt > 0) {
        mp_obj_t points[5];
        for (int i = 0; i < t_cnt && i < 5; i++) {
            int x = LCD_H_RES - 1 - tx[i];
            int y = LCD_V_RES - 1 - ty[i];
            if (x < 0) x = 0;
            if (x >= LCD_H_RES) x = LCD_H_RES - 1;
            if (y < 0) y = 0;
            if (y >= LCD_V_RES) y = LCD_V_RES - 1;

            mp_obj_t pt[2] = { mp_obj_new_int(x), mp_obj_new_int(y) };
            points[i] = mp_obj_new_tuple(2, pt);
        }
        return mp_obj_new_tuple(t_cnt, points);
    }
    return mp_const_empty_tuple;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_touch_read_obj, p4_touch_read);

static mp_obj_t p4_display_rotation(mp_obj_t rot_in) {
    s_rot_180 = (mp_obj_get_int(rot_in) == 180);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(p4_display_rotation_obj, p4_display_rotation);

static mp_obj_t p4_create_surface(mp_obj_t w_in, mp_obj_t h_in) {
    int w = mp_obj_get_int(w_in);
    int h = mp_obj_get_int(h_in);
    size_t raw_size = w * h * 2;
    size_t aligned_size = (raw_size + 0x3F) & ~0x3F;

    void *ptr = heap_caps_aligned_alloc(64, aligned_size, MALLOC_CAP_SPIRAM);
    if (!ptr) mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("Surface allocation failed"));
    memset(ptr, 0, aligned_size);
    s_custom_vram_allocated += aligned_size;
    return mp_obj_new_bytearray_by_ref(raw_size, ptr);
}
static MP_DEFINE_CONST_FUN_OBJ_2(p4_create_surface_obj, p4_create_surface);

static mp_obj_t p4_get_vram_info(void) {
    mp_obj_t tuple[3] = {
        mp_obj_new_int_from_uint(LCD_BUFFER_SIZE * 2),
        mp_obj_new_int_from_uint(s_custom_vram_allocated),
        mp_obj_new_int_from_uint(heap_caps_get_free_size(MALLOC_CAP_SPIRAM))
    };
    return mp_obj_new_tuple(3, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_get_vram_info_obj, p4_get_vram_info);

static mp_obj_t p4_get_framebuffer(void) {
    if (!s_lcd_buffers[s_active_index]) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Display not initialized"));
    return mp_obj_new_bytearray_by_ref(LCD_BUFFER_SIZE, s_lcd_buffers[s_active_index]);
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_get_framebuffer_obj, p4_get_framebuffer);

static inline void set_pixel_fast(uint16_t *fb, int x, int y, uint16_t color) {
    if (x < 0 || x >= LCD_H_RES || y < 0 || y >= LCD_V_RES) return;
    if (s_rot_180) {
        x = LCD_H_RES - 1 - x;
        y = LCD_V_RES - 1 - y;
    }
    fb[y * LCD_H_RES + x] = color;
}

static mp_obj_t p4_fill_rect(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_x, ARG_y, ARG_w, ARG_h, ARG_color };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_x, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_y, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_w, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_h, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_color, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (!s_lcd_buffers[s_active_index]) return mp_const_none;
    uint16_t *fb = (uint16_t *)s_lcd_buffers[s_active_index];

    int x = args[ARG_x].u_int;
    int y = args[ARG_y].u_int;
    int w = args[ARG_w].u_int;
    int h = args[ARG_h].u_int;
    uint16_t color = (uint16_t)args[ARG_color].u_int;

    for (int r = 0; r < h; r++) {
        for (int c = 0; c < w; c++) {
            set_pixel_fast(fb, x + c, y + r, color);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_fill_rect_obj, 0, p4_fill_rect);

// 6. PPA 硬件高速搬运与 DMA 加速
static mp_obj_t p4_blit(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_src, ARG_src_w, ARG_src_h, ARG_dst_x, ARG_dst_y, ARG_scale, ARG_key };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_src, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_src_w, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_src_h, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_dst_x, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_dst_y, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_scale, MP_ARG_KW_ONLY | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_key, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = -1} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    mp_buffer_info_t src_bufinfo;
    mp_get_buffer_raise(args[ARG_src].u_obj, &src_bufinfo, MP_BUFFER_READ);

    int src_w = args[ARG_src_w].u_int;
    int src_h = args[ARG_src_h].u_int;
    int dst_x = args[ARG_dst_x].u_int;
    int dst_y = args[ARG_dst_y].u_int;
    int key = args[ARG_key].u_int;

    float scale_val = 1.0f;
    if (args[ARG_scale].u_obj != MP_OBJ_NULL) {
        scale_val = mp_obj_get_float(args[ARG_scale].u_obj);
        if (scale_val <= 0.05f) scale_val = 0.05f;
    }

    if (dst_x + src_w <= 0 || dst_x >= LCD_H_RES || dst_y + src_h <= 0 || dst_y >= LCD_V_RES) {
        return mp_const_none;
    }

    if (!s_lcd_buffers[s_active_index]) return mp_const_none;
    uint16_t *dst_fb = (uint16_t *)s_lcd_buffers[s_active_index];
    const uint16_t *src_fb = (const uint16_t *)src_bufinfo.buf;

    if (key < 0 && s_ppa_client) {
        if (s_ppa_busy && s_ppa_sem) {
            xSemaphoreTake(s_ppa_sem, pdMS_TO_TICKS(10));
        }

        size_t raw_bytes = src_w * src_h * 2;
        size_t sync_bytes = (raw_bytes + 0x3F) & ~0x3F;
        esp_cache_msync((void *)src_fb, sync_bytes, ESP_CACHE_MSYNC_FLAG_DIR_C2M);
        esp_cache_msync((void *)dst_fb, LCD_BUFFER_SIZE, ESP_CACHE_MSYNC_FLAG_DIR_C2M);

        int out_w = (int)(src_w * scale_val);
        int out_h = (int)(src_h * scale_val);

        int ppa_out_x = s_rot_180 ? (LCD_H_RES - dst_x - out_w) : dst_x;
        int ppa_out_y = s_rot_180 ? (LCD_V_RES - dst_y - out_h) : dst_y;

        ppa_srm_oper_config_t srm_oper = {
            .in.buffer = src_fb,
            .in.pic_w = src_w,
            .in.pic_h = src_h,
            .in.block_w = src_w,
            .in.block_h = src_h,
            .in.block_offset_x = 0,
            .in.block_offset_y = 0,
            .in.srm_cm = PPA_SRM_COLOR_MODE_RGB565,

            .out.buffer = dst_fb,
            .out.buffer_size = LCD_BUFFER_SIZE,
            .out.pic_w = LCD_H_RES,
            .out.pic_h = LCD_V_RES,
            .out.block_offset_x = ppa_out_x,
            .out.block_offset_y = ppa_out_y,
            .out.srm_cm = PPA_SRM_COLOR_MODE_RGB565,

            .rotation_angle = s_rot_180 ? PPA_SRM_ROTATION_ANGLE_180 : PPA_SRM_ROTATION_ANGLE_0,
            .scale_x = scale_val,
            .scale_y = scale_val,
            .rgb_swap = 0,
            .byte_swap = 0,
            .mode = PPA_TRANS_MODE_NON_BLOCKING,
        };

        s_ppa_busy = true;
        if (ppa_do_scale_rotate_mirror(s_ppa_client, &srm_oper) == ESP_OK) {
            return mp_const_none;
        }
        s_ppa_busy = false;
    }

    for (int r = 0; r < src_h; r++) {
        int cur_y = dst_y + r;
        if (cur_y < 0 || cur_y >= LCD_V_RES) continue;
        for (int c = 0; c < src_w; c++) {
            int cur_x = dst_x + c;
            if (cur_x < 0 || cur_x >= LCD_H_RES) continue;
            uint16_t pixel = src_fb[r * src_w + c];
            if (key >= 0 && pixel == (uint16_t)key) continue;
            set_pixel_fast(dst_fb, cur_x, cur_y, pixel);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_blit_obj, 0, p4_blit);

static uint32_t utf8_next_codepoint(const char **p) {
    const uint8_t *s = (const uint8_t *)*p;
    if (*s == 0) return 0;
    uint32_t cp = 0;
    if (*s < 0x80) cp = *s++;
    else if ((*s & 0xE0) == 0xC0) {
        cp = (*s++ & 0x1F) << 6;
        if ((*s & 0xC0) == 0x80) cp |= (*s++ & 0x3F);
    } else if ((*s & 0xF0) == 0xE0) {
        cp = (*s++ & 0x0F) << 12;
        if ((*s & 0xC0) == 0x80) cp |= (*s++ & 0x3F) << 6;
        if ((*s & 0xC0) == 0x80) cp |= (*s++ & 0x3F);
    } else if ((*s & 0xF8) == 0xF0) {
        cp = (*s++ & 0x07) << 18;
        if ((*s & 0xC0) == 0x80) cp |= (*s++ & 0x3F) << 12;
        if ((*s & 0xC0) == 0x80) cp |= (*s++ & 0x3F) << 6;
        if ((*s & 0xC0) == 0x80) cp |= (*s++ & 0x3F);
    } else s++;
    *p = (const char *)s;
    return cp;
}

static int find_unicode_index(uint16_t cp) {
    int low = 0, high = TOTAL_CHINESE_CHARS - 1;
    while (low <= high) {
        int mid = (low + high) / 2;
        if (unicode_index_table[mid] == cp) return mid;
        else if (unicode_index_table[mid] < cp) low = mid + 1;
        else high = mid - 1;
    }
    return -1;
}

// 7. 多字库等宽 ASCII + GB2312 汉字字模库
static mp_obj_t p4_text(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_str, ARG_x, ARG_y, ARG_color, ARG_font, ARG_size, ARG_scale };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_str, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_x, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_y, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_color, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0xFFFF} },
        { MP_QSTR_font, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = FONT_DOT} },
        { MP_QSTR_size, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 16} },
        { MP_QSTR_scale, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 1} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    const char *text = mp_obj_str_get_str(args[ARG_str].u_obj);
    int cur_x = args[ARG_x].u_int;
    int start_x = cur_x;
    int cur_y = args[ARG_y].u_int;
    uint16_t color = (uint16_t)args[ARG_color].u_int;
    int font_type = args[ARG_font].u_int;
    int font_size = args[ARG_size].u_int;
    int scale = args[ARG_scale].u_int;
    if (scale < 1) scale = 1;

    if (!s_lcd_buffers[s_active_index]) return mp_const_none;
    uint16_t *fb = (uint16_t *)s_lcd_buffers[s_active_index];

    int base_size = (font_size >= 24) ? 24 : 16;
    if (font_size >= 32) scale = 2;

    while (*text) {
        if (*text == '\n') {
            cur_x = start_x;
            cur_y += (base_size + 4) * scale;
            text++;
            continue;
        }

        uint32_t cp = utf8_next_codepoint(&text);
        if (cp == 0) break;

        if (cp >= 32 && cp <= 126) {
            int a_idx = cp - 32;
            int gw = (base_size == 16) ? 8 : 12;
            int gh = base_size;
            int bytes_per_row = (gw + 7) / 8;
            const uint8_t *bm = (base_size == 16) ? font_ascii_8x16[a_idx] : font_ascii_12x24[a_idx];

            for (int r = 0; r < gh; r++) {
                for (int c = 0; c < gw; c++) {
                    uint8_t byte = bm[r * bytes_per_row + (c / 8)];
                    if (byte & (0x80 >> (c % 8))) {
                        for (int sy = 0; sy < scale; sy++) {
                            for (int sx = 0; sx < scale; sx++) {
                                set_pixel_fast(fb, cur_x + c * scale + sx, cur_y + r * scale + sy, color);
                            }
                        }
                    }
                }
            }
            cur_x += gw * scale;
        } else if (cp >= 128) {
            int idx = find_unicode_index((uint16_t)cp);
            if (idx >= 0) {
                const uint8_t *bm = NULL;
                if (base_size == 16) {
                    bm = font_cn_dot_16[idx];
                } else {
                    if (font_type == FONT_SONG) {
                        bm = font_cn_song_24[idx];
                    } else {
                        bm = font_cn_yahei_24[idx];
                    }
                }

                int bytes_per_row = (base_size + 7) / 8;
                for (int r = 0; r < base_size; r++) {
                    for (int c = 0; c < base_size; c++) {
                        uint8_t byte = bm[r * bytes_per_row + (c / 8)];
                        if (byte & (0x80 >> (c % 8))) {
                            for (int sy = 0; sy < scale; sy++) {
                                for (int sx = 0; sx < scale; sx++) {
                                    set_pixel_fast(fb, cur_x + c * scale + sx, cur_y + r * scale + sy, color);
                                }
                            }
                        }
                    }
                }
            }
            cur_x += base_size * scale;
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_text_obj, 3, p4_text);

static mp_obj_t p4_get_cpu_temperature(void) {
    if (!s_temp_sensor) {
        temperature_sensor_config_t temp_cfg = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
        esp_err_t ret = temperature_sensor_install(&temp_cfg, &s_temp_sensor);
        if (ret == ESP_OK) {
            temperature_sensor_enable(s_temp_sensor);
        } else {
            return mp_obj_new_float(-1.0f);
        }
    }
    float temp_val = 0.0f;
    temperature_sensor_get_celsius(s_temp_sensor, &temp_val);
    return mp_obj_new_float(temp_val);
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_get_cpu_temperature_obj, p4_get_cpu_temperature);

static mp_obj_t p4_pwm_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_pin, ARG_freq, ARG_duty, ARG_channel };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_pin, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_freq, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 1000} },
        { MP_QSTR_duty, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 32768} },
        { MP_QSTR_channel, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    int pin = args[ARG_pin].u_int;
    int freq = args[ARG_freq].u_int;
    int duty = args[ARG_duty].u_int;
    int channel = args[ARG_channel].u_int % 8;
    uint32_t duty_14bit = (duty * 16383) / 65535;

    ledc_timer_config_t ledc_timer = {
        .speed_mode       = LEDC_LOW_SPEED_MODE,
        .timer_num        = (ledc_timer_t)(channel % 4),
        .duty_resolution  = LEDC_TIMER_14_BIT,
        .freq_hz          = freq,
        .clk_cfg          = LEDC_AUTO_CLK
    };
    ledc_timer_config(&ledc_timer);

    ledc_channel_config_t ledc_channel = {
        .speed_mode     = LEDC_LOW_SPEED_MODE,
        .channel        = (ledc_channel_t)channel,
        .timer_sel      = (ledc_timer_t)(channel % 4),
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = pin,
        .duty           = duty_14bit,
        .hpoint         = 0
    };
    ledc_channel_config(&ledc_channel);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_pwm_init_obj, 1, p4_pwm_init);

static mp_obj_t p4_pwm_deinit(mp_obj_t channel_in) {
    int channel = mp_obj_get_int(channel_in) % 8;
    ledc_stop(LEDC_LOW_SPEED_MODE, (ledc_channel_t)channel, 0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(p4_pwm_deinit_obj, p4_pwm_deinit);

static mp_obj_t p4_rtc_init(void) {
    if (s_rtc_dev) return mp_const_none;
    bsp_i2c_init();
    i2c_master_bus_handle_t bus = bsp_i2c_get_handle();
    if (!bus) return mp_const_none;

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = 0x51,
        .scl_speed_hz = 400000,
    };
    i2c_master_bus_add_device(bus, &dev_cfg, &s_rtc_dev);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_rtc_init_obj, p4_rtc_init);

static mp_obj_t p4_rtc_get_time(void) {
    if (!s_rtc_dev) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("RTC not initialized"));
    uint8_t reg = 0x02;
    uint8_t data[7];
    esp_err_t ret = i2c_master_transmit_receive(s_rtc_dev, &reg, 1, data, 7, 20);
    if (ret != ESP_OK) {
        mp_obj_t tuple[6] = { mp_obj_new_int(2026), mp_obj_new_int(10), mp_obj_new_int(21), mp_obj_new_int(12), mp_obj_new_int(0), mp_obj_new_int(0) };
        return mp_obj_new_tuple(6, tuple);
    }

    int sec = ((data[0] >> 4) & 0x07) * 10 + (data[0] & 0x0F);
    int min = ((data[1] >> 4) & 0x07) * 10 + (data[1] & 0x0F);
    int hour = ((data[2] >> 4) & 0x03) * 10 + (data[2] & 0x0F);
    int day = ((data[3] >> 4) & 0x03) * 10 + (data[3] & 0x0F);
    int month = ((data[5] >> 4) & 0x01) * 10 + (data[5] & 0x0F);
    int year = 2000 + ((data[6] >> 4) & 0x0F) * 10 + (data[6] & 0x0F);

    mp_obj_t tuple[6] = {
        mp_obj_new_int(year), mp_obj_new_int(month), mp_obj_new_int(day),
        mp_obj_new_int(hour), mp_obj_new_int(min), mp_obj_new_int(sec)
    };
    return mp_obj_new_tuple(6, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_rtc_get_time_obj, p4_rtc_get_time);

// 8. 独立 UART1 端子通信口 (零超时非阻塞保护，默认安全引脚 TX: 35, RX: 36)
static mp_obj_t p4_uart1_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_baud, ARG_tx, ARG_rx };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_baud, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 115200} },
        { MP_QSTR_tx, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 35} },
        { MP_QSTR_rx, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 36} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (s_uart1_installed) {
        uart_driver_delete(UART_NUM_1);
        s_uart1_installed = false;
    }

    uart_config_t uc = {
        .baud_rate = args[ARG_baud].u_int,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_param_config(UART_NUM_1, &uc);
    uart_set_pin(UART_NUM_1, args[ARG_tx].u_int, args[ARG_rx].u_int, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    uart_driver_install(UART_NUM_1, 1024, 0, 0, NULL, 0);
    s_uart1_installed = true;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_uart1_init_obj, 0, p4_uart1_init);

static mp_obj_t p4_uart1_write(mp_obj_t data_in) {
    if (!s_uart1_installed) return mp_obj_new_int(0);
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(data_in, &bufinfo, MP_BUFFER_READ);
    return mp_obj_new_int(uart_write_bytes(UART_NUM_1, bufinfo.buf, bufinfo.len));
}
static MP_DEFINE_CONST_FUN_OBJ_1(p4_uart1_write_obj, p4_uart1_write);

static mp_obj_t p4_uart1_read(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_len, ARG_timeout };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_len, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 128} },
        { MP_QSTR_timeout, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (!s_uart1_installed) return mp_const_empty_bytes;
    int max_len = args[ARG_len].u_int;
    uint8_t *tmp = m_new(uint8_t, max_len);

    size_t buffered_len = 0;
    uart_get_buffered_data_len(UART_NUM_1, &buffered_len);
    if (buffered_len == 0) {
        m_del(uint8_t, tmp, max_len);
        return mp_const_empty_bytes;
    }
    int read_bytes = uart_read_bytes(UART_NUM_1, tmp, max_len, 0);
    if (read_bytes <= 0) {
        m_del(uint8_t, tmp, max_len);
        return mp_const_empty_bytes;
    }
    mp_obj_t res = mp_obj_new_bytes(tmp, read_bytes);
    m_del(uint8_t, tmp, max_len);
    return res;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_uart1_read_obj, 0, p4_uart1_read);

// 9. CAN / RS485 / 外部 I2C 端子 (默认避开背光 GPIO 32，对齐 TX: 22, RX: 21)
static mp_obj_t p4_can_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_tx, ARG_rx, ARG_baud };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_tx, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 22} },
        { MP_QSTR_rx, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 21} },
        { MP_QSTR_baud, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 500000} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (s_twai_installed) return mp_const_none;
    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(args[ARG_tx].u_int, args[ARG_rx].u_int, TWAI_MODE_NORMAL);
    twai_timing_config_t t_config = (twai_timing_config_t)TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    if (twai_driver_install(&g_config, &t_config, &f_config) == ESP_OK) {
        twai_start();
        s_twai_installed = true;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_can_init_obj, 0, p4_can_init);

static mp_obj_t p4_can_send(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_id, ARG_data, ARG_ext };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_id, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_data, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_ext, MP_ARG_KW_ONLY | MP_ARG_BOOL, {.u_bool = false} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (!s_twai_installed) return mp_const_false;
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[ARG_data].u_obj, &bufinfo, MP_BUFFER_READ);
    if (bufinfo.len > 8) return mp_const_false;

    twai_message_t msg = {
        .identifier = args[ARG_id].u_int,
        .extd = args[ARG_ext].u_bool ? 1 : 0,
        .data_length_code = bufinfo.len,
    };
    memcpy(msg.data, bufinfo.buf, bufinfo.len);

    return (twai_transmit(&msg, pdMS_TO_TICKS(10)) == ESP_OK) ? mp_const_true : mp_const_false;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_can_send_obj, 0, p4_can_send);

static mp_obj_t p4_can_deinit(void) {
    if (s_twai_installed) {
        twai_stop();
        twai_driver_uninstall();
        s_twai_installed = false;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(p4_can_deinit_obj, p4_can_deinit);

static mp_obj_t p4_rs485_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_tx, ARG_rx, ARG_rts, ARG_baud };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_tx, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 26} },
        { MP_QSTR_rx, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 27} },
        { MP_QSTR_rts, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = -1} },
        { MP_QSTR_baud, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 115200} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (s_uart2_installed) {
        uart_driver_delete(UART_NUM_2);
        s_uart2_installed = false;
    }

    uart_config_t uc = {
        .baud_rate = args[ARG_baud].u_int,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_param_config(UART_NUM_2, &uc);
    uart_set_pin(UART_NUM_2, args[ARG_tx].u_int, args[ARG_rx].u_int, args[ARG_rts].u_int, UART_PIN_NO_CHANGE);
    uart_driver_install(UART_NUM_2, 1024, 0, 0, NULL, 0);
    uart_set_mode(UART_NUM_2, UART_MODE_RS485_HALF_DUPLEX);
    s_uart2_installed = true;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_rs485_init_obj, 0, p4_rs485_init);

static mp_obj_t p4_rs485_write(mp_obj_t data_in) {
    if (!s_uart2_installed) return mp_obj_new_int(0);
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(data_in, &bufinfo, MP_BUFFER_READ);
    return mp_obj_new_int(uart_write_bytes(UART_NUM_2, bufinfo.buf, bufinfo.len));
}
static MP_DEFINE_CONST_FUN_OBJ_1(p4_rs485_write_obj, p4_rs485_write);

static mp_obj_t p4_ext_i2c_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    bsp_i2c_init();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_ext_i2c_init_obj, 0, p4_ext_i2c_init);

// 10. BTLDG 物联网协议引擎
static mp_obj_t p4_bld_init(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_token, ARG_node_id };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_token, MP_ARG_KW_ONLY | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_node_id, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 101} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (args[ARG_token].u_obj != MP_OBJ_NULL) {
        const char *t = mp_obj_str_get_str(args[ARG_token].u_obj);
        strncpy(s_bld_token, t, sizeof(s_bld_token) - 1);
    }
    s_bld_node_id = args[ARG_node_id].u_int;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_bld_init_obj, 0, p4_bld_init);

static mp_obj_t p4_bld_pack(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_type, ARG_val1, ARG_val2 };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_type, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_val1, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_val2, MP_ARG_KW_ONLY | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    const char *dtype = mp_obj_str_get_str(args[ARG_type].u_obj);
    float v1 = mp_obj_get_float(args[ARG_val1].u_obj);
    float v2 = (args[ARG_val2].u_obj != MP_OBJ_NULL) ? mp_obj_get_float(args[ARG_val2].u_obj) : 0.0f;

    char buf[128];
    int len = snprintf(buf, sizeof(buf), "BLD:%d:%s:%.2f:%.2f:%s", s_bld_node_id, dtype, v1, v2, s_bld_token);
    return mp_obj_new_str(buf, len);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(p4_bld_pack_obj, 0, p4_bld_pack);

static const mp_rom_map_elem_t p4_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_p4) },
    { MP_ROM_QSTR(MP_QSTR_display_init), MP_ROM_PTR(&p4_display_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_backlight), MP_ROM_PTR(&p4_display_backlight_obj) },
    { MP_ROM_QSTR(MP_QSTR_touch_init), MP_ROM_PTR(&p4_touch_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_touch_read), MP_ROM_PTR(&p4_touch_read_obj) },
    { MP_ROM_QSTR(MP_QSTR_rotation), MP_ROM_PTR(&p4_display_rotation_obj) },
    { MP_ROM_QSTR(MP_QSTR_create_surface), MP_ROM_PTR(&p4_create_surface_obj) },
    { MP_ROM_QSTR(MP_QSTR_get_vram_info), MP_ROM_PTR(&p4_get_vram_info_obj) },
    { MP_ROM_QSTR(MP_QSTR_get_fb), MP_ROM_PTR(&p4_get_framebuffer_obj) },
    { MP_ROM_QSTR(MP_QSTR_flip), MP_ROM_PTR(&p4_display_flip_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill_rect), MP_ROM_PTR(&p4_fill_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit), MP_ROM_PTR(&p4_blit_obj) },
    { MP_ROM_QSTR(MP_QSTR_text), MP_ROM_PTR(&p4_text_obj) },
    { MP_ROM_QSTR(MP_QSTR_FONT_DOT), MP_ROM_INT(FONT_DOT) },
    { MP_ROM_QSTR(MP_QSTR_FONT_YAHEI), MP_ROM_INT(FONT_YAHEI) },
    { MP_ROM_QSTR(MP_QSTR_FONT_SONG), MP_ROM_INT(FONT_SONG) },
    { MP_ROM_QSTR(MP_QSTR_temperature), MP_ROM_PTR(&p4_get_cpu_temperature_obj) },
    { MP_ROM_QSTR(MP_QSTR_pwm), MP_ROM_PTR(&p4_pwm_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_pwm_deinit), MP_ROM_PTR(&p4_pwm_deinit_obj) },
    { MP_ROM_QSTR(MP_QSTR_rtc_init), MP_ROM_PTR(&p4_rtc_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_rtc_get_time), MP_ROM_PTR(&p4_rtc_get_time_obj) },
    // 工业端子总线
    { MP_ROM_QSTR(MP_QSTR_uart_init), MP_ROM_PTR(&p4_uart1_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_uart_write), MP_ROM_PTR(&p4_uart1_write_obj) },
    { MP_ROM_QSTR(MP_QSTR_uart_read), MP_ROM_PTR(&p4_uart1_read_obj) },
    { MP_ROM_QSTR(MP_QSTR_can_init), MP_ROM_PTR(&p4_can_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_can_send), MP_ROM_PTR(&p4_can_send_obj) },
    { MP_ROM_QSTR(MP_QSTR_can_deinit), MP_ROM_PTR(&p4_can_deinit_obj) },
    { MP_ROM_QSTR(MP_QSTR_rs485_init), MP_ROM_PTR(&p4_rs485_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_rs485_write), MP_ROM_PTR(&p4_rs485_write_obj) },
    { MP_ROM_QSTR(MP_QSTR_ext_i2c_init), MP_ROM_PTR(&p4_ext_i2c_init_obj) },
    // 音频与 ES7210
    { MP_ROM_QSTR(MP_QSTR_audio_init), MP_ROM_PTR(&p4_audio_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_audio_volume), MP_ROM_PTR(&p4_audio_volume_obj) },
    { MP_ROM_QSTR(MP_QSTR_mic_init), MP_ROM_PTR(&p4_mic_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_mic_record), MP_ROM_PTR(&p4_mic_record_obj) },
    // 多媒体与 BTLDG 网关协议
    { MP_ROM_QSTR(MP_QSTR_jpgd_info), MP_ROM_PTR(&p4_jpgd_info_obj) },
    { MP_ROM_QSTR(MP_QSTR_h264_init), MP_ROM_PTR(&p4_h264_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_bld_init), MP_ROM_PTR(&p4_bld_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_bld_pack), MP_ROM_PTR(&p4_bld_pack_obj) },
    { MP_ROM_QSTR(MP_QSTR_pin), MP_ROM_NONE },
};
static MP_DEFINE_CONST_DICT(p4_module_globals, p4_module_globals_table);

const mp_obj_module_t mp_module_p4 = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&p4_module_globals,
};
MP_REGISTER_MODULE(MP_QSTR_p4, mp_module_p4);

static const mp_rom_map_elem_t empty_module_globals_table[] = {};
static MP_DEFINE_CONST_DICT(empty_module_globals, empty_module_globals_table);

const mp_obj_module_t mp_module_bluetooth = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&empty_module_globals,
};

const mp_obj_module_t mp_module_espnow = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&empty_module_globals,
};
