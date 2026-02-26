import time
import threading
import subprocess
import sys
import os
import json
from colorama import init, Fore
from dotenv import load_dotenv
from browser_manager import BrowserManager
from api_crawler import APICrawler
from storage import Storage
from utils import logger, ErrorHandler
from qt_gui import QtGUIServer
from browser_thread import BrowserOperationThread

init(autoreset=True)

# 读取配置文件
def load_config():
    """加载配置文件"""
    # 获取程序所在目录
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    config_path = os.path.join(base_dir, 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
    return {
        "auth_info": {},
        "skip_browser": False,
        "log_level": "ERROR"
    }

# 全局配置
config = load_config()
# 设置日志级别
# 简化日志配置，直接使用默认配置
import logging
logging.basicConfig(level=getattr(logging, config.get('log_level', 'ERROR')),
                    format='%(asctime)s - %(levelname)s - %(message)s')

def install_playwright_browsers():
    """检查Playwright浏览器驱动"""
    try:
        # 如果配置文件设置了跳过浏览器，则直接返回True
        if config.get('skip_browser', False):
            print(Fore.GREEN + "跳过浏览器驱动检查")
            logger.info("跳过浏览器驱动检查")
            return True
        
        print(Fore.CYAN + "正在检查Playwright浏览器驱动...")
        logger.info("正在检查Playwright浏览器驱动...")
        
        # 检测是否在打包后的环境中运行
        is_packaged = getattr(sys, 'frozen', False)
        
        # 尝试导入playwright并检查浏览器是否已安装
        try:
            from playwright.sync_api import sync_playwright
            import os
            
            # 检查浏览器驱动是否存在
            with sync_playwright() as p:
                try:
                    # 尝试启动浏览器，如果驱动不存在会抛出异常
                    browser = p.chromium.launch(headless=True)
                    browser.close()
                    print(Fore.GREEN + "Playwright浏览器驱动已安装")
                    logger.info("Playwright浏览器驱动已安装")
                    return True
                except Exception as e:
                    if "Executable doesn't exist" in str(e) or "doesn't exist at" in str(e):
                        print(Fore.RED + "Playwright浏览器驱动未安装")
                        logger.error("Playwright浏览器驱动未安装")
                        
                        # 尝试获取系统中已安装的Playwright浏览器驱动路径
                        print(Fore.YELLOW + "尝试查找系统中已安装的浏览器驱动...")
                        logger.info("尝试查找系统中已安装的浏览器驱动...")
                        
                        # 常见的Playwright浏览器驱动路径
                        common_paths = [
                            os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
                            os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
                            os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
                            os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-win/chrome.exe"),
                        ]
                        
                        found_driver = False
                        for path_pattern in common_paths:
                            import glob
                            matching_paths = glob.glob(path_pattern)
                            if matching_paths:
                                print(Fore.GREEN + f"找到浏览器驱动: {matching_paths[0]}")
                                logger.info(f"找到浏览器驱动: {matching_paths[0]}")
                                # 设置PLAYWRIGHT_BROWSERS_PATH环境变量
                                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(matching_paths[0]))))
                                print(Fore.GREEN + f"已设置PLAYWRIGHT_BROWSERS_PATH: {os.environ['PLAYWRIGHT_BROWSERS_PATH']}")
                                logger.info(f"已设置PLAYWRIGHT_BROWSERS_PATH: {os.environ['PLAYWRIGHT_BROWSERS_PATH']}")
                                found_driver = True
                                break
                        
                        if found_driver:
                            # 重新检查浏览器驱动
                            try:
                                browser = p.chromium.launch(headless=True)
                                browser.close()
                                print(Fore.GREEN + "Playwright浏览器驱动安装成功！")
                                logger.info("Playwright浏览器驱动安装成功！")
                                return True
                            except Exception as e2:
                                print(Fore.RED + f"设置浏览器驱动路径后仍无法启动: {str(e2)}")
                                logger.error(f"设置浏览器驱动路径后仍无法启动: {str(e2)}")
                        
                        # 如果在打包后的环境中，给出错误提示但仍然允许程序运行
                        if is_packaged:
                            print(Fore.RED + "错误：打包后的程序需要安装Playwright浏览器驱动")
                            print(Fore.RED + "请执行以下命令安装浏览器驱动：")
                            print(Fore.RED + "  playwright install chromium")
                            print(Fore.YELLOW + "程序将尝试使用系统默认浏览器继续运行...")
                            logger.error("打包后的程序需要安装Playwright浏览器驱动，请执行: playwright install chromium")
                            logger.info("程序将尝试使用系统默认浏览器继续运行...")
                            return True  # 即使驱动未安装，也允许程序继续运行
                        else:
                            # 在开发环境中，自动安装
                            print(Fore.YELLOW + "正在自动安装...")
                            logger.info("正在自动安装...")
                            
                            # 使用subprocess运行playwright install命令
                            try:
                                result = subprocess.run(
                                    [sys.executable, "-m", "playwright", "install", "chromium"],
                                    capture_output=True,
                                    text=True,
                                    timeout=600  # 10分钟超时
                                )
                                
                                if result.returncode == 0:
                                    print(Fore.GREEN + "Playwright浏览器驱动安装成功！")
                                    logger.info("Playwright浏览器驱动安装成功！")
                                    return True
                                else:
                                    print(Fore.RED + f"Playwright浏览器驱动安装失败: {result.stderr}")
                                    print(Fore.YELLOW + "程序将尝试使用系统默认浏览器继续运行...")
                                    logger.error(f"Playwright浏览器驱动安装失败: {result.stderr}")
                                    logger.info("程序将尝试使用系统默认浏览器继续运行...")
                                    return True  # 即使安装失败，也允许程序继续运行
                            except subprocess.TimeoutExpired:
                                print(Fore.YELLOW + "Playwright浏览器驱动安装超时，请手动执行: playwright install chromium")
                                print(Fore.YELLOW + "程序将尝试使用系统默认浏览器继续运行...")
                                logger.warning("Playwright浏览器驱动安装超时，请手动执行: playwright install chromium")
                                logger.info("程序将尝试使用系统默认浏览器继续运行...")
                                return True  # 即使超时，也允许程序继续运行
                    else:
                        print(Fore.GREEN + "Playwright浏览器驱动已安装")
                        logger.info("Playwright浏览器驱动已安装")
                        return True
        except ImportError:
            print(Fore.RED + "Playwright未安装")
            logger.error("Playwright未安装")
            
            # 如果在打包后的环境中，给出错误提示
            if is_packaged:
                print(Fore.RED + "错误：打包后的程序需要安装Playwright")
                print(Fore.RED + "请执行以下命令安装：")
                print(Fore.RED + "  pip install playwright")
                print(Fore.RED + "  playwright install chromium")
                print(Fore.RED + "安装完成后重新运行程序")
                logger.error("打包后的程序需要安装Playwright，请执行: pip install playwright && playwright install chromium")
                return False
            else:
                # 在开发环境中，自动安装
                print(Fore.YELLOW + "正在安装Playwright...")
                logger.info("正在安装Playwright...")
                
                # 安装playwright
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "playwright"],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5分钟超时
                    )
                    
                    if result.returncode == 0:
                        print(Fore.GREEN + "Playwright安装成功！")
                        logger.info("Playwright安装成功！")
                        
                        # 继续安装浏览器驱动
                        print(Fore.YELLOW + "正在安装浏览器驱动...")
                        logger.info("正在安装浏览器驱动...")
                        
                        result = subprocess.run(
                            [sys.executable, "-m", "playwright", "install", "chromium"],
                            capture_output=True,
                            text=True,
                            timeout=600  # 10分钟超时
                        )
                        
                        if result.returncode == 0:
                            print(Fore.GREEN + "Playwright浏览器驱动安装成功！")
                            logger.info("Playwright浏览器驱动安装成功！")
                            return True
                        else:
                            print(Fore.RED + f"Playwright浏览器驱动安装失败: {result.stderr}")
                            logger.error(f"Playwright浏览器驱动安装失败: {result.stderr}")
                            return False
                    else:
                        print(Fore.RED + f"Playwright安装失败: {result.stderr}")
                        logger.error(f"Playwright安装失败: {result.stderr}")
                        return False
                except subprocess.TimeoutExpired:
                    print(Fore.YELLOW + "Playwright安装超时，请手动执行: pip install playwright && playwright install chromium")
                    logger.warning("Playwright安装超时，请手动执行: pip install playwright && playwright install chromium")
                    return False
    except Exception as e:
        print(Fore.RED + f"检查Playwright浏览器驱动时发生错误: {str(e)}")
        logger.error(f"检查Playwright浏览器驱动时发生错误: {str(e)}")
        return False

