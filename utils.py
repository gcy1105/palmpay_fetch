import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

def load_env_file():
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
            print(f"已加载环境配置文件: {env_file}")
        else:
            print(f"未找到环境配置文件: {env_file}")
    except Exception as e:
        print(f"加载环境配置文件失败: {str(e)}")

load_env_file()

class Logger:
    def __init__(self):
        self.log_file = os.getenv('LOG_FILE', 'crawler.log')
        self.setup_logger()
    
    def setup_logger(self):
        """设置日志配置"""
        # 创建日志目录
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def info(self, message):
        """记录信息日志"""
        self.logger.info(message)
    
    def warning(self, message):
        """记录警告日志"""
        self.logger.warning(message)
    
    def error(self, message):
        """记录错误日志"""
        self.logger.error(message)
    
    def exception(self, message):
        """记录异常日志"""
        self.logger.exception(message)

# 创建全局日志实例
logger = Logger()

class ErrorHandler:
    """错误处理类"""
    
    @staticmethod
    def handle_exception(func):
        """异常处理装饰器"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"{func.__name__} 函数执行异常: {str(e)}")
                return None
        return wrapper
