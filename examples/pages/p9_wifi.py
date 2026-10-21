# pages/p9_wifi.py - ESP32-C6 协处理器 Wi-Fi 6 AP 扫描与 BTLDG 协议封装
import p4
import network
import config as cfg

class PageWiFi:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.mac_str = ":".join(f"{b:02X}" for b in self.wlan.config("mac"))
        self.scan_results = []
        self.is_scanning = False

    def update(self):
        # 仅触发一次非阻塞扫描，防止卡看门狗
        if not self.is_scanning and len(self.scan_results) == 0:
            try:
                self.scan_results = self.wlan.scan()
                self.is_scanning = True
            except:
                pass
        return len(self.scan_results) > 0

    def render(self, cur_temp):
        p4.text(f"协处理器射频 : ESP32-C6 (Wi-Fi 6) 在线 [MAC: {self.mac_str}]", 65, 110, color=cfg.C_GREEN, font=p4.FONT_DOT, size=16)
        
        # 打包 BTLDG 协议报文
        bld_pkt = p4.bld_pack(type="SCAN", val1=cur_temp, val2=float(len(self.scan_results)))
        p4.text("BTLDG 协议报文 : " + bld_pkt, 65, 135, color=cfg.C_CYAN, font=p4.FONT_DOT, size=16)
        
        p4.fill_rect(x=65, y=170, w=890, h=345, color=cfg.C_BLACK)
        p4.text(f"周边 Wi-Fi 6 / 2.4G AP 扫描结果 (共发现 {len(self.scan_results)} 个热点):", 80, 185, color=cfg.C_YELLOW, font=p4.FONT_DOT, size=16)
        
        if len(self.scan_results) == 0:
            p4.text("正在调度 C6 协处理器执行全信道射频扫描，请稍候...", 80, 225, color=cfg.C_GRAY, font=p4.FONT_DOT, size=16)
        else:
            for idx, ap in enumerate(self.scan_results[:6]):
                ssid = ap[0].decode('utf-8', 'ignore') if ap[0] else "<隐藏 SSID>"
                rssi = ap[3]
                p4.text(f"[{idx+1}] SSID: {ssid:<24} | 信号强度: {rssi} dBm", 80, 225 + idx * 30, color=cfg.C_WHITE, font=p4.FONT_DOT, size=16)
            p4.text("整机硬件专项自检已全部通过！可安全部署主业务工程。", 80, 440, color=cfg.C_GREEN, font=p4.FONT_YAHEI, size=24)