class PalmpayCrawler:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(PalmpayCrawler, cls).__new__(cls)
        return cls._instance

    def _load_env_file(self):
        """加载.env文件，支持打包后的程序"""
        try:
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
                env_file = os.path.join(base_path, '.env')
                if not os.path.exists(env_file):
                    resources_path = os.path.join(os.path.dirname(base_path), 'Resources')
                    env_file = os.path.join(resources_path, '.env')
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
                env_file = os.path.join(base_path, '.env')
            
            if os.path.exists(env_file):
                load_dotenv(env_file)
                print(Fore.GREEN + f"已加载环境配置文件: {env_file}")
                logger.info(f"已加载环境配置文件: {env_file}")
            else:
                print(Fore.YELLOW + f"未找到环境配置文件: {env_file}")
                logger.warning(f"未找到环境配置文件: {env_file}")
        except Exception as e:
            print(Fore.RED + f"加载环境配置文件失败: {str(e)}")
            logger.error(f"加载环境配置文件失败: {str(e)}")
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self._load_env_file()
            self.browser_manager = BrowserManager()
            self.storage = Storage()
            self.crawler = None
            self.is_running = False
            self.start_crawler_event = threading.Event()
            self.stop_crawler_event = threading.Event()
            self.crawler_thread = None
            self.browser_thread = None
            
            # 启动Qt GUI客户端
            self.gui_server = QtGUIServer(self.browser_manager)
            self.gui = self.gui_server.start()
            # 设置GUI的parent属性为当前爬虫实例，以便GUI能够访问爬虫方法
            if self.gui:
                self.gui.parent = self
            
            # 添加初始日志
            print(Fore.CYAN + "=== Palmpay商户后台爬虫 ===")
            print(Fore.GREEN + "日志系统启动成功")
            print(Fore.GREEN + "Qt GUI客户端已启动")
            
            # 启动浏览器操作线程
            self.browser_thread = BrowserOperationThread(self.browser_manager, self.gui_server)
            # 将浏览器线程赋值给gui_server，以便QtGUI能够访问
            self.gui_server.browser_thread = self.browser_thread
            self.browser_thread.start()
            
            # 等待GUI初始化
            time.sleep(2)
            
            # 添加初始日志到GUI
            self.gui_server.add_log("=== Palmpay商户后台爬虫 ===", "info")
            self.gui_server.add_log("日志系统启动成功", "green")
            self.gui_server.add_log("Qt GUI客户端已启动", "info")
            self.gui_server.add_log("浏览器操作线程启动中...", "cyan")
            self.initialized = True
    
    def start(self):
        """启动爬虫"""
        print(Fore.CYAN + "=== Palmpay商户后台爬虫 ===")
        print(Fore.CYAN + "启动爬虫程序...")
        
        try:
            # 创建初始爬虫实例（无浏览器）
            self.crawler = APICrawler(self.browser_manager, self.gui_server, self.storage)
            # 将browser_thread赋值给crawler，以便在token过期时获取新的认证信息
            self.crawler.browser_thread = self.browser_thread
            self.crawler.add_log("=== Palmpay商户后台爬虫 ===", 'info')
            self.crawler.add_log("正在初始化系统...", 'cyan')
            
            # 添加初始日志
            self.gui_server.add_log("系统初始化中...", "green")
            self.gui_server.add_log("正在启动爬虫线程...", "cyan")
            
            # 启动爬虫线程（不包含浏览器初始化，浏览器初始化由BrowserOperationThread负责）
            self.start_crawler_thread()
            
            # 保持程序运行
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(Fore.YELLOW + "用户中断程序")
            finally:
                self.stop_crawler_event.set()
                if hasattr(self, 'browser_thread'):
                    self.browser_thread.stop()
                print(Fore.GREEN + "程序退出")
        except Exception as e:
            print(Fore.RED + f"爬虫启动失败: {str(e)}")
            self.gui_server.add_log(f"爬虫启动失败: {str(e)}", "red")
            if hasattr(self, 'browser_thread'):
                self.browser_thread.stop()
    
    def start_crawler_thread(self):
        """启动爬虫线程"""
        if self.crawler_thread and self.crawler_thread.is_alive():
            print(Fore.YELLOW + "爬虫线程已在运行")
            return
        
        self.crawler_thread = threading.Thread(target=self.run_crawler_task)
        self.crawler_thread.daemon = True
        self.crawler_thread.start()
        print(Fore.GREEN + "爬虫线程已启动")
    
    def run_crawler_task(self):
        """爬虫任务执行函数"""
        # 浏览器初始化由BrowserOperationThread负责
        print(Fore.CYAN + "爬虫线程启动...")
        self.gui_server.add_log("爬虫线程启动...", 'cyan')
        
        try:
            # 检查是否跳过浏览器操作
            skip_browser = getattr(self.browser_manager, 'skip_browser', False)
            if skip_browser:
                print(Fore.GREEN + "跳过浏览器操作，直接从配置文件读取认证信息")
                self.gui_server.add_log("跳过浏览器操作，直接从配置文件读取认证信息", 'green')
                # 直接获取认证信息
                auth_info = self.browser_manager.get_auth_info()
                if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                    print(Fore.GREEN + "从配置文件成功加载认证信息")
                    self.gui_server.add_log("从配置文件成功加载认证信息", 'green')
                else:
                    print(Fore.YELLOW + "配置文件中的认证信息不完整")
                    self.gui_server.add_log("配置文件中的认证信息不完整", 'yellow')
            else:
                # 等待浏览器线程完成认证信息的获取
                print(Fore.CYAN + "等待浏览器线程完成认证信息的获取...")
                time.sleep(10)  # 给浏览器线程足够的时间来获取认证信息
                
                # 检查是否获取到了认证信息
                auth_info = getattr(self.browser_manager, 'auth_info', None)
                if not auth_info:
                    # 尝试从文件中加载认证信息
                    print(Fore.YELLOW + "未获取到认证信息，尝试从文件中加载...")
                    self.gui_server.add_log("未获取到认证信息，尝试从文件中加载...", 'yellow')
                    # 这里可以添加从文件中加载认证信息的逻辑
            
            # 爬虫准备就绪
            print(Fore.GREEN + "爬虫准备就绪！")
            print(Fore.GREEN + "请在Qt GUI客户端中点击 '启动爬虫' 按钮开始爬取数据")
            self.gui_server.add_log("爬虫准备就绪！请点击 '启动爬虫' 按钮开始爬取数据", 'green')
            self.gui_server.add_log("爬虫准备就绪！请在Qt GUI客户端中点击 '启动爬虫' 按钮开始爬取", 'info')
            
        except Exception as e:
            print(Fore.RED + f"初始化爬虫失败: {str(e)}")
            self.gui_server.add_log(f"初始化爬虫失败: {str(e)}", 'red')
            return
        
        # 主循环
        while True:
            # 等待启动事件
            self.start_crawler_event.wait()
            
            # 检查是否需要停止
            if self.stop_crawler_event.is_set():
                break
            
            # 检查是否已经在运行
            if self.is_running:
                print(Fore.YELLOW + "爬虫任务已经在运行，跳过本次执行")
                self.gui_server.add_log("爬虫任务已经在运行，跳过本次执行", 'yellow')
                self.start_crawler_event.clear()
                continue
            
            # 标记为正在运行
            self.is_running = True
            
            # 执行爬虫任务
            try:
                print(Fore.CYAN + "开始执行爬虫任务...")
                self.gui_server.add_log("开始执行爬虫任务...", 'info')
                
                # 执行爬虫
                start_timestamp = getattr(self, 'start_timestamp', None)
                end_timestamp = getattr(self, 'end_timestamp', None)
                settlement_status = getattr(self, 'settlement_status', None)
                
                # 调用API获取订单数据
                order_data = self.crawler.crawl_orders_by_api(start_timestamp, end_timestamp, settlement_status=settlement_status, stop_event=self.stop_crawler_event)
                
                # 检查是否被停止
                if self.stop_crawler_event.is_set():
                    print(Fore.YELLOW + "爬虫任务被用户停止")
                    self.gui_server.add_log("爬虫任务被用户停止", 'yellow')
                    return
                
                # 确保order_data是一个列表
                if not isinstance(order_data, list):
                    order_data = []
                
                # 打印订单数据信息
                print(Fore.GREEN + f"爬取完成，共获取 {len(order_data)} 条订单数据")
                self.gui_server.add_log(f"爬取完成，共获取 {len(order_data)} 条订单数据", 'green')
                
                if not order_data:
                    self.gui_server.add_log("未获取到订单数据", 'yellow')
                    print(Fore.YELLOW + "未获取到订单数据")
                
                sink_label = "存储目标"
                if self.storage and hasattr(self.storage, 'get_sink_label'):
                    sink_label = self.storage.get_sink_label()
                # 数据已通过append_single_to_db实时保存，无需再次批量保存
                print(Fore.GREEN + f"数据已通过实时方式写入{sink_label}")
                self.gui_server.add_log(f"数据已通过实时方式写入{sink_label}", 'green')
                
            except Exception as e:
                print(Fore.RED + f"爬虫任务执行失败: {str(e)}")
                self.gui_server.add_log(f"爬虫任务执行失败: {str(e)}", 'red')
            finally:
                # 标记为不在运行
                self.is_running = False
                # 重置停止事件
                self.stop_crawler_event.clear()
            
            # 重置启动事件
            self.start_crawler_event.clear()
            
            # 更新GUI状态
            self.gui_server.add_log("爬虫任务完成", 'info')
    
    def trigger_crawler(self, start_timestamp, end_timestamp, settlement_status=None):
        """触发爬虫执行（从Qt GUI调用）"""
        if not self.crawler:
            self.gui_server.add_log("爬虫未初始化，请先登录", 'red')
            return False
        
        if self.is_running:
            # 爬虫正在运行，停止爬虫
            self.gui_server.add_log("停止爬虫...", 'yellow')
            self.stop_crawler_event.set()
            # 重置运行状态
            self.is_running = False
            return True
        
        # 存储日期时间戳和结算状态
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.settlement_status = settlement_status
        
        # 重置停止事件
        self.stop_crawler_event.clear()
        # 设置启动事件
        self.start_crawler_event.set()
        self.gui_server.add_log("已触发爬虫执行", 'green')
        return True
    
    def setup_export_listener(self):
        """设置导出监听器"""
        def on_export():
            """导出回调函数"""
            if self.is_running:
                print(Fore.YELLOW + "爬虫正在运行中，停止爬虫...")
                logger.info("用户点击停止按钮，停止爬虫")
                self.is_running = False
                # 更新按钮状态
                self.browser_manager.page.evaluate('''
                    const button = document.getElementById('export-button');
                    if (button) {
                        button.innerHTML = '已停止';
                        button.style.backgroundColor = '#ff9800';
                        setTimeout(() => {
                            button.innerHTML = '一键导出';
                            button.style.backgroundColor = '#4CAF50';
                        }, 2000);
                    }
                ''')
                return
            
            # 在新线程中执行爬虫，避免阻塞主线程
            export_thread = threading.Thread(target=self.run_export)
            export_thread.daemon = True
            export_thread.start()
        
        # 注入监听器到浏览器
        self.browser_manager.page.expose_function("startExport", on_export)
        
        # 在浏览器中添加事件监听器
        self.browser_manager.page.evaluate('''
            window.addEventListener('startExport', function() {
                window.startExport();
            });
        ''')
        
        print(Fore.GREEN + "导出监听器设置成功")
        logger.info("导出监听器设置成功")
    
    @ErrorHandler.handle_exception
    def run_export(self):
        """执行导出任务"""
        self.is_running = True
        logger.info("开始导出数据")
        print(Fore.CYAN + "=== 开始导出数据 ===")
        
        try:
            # 爬取订单数据
            order_data, pagination = self.crawler.get_order_list_from_api()
            
            # 确保order_data是一个列表
            if isinstance(order_data, tuple):
                order_data = order_data[0]
            
            if not order_data:
                logger.warning("未获取到订单数据")
                print(Fore.YELLOW + "未获取到订单数据")
                return
            
            sink_label = "存储目标"
            if self.storage and hasattr(self.storage, 'get_sink_label'):
                sink_label = self.storage.get_sink_label()
            # 存储到当前目标
            if self.storage.save_to_db(order_data, auth_info=getattr(self.crawler, 'auth_info', None)):
                logger.info(f"导出完成，共获取 {len(order_data)} 条订单数据")
                print(Fore.GREEN + f"导出完成，数据已写入{sink_label}！")
                # 更新按钮状态
                self.browser_manager.page.evaluate('''
                    const button = document.getElementById('export-button');
                    if (button) {
                        button.innerHTML = '导出完成';
                        button.style.backgroundColor = '#4CAF50';
                        setTimeout(() => {
                            button.innerHTML = '一键导出';
                        }, 2000);
                    }
                ''')
            else:
                logger.error("导出失败")
                print(Fore.RED + "导出失败")
                # 更新按钮状态
                self.browser_manager.page.evaluate('''
                    const button = document.getElementById('export-button');
                    if (button) {
                        button.innerHTML = '导出失败';
                        button.style.backgroundColor = '#f44336';
                        setTimeout(() => {
                            button.innerHTML = '一键导出';
                            button.style.backgroundColor = '#4CAF50';
                        }, 2000);
                    }
                ''')
        except Exception as e:
            logger.exception(f"导出过程中发生错误: {str(e)}")
            print(Fore.RED + f"导出过程中发生错误: {str(e)}")
            # 更新按钮状态
            self.browser_manager.page.evaluate('''
                const button = document.getElementById('export-button');
                if (button) {
                    button.innerHTML = '导出失败';
                    button.style.backgroundColor = '#f44336';
                    setTimeout(() => {
                        button.innerHTML = '一键导出';
                        button.style.backgroundColor = '#4CAF50';
                    }, 2000);
                }
            ''')
        finally:
            self.is_running = False
            logger.info("导出任务结束")

if __name__ == "__main__":
    import threading
    
    # 首先检查并安装Playwright浏览器驱动
    print(Fore.CYAN + "=== Palmpay商户后台爬虫 ===")
    install_playwright_browsers()
    
    # 创建爬虫实例
    crawler = PalmpayCrawler()
    
    # 在单独的线程中运行爬虫
    def run_crawler():
        try:
            crawler.start()
        except Exception as e:
            print(Fore.RED + f"运行爬虫时发生错误: {str(e)}")
            logger.error(f"运行爬虫时发生错误: {str(e)}")
    
    crawler_thread = threading.Thread(target=run_crawler)
    crawler_thread.daemon = True
    crawler_thread.start()
    
    # 运行Qt应用事件循环
    if hasattr(crawler, 'gui_server') and crawler.gui_server:
        crawler.gui_server.run()
