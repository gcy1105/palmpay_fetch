import time
import json
import sys
import requests
from colorama import init, Fore
from dotenv import load_dotenv
import os
from utils import logger, ErrorHandler
from sign_generator import generate_signature_headers

# 本地存储文件路径
AUTH_STORAGE_FILE = 'auth_cache.json'

init(autoreset=True)

class APICrawler:
    def __init__(self, browser_manager, gui_server, storage=None):
        self._load_env_file()
        self.browser_manager = browser_manager
        self.page = browser_manager.get_page()
        self.gui_server = gui_server
        self.storage = storage
        self.order_list_api = os.getenv('ORDER_LIST_API')
        self.order_detail_api = os.getenv('ORDER_DETAIL_API')
        self.request_delay = float(os.getenv('REQUEST_DELAY', '0.01'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.page_size = int(os.getenv('PAGE_SIZE', '20'))
        self.order_data = []
        self.is_running = False
        self.auth_info = self.load_auth_info()

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
        
    def save_auth_info(self, auth_info):
        """保存认证信息到本地文件"""
        try:
            auth_data = {
                'auth_info': auth_info,
                'timestamp': time.time(),
                'expires_at': time.time() + (24 * 60 * 60)  # 24小时过期
            }
            with open(AUTH_STORAGE_FILE, 'w', encoding='utf-8') as f:
                json.dump(auth_data, f, indent=2)
            print(Fore.GREEN + "认证信息已保存到本地")
            logger.info("认证信息已保存到本地")
            self.add_log("认证信息已保存到本地", 'green')
        except Exception as e:
            print(Fore.RED + f"保存认证信息失败: {str(e)}")
            logger.error(f"保存认证信息失败: {str(e)}")
            self.add_log(f"保存认证信息失败: {str(e)}", 'red')
    
    def load_auth_info(self):
        """从本地文件加载认证信息"""
        try:
            if os.path.exists(AUTH_STORAGE_FILE):
                with open(AUTH_STORAGE_FILE, 'r', encoding='utf-8') as f:
                    auth_data = json.load(f)
                
                # 检查是否过期
                if time.time() < auth_data.get('expires_at', 0):
                    print(Fore.GREEN + "从本地加载认证信息成功")
                    logger.info("从本地加载认证信息成功")
                    self.add_log("从本地加载认证信息成功", 'green')
                    return auth_data.get('auth_info', {})
                else:
                    print(Fore.YELLOW + "认证信息已过期")
                    logger.info("认证信息已过期")
                    self.add_log("认证信息已过期", 'yellow')
                    os.remove(AUTH_STORAGE_FILE)
        except Exception as e:
            print(Fore.RED + f"加载认证信息失败: {str(e)}")
            logger.error(f"加载认证信息失败: {str(e)}")
            self.add_log(f"加载认证信息失败: {str(e)}", 'red')
        return {}
    
    def is_auth_valid(self):
        """检查认证信息是否有效"""
        # 检查认证信息是否存在
        if not self.auth_info:
            return False
        
        # 检查是否有有效的token
        if not (self.auth_info.get('token') or self.auth_info.get('pp_token')):
            return False
        
        # 检查认证信息是否过期（如果有过期时间）
        if hasattr(self, 'auth_expires_at') and time.time() > self.auth_expires_at:
            print(Fore.YELLOW + "认证信息已过期")
            self.add_log("认证信息已过期", 'yellow')
            return False
        
        return True
    
    def update_auth_info(self, new_auth_info):
        """更新认证信息并保存"""
        merged_auth_info = dict(self.auth_info or {})
        merged_auth_info.update(new_auth_info or {})
        self.auth_info = merged_auth_info
        # 设置认证信息过期时间（1小时）
        self.auth_expires_at = time.time() + (60 * 60)
        self.save_auth_info(self.auth_info)
    
    def add_log(self, message, log_type='info'):
        try:
            self.gui_server.add_log(message, log_type)
        except Exception as e:
            print(f"添加日志失败: {e}")
    
    def get_order_list_from_api(self, start_timestamp=None, end_timestamp=None, page_number=1, page_size=20, settlement_status=None):
        """通过API直接获取订单列表"""
        orders = []
        
        try:
            # 直接使用传入的时间戳
            start_time = start_timestamp
            end_time = end_timestamp
            
            # 获取认证信息
            if not self.is_auth_valid():
                # 检查是否跳过浏览器操作
                if hasattr(self.browser_manager, 'skip_browser') and self.browser_manager.skip_browser:
                    auth_info = self.browser_manager.get_auth_info()
                    if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                        self.update_auth_info(auth_info)
                    else:
                        print(Fore.RED + "配置文件中的认证信息不完整，请检查config.json文件")
                        self.add_log("配置文件中的认证信息不完整，请检查config.json文件", 'red')
                        return orders, {
                            'current': page_number,
                            'total': 0,
                            'size': self.page_size,
                            'pages': 0
                        }
                else:
                    # 检查self.page是否为None，如果是，则重新初始化
                    if not self.page:
                        self.page = self.browser_manager.page
                        if not self.page:
                            print(Fore.RED + "无法获取浏览器页面，请先登录")
                            self.add_log("无法获取浏览器页面，请先登录", 'red')
                            return orders, {
                                'current': page_number,
                                'total': 0,
                                'size': self.page_size,
                                'pages': 0
                            }
                    
                    # 从browser_thread的共享变量中获取认证信息
                    browser_auth_info = None
                    if hasattr(self, 'browser_thread') and self.browser_thread:
                        # 添加操作到browser_thread的队列，让它更新认证信息
                        self.browser_thread.add_operation({
                            'type': 'get_auth_info',
                            'callback': None  # 不需要回调，直接从共享变量读取
                        })
                        
                        # 等待一段时间让browser_thread执行操作并更新共享变量
                        time.sleep(3)  # 等待3秒让browser_thread执行操作
                        
                        # 从共享变量中读取认证信息
                        with self.browser_thread.auth_info_lock:
                            browser_auth_info = self.browser_thread.shared_auth_info
                    
                    if browser_auth_info and (browser_auth_info.get('token') or browser_auth_info.get('pp_token')):
                        self.update_auth_info(browser_auth_info)
                    else:
                        print(Fore.RED + "无法从浏览器获取认证信息，请先登录")
                        self.add_log("无法从浏览器获取认证信息，请先登录", 'red')
                        return orders, {
                            'current': page_number,
                            'total': 0,
                            'size': self.page_size,
                            'pages': 0
                        }
            
            # 构造请求参数
            params = {
                'current': page_number,
                'pageSize': page_size,
                'orderTypes': ["300-0"],
                'pageIndex': page_number,
                'createStartTime': start_time,
                'createEndTime': end_time,
                'countryCodes': ['GH'],
                'startOrderAmount': None,
                'endOrderAmount': None
            }
            
            # 根据settlement_status控制orderStatus参数
            if settlement_status == '2':
                params['orderStatus'] = "2"
            # 如果为'None'则不添加orderStatus参数
            
            # 生成时间戳
            timestamp = int(time.time() * 1000)
            
            # 获取认证信息
            token = self.auth_info.get('token', '') or self.auth_info.get('pp_token', '')
            device_id = self.auth_info.get('deviceId', '') or self.auth_info.get('pp_device_id', '')
            country_code = 'gsa'  # 使用'gsa'，与test_order_list.py一致
            merchantid = self.auth_info.get('merchantid', '') or self.auth_info.get('merchantId', '125072409535231')
            
            # 生成包含签名的请求头（使用POST方法）
            headers = generate_signature_headers(token, device_id, country_code, params, method='POST', merchantid=merchantid)
            
            # 实现带重试机制的API请求，处理服务器繁忙错误
            retry_count = 0
            max_retries = 5
            base_delay = 0.1  # 基础延迟时间（秒）
            
            while retry_count < max_retries:
                try:
                    # 添加指数退避延迟
                    delay = base_delay * (2 ** retry_count)
                    if delay > 1:
                        time.sleep(delay)
                    else:
                        # 延迟小于1秒时不打印日志，直接休眠
                        time.sleep(delay)
                    
                    # 发起API请求
                    response = requests.post(
                        self.order_list_api,
                        json=params,
                        headers=headers,
                        timeout=30
                    )
                    
                    # 如果请求成功，跳出重试循环
                    if response.status_code == 200:
                        break
                    
                    # 如果服务器返回503（服务不可用）或429（请求过多），继续重试
                    if response.status_code in [503, 429]:
                        retry_count += 1
                        continue
                    
                    # 其他错误状态码，直接跳出重试循环
                    break
                    
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(Fore.RED + f"请求失败，已达到最大重试次数")
                        self.add_log("请求失败，已达到最大重试次数", 'red')
                        return orders, {
                            'current': page_number,
                            'total': 0,
                            'size': self.page_size,
                            'pages': 0
                        }
            
            if response.status_code == 200:
                try:
                    api_response = response.json()
                    
                    if api_response and 'error' not in api_response:
                        # 解析API响应
                        if api_response.get('respCode') == '00000000':
                            data = api_response.get('data', {})
                            # 确保获取到list字段
                            data_list = data.get('list', [])
                            
                            # 获取分页信息
                            current_page = data.get('current', page_number)
                            # 优先使用 totalCount 字段，然后使用 total 字段
                            total = data.get('totalCount', data.get('total', 0))
                            size = data.get('size', self.page_size)
                            pages = data.get('pages', 0)
                            
                            # 计算当前页的起始和结束位置
                            start_item = (current_page - 1) * size + 1
                            end_item = min(current_page * size, total)
                            
                            # 打印详细的分页信息（更加醒目）
                            print(Fore.CYAN + "=" * 60)
                            print(Fore.CYAN + f"【分页信息】当前页: {current_page} | 总页数: {pages} | 总条数: {total}")
                            print(Fore.CYAN + f"【分页信息】当前页范围: 第 {start_item} 到第 {end_item} 条")
                            print(Fore.CYAN + "=" * 60)
                            logger.info(f"获取到第 {current_page} 页，共 {pages} 页，总 {total} 条订单")
                            self.add_log(f"【分页信息】第 {current_page}/{pages} 页，共 {total} 条订单", 'cyan')
                            
                            # 转换为订单对象
                            for item in data_list:
                                order = {
                                    'order_no': item.get('orderNo', ''),
                                    'order_type': item.get('orderType', ''),
                                    'order_status': item.get('orderStatus', ''),
                                    'order_amount': item.get('orderAmount', ''),
                                    'create_time': item.get('createTime', ''),
                                    'settlement_status': item.get('settlementStatus', ''),
                                    'settlement_amount': item.get('settlementAmount', ''),
                                    'settlement_time': item.get('settlementTime', ''),
                                    'country_code': item.get('countryCode', ''),
                                    'merchant_id': item.get('merchantId', ''),
                                    'pay_id': item.get('payId', ''),
                                    'out_order_no': item.get('outOrderNo', ''),
                                    'user_mobile_no': item.get('payerAccountNo', '')  # 从订单列表中获取用户手机号
                                }
                                orders.append(order)
                            
                            # 返回订单列表和分页信息
                            return orders, {
                                'current': current_page,
                                'total': total,
                                'size': size,
                                'pages': pages
                            }
                        else:
                            error_message = api_response.get('respMsg', 'Unknown error')
                            print(Fore.RED + f"API返回错误: {error_message}")
                            self.add_log(f"API返回错误: {error_message}", 'red')
                            
                            # 处理token过期错误
                            if 'token time out' in error_message or 'token expired' in error_message:
                                # 从browser_thread的共享变量中获取认证信息
                                browser_auth_info = None
                                if hasattr(self, 'browser_thread') and self.browser_thread:
                                    # 添加操作到browser_thread的队列，让它更新认证信息
                                    self.browser_thread.add_operation({
                                        'type': 'get_auth_info',
                                        'callback': None  # 不需要回调，直接从共享变量读取
                                    })
                                    
                                    # 等待一段时间让browser_thread执行操作并更新共享变量
                                    time.sleep(3)  # 等待3秒让browser_thread执行操作
                                    
                                    # 从共享变量中读取认证信息
                                    with self.browser_thread.auth_info_lock:
                                        browser_auth_info = self.browser_thread.shared_auth_info
                                
                                if browser_auth_info and (browser_auth_info.get('token') or browser_auth_info.get('pp_token')):
                                    self.update_auth_info(browser_auth_info)
                                    
                                    # 重新生成请求头
                                    token = self.auth_info.get('token', '') or self.auth_info.get('pp_token', '')
                                    device_id = self.auth_info.get('deviceId', '') or self.auth_info.get('pp_device_id', '')
                                    merchantid = self.auth_info.get('merchantid', '') or self.auth_info.get('merchantId', '')
                                    headers = generate_signature_headers(token, device_id, country_code, params, method='POST', merchantid=merchantid)
                                    
                                    # 重新发起API请求
                                    time.sleep(self.request_delay)
                                    
                                    response = requests.post(
                                        self.order_list_api,
                                        json=params,
                                        headers=headers,
                                        timeout=30
                                    )
                                    
                                    if response.status_code == 200:
                                        new_api_response = response.json()
                                        
                                        if new_api_response.get('respCode') == '00000000':
                                            data = new_api_response.get('data', {})
                                            data_list = data.get('list', [])
                                            
                                            # 解析订单数据
                                            for item in data_list:
                                                order = {
                                                    'order_no': item.get('orderNo', ''),
                                                    'order_type': item.get('orderType', ''),
                                                    'order_status': item.get('orderStatus', ''),
                                                    'order_amount': item.get('orderAmount', ''),
                                                    'create_time': item.get('createTime', ''),
                                                    'settlement_status': item.get('settlementStatus', ''),
                                                    'settlement_amount': item.get('settlementAmount', ''),
                                                    'settlement_time': item.get('settlementTime', ''),
                                                    'country_code': item.get('countryCode', ''),
                                                    'merchant_id': item.get('merchantId', ''),
                                                    'pay_id': item.get('payId', ''),
                                                    'out_order_no': item.get('outOrderNo', ''),
                                                    'user_mobile_no': item.get('payerAccountNo', '')
                                                }
                                                orders.append(order)
                                            
                                            return orders, {
                                                'current': page_number,
                                                'total': data.get('total', 0),
                                                'size': data.get('size', self.page_size),
                                                'pages': data.get('pages', 0)
                                            }
                    else:
                        print(Fore.RED + f"API调用失败: {api_response}")
                        self.add_log(f"API调用失败: {api_response}", 'red')
                except Exception as e:
                    print(Fore.RED + f"解析响应失败: {str(e)}")
                    self.add_log(f"解析响应失败: {str(e)}", 'red')
            else:
                print(Fore.RED + f"API请求失败，状态码: {response.status_code}")
                self.add_log(f"API请求失败，状态码: {response.status_code}", 'red')
            
            # 返回订单列表和空的分页信息
            return orders, {
                'current': page_number,
                'total': 0,
                'size': self.page_size,
                'pages': 0
            }
        except Exception as e:
            print(Fore.RED + f"通过API获取订单列表失败: {str(e)}")
            logger.error(f"通过API获取订单列表失败: {str(e)}")
            self.add_log(f"通过API获取订单列表失败: {str(e)}", 'red')
            # 返回订单列表和空的分页信息
            return [], {
                'current': page_number,
                'total': 0,
                'size': self.page_size,
                'pages': 0
            }

    def get_order_detail_from_api(self, order_no, order_type):
        """通过API直接获取订单详情"""
        
        try:
            # 检查认证信息是否有效
            if not self.is_auth_valid():
                # 检查是否跳过浏览器操作
                if hasattr(self.browser_manager, 'skip_browser') and self.browser_manager.skip_browser:
                    auth_info = self.browser_manager.get_auth_info()
                    if auth_info and (auth_info.get('token') or auth_info.get('pp_token')):
                        self.update_auth_info(auth_info)
                    else:
                        print(Fore.RED + "配置文件中的认证信息不完整，请检查config.json文件")
                        self.add_log("配置文件中的认证信息不完整，请检查config.json文件", 'red')
                        return None
                else:
                    # 检查self.page是否为None，如果是，则重新初始化
                    if not self.page:
                        self.page = self.browser_manager.page
                        if not self.page:
                            print(Fore.RED + "无法获取浏览器页面，请先登录")
                            self.add_log("无法获取浏览器页面，请先登录", 'red')
                            return None
                    
                    # 从browser_thread的共享变量中获取认证信息
                    browser_auth_info = None
                    if hasattr(self, 'browser_thread') and self.browser_thread:
                        # 添加操作到browser_thread的队列，让它更新认证信息
                        self.browser_thread.add_operation({
                            'type': 'get_auth_info',
                            'callback': None  # 不需要回调，直接从共享变量读取
                        })
                        
                        # 等待一段时间让browser_thread执行操作并更新共享变量
                        time.sleep(3)  # 等待3秒让browser_thread执行操作
                        
                        # 从共享变量中读取认证信息
                        with self.browser_thread.auth_info_lock:
                            browser_auth_info = self.browser_thread.shared_auth_info
                    
                    if browser_auth_info and (browser_auth_info.get('token') or browser_auth_info.get('pp_token')):
                        self.update_auth_info(browser_auth_info)
                    else:
                        print(Fore.RED + "无法从浏览器获取认证信息，请先登录")
                        self.add_log("无法从浏览器获取认证信息，请先登录", 'red')
                        return None
            
            # 获取认证信息
            token = self.auth_info.get('token', '') or self.auth_info.get('pp_token', '')
            device_id = self.auth_info.get('deviceId', '') or self.auth_info.get('pp_device_id', '')
            merchantid = self.auth_info.get('merchantid', '') or self.auth_info.get('merchantId', '')
            country_code = 'gsa'  # 使用'gsa'，与订单列表API一致
            
            # 构造请求参数
            params = {
                'orderNo': order_no,
                'orderType': order_type,
                'dataSource': 'lindorm',  # 添加dataSource参数
                'timestamp': int(time.time() * 1000)
            }
            
            # 生成包含签名的请求头（使用GET方法）
            headers = generate_signature_headers(token, device_id, country_code, params, method='GET', merchantid=merchantid)
            
            # 替换sec-ch-ua为与curl一致的值
            headers['sec-ch-ua'] = '"Chromium";v="143", "Not A(Brand";v="24"'
            # 替换user-agent为与curl一致的值
            headers['user-agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
            
            # 实现带重试机制的API请求，处理服务器繁忙错误
            retry_count = 0
            max_retries = 5
            base_delay = 0.1  # 基础延迟时间（秒）
            
            while retry_count < max_retries:
                try:
                    # 添加指数退避延迟
                    delay = base_delay * (2 ** retry_count)
                    if delay > 1:
                        time.sleep(delay)
                    else:
                        # 延迟小于1秒时不打印日志，直接休眠
                        time.sleep(delay)
                    
                    # 发起API请求（使用GET方法，参数放在URL中）
                    response = requests.get(
                        self.order_detail_api,
                        params=params,
                        headers=headers,
                        timeout=30
                    )
                    
                    # 如果请求成功，跳出重试循环
                    if response.status_code == 200:
                        break
                    
                    # 如果服务器返回503（服务不可用）或429（请求过多），继续重试
                    if response.status_code in [503, 429]:
                        retry_count += 1
                        continue
                    
                    # 其他错误状态码，直接跳出重试循环
                    break
                    
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(Fore.RED + f"请求失败，已达到最大重试次数")
                        self.add_log("请求失败，已达到最大重试次数", 'red')
                        return None
            
            if response.status_code == 200:
                api_response = response.json()
                
                if api_response and 'error' not in api_response:
                    # 解析API响应
                    if api_response.get('respCode') == '00000000':
                        detail_data = self.parse_detail_data(api_response)
                        return detail_data
                    else:
                        error_message = api_response.get('respMsg', 'Unknown error')
                        print(Fore.RED + f"API返回错误: {error_message}")
                        self.add_log(f"API返回错误: {error_message}", 'red')
                        
                        # 处理token过期错误
                        if 'token time out' in error_message or 'token expired' in error_message:
                            # 从browser_thread的共享变量中获取认证信息
                            browser_auth_info = None
                            if hasattr(self, 'browser_thread') and self.browser_thread:
                                # 添加操作到browser_thread的队列，让它更新认证信息
                                self.browser_thread.add_operation({
                                    'type': 'get_auth_info',
                                    'callback': None  # 不需要回调，直接从共享变量读取
                                })
                                
                                # 等待一段时间让browser_thread执行操作并更新共享变量
                                time.sleep(3)  # 等待3秒让browser_thread执行操作
                                
                                # 从共享变量中读取认证信息
                                with self.browser_thread.auth_info_lock:
                                    browser_auth_info = self.browser_thread.shared_auth_info
                            
                            if browser_auth_info and (browser_auth_info.get('token') or browser_auth_info.get('pp_token')):
                                self.update_auth_info(browser_auth_info)
                                
                                # 重新生成请求头
                                token = self.auth_info.get('token', '') or self.auth_info.get('pp_token', '')
                                device_id = self.auth_info.get('deviceId', '') or self.auth_info.get('pp_device_id', '')
                                merchantid = self.auth_info.get('merchantid', '') or self.auth_info.get('merchantId', '')
                                headers = generate_signature_headers(token, device_id, country_code, params, method='GET', merchantid=merchantid)
                                
                                # 替换sec-ch-ua为与curl一致的值
                                headers['sec-ch-ua'] = '"Chromium";v="143", "Not A(Brand";v="24"'
                                # 替换user-agent为与curl一致的值
                                headers['user-agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
                                
                                # 重新发起API请求
                                time.sleep(self.request_delay)
                                
                                response = requests.get(
                                    self.order_detail_api,
                                    params=params,
                                    headers=headers,
                                    timeout=30
                                )
                                
                                if response.status_code == 200:
                                    new_api_response = response.json()
                                    
                                    if new_api_response.get('respCode') == '00000000':
                                        detail_data = self.parse_detail_data(new_api_response)
                                        return detail_data
                        return None
                else:
                    print(Fore.RED + f"API调用失败: {api_response}")
                    self.add_log(f"API调用失败: {api_response}", 'red')
                    return None
            else:
                print(Fore.RED + f"API请求失败，状态码: {response.status_code}")
                self.add_log(f"API请求失败，状态码: {response.status_code}", 'red')
                return None
        except Exception as e:
            print(Fore.RED + f"通过API获取订单详情失败: {str(e)}")
            logger.error(f"通过API获取订单详情失败: {str(e)}")
            self.add_log(f"通过API获取订单详情失败: {str(e)}", 'red')
            return None
    
    def parse_detail_data(self, detail_response):
        """解析订单详情数据，提取所有key-value对"""
        parsed_data = {}
        other_info_values = []
        
        if not detail_response or detail_response.get('respCode') != '00000000':
            return parsed_data
        
        data_list = detail_response.get('data', [])
        
        # 遍历所有信息块
        for info_block in data_list:
            block_key = info_block.get('key', '')
            block_title = info_block.get('title', '')
            value_list = info_block.get('value', [])
            
            # 遍历信息块中的所有字段
            for field in value_list:
                field_key = field.get('key', '')
                field_title = field.get('title', '')
                field_value = field.get('value', '')
                value_type = field.get('valueType', '')
                
                # 构建字段名：使用title作为列名
                if field_title:
                    column_name = f"{block_title}_{field_title}" if block_title else field_title
                else:
                    column_name = field_key if field_key else f"{block_key}_field"
                
                # 处理不同类型的值
                if value_type == 'date' and field_value:
                    # 时间戳转换为可读格式（使用西非时间UTC+1）
                    try:
                        import datetime
                        if isinstance(field_value, (int, float)):
                            timestamp = field_value / 1000 if field_value > 1000000000000 else field_value
                            # 使用西非时间（UTC+1）
                            wat_tz = datetime.timezone(datetime.timedelta(hours=1))
                            field_value = datetime.datetime.fromtimestamp(timestamp, wat_tz).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                
                # 存储到解析后的数据中
                parsed_data[column_name] = field_value
                
                # 特别处理User Mobile No，确保它存储到与列表中相同的列
                if field_title == 'User Mobile No':
                    parsed_data['user_mobile_no'] = field_value
                
                # 收集Other Information块中的所有值
                if block_title == 'Other Information' and field_value:
                    other_info_values.append(field_value)
        
        # 如果没有找到User Mobile No，将Other Information中的所有值合并后填到user_mobile_no
        if 'user_mobile_no' not in parsed_data and other_info_values:
            parsed_data['user_mobile_no'] = ' | '.join(other_info_values)
        
        return parsed_data
    
    def get_order_list_from_website(self, page_number=1, page_size=20):
        """通过调用网站原始的订单列表请求函数获取订单列表"""
        orders = []
        print(Fore.CYAN + "通过网站原始函数获取订单列表...")
        logger.info("通过网站原始函数获取订单列表")
        self.add_log("通过网站原始函数获取订单列表...", 'cyan')
        
        try:
            # 计算时间戳（最近30天）
            end_time = int(time.time() * 1000)
            start_time = end_time - (30 * 24 * 60 * 60 * 1000)
            
            # 构造请求参数
            params = {
                'current': page_number,
                'pageSize': page_size,
                'orderTypes': [],
                'pageIndex': page_number,
                'createStartTime': start_time,
                'createEndTime': end_time,
                'countryCodes': ['GH'],
                'startOrderAmount': None,
                'endOrderAmount': None
            }
            
            # 执行JavaScript代码，查找并调用网站的原始订单列表请求函数
            api_response = self.page.evaluate('''
                function(params) {
                    try {
                        // 1. 查找网站中用于请求订单列表的函数
                        console.log('开始查找网站原始订单列表请求函数...');
                        
                        // 2. 重写fetch和XMLHttpRequest，捕获订单列表API请求
                        let orderListResponse = null;
                        let originalFetch = window.fetch;
                        let originalXhrOpen = XMLHttpRequest.prototype.open;
                        let originalXhrSend = XMLHttpRequest.prototype.send;
                        
                        // 重写fetch
                        window.fetch = function(...args) {
                            const url = args[0];
                            const options = args[1] || {};
                            console.log('捕获到fetch请求:', url);
                            
                            // 检查是否是订单列表API请求
                            if (url.includes('order/page') || url.includes('transaction/v2/order/page')) {
                                console.log('捕获到订单列表API请求:', url);
                                console.log('请求参数:', options.body);
                                console.log('请求头:', options.headers);
                                
                                // 发送原始请求并捕获响应
                                return originalFetch.apply(this, args).then(response => {
                                    return response.clone().json().then(data => {
                                        console.log('订单列表API响应:', data);
                                        orderListResponse = data;
                                        return response;
                                    }).catch(() => response);
                                });
                            }
                            
                            return originalFetch.apply(this, args);
                        };
                        
                        // 重写XMLHttpRequest
                        XMLHttpRequest.prototype.open = function(...args) {
                            const url = args[1];
                            console.log('捕获到XHR请求:', url);
                            
                            // 检查是否是订单列表API请求
                            if (url.includes('order/page') || url.includes('transaction/v2/order/page')) {
                                this._isOrderListRequest = true;
                                console.log('捕获到订单列表API请求:', url);
                            }
                            
                            return originalXhrOpen.apply(this, args);
                        };
                        
                        XMLHttpRequest.prototype.send = function(...args) {
                            if (this._isOrderListRequest) {
                                console.log('订单列表API请求参数:', args[0]);
                                
                                // 监听响应
                                this.onreadystatechange = function() {
                                    if (this.readyState === 4 && this.status === 200) {
                                        try {
                                            const data = JSON.parse(this.responseText);
                                            console.log('订单列表API响应:', data);
                                            orderListResponse = data;
                                        } catch (e) {
                                            console.error('解析XHR响应失败:', e);
                                        }
                                    }
                                };
                            }
                            
                            return originalXhrSend.apply(this, args);
                        };
                        
                        // 3. 尝试触发网站的订单列表请求
                        console.log('尝试触发网站的订单列表请求...');
                        
                        // 方法2: 直接调用可能存在的订单列表请求函数
                        try {
                            console.log('方法2: 尝试调用可能存在的订单列表请求函数...');
                            
                            // 搜索全局对象中的可能函数
                            for (let key in window) {
                                if (window.hasOwnProperty(key)) {
                                    try {
                                        const value = window[key];
                                        if (typeof value === 'function') {
                                            const funcStr = value.toString();
                                            if ((funcStr.includes('order') && funcStr.includes('list')) || 
                                                (funcStr.includes('transaction') && funcStr.includes('page')) ||
                                                (funcStr.includes('fetch') && funcStr.includes('order'))) {
                                                console.log('找到可能的订单列表函数:', key);
                                                // 尝试调用函数
                                                try {
                                                    const result = value(params);
                                                    if (result && typeof result.then === 'function') {
                                                        result.then(data => {
                                                            console.log('函数调用返回:', data);
                                                            if (!orderListResponse) {
                                                                orderListResponse = data;
                                                            }
                                                        });
                                                    } else {
                                                        console.log('函数调用返回:', result);
                                                        if (!orderListResponse) {
                                                            orderListResponse = result;
                                                        }
                                                    }
                                                } catch (e) {
                                                    console.error('调用函数失败:', e);
                                                }
                                            }
                                        }
                                    } catch (e) {
                                        // 忽略错误
                                    }
                                }
                            }
                        } catch (e) {
                            console.error('方法2失败:', e);
                        }
                        
                        // 方法3: 直接模拟网站的API请求（使用网站的fetch，这样会自动带上签名）
                        try {
                            console.log('方法3: 直接使用网站的fetch发起请求...');
                            
                            // 尝试获取订单列表API URL
                            let apiUrl = '';
                            if (window.location.origin) {
                                apiUrl = window.location.origin + '/api/business-bff-product/merchant/transaction/v2/order/page';
                            } else {
                                apiUrl = 'https://gsa-m.palmpay.com/api/business-bff-product/merchant/transaction/v2/order/page';
                            }
                            
                            console.log('使用API URL:', apiUrl);
                            
                            // 使用网站的fetch发起请求
                            originalFetch(apiUrl, {
                                method: 'POST',
                                credentials: 'include',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'accept': 'application/json, text/plain, */*'
                                },
                                body: JSON.stringify(params)
                            }).then(response => {
                                console.log('直接请求响应状态:', response.status);
                                
                                if (response.ok) {
                                    response.json().then(data => {
                                        console.log('直接请求响应数据:', data);
                                        orderListResponse = data;
                                    });
                                }
                            }).catch(e => {
                                console.error('方法3失败:', e);
                            });
                        } catch (e) {
                            console.error('方法3失败:', e);
                        }
                        
                        // 等待一段时间，确保请求完成
                        setTimeout(function() {
                            // 恢复原始方法
                            window.fetch = originalFetch;
                            XMLHttpRequest.prototype.open = originalXhrOpen;
                            XMLHttpRequest.prototype.send = originalXhrSend;
                        }, 3000);
                        
                        // 返回捕获的响应
                        console.log('最终获取到的订单列表响应:', orderListResponse);
                        return orderListResponse;
                    } catch (error) {
                        console.error('获取订单列表失败:', error);
                        console.error('错误堆栈:', error.stack);
                        return { error: error.message, stack: error.stack };
                    }
                }
            ''', params)
            
            if api_response and 'error' not in api_response:
                print(Fore.GREEN + f"网站原始函数调用成功")
                logger.info(f"网站原始函数调用成功")
                self.add_log("网站原始函数调用成功", 'green')
                
                # 解析API响应
                if api_response.get('respCode') == '00000000':
                    data = api_response.get('data', {})
                    data_list = data.get('list', [])
                    print(Fore.GREEN + f"获取到 {len(data_list)} 条订单")
                    self.add_log(f"获取到 {len(data_list)} 条订单", 'green')
                    
                    # 转换为订单对象
                    for item in data_list:
                        orders.append({
                            'order_no': item.get('orderNo', ''),
                            'order_type': item.get('orderType', ''),
                            'order_status': item.get('orderStatus', ''),
                            'order_amount': item.get('orderAmount', ''),
                            'create_time': item.get('createTime', ''),
                            'settlement_status': item.get('settlementStatus', ''),
                            'settlement_amount': item.get('settlementAmount', ''),
                            'settlement_time': item.get('settlementTime', ''),
                            'country_code': item.get('countryCode', ''),
                            'merchant_id': item.get('merchantId', ''),
                            'pay_id': item.get('payId', ''),
                            'out_order_no': item.get('outOrderNo', '')
                        })
                else:
                    print(Fore.RED + f"API返回错误: {api_response.get('respMsg', 'Unknown error')}")
                    self.add_log(f"API返回错误: {api_response.get('respMsg', 'Unknown error')}", 'red')
                    
                    # 打印完整响应
                    print(Fore.YELLOW + f"完整API响应: {api_response}")
            else:
                print(Fore.RED + f"网站原始函数调用失败: {api_response}")
                self.add_log(f"网站原始函数调用失败: {api_response}", 'red')
            
            return orders
        except Exception as e:
            print(Fore.RED + f"通过网站原始函数获取订单列表失败: {str(e)}")
            logger.error(f"通过网站原始函数获取订单列表失败: {str(e)}")
            self.add_log(f"通过网站原始函数获取订单列表失败: {str(e)}", 'red')
            return orders
    
    def analyze_js_files(self):
        """分析网站的JS文件，查找签名生成逻辑"""
        print(Fore.CYAN + "开始分析网站JS文件，查找签名生成逻辑...")
        logger.info("开始分析网站JS文件，查找签名生成逻辑")
        self.add_log("开始分析网站JS文件，查找签名生成逻辑...", 'cyan')
        
        try:
            # 1. 获取页面中的所有script标签信息，包括动态加载的
            js_info = self.page.evaluate('''
            function() {
                var info = {};
                
                // 获取所有script标签的src
                var scripts = document.getElementsByTagName('script');
                var scriptSrcs = [];
                for (var i = 0; i < scripts.length; i++) {
                    if (scripts[i].src) {
                        scriptSrcs.push(scripts[i].src);
                    }
                }
                
                // 监听动态加载的script标签
                var dynamicScripts = [];
                var importScripts = [];
                var xhrScripts = [];
                
                // 重写document.createElement以捕获动态创建的script标签
                var originalCreateElement = document.createElement;
                document.createElement = function(tag) {
                    var element = originalCreateElement.call(document, tag);
                    if (tag === 'script') {
                        Object.defineProperty(element, 'src', {
                            set: function(url) {
                                if (url) {
                                    dynamicScripts.push(url);
                                }
                                this.setAttribute('src', url);
                            }
                        });
                    }
                    return element;
                };
                
                // 重写import()函数以捕获动态导入的模块
                var originalImport = window.import;
                if (window.import) {
                    window.import = function(modulePath) {
                        importScripts.push(modulePath);
                        return originalImport.call(this, modulePath);
                    };
                }
                
                // 重写XMLHttpRequest以捕获通过XHR加载的脚本
                var originalXHR = XMLHttpRequest;
                XMLHttpRequest = function() {
                    var xhr = new originalXHR();
                    var originalOpen = xhr.open;
                    xhr.open = function(method, url) {
                        if (url && url.endsWith('.js')) {
                            xhrScripts.push(url);
                        }
                        return originalOpen.call(this, method, url);
                    };
                    return xhr;
                };
                
                // 等待一段时间，让页面有机会加载动态脚本
                setTimeout(function() {
                    // 恢复原始方法
                    document.createElement = originalCreateElement;
                    if (originalImport) {
                        window.import = originalImport;
                    }
                    if (originalXHR) {
                        XMLHttpRequest = originalXHR;
                    }
                    
                    // 合并静态和动态脚本
                    var allScripts = [...new Set([...scriptSrcs, ...dynamicScripts, ...importScripts, ...xhrScripts])];
                    info.scripts = allScripts;
                    info.dynamic_scripts = dynamicScripts;
                    info.import_scripts = importScripts;
                    info.xhr_scripts = xhrScripts;
                    
                    // 获取localStorage中的认证信息
                    var authInfo = {};
                    try {
                        if (localStorage.getItem('pp_token')) {
                            authInfo.pp_token = localStorage.getItem('pp_token');
                        }
                        if (localStorage.getItem('authData')) {
                            authInfo.authData = localStorage.getItem('authData');
                        }
                        // 获取所有localStorage中的pp_相关项
                        for (var key in localStorage) {
                            if (key.indexOf('pp_') === 0 || key.indexOf('token') !== -1) {
                                authInfo[key] = localStorage.getItem(key);
                            }
                        }
                    } catch (e) {
                        authInfo.error = 'Error accessing localStorage';
                    }
                    info.authInfo = authInfo;
                    
                    // 获取cookie信息
                    var cookieInfo = {};
                    try {
                        var cookies = document.cookie.split(';');
                        for (var j = 0; j < cookies.length; j++) {
                            var cookie = cookies[j].trim();
                            var parts = cookie.split('=');
                            if (parts.length >= 2) {
                                var key = parts[0];
                                var value = parts.slice(1).join('=');
                                if (key.indexOf('pp_') === 0) {
                                    cookieInfo[key] = value;
                                }
                            }
                        }
                    } catch (e) {
                        cookieInfo.error = 'Error accessing cookies';
                    }
                    info.cookieInfo = cookieInfo;
                    
                    // 获取网络请求记录，查找JS文件
                    var networkRequests = [];
                    try {
                        // 检查是否有Performance API可用
                        if (window.performance && window.performance.getEntriesByType) {
                            var entries = window.performance.getEntriesByType('resource');
                            for (var k = 0; k < entries.length; k++) {
                                var entry = entries[k];
                                if (entry.initiatorType === 'script' && entry.name) {
                                    networkRequests.push(entry.name);
                                }
                            }
                        }
                    } catch (e) {
                        console.log('Error getting network requests:', e);
                    }
                    info.network_requests = networkRequests;
                    
                    // 合并所有可能的JS文件
                    var allPossibleScripts = [...new Set([...allScripts, ...networkRequests])];
                    info.all_scripts = allPossibleScripts;
                }, 10000);
                
                return info;
            }
            ''')
            
            # 2. 创建保存JS文件的目录
            import os
            js_dir = 'js_files'
            if not os.path.exists(js_dir):
                os.makedirs(js_dir)
                print(Fore.GREEN + f"创建JS文件保存目录: {js_dir}")
            
            # 3. 下载外部JS文件
            print(Fore.CYAN + "\n开始下载外部JS文件...")
            downloaded_files = []
            
            # 打印动态加载的脚本信息
            if 'dynamic_scripts' in js_info and js_info['dynamic_scripts']:
                print(Fore.YELLOW + f"发现 {len(js_info['dynamic_scripts'])} 个动态加载的脚本:")
                for script in js_info['dynamic_scripts']:
                    print(Fore.WHITE + f"  - {script}")
            
            # 打印import动态导入的脚本信息
            if 'import_scripts' in js_info and js_info['import_scripts']:
                print(Fore.YELLOW + f"发现 {len(js_info['import_scripts'])} 个import动态导入的脚本:")
                for script in js_info['import_scripts']:
                    print(Fore.WHITE + f"  - {script}")
            
            # 打印XHR加载的脚本信息
            if 'xhr_scripts' in js_info and js_info['xhr_scripts']:
                print(Fore.YELLOW + f"发现 {len(js_info['xhr_scripts'])} 个XHR加载的脚本:")
                for script in js_info['xhr_scripts']:
                    print(Fore.WHITE + f"  - {script}")
            
            # 使用所有可能的脚本列表
            all_scripts = js_info.get('all_scripts', js_info.get('scripts', []))
            print(Fore.CYAN + f"总共发现 {len(all_scripts)} 个脚本文件")
            
            for i, script_url in enumerate(all_scripts):
                try:
                    # 生成文件名
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(script_url)
                    filename = os.path.basename(parsed_url.path)
                    if not filename:
                        filename = f'script_{i}.js'
                    elif not filename.endswith('.js'):
                        filename += '.js'
                    
                    filepath = os.path.join(js_dir, filename)
                    
                    # 下载JS文件
                    print(Fore.YELLOW + f"  下载: {script_url}")
                    print(Fore.WHITE + f"  保存到: {filepath}")
                    
                    # 尝试多种方式下载文件
                    js_content = None
                    
                    # 方式1: 使用Playwright的fetch API
                    try:
                        js_content = self.page.evaluate(f'''
                        function() {{
                            return fetch('{script_url}', {{
                                method: 'GET',
                                headers: {{
                                    'Accept': '*/*',
                                    'User-Agent': navigator.userAgent
                                }},
                                credentials: 'include'
                            }}).then(function(response) {{
                                if (response.ok) {{
                                    return response.text();
                                }} else {{
                                    console.log('Fetch failed with status:', response.status);
                                    return null;
                                }}
                            }}).catch(function(e) {{
                                console.log('Fetch error:', e);
                                return null;
                            }});
                        }}
                        ''')
                    except Exception as e:
                        print(Fore.RED + f"  ❌ 方式1下载错误: {str(e)}")
                    
                    # 方式2: 如果方式1失败，尝试使用Python的requests库
                    if not js_content:
                        try:
                            print(Fore.YELLOW + f"  尝试使用方式2下载...")
                            import requests
                            headers = {
                                'Accept': '*/*',
                                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
                            }
                            response = requests.get(script_url, headers=headers, timeout=10)
                            if response.status_code == 200:
                                js_content = response.text
                                print(Fore.GREEN + f"  ✅ 方式2下载成功")
                            else:
                                print(Fore.RED + f"  ❌ 方式2下载失败，状态码: {response.status_code}")
                        except Exception as e:
                            print(Fore.RED + f"  ❌ 方式2下载错误: {str(e)}")
                    
                    # 保存到文件
                    if js_content:
                        with open(filepath, 'w', encoding='utf-8', errors='ignore') as f:
                            f.write(js_content)
                        downloaded_files.append(filepath)
                        print(Fore.GREEN + f"  ✅ 下载成功")
                    else:
                        print(Fore.RED + f"  ❌ 下载失败")
                    
                except Exception as e:
                    print(Fore.RED + f"  ❌ 下载错误: {str(e)}")
                
                # 防止请求过快
                import time
                time.sleep(0.5)
            
            # 4. 分析下载的JS文件
            print(Fore.CYAN + "\n开始分析下载的JS文件...")
            signature_related_files = []
            
            signature_keywords = ['pp_req_sign', 'pp_timestamp', 'pp_token', 'sign', 'signature', 'encrypt']
            
            for filepath in downloaded_files:
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # 检查是否包含签名相关关键词
                    found_keywords = []
                    for keyword in signature_keywords:
                        if keyword in content:
                            found_keywords.append(keyword)
                    
                    if found_keywords:
                        signature_related_files.append({
                            'file': filepath,
                            'keywords': found_keywords
                        })
                        print(Fore.GREEN + f"  ✅ {os.path.basename(filepath)} 包含关键词: {', '.join(found_keywords)}")
                    
                except Exception as e:
                    print(Fore.RED + f"  ❌ 分析文件 {filepath} 错误: {str(e)}")
            
            # 5. 打印分析结果
            print(Fore.GREEN + "\n=== JS文件分析结果 ===")
            print(Fore.CYAN + f"找到 {len(all_scripts)} 个外部JS文件")
            print(Fore.CYAN + f"成功下载 {len(downloaded_files)} 个JS文件")
            print(Fore.CYAN + f"找到 {len(signature_related_files)} 个包含签名相关关键词的文件")
            
            # 打印外部JS文件
            print(Fore.YELLOW + "\n外部JS文件:")
            for script in all_scripts:
                print(Fore.WHITE + f"  - {script}")
            
            # 打印动态加载的脚本
            if 'dynamic_scripts' in js_info and js_info['dynamic_scripts']:
                print(Fore.YELLOW + "\n动态加载的脚本:")
                for script in js_info['dynamic_scripts']:
                    print(Fore.WHITE + f"  - {script}")
            
            # 打印下载的文件
            print(Fore.YELLOW + "\n下载的JS文件:")
            for filepath in downloaded_files:
                print(Fore.WHITE + f"  - {filepath}")
            
            # 打印签名相关文件
            print(Fore.YELLOW + "\n签名相关的JS文件:")
            for item in signature_related_files:
                print(Fore.WHITE + f"  - {os.path.basename(item['file'])}: {', '.join(item['keywords'])}")
            
            # 打印认证信息
            print(Fore.GREEN + "\n=== 认证信息 ===")
            print(Fore.YELLOW + "LocalStorage中的认证信息:")
            for key, value in js_info['authInfo'].items():
                print(Fore.WHITE + f"  {key}: {value}")
            
            print(Fore.YELLOW + "\nCookie中的pp_*参数:")
            for key, value in js_info['cookieInfo'].items():
                print(Fore.WHITE + f"  {key}: {value}")
            
            # 6. 添加日志到GUI
            self.add_log("JS文件分析完成", 'green')
            self.add_log(f"找到 {len(js_info['scripts'])} 个外部JS文件", 'info')
            self.add_log(f"成功下载 {len(downloaded_files)} 个JS文件", 'info')
            self.add_log(f"找到 {len(signature_related_files)} 个包含签名相关关键词的文件", 'info')
            
            return {
                'js_info': js_info,
                'downloaded_files': downloaded_files,
                'signature_related_files': signature_related_files
            }
        except Exception as e:
            print(Fore.RED + f"分析JS文件失败: {str(e)}")
            logger.error(f"分析JS文件失败: {str(e)}")
            self.add_log(f"分析JS文件失败: {str(e)}", 'red')
            return None
    
    @ErrorHandler.handle_exception
    def crawl_orders_by_api(self, start_timestamp=None, end_timestamp=None, settlement_status=None, stop_event=None):
        """通过API爬取订单数据"""
        logger.info("开始通过API爬取订单数据")
        print(Fore.CYAN + "开始通过API爬取订单数据...")
        self.add_log("开始通过API爬取订单数据...", 'cyan')
        self.order_data = []
        self.is_running = True
        sink_label = "存储"
        if self.storage and hasattr(self.storage, 'get_sink_label'):
            sink_label = self.storage.get_sink_label()

        if self.storage and hasattr(self.storage, 'resolve_account_info'):
            account_info = self.storage.resolve_account_info(self.auth_info)
            account_id = account_info.get('account_id', 'unknown_account')
            logger.info(f"当前写入账号: {account_id}")
            print(Fore.CYAN + f"当前写入账号: {account_id}")
            self.add_log(f"当前写入账号: {account_id}", 'info')

        if self.storage and hasattr(self.storage, 'start_csv_session'):
            csv_file_path = self.storage.start_csv_session(auth_info=self.auth_info, force_new=True)
            if csv_file_path:
                logger.info(f"本次爬取CSV文件: {csv_file_path}")
                print(Fore.CYAN + f"本次爬取CSV文件: {csv_file_path}")
                self.add_log(f"本次爬取CSV文件: {csv_file_path}", 'info')
        
        # 页面翻页爬取
        page_number = 1
        processed_count = 0
        # 保存订单总数
        self.total_orders = 0
        
        while self.is_running:
            # 检查是否收到停止信号
            if stop_event and stop_event.is_set():
                logger.info("收到停止信号，停止爬取")
                print(Fore.YELLOW + "收到停止信号，停止爬取")
                self.add_log("收到停止信号，停止爬取", 'yellow')
                break
            
            print(Fore.CYAN + f"处理第 {page_number} 页...")
            logger.info(f"处理第 {page_number} 页")
            self.add_log(f"处理第 {page_number} 页...", 'cyan')
            
            # 通过API获取订单列表
            orders, pagination = self.get_order_list_from_api(start_timestamp, end_timestamp, page_number=page_number, page_size=self.page_size, settlement_status=settlement_status)
            
            if not orders:
                if page_number == 1:
                    logger.warning("没有找到订单，爬取结束")
                    print(Fore.RED + "没有找到订单，爬取结束")
                    self.add_log("没有找到订单，爬取结束", 'red')
                else:
                    logger.info("已获取所有订单，爬取完成")
                    print(Fore.GREEN + "已获取所有订单，爬取完成")
                    self.add_log("已获取所有订单，爬取完成", 'green')
                break
            
            # 检查是否已经到达最后一页
            current_page = pagination.get('current', page_number)
            total_pages = pagination.get('pages', 0)
            total_orders = pagination.get('total', 0)
            
            # 打印分页信息（更加醒目）
            print(Fore.CYAN + "=" * 60)
            print(Fore.CYAN + f"【爬取进度】当前页: {current_page} | 总页数: {total_pages} | 总条数: {total_orders}")
            print(Fore.CYAN + "=" * 60)
            logger.info(f"当前页: {current_page}, 总页数: {total_pages}, 总条数: {total_orders}")
            self.add_log(f"【爬取进度】第 {current_page}/{total_pages} 页，共 {total_orders} 条订单", 'cyan')
            
            # 保存订单总数
            if total_orders > 0:
                self.total_orders = total_orders
            else:
                # 如果API返回的total为0，累加当前页的订单数
                self.total_orders += len(orders)
            
            # 批量获取订单详情
            batch_orders = self.get_order_details_batch(orders)
            
            # 处理获取到的订单详情
            for order in batch_orders:
                # 检查是否应该停止
                if not self.is_running or (stop_event and stop_event.is_set()):
                    logger.info("收到停止信号，停止爬取")
                    print(Fore.YELLOW + "收到停止信号，停止爬取")
                    self.add_log("收到停止信号，停止爬取", 'yellow')
                    break
                
                # 添加到总数据
                self.order_data.append(order)
                processed_count += 1
                
                # 实时写入当前存储目标（接口或数据库）
                if self.storage:
                    self.storage.append_single_to_db(order, auth_info=self.auth_info)
                
                # 确保总订单数正确显示
                current_total = getattr(self, 'total_orders', total_orders)
                # 如果总订单数为0，使用已处理订单数作为临时替代
                if current_total == 0:
                    current_total = processed_count
                logger.info(f"已处理 {processed_count} / {current_total}个订单，正在写入第 {processed_count} 条到{sink_label}")
                print(Fore.GREEN + f"已处理 {processed_count} / {current_total}个订单，正在写入第 {processed_count} 条到{sink_label}")
                self.add_log(f"已处理 {processed_count} / {current_total}个订单，正在写入第 {processed_count} 条到{sink_label}", 'green')
            
            # 检查是否应该停止
            if not self.is_running or (stop_event and stop_event.is_set()):
                logger.info("收到停止信号，停止翻页")
                break
            
            if current_page >= total_pages and total_pages > 0:
                logger.info(f"已到达最后一页（第 {current_page} 页，共 {total_pages} 页），爬取完成")
                print(Fore.GREEN + f"已到达最后一页（第 {current_page} 页，共 {total_pages} 页），爬取完成")
                self.add_log(f"已到达最后一页（第 {current_page} 页，共 {total_pages} 页），爬取完成", 'green')
                break
            
            page_number += 1
            
            # 防止请求过快
            time.sleep(self.request_delay)
        
        if self.storage and hasattr(self.storage, 'flush_pending'):
            flush_ok = self.storage.flush_pending(auth_info=self.auth_info)
            if flush_ok:
                self.add_log("已完成CSV到接口推送", 'green')
            else:
                self.add_log("CSV到接口推送失败，请检查接口状态", 'yellow')

        logger.info(f"API爬取完成，共处理 {processed_count} 个订单")
        print(Fore.GREEN + f"API爬取完成，共处理 {processed_count} 个订单")
        self.add_log(f"API爬取完成，共处理 {processed_count} 个订单", 'green')
        
        # 输出保存完毕的日志
        logger.info("保存完毕，爬虫停止")
        print(Fore.GREEN + "保存完毕，爬虫停止")
        self.add_log("保存完毕，爬虫停止", 'green')
        
        return self.order_data
    
    def get_order_details_batch(self, orders):
        """批量获取订单详情"""
        import concurrent.futures
        
        batch_orders = []
        
        # 定义获取单个订单详情的函数
        def get_order_detail(order):
            order_no = order['order_no']
            order_type = order['order_type']
            
            # 打印订单总数信息
            if hasattr(self, 'total_orders') and self.total_orders > 0:
                print(Fore.CYAN + f"通过API获取订单 {order_no} 详情... (订单总数: {self.total_orders})")
                logger.info(f"通过API获取订单 {order_no} 详情 (订单总数: {self.total_orders})")
                self.add_log(f"通过API获取订单 {order_no} 详情... (订单总数: {self.total_orders})")
            else:
                print(Fore.CYAN + f"通过API获取订单 {order_no} 详情...")
                logger.info(f"通过API获取订单 {order_no} 详情")
                self.add_log(f"通过API获取订单 {order_no} 详情...")
            
            # 通过API获取订单详情
            detail_data = self.get_order_detail_from_api(order_no, order_type)
            
            if detail_data:
                # 只使用订单详情中的信息，不合并订单列表中的信息
                # 添加订单号到详情数据中，以便识别
                detail_data['order_no'] = order_no
                print(Fore.GREEN + f"成功获取订单 {order_no} 详情")
                logger.info(f"成功获取订单 {order_no} 详情")
                self.add_log(f"成功获取订单 {order_no} 详情", 'green')
                return detail_data
            else:
                print(Fore.YELLOW + f"未获取到订单 {order_no} 详情数据，使用订单列表中的基本信息")
                logger.warning(f"未获取到订单 {order_no} 详情数据，使用订单列表中的基本信息")
                self.add_log(f"未获取到订单 {order_no} 详情数据，使用订单列表中的基本信息", 'yellow')
                # 未获取到详情时，返回订单列表中的基本信息
                return order
            
            return order
        
        # 使用线程池并行获取订单详情
        max_workers = min(5, len(orders))  # 最多5个线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有订单详情请求
            future_to_order = {executor.submit(get_order_detail, order): order for order in orders}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_order):
                try:
                    order = future.result()
                    batch_orders.append(order)
                except Exception as e:
                    order = future_to_order[future]
                    print(Fore.RED + f"获取订单 {order['order_no']} 详情时出错: {str(e)}")
                    logger.error(f"获取订单 {order['order_no']} 详情时出错: {str(e)}")
                    self.add_log(f"获取订单 {order['order_no']} 详情时出错: {str(e)}", 'red')
                    batch_orders.append(order)  # 即使出错也添加原始订单数据
        
        return batch_orders
    
    def stop(self):
        """停止爬取"""
        self.is_running = False
        logger.info("停止API爬取")
        print(Fore.YELLOW + "停止API爬取...")
        self.add_log("停止API爬取", 'yellow')
