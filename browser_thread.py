import threading
import time
from colorama import Fore

class BrowserOperationThread(threading.Thread):
    """浏览器操作线程，用于在单独的线程中执行浏览器操作"""
    def __init__(self, browser_manager, gui_server):
        super().__init__()
        self.browser_manager = browser_manager
        self.gui_server = gui_server
        self.daemon = True
        self.operations = []
        self.operation_lock = threading.Lock()
        self.running = True
        self.shared_auth_info = None  # 共享的认证信息，供其他线程读取
        self.auth_info_lock = threading.Lock()  # 认证信息的锁
        self._skip_browser_logged = False  # 标志位，控制跳过浏览器操作时的日志输出
    
    def run(self):
        """线程运行函数"""
        print(Fore.CYAN + "浏览器操作线程启动...")
        self.gui_server.add_log("浏览器操作线程启动...", "cyan")
        
        # 初始化浏览器
        self.initialize_browser()
        
        # 处理操作队列
        while self.running:
            self.process_operations()
            time.sleep(0.1)
    
    def initialize_browser(self):
        """初始化浏览器"""
        try:
            # 检查是否跳过浏览器操作
            if hasattr(self.browser_manager, 'skip_browser') and self.browser_manager.skip_browser:
                print(Fore.GREEN + "跳过浏览器初始化，使用配置文件中的认证信息")
                self.gui_server.add_log("跳过浏览器初始化，使用配置文件中的认证信息", "green")
                
                # 直接从浏览器管理器获取认证信息（会从配置文件读取）
                auth_info = self.browser_manager.get_auth_info()
                with self.auth_info_lock:
                    self.shared_auth_info = auth_info
                if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                    print(Fore.GREEN + "认证信息已从配置文件加载并更新到共享变量")
                    self.gui_server.add_log("认证信息已从配置文件加载并更新到共享变量", "green")
                else:
                    print(Fore.YELLOW + "配置文件中的认证信息不完整")
                    self.gui_server.add_log("配置文件中的认证信息不完整", "yellow")
                return
            
            print(Fore.CYAN + "初始化浏览器...")
            self.gui_server.add_log("初始化浏览器...", "cyan")
            
            # 启动浏览器
            page = self.browser_manager.start_browser()
            if page:
                print(Fore.GREEN + "浏览器启动成功")
                self.gui_server.add_log("浏览器启动成功", "green")
                
                # 导航到订单列表页面
                print(Fore.CYAN + "正在导航到订单列表页面...")
                self.gui_server.add_log("正在导航到订单列表页面...", "cyan")
                
                success = self.browser_manager.navigate_to_order_list()
                if success:
                    print(Fore.GREEN + "订单列表页面加载成功")
                    self.gui_server.add_log("订单列表页面加载成功", "green")
                    
                    # 获取认证信息并保存到共享变量
                    auth_info = self.browser_manager.get_auth_info()
                    with self.auth_info_lock:
                        self.shared_auth_info = auth_info
                    if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                        print(Fore.GREEN + "认证信息已更新到共享变量")
                        self.gui_server.add_log("认证信息已更新到共享变量", "green")
                    else:
                        print(Fore.YELLOW + "无法获取认证信息")
                        self.gui_server.add_log("无法获取认证信息", "yellow")
                else:
                    print(Fore.RED + "导航到订单列表失败")
                    self.gui_server.add_log("导航到订单列表失败", "red")
            else:
                print(Fore.RED + "浏览器启动失败")
                self.gui_server.add_log("浏览器启动失败", "red")
        except Exception as e:
            print(Fore.RED + f"初始化浏览器失败: {str(e)}")
            self.gui_server.add_log(f"初始化浏览器失败: {str(e)}", "red")
    
    def process_operations(self):
        """处理操作队列"""
        with self.operation_lock:
            if self.operations:
                operation = self.operations.pop(0)
                self.execute_operation(operation)
    
    def execute_operation(self, operation):
        """执行操作"""
        try:
            operation_type = operation.get('type')
            callback = operation.get('callback')
            
            if operation_type == 'navigate_to_order_list':
                result = self.navigate_to_order_list()
            elif operation_type == 'check_login_status':
                result = self.check_login_status()
            elif operation_type == 'check_order_page_status':
                result = self.check_order_page_status()
            elif operation_type == 'get_auth_info':
                result = self.get_auth_info()
            else:
                result = None
            
            # 如果有回调函数，调用它来返回结果
            if callback:
                callback(result)
        except Exception as e:
            print(Fore.RED + f"执行操作失败: {str(e)}")
            self.gui_server.add_log(f"执行操作失败: {str(e)}", "red")
            
            # 如果有回调函数，调用它来返回错误结果
            callback = operation.get('callback')
            if callback:
                callback(False)
    
    def get_auth_info(self):
        """获取认证信息并更新到共享变量"""
        try:
            print(Fore.CYAN + "正在获取认证信息...")
            self.gui_server.add_log("正在获取认证信息...", "cyan")
            
            auth_info = self.browser_manager.get_auth_info()
            
            # 更新共享变量
            with self.auth_info_lock:
                self.shared_auth_info = auth_info
            
            if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                print(Fore.GREEN + "获取认证信息成功")
                self.gui_server.add_log("获取认证信息成功", "green")
                print(Fore.CYAN + f"获取到的认证信息: {auth_info}")
                return True
            else:
                print(Fore.RED + "获取认证信息失败")
                self.gui_server.add_log("获取认证信息失败", "red")
                return False
        except Exception as e:
            print(Fore.RED + f"获取认证信息失败: {str(e)}")
            self.gui_server.add_log(f"获取认证信息失败: {str(e)}", "red")
            return False
    
    def navigate_to_order_list(self):
        """导航到订单列表页面"""
        try:
            print(Fore.CYAN + "正在导航到订单列表页面...")
            self.gui_server.add_log("正在导航到订单列表页面...", "cyan")
            
            success = self.browser_manager.navigate_to_order_list()
            if success:
                print(Fore.GREEN + "成功跳转到订单列表页面")
                self.gui_server.add_log("成功跳转到订单列表页面", "green")
                return True
            else:
                print(Fore.RED + "跳转订单列表页面失败")
                self.gui_server.add_log("跳转订单列表页面失败", "red")
                return False
        except Exception as e:
            print(Fore.RED + f"导航到订单列表页面失败: {str(e)}")
            self.gui_server.add_log(f"导航到订单列表页面失败: {str(e)}", "red")
            return False
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            # 检查是否跳过浏览器操作
            if hasattr(self.browser_manager, 'skip_browser') and self.browser_manager.skip_browser:
                if not self._skip_browser_logged:
                    print(Fore.GREEN + "跳过浏览器操作，直接检查配置文件中的认证信息")
                    self.gui_server.add_log("跳过浏览器操作，直接检查配置文件中的认证信息", "green")
                auth_info = self.browser_manager.get_auth_info()
                if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                    if not self._skip_browser_logged:
                        print(Fore.GREEN + "配置文件中存在有效的认证信息，视为已登录")
                        self.gui_server.add_log("配置文件中存在有效的认证信息，视为已登录", "green")
                        self._skip_browser_logged = True
                    return True
                else:
                    print(Fore.YELLOW + "配置文件中的认证信息不完整")
                    self.gui_server.add_log("配置文件中的认证信息不完整", "yellow")
                    return False
            
            page = self.browser_manager.get_page()
            if page:
                current_url = page.url
                print(Fore.CYAN + f"当前浏览器URL: {current_url}")
                self.gui_server.add_log(f"当前浏览器URL: {current_url}", "info")
                
                if 'login' in current_url:
                    print(Fore.YELLOW + "检测到登录页面，未登录")
                    self.gui_server.add_log("检测到登录页面，未登录", "yellow")
                    return False
                elif 'reconciliation/transaction/list' in current_url:
                    print(Fore.GREEN + "检测到订单列表页面，已登录")
                    self.gui_server.add_log("检测到订单列表页面，已登录", "green")
                    return True
                else:
                    # 不在登录页也不在订单页，尝试获取认证信息来判断是否登录
                    print(Fore.CYAN + "尝试获取认证信息来判断登录状态...")
                    auth_info = self.browser_manager.get_auth_info()
                    print(Fore.CYAN + f"获取到的认证信息: {auth_info}")
                    if auth_info:
                        if auth_info.get('token'):
                            print(Fore.GREEN + "检测到token，已登录")
                            self.gui_server.add_log("检测到token，已登录", "green")
                            return True
                        elif auth_info.get('pp_token'):
                            print(Fore.GREEN + "检测到pp_token，已登录")
                            self.gui_server.add_log("检测到pp_token，已登录", "green")
                            return True
                        else:
                            print(Fore.YELLOW + "未检测到有效的认证信息，未登录")
                            self.gui_server.add_log("未检测到有效的认证信息，未登录", "yellow")
                            return False
                    else:
                        print(Fore.YELLOW + "未获取到认证信息，未登录")
                        self.gui_server.add_log("未获取到认证信息，未登录", "yellow")
                        return False
            else:
                print(Fore.YELLOW + "无法获取浏览器页面")
                self.gui_server.add_log("无法获取浏览器页面", "yellow")
                return False
        except Exception as e:
            print(Fore.RED + f"检查登录状态失败: {str(e)}")
            self.gui_server.add_log(f"检查登录状态失败: {str(e)}", "red")
            return False
    
    def check_order_page_status(self):
        """检查是否在订单列表页"""
        try:
            # 检查是否跳过浏览器操作
            if hasattr(self.browser_manager, 'skip_browser') and self.browser_manager.skip_browser:
                if not self._skip_browser_logged:
                    print(Fore.GREEN + "跳过浏览器操作，直接检查配置文件中的认证信息")
                    self.gui_server.add_log("跳过浏览器操作，直接检查配置文件中的认证信息", "green")
                auth_info = self.browser_manager.get_auth_info()
                if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                    if not self._skip_browser_logged:
                        print(Fore.GREEN + "配置文件中存在有效的认证信息，视为已在订单页面")
                        self.gui_server.add_log("配置文件中存在有效的认证信息，视为已在订单页面", "green")
                        self._skip_browser_logged = True
                    return True
                else:
                    print(Fore.YELLOW + "配置文件中的认证信息不完整")
                    self.gui_server.add_log("配置文件中的认证信息不完整", "yellow")
                    return False
            
            page = self.browser_manager.get_page()
            if page:
                current_url = page.url
                print(Fore.CYAN + f"当前浏览器URL: {current_url}")
                self.gui_server.add_log(f"当前浏览器URL: {current_url}", "info")
                
                if 'reconciliation/transaction/list' in current_url:
                    print(Fore.GREEN + "检测到订单列表页面")
                    self.gui_server.add_log("检测到订单列表页面", "green")
                    return True
                else:
                    # 检查是否已经登录
                    auth_info = self.browser_manager.get_auth_info()
                    if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                        # 已登录但不在订单列表页，自动导航到订单列表页
                        print(Fore.YELLOW + "未检测到订单列表页面，正在导航...")
                        self.gui_server.add_log("未检测到订单列表页面，正在导航...", "yellow")
                        success = self.browser_manager.navigate_to_order_list()
                        if success:
                            print(Fore.GREEN + "成功导航到订单列表页面")
                            self.gui_server.add_log("成功导航到订单列表页面", "green")
                            return True
                        else:
                            print(Fore.RED + "导航到订单列表页面失败")
                            self.gui_server.add_log("导航到订单列表页面失败", "red")
                            return False
                    else:
                        print(Fore.YELLOW + "未检测到订单列表页面，且未登录")
                        self.gui_server.add_log("未检测到订单列表页面，且未登录", "yellow")
                        return False
            else:
                print(Fore.YELLOW + "无法获取浏览器页面")
                self.gui_server.add_log("无法获取浏览器页面", "yellow")
                return False
        except Exception as e:
            print(Fore.RED + f"检查订单页状态失败: {str(e)}")
            self.gui_server.add_log(f"检查订单页状态失败: {str(e)}", "red")
            return False
    
    def add_operation(self, operation):
        """添加操作到队列"""
        with self.operation_lock:
            self.operations.append(operation)
    
    def stop(self):
        """停止线程"""
        self.running = False
        # 检查是否跳过浏览器操作
        if not (hasattr(self.browser_manager, 'skip_browser') and self.browser_manager.skip_browser):
            self.browser_manager.close_browser()
        print(Fore.CYAN + "浏览器操作线程停止")
        self.gui_server.add_log("浏览器操作线程停止", "cyan")
