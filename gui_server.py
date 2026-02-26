import http.server
import socketserver
import threading
import webbrowser
import json
import time
import os

class GUIServer:
    def __init__(self):
        self.logs = []
        self.is_running = False
        self.server = None
        self.server_thread = None
        self.port = 8888
        self.html_content = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Palmpay爬虫控制面板</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background-color: #1a1a1a;
            color: #ffffff;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .header h1 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .container {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 120px);
            padding: 20px;
            gap: 20px;
        }
        
        .button-section {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            flex: 1;
            min-width: 150px;
        }
        
        .btn-primary {
            background-color: #4CAF50;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #45a049;
            transform: translateY(-2px);
        }
        
        .btn-secondary {
            background-color: #2196F3;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #1976D2;
            transform: translateY(-2px);
        }
        
        .btn-warning {
            background-color: #ff9800;
            color: white;
        }
        
        .btn-warning:hover {
            background-color: #f57c00;
            transform: translateY(-2px);
        }
        
        .btn-danger {
            background-color: #f44336;
            color: white;
        }
        
        .btn-danger:hover {
            background-color: #d32f2f;
            transform: translateY(-2px);
        }
        
        .log-section {
            flex: 1;
            background-color: #0d0d0d;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 15px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }
        
        .log-header h2 {
            font-size: 16px;
            color: #4CAF50;
        }
        
        .log-controls {
            display: flex;
            gap: 10px;
        }
        
        .log-content {
            flex: 1;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
        }
        
        .log-entry {
            margin-bottom: 5px;
        }
        
        .log-time {
            color: #888;
            margin-right: 10px;
        }
        
        .log-info {
            color: #00ff00;
        }
        
        .log-green {
            color: #4CAF50;
        }
        
        .log-red {
            color: #ff4444;
        }
        
        .log-yellow {
            color: #ffaa00;
        }
        
        .log-cyan {
            color: #00ffff;
        }
        
        .status-section {
            background-color: #2a2a2a;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 15px;
        }
        
        .status-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        
        .status-label {
            color: #888;
        }
        
        .status-value {
            font-weight: bold;
        }
        
        .status-running {
            color: #4CAF50;
        }
        
        .status-stopped {
            color: #ff4444;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .button-section {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐊 Palmpay爬虫控制面板</h1>
        <p>实时监控爬虫状态和日志</p>
    </div>
    
    <div class="container">
        <div class="button-section">
            <button class="btn btn-primary" onclick="startCrawler()">启动爬虫</button>
            <button class="btn btn-warning" onclick="stopCrawler()">停止爬虫</button>
            <button class="btn btn-secondary" onclick="navigateToLogin()">打开登录页</button>
            <button class="btn btn-danger" onclick="exitProgram()">退出程序</button>
        </div>
        
        <div class="log-section">
            <div class="log-header">
                <h2>📋 实时日志</h2>
                <div class="log-controls">
                    <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="clearLogs()">清空</button>
                    <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="saveLogs()">保存</button>
                </div>
            </div>
            <div class="log-content" id="logContent">
                <div class="log-entry"><span class="log-time">[系统]</span><span class="log-info">控制面板已初始化</span></div>
            </div>
        </div>
        
        <div class="status-section">
            <div class="status-item">
                <span class="status-label">爬虫状态:</span>
                <span class="status-value status-stopped" id="crawlerStatus">未运行</span>
            </div>
            <div class="status-item">
                <span class="status-label">已处理订单:</span>
                <span class="status-value" id="processedOrders">0</span>
            </div>
            <div class="status-item">
                <span class="status-label">运行时间:</span>
                <span class="status-value" id="runTime">00:00:00</span>
            </div>
            <div class="status-item">
                <span class="status-label">上次更新:</span>
                <span class="status-value" id="lastUpdate">-</span>
            </div>
        </div>
    </div>
    
    <script>
        // 状态变量
        let crawlerRunning = false;
        let processedOrders = 0;
        let startTime = null;
        
        // 更新时间显示
        function updateTime() {
            if (startTime) {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
                const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
                const seconds = (elapsed % 60).toString().padStart(2, '0');
                document.getElementById('runTime').textContent = `${hours}:${minutes}:${seconds}`;
            }
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            setTimeout(updateTime, 1000);
        }
        
        // 启动爬虫
        function startCrawler() {
            if (!crawlerRunning) {
                fetch('/api/start', {
                    method: 'POST'
                }).then(response => response.json())
                  .then(data => {
                    if (data.success) {
                        crawlerRunning = true;
                        startTime = Date.now();
                        document.getElementById('crawlerStatus').textContent = '运行中';
                        document.getElementById('crawlerStatus').className = 'status-value status-running';
                        addLog('爬虫已启动', 'green');
                    } else {
                        addLog('启动爬虫失败: ' + data.error, 'red');
                    }
                  });
            }
        }
        
        // 停止爬虫
        function stopCrawler() {
            if (crawlerRunning) {
                fetch('/api/stop', {
                    method: 'POST'
                }).then(response => response.json())
                  .then(data => {
                    if (data.success) {
                        crawlerRunning = false;
                        document.getElementById('crawlerStatus').textContent = '已停止';
                        document.getElementById('crawlerStatus').className = 'status-value status-stopped';
                        addLog('爬虫已停止', 'yellow');
                    } else {
                        addLog('停止爬虫失败: ' + data.error, 'red');
                    }
                  });
            }
        }
        
        // 导航到登录页
        function navigateToLogin() {
            fetch('/api/navigate/login', {
                method: 'POST'
            }).then(response => response.json())
              .then(data => {
                if (data.success) {
                    addLog('已打开登录页面', 'info');
                } else {
                    addLog('打开登录页面失败: ' + data.error, 'red');
                }
              });
        }
        
        // 退出程序
        function exitProgram() {
            if (confirm('确定要退出程序吗？')) {
                fetch('/api/exit', {
                    method: 'POST'
                });
            }
        }
        
        // 清空日志
        function clearLogs() {
            document.getElementById('logContent').innerHTML = '';
            addLog('日志已清空', 'info');
        }
        
        // 保存日志
        function saveLogs() {
            const logs = document.getElementById('logContent').innerHTML;
            const blob = new Blob([logs], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `palmpay-logs-${new Date().toISOString().slice(0, 10)}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            addLog('日志已保存', 'green');
        }
        
        // 添加日志
        function addLog(message, type = 'info') {
            const logContent = document.getElementById('logContent');
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            
            const timestamp = new Date().toLocaleTimeString();
            logEntry.innerHTML = `<span class="log-time">[${timestamp}]</span><span class="log-${type}">${message}</span>`;
            logContent.appendChild(logEntry);
            logContent.scrollTop = logContent.scrollHeight;
        }
        
        // 定期获取日志
        function fetchLogs() {
            fetch('/api/logs')
                .then(response => response.json())
                .then(data => {
                    if (data.logs && data.logs.length > 0) {
                        data.logs.forEach(log => {
                            addLog(log.message, log.type);
                        });
                    }
                });
            setTimeout(fetchLogs, 2000);
        }
        
        // 初始化
        function init() {
            updateTime();
            fetchLogs();
            addLog('控制面板已启动', 'info');
        }
        
        // 页面加载完成后初始化
        window.onload = init;
    </script>
</body>
</html>
        '''
    
    def start(self):
        """启动GUI服务器"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 创建HTTP服务器
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=None, **kwargs)
            
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(self.server.gui.html_content.encode('utf-8'))
                elif self.path == '/api/logs':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    logs = self.server.gui.logs
                    self.server.gui.logs = []  # 清空已发送的日志
                    self.wfile.write(json.dumps({'logs': logs}).encode('utf-8'))
                else:
                    self.send_error(404)
            
            def do_POST(self):
                if self.path == '/api/start':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    # 这里可以添加启动爬虫的逻辑
                    self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
                elif self.path == '/api/stop':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    # 这里可以添加停止爬虫的逻辑
                    self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
                elif self.path == '/api/navigate/login':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    # 这里可以添加导航到登录页的逻辑
                    self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
                elif self.path == '/api/exit':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
                    # 退出程序
                    import threading
                    threading.Thread(target=lambda: os._exit(0), daemon=True).start()
                else:
                    self.send_error(404)
        
        # 创建服务器实例
        self.server = socketserver.TCPServer(('', self.port), Handler)
        self.server.gui = self
        
        # 启动服务器线程
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        
        # 打开浏览器
        url = f'http://localhost:{self.port}'
        webbrowser.open(url)
        
        print(f"GUI服务器已启动，访问地址: {url}")
        return url
    
    def stop(self):
        """停止GUI服务器"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.server:
            self.server.shutdown()
        if self.server_thread:
            self.server_thread.join(timeout=1)
        
        print("GUI服务器已停止")
    
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

# 测试代码
if __name__ == "__main__":
    gui = GUIServer()
    gui.start()
    
    # 测试添加日志
    gui.add_log("GUI服务器启动成功", "green")
    gui.add_log("等待用户操作...", "info")
    
    # 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        gui.stop()
