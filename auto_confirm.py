import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pyautogui
import cv2
import numpy as np
import time
from PIL import Image, ImageTk, ImageGrab
import keyboard
import threading
import json
import os

class TargetImage:
    def __init__(self, path=None, image=None, confidence=0.8, enabled=True):
        self.path = path
        self.image = image
        self.confidence = confidence
        self.enabled = enabled
        self.last_click_time = 0
        
class AutoClickGUI:
    # 监控目标数量
    MAX_TARGETS = 2
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("多目标自动点击监控工具")
        self.root.geometry("800x800")
        
        # 状态变量
        self.monitoring = False
        self.region = None
        self.targets = [TargetImage() for _ in range(self.MAX_TARGETS)]
        self.monitor_thread = None
        self.click_cooldown = 1.0  # 点击冷却时间（秒）
        
        # 注册全局快捷键
        self.setup_global_hotkey()
        
        self.create_gui()
        self.load_config()
        
    def setup_global_hotkey(self):
        """设置全局快捷键"""
        keyboard.on_press_key("r", self.handle_hotkey, suppress=True)
        
    def handle_hotkey(self, e):
        """处理快捷键事件"""
        if keyboard.is_pressed('ctrl'):
            # 在主线程中执行GUI操作
            self.root.after(0, self.toggle_monitoring)
            
    def create_gui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 控制按钮和状态显示
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, columnspan=2, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="开始监控", command=self.toggle_monitoring)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.status_label = ttk.Label(control_frame, text="就绪")
        self.status_label.grid(row=0, column=1, padx=5)
        
        # 区域选择部分
        region_frame = ttk.LabelFrame(main_frame, text="监控区域", padding="5")
        region_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.region_label = ttk.Label(region_frame, text="未选择区域")
        self.region_label.grid(row=0, column=0, padx=5)
        
        ttk.Button(region_frame, text="选择区域", command=self.select_region).grid(row=0, column=1, padx=5)
        
        # 目标图像部分
        self.target_frames = []
        self.target_labels = []
        self.preview_labels = []
        self.confidence_vars = []
        self.enabled_vars = []
        
        for i in range(self.MAX_TARGETS):
            target_frame = ttk.LabelFrame(main_frame, text=f"目标 {i+1}", padding="5")
            target_frame.grid(row=i+2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
            
            # 图像信息和按钮
            info_frame = ttk.Frame(target_frame)
            info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            # 启用复选框
            enabled_var = tk.BooleanVar(value=True)
            self.enabled_vars.append(enabled_var)
            ttk.Checkbutton(info_frame, text="启用", variable=enabled_var).grid(row=0, column=0, padx=5)
            
            # 图像标签
            label = ttk.Label(info_frame, text="未选择图像")
            label.grid(row=0, column=1, padx=5)
            self.target_labels.append(label)
            
            # 按钮框架
            button_frame = ttk.Frame(info_frame)
            button_frame.grid(row=0, column=2, padx=5)
            
            ttk.Button(button_frame, text="选择图像", 
                      command=lambda idx=i: self.select_image(idx)).grid(row=0, column=0, padx=2)
            ttk.Button(button_frame, text="截取区域", 
                      command=lambda idx=i: self.capture_region_as_target(idx)).grid(row=0, column=1, padx=2)
            
            # 匹配精度
            confidence_frame = ttk.Frame(info_frame)
            confidence_frame.grid(row=0, column=3, padx=5)
            
            ttk.Label(confidence_frame, text="匹配精度:").grid(row=0, column=0)
            confidence_var = tk.StringVar(value="0.8")
            self.confidence_vars.append(confidence_var)
            confidence_entry = ttk.Entry(confidence_frame, textvariable=confidence_var, width=5)
            confidence_entry.grid(row=0, column=1)
            
            # 预览图像
            preview_label = ttk.Label(target_frame)
            preview_label.grid(row=1, column=0, pady=5)
            self.preview_labels.append(preview_label)
            
            self.target_frames.append(target_frame)
        
        # 全局设置
        settings_frame = ttk.LabelFrame(main_frame, text="全局设置", padding="5")
        settings_frame.grid(row=self.MAX_TARGETS+2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(settings_frame, text="点击冷却时间(秒):").grid(row=0, column=0, padx=5)
        self.cooldown_var = tk.StringVar(value="1.0")
        cooldown_entry = ttk.Entry(settings_frame, textvariable=self.cooldown_var, width=5)
        cooldown_entry.grid(row=0, column=1, padx=5)
        
    def select_image(self, target_index):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")]
        )
        if file_path:
            try:
                # 先用OpenCV读取图像
                target_image = cv2.imread(file_path)
                if target_image is None:
                    messagebox.showerror("错误", "无法加载图像，请确保图像格式正确")
                    return
                
                self.targets[target_index].path = file_path
                self.targets[target_index].image = target_image
                self.target_labels[target_index].config(text=f"已选择图像: {os.path.basename(file_path)}")
                
                # 使用PIL显示预览图像
                try:
                    preview = Image.open(file_path)
                    preview.thumbnail((150, 150))  # 缩放预览图像
                    photo = ImageTk.PhotoImage(preview)
                    self.preview_labels[target_index].config(image=photo)
                    self.preview_labels[target_index].image = photo  # 保持引用
                except Exception as e:
                    print(f"预览图像显示失败: {str(e)}")
                
                self.save_config()
            except Exception as e:
                messagebox.showerror("错误", f"加载图像时出错: {str(e)}")

    def capture_region_as_target(self, target_index):
        """截取屏幕区域作为目标图像"""
        self.root.iconify()  # 最小化主窗口
        time.sleep(0.5)  # 等待窗口最小化
        
        select_window = tk.Tk()
        select_window.attributes('-alpha', 0.3, '-fullscreen', True)
        select_window.configure(cursor="cross")
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        def on_mouse_down(event):
            self.start_x = event.x
            self.start_y = event.y
            
        def on_mouse_drag(event):
            if hasattr(self, 'rect'):
                select_window.delete(self.rect)
            self.rect = select_window.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline='red', width=2
            )
            
        def on_mouse_up(event):
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
            
            if x2 - x1 > 0 and y2 - y1 > 0:
                # 创建保存目录
                if not os.path.exists('target_images'):
                    os.makedirs('target_images')
                
                # 生成文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                file_path = os.path.join('target_images', f'target_{timestamp}.png')
                
                # 截取并保存图像
                try:
                    screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                    screenshot.save(file_path, 'PNG')
                    
                    # 加载图像
                    target_image = cv2.imread(file_path)
                    if target_image is None:
                        raise ValueError("无法加载截取的图像")
                    
                    self.targets[target_index].path = file_path
                    self.targets[target_index].image = target_image
                    self.target_labels[target_index].config(text=f"已截取图像: {os.path.basename(file_path)}")
                    
                    # 显示预览
                    preview = Image.open(file_path)
                    preview.thumbnail((150, 150))
                    photo = ImageTk.PhotoImage(preview)
                    self.preview_labels[target_index].config(image=photo)
                    self.preview_labels[target_index].image = photo
                    
                    self.save_config()
                    select_window.quit()
                except Exception as e:
                    messagebox.showerror("错误", f"保存截图时出错: {str(e)}")
            else:
                messagebox.showerror("错误", "请选择一个有效的区域")
        
        select_window.bind('<Button-1>', on_mouse_down)
        select_window.bind('<B1-Motion>', on_mouse_drag)
        select_window.bind('<ButtonRelease-1>', on_mouse_up)
        select_window.bind('<Escape>', lambda e: select_window.quit())
        
        select_window.mainloop()
        try:
            select_window.destroy()
        except:
            pass
        
        self.root.deiconify()  # 恢复主窗口

    def select_region(self):
        self.root.iconify()  # 最小化主窗口
        time.sleep(0.5)  # 等待窗口最小化
        
        select_window = tk.Tk()
        select_window.attributes('-alpha', 0.3, '-fullscreen', True)
        select_window.configure(cursor="cross")
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        def on_mouse_down(event):
            self.start_x = event.x
            self.start_y = event.y
            
        def on_mouse_drag(event):
            if hasattr(self, 'rect'):
                select_window.delete(self.rect)
            self.rect = select_window.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline='red', width=2
            )
            
        def on_mouse_up(event):
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
            
            if x2 - x1 > 0 and y2 - y1 > 0:
                self.region = (x1, y1, x2, y2)
                self.region_label.config(text=f"已选择区域: ({x1}, {y1}) -> ({x2}, {y2})")
                select_window.quit()
            else:
                messagebox.showerror("错误", "请选择一个有效的区域")
        
        select_window.bind('<Button-1>', on_mouse_down)
        select_window.bind('<B1-Motion>', on_mouse_drag)
        select_window.bind('<ButtonRelease-1>', on_mouse_up)
        select_window.bind('<Escape>', lambda e: select_window.quit())
        
        select_window.mainloop()
        try:
            select_window.destroy()
        except:
            pass
        
        self.root.deiconify()  # 恢复主窗口
        self.save_config()

    def toggle_monitoring(self):
        if not self.monitoring:
            if not self.region:
                messagebox.showerror("错误", "请先选择监控区域")
                return
                
            if not any(target.enabled and target.image is not None for target in self.targets):
                messagebox.showerror("错误", "请至少启用并设置一个目标图像")
                return
                
            try:
                cooldown = float(self.cooldown_var.get())
                if cooldown <= 0:
                    raise ValueError
                for i, target in enumerate(self.targets):
                    if target.enabled:
                        confidence = float(self.confidence_vars[i].get())
                        if not 0 <= confidence <= 1:
                            raise ValueError
            except ValueError:
                messagebox.showerror("错误", "冷却时间必须大于0，匹配精度必须在0到1之间")
                return
                
            self.monitoring = True
            self.start_button.config(text="停止监控")
            self.status_label.config(text="监控中...")
            self.monitor_thread = threading.Thread(target=self.monitor_screen, daemon=True)
            self.monitor_thread.start()
        else:
            self.monitoring = False
            self.start_button.config(text="开始监控")
            self.status_label.config(text="已停止")
            
    def monitor_screen(self):
        while self.monitoring:
            try:
                # 检查是否有启用的目标
                enabled_targets = [target for i, target in enumerate(self.targets) 
                                if self.enabled_vars[i].get() and target.image is not None]
                
                if not enabled_targets:
                    raise ValueError("没有启用的有效目标")
                
                # 捕获屏幕区域
                x1, y1, x2, y2 = self.region
                screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                if screenshot is None:
                    raise ValueError("无法捕获屏幕区域")
                
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                current_time = time.time()
                
                # 检查每个目标
                for i, target in enumerate(self.targets):
                    # 检查目标是否启用
                    if not self.enabled_vars[i].get() or target.image is None:
                        continue
                        
                    # 检查点击冷却时间
                    if current_time - target.last_click_time < float(self.cooldown_var.get()):
                        continue
                    
                    # 转换图像格式
                    if len(screenshot.shape) != len(target.image.shape):
                        current_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                        target_img = cv2.cvtColor(target.image, cv2.COLOR_BGR2GRAY)
                    elif screenshot.shape[2] != target.image.shape[2]:
                        current_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                        target_img = cv2.cvtColor(target.image, cv2.COLOR_BGR2GRAY)
                    else:
                        current_screenshot = screenshot
                        target_img = target.image
                    
                    # 确保目标图像不大于截图
                    if (target_img.shape[0] > current_screenshot.shape[0] or 
                        target_img.shape[1] > current_screenshot.shape[1]):
                        self.status_label.config(text=f"错误: 目标 {i+1} 大于监控区域")
                        continue
                    
                    # 模板匹配
                    try:
                        target.confidence = float(self.confidence_vars[i].get())
                    except ValueError:
                        target.confidence = 0.8
                    
                    result = cv2.matchTemplate(current_screenshot, target_img, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    if max_val >= target.confidence:
                        x = x1 + max_loc[0] + target.image.shape[1] // 2
                        y = y1 + max_loc[1] + target.image.shape[0] // 2
                        pyautogui.click(x, y)
                        target.last_click_time = current_time
                        self.status_label.config(text=f"找到目标 {i+1} 并点击: ({x}, {y})")
                
            except Exception as e:
                self.status_label.config(text=f"错误: {str(e)}")
                self.monitoring = False
                self.start_button.config(text="开始监控")
                break
                
            time.sleep(0.1)  # 降低CPU使用率

    def save_config(self):
        config = {
            'region': self.region,
            'max_targets': self.MAX_TARGETS,
            'targets': [{
                'path': target.path,
                'confidence': self.confidence_vars[i].get(),
                'enabled': self.enabled_vars[i].get()
            } for i, target in enumerate(self.targets)],
            'cooldown': self.cooldown_var.get()
        }
        try:
            with open('auto_click_config.json', 'w') as f:
                json.dump(config, f, indent=4)
        except:
            pass
            
    def load_config(self):
        try:
            with open('auto_click_config.json', 'r') as f:
                config = json.load(f)
                
            if config.get('region'):
                self.region = tuple(config['region'])
                self.region_label.config(text=f"已选择区域: ({self.region[0]}, {self.region[1]}) -> ({self.region[2]}, {self.region[3]})")
                
            if config.get('targets'):
                # 只加载与当前MAX_TARGETS数量相匹配的配置
                for i, target_config in enumerate(config['targets'][:self.MAX_TARGETS]):
                    if target_config.get('path') and os.path.exists(target_config['path']):
                        self.targets[i].path = target_config['path']
                        self.targets[i].image = cv2.imread(target_config['path'])
                        self.target_labels[i].config(text=f"已选择图像: {os.path.basename(target_config['path'])}")
                        
                        preview = Image.open(target_config['path'])
                        preview.thumbnail((150, 150))
                        photo = ImageTk.PhotoImage(preview)
                        self.preview_labels[i].config(image=photo)
                        self.preview_labels[i].image = photo
                        
                    if target_config.get('confidence'):
                        self.confidence_vars[i].set(target_config['confidence'])
                    if target_config.get('enabled') is not None:
                        self.enabled_vars[i].set(target_config['enabled'])
                        
            if config.get('cooldown'):
                self.cooldown_var.set(config['cooldown'])
        except:
            pass
            
    def run(self):
        self.root.mainloop()

    def __del__(self):
        """清理资源"""
        try:
            keyboard.unhook_all()  # 清理所有快捷键
        except:
            pass

def main():
    app = AutoClickGUI()
    app.run()

if __name__ == "__main__":
    main()
