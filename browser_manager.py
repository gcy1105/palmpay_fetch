import time
import os
import threading
import webbrowser
import json
import sys

# 条件性导入playwright
def get_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        return None

class BrowserManager:
    def __init__(self):
        # 获取程序所在目录
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 读取配置文件
        self.config_path = os.path.join(base_dir, 'config.json')
        self.config = self.load_config()
        
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.browser_data_dir = os.path.join(os.getcwd(), 'browser_data')
        self.browser_thread_id = None  # 记录浏览器启动的线程ID
        self.use_system_browser = False  # 是否使用系统默认浏览器
        self.auth_info_path = os.path.join(os.getcwd(), 'auth_info.json')  # 认证信息存储路径
        self.skip_browser = self.config.get('skip_browser', False)  # 是否跳过浏览器操作
        self._skip_browser_logged = False  # 标志位，控制跳过浏览器操作时的日志输出
    
    def load_config(self):
        """加载配置文件"""
        print(f"加载配置文件，路径: {self.config_path}")
        print(f"配置文件是否存在: {os.path.exists(self.config_path)}")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"从配置文件读取的内容: {config}")
                return config
            except Exception as e:
                print(f"加载配置文件失败: {str(e)}")
        return {
            "auth_info": {},
            "skip_browser": False,
            "log_level": "ERROR"
        }
    
    def start_browser(self):
        """启动浏览器"""
        # 如果配置文件设置了跳过浏览器，则直接返回True
        if self.skip_browser:
            print("跳过浏览器启动")
            return True
        
        try:
            # 记录浏览器启动的线程ID
            self.browser_thread_id = threading.get_ident()
            print(f"浏览器启动线程ID: {self.browser_thread_id}")
            
            # 获取playwright
            sync_playwright = get_playwright()
            if not sync_playwright:
                print("playwright未安装，将使用系统默认浏览器")
                self.use_system_browser = True
                return self.start_system_browser()
            
            self.playwright = sync_playwright().start()
            
            # 启动浏览器，使用持久化上下文
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.browser_data_dir,
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            
            # 获取第一个页面，如果没有则创建一个
            if len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()
            
            return self.page
        except Exception as e:
            print(f"启动浏览器失败: {str(e)}")
            # 尝试使用系统默认浏览器
            print("尝试使用系统默认浏览器...")
            self.use_system_browser = True
            return self.start_system_browser()
    
    def start_system_browser(self):
        """使用系统默认浏览器"""
        try:
            print("正在打开系统默认浏览器...")
            # 打开系统默认浏览器并导航到登录页面
            login_url = 'https://business.palmpay.com/#/login'
            webbrowser.open(login_url)
            
            print("系统默认浏览器已打开，请在浏览器中完成登录")
            print("登录完成后，请按回车键继续...")
            
            # 等待用户确认登录完成
            input()
            
            # 尝试从本地文件加载认证信息
            if os.path.exists(self.auth_info_path):
                try:
                    with open(self.auth_info_path, 'r', encoding='utf-8') as f:
                        auth_info = json.load(f)
                    print("从本地文件加载认证信息成功")
                    return True
                except Exception as e:
                    print(f"从本地文件加载认证信息失败: {str(e)}")
            
            print("请手动输入认证信息...")
            print("请打开浏览器开发者工具，查看网络请求中的认证字段")
            print("通常在请求头或响应中包含 token、pp_token 等字段")
            
            # 手动输入认证信息
            auth_info = {
                'pp_token': input("请输入 pp_token: "),
                'token': input("请输入 token (可选): "),
                'deviceId': input("请输入 deviceId (可选，默认值: 8db6b9f4907b241696062774623cb93d): ") or '8db6b9f4907b241696062774623cb93d',
                'pp_device_id': input("请输入 pp_device_id (可选): "),
                'pp_client_ver': input("请输入 pp_client_ver (可选，默认值: 1.0.0): ") or '1.0.0',
                'merchantid': input("请输入 merchantid (可选): "),
                'merchantId': input("请输入 merchantId (可选): ")
            }
            
            # 保存认证信息到本地文件
            with open(self.auth_info_path, 'w', encoding='utf-8') as f:
                json.dump(auth_info, f, ensure_ascii=False, indent=2)
            print("认证信息已保存到本地文件")
            
            return True
        except Exception as e:
            print(f"使用系统默认浏览器失败: {str(e)}")
            return None
    
    def get_page(self):
        """获取浏览器页面"""
        # 如果跳过浏览器操作，返回None
        if self.skip_browser:
            return None
        # 直接返回页面对象，不检查线程ID
        # 因为现在所有浏览器操作都通过BrowserOperationThread执行
        return self.page
    
    def close_browser(self):
        """关闭浏览器"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"关闭浏览器失败: {str(e)}")
    

    
    def login(self):
        """登录Palmpay商户后台（优先使用缓存的登录状态）"""
        try:
            # 如果配置文件设置了跳过浏览器，则直接从配置文件读取认证信息
            if self.skip_browser:
                if not self._skip_browser_logged:
                    print("跳过浏览器登录，从配置文件读取认证信息")
                auth_info = self.config.get('auth_info', {})
                # 检查认证信息是否完整
                if auth_info.get('pp_token') or auth_info.get('token'):
                    if not self._skip_browser_logged:
                        print("配置文件中的认证信息完整，跳过登录步骤")
                        self._skip_browser_logged = True
                    return True
                else:
                    print("配置文件中的认证信息不完整，请检查config.json文件")
                    return False
            
            # 首先检查是否使用系统默认浏览器
            if self.use_system_browser:
                print("使用系统默认浏览器模式登录")
                # 检查是否已经有保存的认证信息
                if os.path.exists(self.auth_info_path):
                    try:
                        with open(self.auth_info_path, 'r', encoding='utf-8') as f:
                            auth_info = json.load(f)
                        print("从本地文件加载认证信息成功")
                        # 检查认证信息是否完整
                        if auth_info.get('pp_token') or auth_info.get('token'):
                            print("认证信息完整，跳过登录步骤")
                            return True
                    except Exception as e:
                        print(f"从本地文件加载认证信息失败: {str(e)}")
                
                # 启动系统默认浏览器进行登录
                if self.start_system_browser():
                    return True
                else:
                    return False
            
            # 原有的Playwright浏览器登录逻辑
            if not self.page:
                self.page = self.start_browser()
                if not self.page:
                    # 如果启动失败，尝试使用系统默认浏览器
                    print("Playwright浏览器启动失败，尝试使用系统默认浏览器")
                    self.use_system_browser = True
                    return self.login()
            
            # 首先尝试导航到订单列表页面，检查是否已经登录
            print("检查是否已登录...")
            self.page.goto('https://business.palmpay.com/#/reconciliation/transaction/list')
            time.sleep(3)  # 等待页面加载
            
            # 检查是否已经登录（如果能成功导航到订单列表页面，则说明已登录）
            if 'reconciliation/transaction/list' in self.page.url:
                print("检测到已登录状态，跳过登录步骤")
                # 自动获取认证字段
                auth_info = self.get_auth_info()
                if auth_info:
                    print("自动获取认证字段成功")
                    # 保存认证信息到本地文件
                    with open(self.auth_info_path, 'w', encoding='utf-8') as f:
                        json.dump(auth_info, f, ensure_ascii=False, indent=2)
                    return True
                else:
                    print("已登录但获取认证字段失败，继续执行")
                    # 即使获取认证字段失败，只要能导航到订单列表页面，就认为登录成功
                    # 因为认证字段可能在后续的API请求中通过浏览器自动处理
                    return True
            
            # 如果未登录，导航到登录页面
            print("未检测到登录状态，导航到登录页面...")
            self.page.goto('https://business.palmpay.com/#/login')
            
            # 等待用户手动登录
            print("请在浏览器中完成登录...")
            print("登录完成后，请按回车键继续...")
            input()
            
            # 检查是否登录成功
            if 'login' in self.page.url:
                print("登录失败")
                return False
            
            # 自动获取认证字段
            auth_info = self.get_auth_info()
            if auth_info:
                print("自动获取认证字段成功")
                # 保存认证信息到本地文件
                with open(self.auth_info_path, 'w', encoding='utf-8') as f:
                    json.dump(auth_info, f, ensure_ascii=False, indent=2)
                return True
            else:
                print("自动获取认证字段失败，但登录过程已完成")
                # 即使获取认证字段失败，只要能成功登录，就认为登录成功
                return True
        except Exception as e:
            print(f"登录失败: {str(e)}")
            # 尝试使用系统默认浏览器
            print("尝试使用系统默认浏览器...")
            self.use_system_browser = True
            return self.login()
    
    def navigate_to_order_list(self):
        """导航到订单列表页面"""
        try:
            if not self.page:
                return False
            
            # 导航到订单列表页面
            self.page.goto('https://business.palmpay.com/#/reconciliation/transaction/list')
            
            # 等待页面加载
            time.sleep(3)
            
            # 检查是否导航成功
            if 'reconciliation/transaction/list' in self.page.url:
                return True
            else:
                return False
        except Exception as e:
            print(f"导航到订单列表页面失败: {str(e)}")
            return False
    
    def get_auth_info_from_network(self):
        """从网络请求中获取认证字段"""
        try:
            if not self.page:
                return None
            
            print("尝试从网络请求中获取认证字段...")
            
            # 直接从页面的JavaScript环境中获取认证信息
            print("从页面的JavaScript环境中获取认证信息...")
            auth_info = self.page.evaluate('''
                function() {
                    try {
                        var authInfo = {};
                        var debugInfo = {};
                        
                        // 从localStorage中获取
                        try {
                            debugInfo.localStorage = {};
                            for (var i = 0; i < localStorage.length; i++) {
                                var key = localStorage.key(i);
                                debugInfo.localStorage[key] = localStorage.getItem(key);
                            }
                            
                            var authData = localStorage.getItem('authData');
                            if (authData) {
                                try {
                                    var parsed = JSON.parse(authData);
                                    authInfo.token = parsed.token || '';
                                    authInfo.merchantId = parsed.merchantId || '';
                                } catch (e) {
                                    console.log('解析authData失败:', e);
                                }
                            }
                            
                            // 获取所有可能的认证字段
                            authInfo.token = localStorage.getItem('token') || localStorage.getItem('globalToken') || authInfo.token;
                            authInfo.pp_token = localStorage.getItem('pp_token') || authInfo.pp_token || '';
                            authInfo.deviceId = localStorage.getItem('deviceId') || authInfo.deviceId || '';
                            authInfo.pp_device_id = localStorage.getItem('pp_device_id') || authInfo.pp_device_id || '';
                            authInfo.pp_client_ver = localStorage.getItem('pp_client_ver') || '1.0.0';
                            authInfo.merchantid = localStorage.getItem('merchantid') || localStorage.getItem('globalMerchantId') || authInfo.merchantid || '';
                            authInfo.merchantId = localStorage.getItem('merchantId') || localStorage.getItem('globalMerchantId') || authInfo.merchantId || '';
                        } catch (e) {
                            console.log('localStorage error:', e);
                        }
                        
                        // 从sessionStorage中获取
                        try {
                            debugInfo.sessionStorage = {};
                            for (var i = 0; i < sessionStorage.length; i++) {
                                var key = sessionStorage.key(i);
                                debugInfo.sessionStorage[key] = sessionStorage.getItem(key);
                            }
                            
                            // 获取所有可能的认证字段
                            authInfo.token = sessionStorage.getItem('token') || sessionStorage.getItem('globalToken') || authInfo.token;
                            authInfo.pp_token = sessionStorage.getItem('pp_token') || authInfo.pp_token || '';
                            authInfo.deviceId = sessionStorage.getItem('deviceId') || authInfo.deviceId || '';
                            authInfo.pp_device_id = sessionStorage.getItem('pp_device_id') || authInfo.pp_device_id || '';
                            authInfo.pp_client_ver = sessionStorage.getItem('pp_client_ver') || authInfo.pp_client_ver || '1.0.0';
                            authInfo.merchantid = sessionStorage.getItem('merchantid') || sessionStorage.getItem('globalMerchantId') || authInfo.merchantid || '';
                            authInfo.merchantId = sessionStorage.getItem('merchantId') || sessionStorage.getItem('globalMerchantId') || authInfo.merchantId || '';
                        } catch (e) {
                            console.log('sessionStorage error:', e);
                        }
                        
                        // 从cookie中获取
                        try {
                            debugInfo.cookies = document.cookie;
                            var cookieParts = document.cookie.split(';');
                            for (var i = 0; i < cookieParts.length; i++) {
                                var part = cookieParts[i];
                                var parts = part.trim().split('=');
                                var key = parts[0];
                                var value = parts.slice(1).join('=');
                                
                                if (key === 'token') authInfo.token = value;
                                if (key === 'pp_token') authInfo.pp_token = value;
                                if (key === 'deviceId') authInfo.deviceId = value;
                                if (key === 'pp_device_id') authInfo.pp_device_id = value;
                                if (key === 'pp_client_ver') authInfo.pp_client_ver = value;
                                if (key === 'merchantid') authInfo.merchantid = value;
                            }
                        } catch (e) {
                            console.log('cookie error:', e);
                        }
                        
                        // 从window对象中获取
                        try {
                            debugInfo.windowKeys = [];
                            for (var key in window) {
                                if (window.hasOwnProperty(key)) {
                                    debugInfo.windowKeys.push(key);
                                    try {
                                        if (key === 'token') authInfo.token = window[key];
                                        if (key === 'pp_token') authInfo.pp_token = window[key];
                                        if (key === 'deviceId') authInfo.deviceId = window[key];
                                        if (key === 'pp_device_id') authInfo.pp_device_id = window[key];
                                        if (key === 'pp_client_ver') authInfo.pp_client_ver = window[key];
                                        if (key === 'merchantid') authInfo.merchantid = window[key];
                                        if (key === 'merchantId') authInfo.merchantId = window[key];
                                    } catch (e) {
                                        console.log('window property error:', e);
                                    }
                                }
                            }
                        } catch (e) {
                            console.log('window error:', e);
                        }
                        
                        // 确保返回的对象包含必要的字段
                        authInfo.token = authInfo.token || authInfo.pp_token || '';
                        authInfo.deviceId = authInfo.deviceId || authInfo.pp_device_id || '8db6b9f4907b241696062774623cb93d';
                        authInfo.pp_client_ver = authInfo.pp_client_ver || '1.0.0';
                        
                        // 添加调试信息
                        authInfo.debugInfo = debugInfo;
                        
                        return authInfo;
                    } catch (e) {
                        console.log('获取认证信息失败:', e);
                        return { token: '', pp_token: '', deviceId: '', pp_device_id: '', pp_client_ver: '1.0.0', merchantid: '' };
                    }
                }
            ''')
            
            # 打印获取到的认证信息
            print(f"从页面的JavaScript环境中获取到的认证信息: {auth_info}")
            
            # 确保返回的对象包含必要的字段
            if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                auth_info['token'] = auth_info['token'] or auth_info['pp_token']
                auth_info['deviceId'] = auth_info['deviceId'] or auth_info['pp_device_id'] or '8db6b9f4907b241696062774623cb93d'
                auth_info['pp_client_ver'] = auth_info['pp_client_ver'] or '1.0.0'
                # 更新配置文件
                self.update_config_file(auth_info)
                return auth_info
            
            # 如果仍然没有获取到认证信息，尝试触发一个API请求，然后再次获取
            print("触发API请求来生成认证信息...")
            self.page.evaluate('''
                function() {
                    // 触发一个API请求来生成认证信息
                    fetch('https://gsa-m.palmpay.com/api/business-bff-product/merchant/transaction/v2/order/page', {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            'Content-Type': 'application/json',
                            'accept': 'application/json, text/plain, */*',
                            'appsource': '30',
                            'countrycode': 'gsa',
                            'origin': 'https://business.palmpay.com',
                            'pp_device_type': 'WEB',
                            'priority': 'u=1, i',
                            'referer': 'https://business.palmpay.com/',
                            'sec-ch-ua': 'Chromium;v=143, Not A(Brand;v=24',
                            'sec-ch-ua-mobile': '?0',
                            'sec-ch-ua-platform': 'macOS',
                            'sec-fetch-dest': 'empty',
                            'sec-fetch-mode': 'cors',
                            'sec-fetch-site': 'same-site',
                            'tntcode': 'palmpayhk',
                            'user-agent': navigator.userAgent
                        },
                        body: JSON.stringify({
                            current: 1,
                            pageSize: 20,
                            orderTypes: [],
                            pageIndex: 1,
                            createStartTime: Date.now() - 7 * 24 * 60 * 60 * 1000,
                            createEndTime: Date.now(),
                            countryCodes: ['GH'],
                            startOrderAmount: null,
                            endOrderAmount: null
                        })
                    })
                }
            ''')
            
            # 等待一段时间让网络请求完成
            time.sleep(3)
            
            # 再次尝试从页面的JavaScript环境中获取认证信息
            print("再次从页面的JavaScript环境中获取认证信息...")
            auth_info = self.page.evaluate('''
                function() {
                    try {
                        var authInfo = {};
                        
                        // 从localStorage中获取
                        try {
                            var authData = localStorage.getItem('authData');
                            if (authData) {
                                try {
                                    var parsed = JSON.parse(authData);
                                    authInfo.token = parsed.token || '';
                                    authInfo.merchantId = parsed.merchantId || '';
                                } catch (e) {
                                    console.log('解析authData失败:', e);
                                }
                            }
                            
                            // 获取所有可能的认证字段
                            authInfo.token = localStorage.getItem('token') || localStorage.getItem('globalToken') || authInfo.token;
                            authInfo.pp_token = localStorage.getItem('pp_token') || authInfo.pp_token || '';
                            authInfo.deviceId = localStorage.getItem('deviceId') || authInfo.deviceId || '';
                            authInfo.pp_device_id = localStorage.getItem('pp_device_id') || authInfo.pp_device_id || '';
                            authInfo.pp_client_ver = localStorage.getItem('pp_client_ver') || '1.0.0';
                            authInfo.merchantid = localStorage.getItem('merchantid') || localStorage.getItem('globalMerchantId') || authInfo.merchantid || '';
                            authInfo.merchantId = localStorage.getItem('merchantId') || localStorage.getItem('globalMerchantId') || authInfo.merchantId || '';
                        } catch (e) {
                            console.log('localStorage error:', e);
                        }
                        
                        // 从sessionStorage中获取
                        try {
                            authInfo.token = sessionStorage.getItem('token') || sessionStorage.getItem('globalToken') || authInfo.token;
                            authInfo.pp_token = sessionStorage.getItem('pp_token') || authInfo.pp_token || '';
                            authInfo.deviceId = sessionStorage.getItem('deviceId') || authInfo.deviceId || '';
                            authInfo.pp_device_id = sessionStorage.getItem('pp_device_id') || authInfo.pp_device_id || '';
                            authInfo.pp_client_ver = sessionStorage.getItem('pp_client_ver') || authInfo.pp_client_ver || '1.0.0';
                            authInfo.merchantid = sessionStorage.getItem('merchantid') || sessionStorage.getItem('globalMerchantId') || authInfo.merchantid || '';
                            authInfo.merchantId = sessionStorage.getItem('merchantId') || sessionStorage.getItem('globalMerchantId') || authInfo.merchantId || '';
                        } catch (e) {
                            console.log('sessionStorage error:', e);
                        }
                        
                        // 从cookie中获取
                        try {
                            var cookieParts = document.cookie.split(';');
                            for (var i = 0; i < cookieParts.length; i++) {
                                var part = cookieParts[i];
                                var parts = part.trim().split('=');
                                var key = parts[0];
                                var value = parts.slice(1).join('=');
                                
                                if (key === 'token') authInfo.token = value;
                                if (key === 'pp_token') authInfo.pp_token = value;
                                if (key === 'deviceId') authInfo.deviceId = value;
                                if (key === 'pp_device_id') authInfo.pp_device_id = value;
                                if (key === 'pp_client_ver') authInfo.pp_client_ver = value;
                                if (key === 'merchantid') authInfo.merchantid = value;
                            }
                        } catch (e) {
                            console.log('cookie error:', e);
                        }
                        
                        // 从window对象中获取
                        try {
                            for (var key in window) {
                                if (window.hasOwnProperty(key)) {
                                    try {
                                        if (key === 'token') authInfo.token = window[key];
                                        if (key === 'pp_token') authInfo.pp_token = window[key];
                                        if (key === 'deviceId') authInfo.deviceId = window[key];
                                        if (key === 'pp_device_id') authInfo.pp_device_id = window[key];
                                        if (key === 'pp_client_ver') authInfo.pp_client_ver = window[key];
                                        if (key === 'merchantid') authInfo.merchantid = window[key];
                                        if (key === 'merchantId') authInfo.merchantId = window[key];
                                    } catch (e) {
                                        console.log('window property error:', e);
                                    }
                                }
                            }
                        } catch (e) {
                            console.log('window error:', e);
                        }
                        
                        // 确保返回的对象包含必要的字段
                        authInfo.token = authInfo.token || authInfo.pp_token || '';
                        authInfo.deviceId = authInfo.deviceId || authInfo.pp_device_id || '8db6b9f4907b241696062774623cb93d';
                        authInfo.pp_client_ver = authInfo.pp_client_ver || '1.0.0';
                        
                        return authInfo;
                    } catch (e) {
                        console.log('获取认证信息失败:', e);
                        return { token: '', pp_token: '', deviceId: '', pp_device_id: '', pp_client_ver: '1.0.0', merchantid: '' };
                    }
                }
            ''')
            
            # 打印最终获取到的认证信息
            print(f"最终从页面的JavaScript环境中获取到的认证信息: {auth_info}")
            
            # 确保返回的对象包含必要的字段
            if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                auth_info['token'] = auth_info['token'] or auth_info['pp_token']
                auth_info['deviceId'] = auth_info['deviceId'] or auth_info['pp_device_id'] or '8db6b9f4907b241696062774623cb93d'
                auth_info['pp_client_ver'] = auth_info['pp_client_ver'] or '1.0.0'
                # 更新配置文件
                self.update_config_file(auth_info)
                return auth_info
            
            return None
        except Exception as e:
            print(f"从网络请求中获取认证字段失败: {str(e)}")
            return None
    
    def update_config_file(self, auth_info):
        """更新配置文件中的认证信息"""
        try:
            # 加载当前配置
            current_config = self.load_config()
            # 更新认证信息
            current_config['auth_info'] = auth_info
            # 保存到配置文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(current_config, f, ensure_ascii=False, indent=2)
            print("配置文件已更新")
        except Exception as e:
            print(f"更新配置文件失败: {str(e)}")
    
    def get_auth_info(self):
        """从浏览器中获取认证字段"""
        try:
            # 如果配置文件设置了跳过浏览器，则直接从配置文件读取认证信息
            if self.skip_browser:
                if not self._skip_browser_logged:
                    print("从配置文件读取认证信息")
                # 每次都重新读取配置文件，确保使用最新的配置
                current_config = self.load_config()
                auth_info = current_config.get('auth_info', {})
                # 确保返回的对象包含必要的字段
                auth_info['token'] = auth_info.get('token') or auth_info.get('pp_token') or ''
                auth_info['deviceId'] = auth_info.get('deviceId') or auth_info.get('pp_device_id') or '8db6b9f4907b241696062774623cb93d'
                auth_info['pp_client_ver'] = auth_info.get('pp_client_ver') or '1.0.0'
                if not self._skip_browser_logged:
                    print(f"从配置文件获取的认证信息: {auth_info}")
                return auth_info
            
            # 如果使用系统默认浏览器，从本地文件加载认证信息
            if self.use_system_browser:
                if os.path.exists(self.auth_info_path):
                    try:
                        with open(self.auth_info_path, 'r', encoding='utf-8') as f:
                            auth_info = json.load(f)
                        print("从本地文件加载认证信息成功")
                        # 检查认证信息是否完整
                        if auth_info.get('pp_token') or auth_info.get('token'):
                            print(f"从本地文件获取的认证信息: {auth_info}")
                            # 更新配置文件
                            self.update_config_file(auth_info)
                            return auth_info
                        else:
                            print("本地文件中的认证信息不完整")
                    except Exception as e:
                        print(f"从本地文件加载认证信息失败: {str(e)}")
                else:
                    print("认证信息文件不存在")
                return None
            
            # 原有的从浏览器获取认证信息逻辑
            if not self.page:
                return None
            
            # 从浏览器中获取认证字段
            auth_info = self.page.evaluate('''
                function() {
                    try {
                        var authInfo = {};
                        var debugInfo = {};
                        
                        // 从localStorage中获取
                        try {
                            debugInfo.localStorage = {};
                            for (var i = 0; i < localStorage.length; i++) {
                                var key = localStorage.key(i);
                                if (key.includes('token') || key.includes('auth') || key.includes('device') || key.includes('client') || key.includes('merchant')) {
                                    debugInfo.localStorage[key] = localStorage.getItem(key);
                                }
                            }
                            
                            var authData = localStorage.getItem('authData');
                            if (authData) {
                                try {
                                    var parsed = JSON.parse(authData);
                                    authInfo.token = parsed.token || '';
                                    authInfo.merchantId = parsed.merchantId || '';
                                } catch (e) {
                                    console.log('解析authData失败:', e);
                                }
                            }
                            
                            // 获取pp_相关字段
                            authInfo.token = localStorage.getItem('token') || localStorage.getItem('globalToken') || authInfo.token;
                            authInfo.pp_token = localStorage.getItem('pp_token') || authInfo.pp_token || '';
                            authInfo.deviceId = localStorage.getItem('deviceId') || authInfo.deviceId || '';
                            authInfo.pp_device_id = localStorage.getItem('pp_device_id') || authInfo.pp_device_id || '';
                            authInfo.pp_client_ver = localStorage.getItem('pp_client_ver') || '1.0.0';
                            authInfo.merchantid = localStorage.getItem('merchantid') || localStorage.getItem('globalMerchantId') || authInfo.merchantid || '';
                            authInfo.merchantId = localStorage.getItem('merchantId') || localStorage.getItem('globalMerchantId') || authInfo.merchantId || '';
                        } catch (e) {
                            console.log('localStorage error:', e);
                        }
                        
                        // 从cookie中获取
                        try {
                            debugInfo.cookies = document.cookie;
                            var cookieParts = document.cookie.split(';');
                            for (var i = 0; i < cookieParts.length; i++) {
                                var part = cookieParts[i];
                                var parts = part.trim().split('=');
                                var key = parts[0];
                                var value = parts.slice(1).join('=');
                                
                                if (key === 'token') authInfo.token = value;
                                if (key === 'pp_token') authInfo.pp_token = value;
                                if (key === 'deviceId') authInfo.deviceId = value;
                                if (key === 'pp_device_id') authInfo.pp_device_id = value;
                                if (key === 'pp_client_ver') authInfo.pp_client_ver = value;
                                if (key === 'merchantid') authInfo.merchantid = value;
                            }
                        } catch (e) {
                            console.log('cookie error:', e);
                        }
                        
                        // 从window对象中获取
                        try {
                            debugInfo.windowKeys = [];
                            for (var key in window) {
                                if (window.hasOwnProperty(key)) {
                                    if (key.includes('token') || key.includes('auth') || key.includes('device') || key.includes('client') || key.includes('merchant')) {
                                        debugInfo.windowKeys.push(key);
                                        try {
                                            if (key === 'token') authInfo.token = window[key];
                                            if (key === 'pp_token') authInfo.pp_token = window[key];
                                            if (key === 'deviceId') authInfo.deviceId = window[key];
                                            if (key === 'pp_device_id') authInfo.pp_device_id = window[key];
                                            if (key === 'pp_client_ver') authInfo.pp_client_ver = window[key];
                                            if (key === 'merchantid') authInfo.merchantid = window[key];
                                            if (key === 'merchantId') authInfo.merchantId = window[key];
                                        } catch (e) {
                                            console.log('获取window.' + key + '失败:', e);
                                        }
                                    }
                                }
                            }
                        } catch (e) {
                            console.log('window error:', e);
                        }
                        
                        // 确保返回的对象包含必要的字段
                        authInfo.token = authInfo.token || authInfo.pp_token || '';
                        authInfo.deviceId = authInfo.deviceId || authInfo.pp_device_id || '';
                        authInfo.pp_client_ver = authInfo.pp_client_ver || '1.0.0';
                        authInfo.debug = debugInfo;
                        
                        return authInfo;
                    } catch (e) {
                        console.log('获取认证字段失败:', e);
                        return { token: '', pp_token: '', deviceId: '', pp_device_id: '', pp_client_ver: '1.0.0', merchantid: '', debug: { error: e.message } };
                    }
                }
            ''')
            
            # 打印调试信息
            if auth_info.get('debug'):
                print(f"调试信息: {auth_info['debug']}")
            
            # 确保返回的是一个对象
            if not isinstance(auth_info, dict):
                auth_info = {}
            
            # 检查是否有必要的认证字段
            if auth_info.get('pp_token') or auth_info.get('token'):
                print(f"从浏览器中获取的认证信息: {auth_info}")
                # 更新配置文件
                self.update_config_file(auth_info)
                return auth_info
            else:
                print("获取的认证信息不完整，缺少必要的token字段")
                # 尝试从网络请求中获取认证字段
                return self.get_auth_info_from_network()
        except Exception as e:
            print(f"获取认证字段失败: {str(e)}")
            # 尝试从本地文件加载认证信息
            if os.path.exists(self.auth_info_path):
                try:
                    with open(self.auth_info_path, 'r', encoding='utf-8') as f:
                        auth_info = json.load(f)
                    print("从本地文件加载认证信息成功")
                    return auth_info
                except Exception as e:
                    print(f"从本地文件加载认证信息失败: {str(e)}")
            # 尝试从网络请求中获取认证字段
            return self.get_auth_info_from_network()
    
    def get_browser_signature(self, params):
        """从浏览器中获取签名值"""
        try:
            # 如果配置文件设置了跳过浏览器，则直接返回None
            if self.skip_browser:
                print("跳过浏览器操作，无法获取签名值")
                return None
            
            # 如果使用系统默认浏览器，返回None（无法直接获取签名）
            if self.use_system_browser:
                print("使用系统默认浏览器时无法直接获取签名值")
                return None
            
            if not self.page:
                return None
            
            # 从浏览器中获取签名值
            signature = self.page.evaluate('''
                function(params) {
                    try {
                        // 重写fetch，捕获签名值
                        let originalFetch = window.fetch;
                        let capturedSignature = null;
                        
                        window.fetch = function(...args) {
                            const url = args[0];
                            const options = args[1] || {};
                            
                            // 检查是否是订单列表API请求
                            if (url.includes('order/page') || url.includes('transaction/v2/order/page')) {
                                // 捕获请求头中的签名值
                                if (options.headers && options.headers['PP_REQ_SIGN']) {
                                    capturedSignature = options.headers['PP_REQ_SIGN'];
                                }
                            }
                            
                            return originalFetch.apply(this, args);
                        };
                        
                        // 触发一个API请求以捕获签名
                        fetch('https://gsa-m.palmpay.com/api/business-bff-product/merchant/transaction/v2/order/page', {
                            method: 'POST',
                            credentials: 'include',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(params)
                        });
                        
                        // 等待一段时间，确保请求完成
                        setTimeout(function() {
                            window.fetch = originalFetch;
                        }, 2000);
                        
                        return capturedSignature;
                    } catch (e) {
                        console.log('获取签名失败:', e);
                        return null;
                    }
                }
            ''', params)
            
            return signature
        except Exception as e:
            print(f"获取浏览器签名失败: {str(e)}")
            return None
