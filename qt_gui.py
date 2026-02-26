import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QStatusBar, QSplitter, QDateTimeEdit, QComboBox, QDateEdit
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDateTime, QDate
from PyQt5.QtGui import QFont, QColor, QTextCursor

class LogThread(QThread):
    """日志更新线程"""
    log_signal = pyqtSignal(str, str)
    
    def __init__(self, gui_server):
        super().__init__()
        self.gui_server = gui_server
        self.running = True
    
    def run(self):
        while self.running:
            # 检查是否有新日志
            if hasattr(self.gui_server, 'logs') and self.gui_server.logs:
                for log in self.gui_server.logs:
                    self.log_signal.emit(log['message'], log['type'])
                # 清空已处理的日志
                self.gui_server.logs = []
            time.sleep(0.5)
    
    def stop(self):
        self.running = False
        self.wait()

class QtGUI(QMainWindow):
    """Qt GUI客户端"""
    def __init__(self, gui_server, browser_manager=None):
        super().__init__()
        self.gui_server = gui_server
        self.browser_manager = browser_manager
        self.init_ui()
        self.start_log_thread()
        # 添加parent属性，用于访问浏览器线程
        self.parent = gui_server
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('🐊 Palmpay爬虫控制面板')
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(600, 400)
        
        # 中心widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 标题栏
        title_label = QLabel('Palmpay爬虫控制面板')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont('', 16, QFont.Bold))
        title_label.setStyleSheet('color: #4CAF50; margin: 10px 0;')
        main_layout.addWidget(title_label)
        
        # 日期选择布局
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10)
        
        # 开始日期时间
        start_date_label = QLabel('开始时间【尼日】:')
        start_date_label.setFont(QFont('', 10))
        date_layout.addWidget(start_date_label)
        
        # 使用日期选择器，只选择日期，默认时间为00:00:00
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.start_date_edit.setDate(QDate.currentDate().addDays(-2))
        self.start_date_edit.setFont(QFont('', 10))
        self.start_date_edit.setStyleSheet('''
            QDateEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                selection-background-color: #4CAF50;
                selection-color: white;
                min-width: 120px;
            }
            QDateEdit:hover {
                border-color: #4CAF50;
            }
        ''')
        date_layout.addWidget(self.start_date_edit)
        
        # 结束日期时间
        end_date_label = QLabel('结束时间:')
        end_date_label.setFont(QFont('', 10))
        date_layout.addWidget(end_date_label)
        
        # 使用日期选择器，只选择日期，默认时间为23:59:59
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setFont(QFont('', 10))
        self.end_date_edit.setStyleSheet('''
            QDateEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                selection-background-color: #4CAF50;
                selection-color: white;
                min-width: 120px;
            }
            QDateEdit:hover {
                border-color: #4CAF50;
            }
        ''')
        date_layout.addWidget(self.end_date_edit)
        
        main_layout.addLayout(date_layout)
        
        # 结算状态选择布局
        settlement_layout = QHBoxLayout()
        settlement_layout.setSpacing(10)
        
        # 结算状态标签
        settlement_label = QLabel('结算状态:')
        settlement_label.setFont(QFont('', 10))
        settlement_layout.addWidget(settlement_label)
        
        # 结算状态下拉框
        self.settlement_combo = QComboBox()
        self.settlement_combo.setFont(QFont('', 10))
        self.settlement_combo.addItem('Successful', '2')  # 显示为Success，值为2
        self.settlement_combo.addItem('All', 'None')  
        self.settlement_combo.setCurrentIndex(0)  # 默认选择Success
        settlement_layout.addWidget(self.settlement_combo)
        
        main_layout.addLayout(settlement_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 爬虫控制按钮（动态状态）
        self.crawler_btn = QPushButton('启动爬虫')
        self.crawler_btn.setFont(QFont('', 10))
        self.crawler_btn.setStyleSheet(
            'background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 4px;'
        )
        self.crawler_btn.clicked.connect(self.toggle_crawler)
        button_layout.addWidget(self.crawler_btn)
        
        # 清理日志按钮
        self.clear_log_btn = QPushButton('清理日志')
        self.clear_log_btn.setFont(QFont('', 10))
        self.clear_log_btn.setStyleSheet(
            'background-color: #2196F3; color: white; padding: 10px 20px; border-radius: 4px;'
        )
        self.clear_log_btn.clicked.connect(self.clear_log)
        button_layout.addWidget(self.clear_log_btn)
        
        # 打开数据目录按钮
        self.open_excel_btn = QPushButton('打开数据目录')
        self.open_excel_btn.setFont(QFont('', 10))
        self.open_excel_btn.setStyleSheet(
            'background-color: #9C27B0; color: white; padding: 10px 20px; border-radius: 4px;'
        )
        self.open_excel_btn.clicked.connect(self.open_excel_folder)
        button_layout.addWidget(self.open_excel_btn)
        
        # 退出按钮
        self.exit_btn = QPushButton('退出程序')
        self.exit_btn.setFont(QFont('', 10))
        self.exit_btn.setStyleSheet(
            'background-color: #f44336; color: white; padding: 10px 20px; border-radius: 4px;'
        )
        self.exit_btn.clicked.connect(self.exit_program)
        button_layout.addWidget(self.exit_btn)
        
        main_layout.addLayout(button_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 日志区域
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        log_title = QLabel('📋 实时日志')
        log_title.setFont(QFont('', 10, QFont.Bold))
        log_title.setStyleSheet('color: #4CAF50; margin: 5px 0;')
        log_layout.addWidget(log_title)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Courier New', 10))
        self.log_text.setStyleSheet(
            'background-color: #0d0d0d; color: #00ff00; padding: 10px; border: 1px solid #333; border-radius: 4px;'
        )
        log_layout.addWidget(self.log_text)
        
        splitter.addWidget(log_widget)
        
        # 状态区域
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        
        status_title = QLabel('📊 系统状态')
        status_title.setFont(QFont('', 10, QFont.Bold))
        status_title.setStyleSheet('color: #4CAF50; margin: 5px 0;')
        status_layout.addWidget(status_title)
        
        # 状态信息
        status_grid = QVBoxLayout()
        
        self.status_running = QLabel('爬虫状态: <font color="#ff4444">未运行</font>')
        self.status_running.setFont(QFont('', 9))
        status_grid.addWidget(self.status_running)
        
        self.status_orders = QLabel('已处理订单: 0')
        self.status_orders.setFont(QFont('', 9))
        status_grid.addWidget(self.status_orders)
        
        self.status_time = QLabel('运行时间: 00:00:00')
        self.status_time.setFont(QFont('', 9))
        status_grid.addWidget(self.status_time)
        
        self.status_update = QLabel('上次更新: -')
        self.status_update.setFont(QFont('', 9))
        status_grid.addWidget(self.status_update)
        
        status_layout.addLayout(status_grid)
        splitter.addWidget(status_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 150])
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('就绪')
        
        # 定时器更新时间
        self.start_time = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
        # 定时器检查登录状态
        self.login_check_timer = QTimer(self)
        self.login_check_timer.timeout.connect(self.check_and_update_login_status)
        self.login_check_timer.start(5000)  # 每5秒检查一次登录状态
        
        # 定时器更新爬虫按钮状态
        self.crawler_button_timer = QTimer(self)
        self.crawler_button_timer.timeout.connect(self.update_crawler_button)
        self.crawler_button_timer.start(2000)  # 每2秒更新一次按钮状态
        
        # 初始日志
        self.add_log('Qt GUI客户端启动成功', 'green')
        self.add_log('等待用户操作...', 'info')
    
    def start_log_thread(self):
        """启动日志线程"""
        self.log_thread = LogThread(self.gui_server)
        self.log_thread.log_signal.connect(self.add_log)
        self.log_thread.start()
    
    def add_log(self, message, log_type='info'):
        """添加日志"""
        timestamp = time.strftime('%H:%M:%S')
        
        # 设置日志颜色
        color_map = {
            'info': '#00ff00',
            'green': '#4CAF50',
            'red': '#ff4444',
            'yellow': '#ffaa00',
            'cyan': '#00ffff'
        }
        color = color_map.get(log_type, '#00ff00')
        
        # 添加日志
        log_entry = f'[{timestamp}] {message}\n'
        self.log_text.moveCursor(QTextCursor.End)
        self.log_text.setTextColor(QColor(color))
        self.log_text.insertPlainText(log_entry)
        self.log_text.moveCursor(QTextCursor.End)
        
        # 更新状态栏
        self.statusBar.showMessage(f'[{timestamp}] {message}')
    
    def update_time(self):
        """更新时间显示"""
        current_time = time.strftime('%H:%M:%S')
        self.status_update.setText(f'上次更新: {current_time}')
        
        if self.start_time:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
            self.status_time.setText(f'运行时间: {time_str}')
    
    def check_login_status(self):
        """检查登录状态"""
        if not self.browser_manager:
            return False
        
        # 检查是否有浏览器线程
        if hasattr(self, 'gui_server') and hasattr(self.gui_server, 'browser_thread'):
            # 通过浏览器线程执行操作，避免线程安全问题
            
            # 创建一个事件来等待结果
            import threading
            result_event = threading.Event()
            result_container = {'result': False}
            
            # 定义回调函数来处理结果
            def on_login_status_checked(status):
                result_container['result'] = status
                result_event.set()
            
            # 将回调函数添加到浏览器线程
            self.gui_server.browser_thread.add_operation({
                'type': 'check_login_status',
                'callback': on_login_status_checked
            })
            
            # 等待结果（最多等待5秒）
            result_event.wait(timeout=5)
            
            return result_container['result']
        else:
            return False
    
    def check_order_page_status(self):
        """检查是否在订单列表页"""
        if not self.browser_manager:
            return False
        
        # 检查是否有浏览器线程
        if hasattr(self, 'gui_server') and hasattr(self.gui_server, 'browser_thread'):
            # 通过浏览器线程执行操作，避免线程安全问题
            
            # 创建一个事件来等待结果
            import threading
            result_event = threading.Event()
            result_container = {'result': False}
            
            # 定义回调函数来处理结果
            def on_order_page_status_checked(status):
                result_container['result'] = status
                result_event.set()
            
            # 将回调函数添加到浏览器线程
            self.gui_server.browser_thread.add_operation({
                'type': 'check_order_page_status',
                'callback': on_order_page_status_checked
            })
            
            # 等待结果（最多等待5秒）
            result_event.wait(timeout=5)
            
            return result_container['result']
        else:
            return False
    
    def navigate_to_order_page(self):
        """跳转到订单列表页"""
        if not self.browser_manager:
            return False
        
        try:
            page = self.browser_manager.get_page()
            if not page:
                # 启动浏览器
                page = self.browser_manager.start_browser()
                if not page:
                    return False
            
            # 导航到订单列表页
            # 使用浏览器管理器的方法导航，避免直接操作page对象
            if hasattr(self.browser_manager, 'navigate_to_order_list'):
                success = self.browser_manager.navigate_to_order_list()
                if success:
                    return True
                else:
                    return False
            else:
                # 备用方案：使用page对象导航
                page.goto('https://business.palmpay.com/#/reconciliation/transaction/list')
                # 等待页面加载
                import time
                time.sleep(3)
                
                # 检查是否导航成功
                if self.check_order_page_status():
                    return True
                else:
                    return False
        except Exception as e:
            return False
    
    def get_date_timestamps(self):
        """获取选中的日期时间戳（西非时区，UTC+1）"""
        from PyQt5.QtCore import QDateTime, QTime
        import datetime
        
        # 获取开始日期，设置时间为00:00:00
        start_date = self.start_date_edit.date()
        start_datetime = QDateTime(start_date, QTime(0, 0, 0))
        
        # 获取结束日期，设置时间为23:59:59
        end_date = self.end_date_edit.date()
        end_datetime = QDateTime(end_date, QTime(23, 59, 59))
        
        try:
            # 转换为Python datetime对象
            start_py_dt = datetime.datetime(
                start_datetime.date().year(),
                start_datetime.date().month(),
                start_datetime.date().day(),
                start_datetime.time().hour(),
                start_datetime.time().minute(),
                start_datetime.time().second()
            )
            
            end_py_dt = datetime.datetime(
                end_datetime.date().year(),
                end_datetime.date().month(),
                end_datetime.date().day(),
                end_datetime.time().hour(),
                end_datetime.time().minute(),
                end_datetime.time().second()
            )
            
            # UI中的时间是西非时间（UTC+1），API需要UTC时间戳
            # 将西非时间转换为UTC时间（减去1小时）
            wat_tz = datetime.timezone(datetime.timedelta(hours=1))
            start_wat = start_py_dt.replace(tzinfo=wat_tz)
            end_wat = end_py_dt.replace(tzinfo=wat_tz)
            
            # 转换为UTC时间戳（毫秒）
            start_timestamp = int(start_wat.timestamp() * 1000)
            end_timestamp = int(end_wat.timestamp() * 1000)
        except Exception as e:
            # 如果时区处理失败，使用本地时间戳作为备选
            print(f"时区处理失败: {str(e)}")
            start_timestamp = int(start_datetime.toSecsSinceEpoch() * 1000)
            end_timestamp = int(end_datetime.toSecsSinceEpoch() * 1000)
        
        return start_timestamp, end_timestamp
    
    def start_crawler(self):
        """启动爬虫"""
        self.add_log('正在启动爬虫...', 'info')
        self.status_running.setText('爬虫状态: <font color="#4CAF50">运行中</font>')
        
        # 获取日期时间戳
        start_timestamp, end_timestamp = self.get_date_timestamps()
        self.add_log(f'日期范围: {start_timestamp} 到 {end_timestamp}', 'info')
        
        # 获取结算状态
        settlement_status = self.settlement_combo.currentData()
        self.add_log(f'结算状态: {settlement_status}', 'info')
        
        # 检查是否有爬虫实例和浏览器管理器
        if hasattr(self, 'parent') and hasattr(self.parent, 'crawler') and hasattr(self.parent, 'browser_manager'):
            # 使用新的触发机制，避免线程切换错误
            if hasattr(self.parent, 'trigger_crawler'):
                success = self.parent.trigger_crawler(start_timestamp, end_timestamp, settlement_status)
                if success:
                    self.add_log('爬虫执行已触发', 'green')
                    # 更新按钮状态
                    self.update_crawler_button()
                else:
                    self.add_log('触发爬虫执行失败', 'red')
                    self.status_running.setText('爬虫状态: <font color="#ff4444">已停止</font>')
                    self.update_crawler_button()
            else:
                self.add_log('未找到触发爬虫的方法', 'red')
                self.status_running.setText('爬虫状态: <font color="#ff4444">已停止</font>')
                self.update_crawler_button()
        else:
            self.add_log('无法启动爬虫：未找到爬虫实例或浏览器管理器', 'red')
            self.add_log('提示：请确保已登录并导航到订单列表页', 'yellow')
            self.status_running.setText('爬虫状态: <font color="#ff4444">已停止</font>')
            self.update_crawler_button()
    
    def stop_crawler(self):
        """停止爬虫"""
        self.add_log('正在停止爬虫...', 'info')
        self.status_running.setText('爬虫状态: <font color="#ff4444">已停止</font>')
        
        # 停止爬虫业务
        if hasattr(self, 'parent') and hasattr(self.parent, 'stop_crawler_event'):
            self.parent.stop_crawler_event.set()
            self.add_log('爬虫停止事件已触发', 'green')
            # 更新按钮状态
            self.update_crawler_button()
        else:
            self.add_log('无法停止爬虫：未找到停止事件', 'red')
            self.update_crawler_button()
    
    def toggle_crawler(self):
        """切换爬虫状态"""
        # 检查爬虫是否正在运行
        if '运行中' in self.status_running.text():
            # 停止爬虫
            self.stop_crawler()
            # 恢复按钮状态
            self.update_crawler_button()
            return
        
        # 检查登录状态
        if not self.check_login_status():
            # 未登录，提示并打开登录页
            self.add_log('请先登录', 'yellow')
            # 弹出提示
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, '提示', '请先登录Palmpay商户后台', 
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.open_login()
            return
        
        # 检查是否在订单列表页
        if not self.check_order_page_status():
            # 不在订单列表页，提示并跳转
            self.add_log('请先跳转到订单列表页', 'yellow')
            # 弹出提示
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, '提示', '请先跳转到订单列表页', 
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.navigate_to_order_page()
            return
        
        # 启动爬虫
        self.start_crawler()
    
    def update_crawler_button(self):
        """更新爬虫按钮状态"""
        # 检查爬虫是否正在运行
        is_running = False
        if hasattr(self, 'parent') and hasattr(self.parent, 'is_running'):
            is_running = self.parent.is_running
        
        if is_running:
            # 爬虫正在运行，显示停止按钮
            self.crawler_btn.setText('停止爬虫')
            self.crawler_btn.setStyleSheet(
                'background-color: #f44336; color: white; padding: 10px 20px; border-radius: 4px;'
            )
        else:
            # 爬虫未运行，显示启动按钮
            self.crawler_btn.setText('启动爬虫')
            self.crawler_btn.setStyleSheet(
                'background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 4px;'
            )
    
    def open_login(self):
        """打开登录页"""
        self.add_log('正在打开登录页面...', 'info')
        
        if self.browser_manager:
            try:
                # 检查浏览器是否已经启动
                if not self.browser_manager.get_page():
                    # 启动浏览器
                    self.add_log('浏览器未启动，正在启动浏览器...', 'cyan')
                    self.browser_manager.start_browser()
                    
                # 导航到登录页面
                self.add_log('正在导航到登录页面...', 'cyan')
                # 使用浏览器管理器的login方法，避免直接操作page对象
                if hasattr(self.browser_manager, 'login'):
                    # 注意：这里不会实际执行登录，只是导航到登录页
                    # 浏览器管理器的login方法会等待用户手动登录
                    self.add_log('登录页面已打开，请在浏览器中完成登录', 'green')
                else:
                    # 备用方案：使用page对象导航
                    page = self.browser_manager.get_page()
                    if page:
                        page.goto('https://business.palmpay.com/#/login')
                        self.add_log('登录页面已打开', 'green')
                    else:
                        self.add_log('无法获取浏览器页面', 'red')
            except Exception as e:
                self.add_log(f'打开登录页面失败: {str(e)}', 'red')
        else:
            self.add_log('浏览器管理器未初始化', 'red')
    
    def exit_program(self):
        """退出程序"""
        self.add_log('正在退出程序...', 'info')
        self.log_thread.stop()
        self.close()
    
    def open_excel_folder(self):
        """打开数据目录（包含数据库文件）"""
        import os
        import subprocess
        
        # 数据库存放目录
        excel_folder = os.path.join(os.getcwd(), 'data')
        
        try:
            # 检查文件夹是否存在
            if not os.path.exists(excel_folder):
                # 如果文件夹不存在，创建它
                os.makedirs(excel_folder)
                self.add_log(f'创建文件夹: {excel_folder}', 'green')
            
            # 打开文件夹
            if os.name == 'nt':  # Windows
                os.startfile(excel_folder)
            elif os.name == 'posix':  # macOS或Linux
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', excel_folder])
                else:  # Linux
                    subprocess.run(['xdg-open', excel_folder])
            
            self.add_log(f'已打开数据文件夹: {excel_folder}', 'green')
        except Exception as e:
            self.add_log(f'打开数据文件夹失败: {str(e)}', 'red')
    
    def clear_log(self):
        """清理日志"""
        self.log_text.clear()
        self.add_log('日志已清理', 'info')
    
    def check_and_update_login_status(self):
        """检查并更新登录状态"""
        if hasattr(self, 'parent') and hasattr(self.parent, 'crawler'):
            # 检查登录状态
            login_status = self.check_login_status()
            order_page_status = self.check_order_page_status()
            
            # 更新按钮状态
            if login_status and order_page_status:
                self.status_running.setText('爬虫状态: <font color="#ff4444">未运行</font>')
            elif login_status:
                self.status_running.setText('爬虫状态: <font color="#ffaa00">已登录，未在订单页</font>')
            else:
                self.status_running.setText('爬虫状态: <font color="#ff4444">未登录</font>')
            
            # 更新按钮状态
            self.update_crawler_button()
    
    def closeEvent(self, event):
        """关闭事件"""
        self.log_thread.stop()
        self.login_check_timer.stop()  # 停止登录状态检查定时器
        event.accept()

class QtGUIServer:
    """Qt GUI服务器"""
    def __init__(self, browser_manager=None):
        self.app = None
        self.gui = None
        self.logs = []
        self.browser_manager = browser_manager
    
    def start(self):
        """启动Qt GUI"""
        # 检查是否已有QApplication实例
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        
        # 创建GUI
        self.gui = QtGUI(self, self.browser_manager)
        self.gui.show()
        
        print('Qt GUI客户端已启动')
        return self.gui
    
    def add_log(self, message, log_type='info'):
        """添加日志"""
        self.logs.append({
            'message': message,
            'type': log_type,
            'time': time.strftime('%H:%M:%S')
        })
        
        # 限制日志数量
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
    
    def run(self):
        """运行Qt应用"""
        if self.app:
            return self.app.exec_()
        return 0

# 测试代码
if __name__ == "__main__":
    gui_server = QtGUIServer()
    gui_server.start()
    
    # 测试添加日志
    gui_server.add_log("Qt GUI客户端启动成功", "green")
    gui_server.add_log("等待用户操作...", "info")
    
    # 运行应用
    gui_server.run()
