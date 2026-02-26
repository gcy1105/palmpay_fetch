# Palmpay商户后台爬虫

## 功能介绍
- 🎯 自动登录Palmpay商户后台并获取认证信息
- 🔍 通过API方式高效获取订单列表和详情
- ⚡ 支持批量爬取和自动翻页遍历
- 💾 默认将数据打包推送到外部接口（可选切换 MySQL）
- 🖥️ 全新Qt GUI界面，操作更加直观
- 🛡️ 完善的错误处理和日志记录
- 🔄 自动检测和处理token过期问题
- ⏱️ 可配置的请求延迟和重试机制
- 📊 实时显示爬取进度和统计信息

## 技术特点
- 使用Playwright浏览器自动化完成登录和认证
- 通过API接口获取数据，速度快且稳定
- 自动处理API签名生成，支持HMAC-SHA1加密
- 智能识别和处理"server busy"等错误
- 线程安全的浏览器操作和数据处理
- 单例模式设计，避免重复启动爬虫
- 自动安装Playwright浏览器驱动

## 安装依赖
```bash
# 安装Python 3.8+
# 安装项目依赖
pip install -r requirements.txt

# 安装Playwright浏览器驱动（首次运行会自动安装）
python -m playwright install chromium
```

## 配置说明
1. 编辑 `.env` 文件，设置相关配置
2. 主要配置项：
  - `ORDER_DETAIL_API`: 订单详情API接口
  - `REQUEST_DELAY`: 请求延迟（秒），默认0.1
  - `MAX_RETRIES`: 最大重试次数
  - `STORAGE_MODE`: 存储模式（`api` 或 `mysql`，默认 `api`）
  - `PUSH_API_URL`: 接口地址（`STORAGE_MODE=api` 必填）
  - `PUSH_API_METHOD`: 推送方法（默认 `POST`）
  - `PUSH_API_AUTH_TOKEN`: Bearer Token（可选）
  - `PUSH_API_HEADERS_JSON`: 额外请求头（JSON字符串，可选）
  - `MYSQL_HOST`: MySQL主机（`STORAGE_MODE=mysql` 时生效）
  - `MYSQL_PORT`: MySQL端口（默认 `3306`）
  - `MYSQL_USER`: MySQL用户名
  - `MYSQL_PASSWORD`: MySQL密码
  - `MYSQL_DATABASE`: MySQL库名（默认 `palmpay_fetch`）
  - `MYSQL_ACCOUNTS_TABLE`: 账号表名（默认 `accounts`）
  - `MYSQL_ORDERS_TABLE`: 订单表名（默认 `orders`）
  - `ACCOUNT_NAME`: 账号别名（可选，merchantId 缺失时用于区分账号）

## 运行方式
```bash
# 直接运行主脚本
python main.py

# 或使用python3
python3 main.py
```

## 详细操作流程

### 1. 启动程序
- 运行 `python main.py` 启动应用
- 首次运行时，程序会自动检查并安装Playwright浏览器驱动
- 等待安装完成后，Qt GUI界面会自动显示

### 2. 浏览器登录
- 在Qt GUI界面中，点击"启动浏览器"按钮
- 浏览器会自动打开并导航到Palmpay商户后台登录页面
- 在浏览器中手动完成登录（输入账号密码和邮件验证码）
- 登录成功后，浏览器会跳转到订单列表页面
- 程序会自动从浏览器中获取认证信息（token、签名密钥等）

### 3. 开始爬取
- 在Qt GUI界面中，设置爬取参数（可选）
- 点击"启动爬虫"按钮开始爬取数据
- 爬虫会自动：
  1. 获取订单列表数据
  2. 遍历每个订单并获取详情
  3. 将数据实时打包推送到接口（或按配置写入MySQL）
  4. 实时显示爬取进度

### 4. 停止爬取
- 爬取过程中，点击"停止爬虫"按钮可以停止爬取
- 程序会保存已爬取的数据，然后停止

### 5. 查看结果
- 爬取完成后，数据会实时推送到 `PUSH_API_URL`
- 推送失败的数据会写入 `data/push_failed.jsonl`
- 订单会按 `account_id` 区分账号（优先使用 `merchantId/merchantid`）

## 界面操作说明

### Qt GUI界面功能
- **启动浏览器**: 打开浏览器并导航到登录页面
- **启动爬虫**: 开始爬取订单数据
- **停止爬虫**: 停止正在运行的爬虫
- **日志显示**: 实时显示爬取过程和状态信息
- **状态指示**: 显示当前爬虫状态和进度

### 日志格式说明
- `已处理 30 / 5000个订单，正在写入第 30 条到接口`
- 实时显示当前处理进度和总数

## 注意事项
- 请确保网络连接正常，首次运行需要下载浏览器驱动（约300MB）
- 登录过程中需要手动输入邮件验证码
- 爬虫运行过程中不要关闭浏览器窗口
- 数据量较大时，爬取过程可能需要较长时间
- 所有操作都会记录到日志文件
- 使用API方式爬取，速度比页面点击方式快很多
- 自动处理token过期问题，无需手动重新登录

## 数据字段说明
爬虫会自动提取API返回的所有字段，包括但不限于：

**订单信息:**
- Status: 订单状态
- Create Time: 创建时间
- Order No: 订单号
- Merchant Order No: 商户订单号
- Merchant ID: 商户ID
- Order Type: 订单类型
- Order Amount: 订单金额
- Order Currency: 订单货币
- Net Amount: 净金额
- Product: 产品
- Pay ID: 支付ID
- Update Time: 更新时间

**付款人信息:**
- Payer Bank Name: 付款人银行名称
- Payer Account Number: 付款人账号

**收款人信息:**
- Payee Bank Name: 收款人银行名称
- Payee Account Name: 收款人账户名称

**支付工具信息:**
- Payment Method: 支付方式

**结算信息:**
- Settlement Time: 结算时间
- Settlement Status: 结算状态
- Settlement Batch No: 结算批次号
- Settlement Amount: 结算金额
- Settlement Fee: 结算手续费

**其他信息:**
- User Mobile No: 用户手机号

**退款信息:**
- (根据实际API返回动态添加)

## 常见问题

### Q: 首次运行时显示"正在安装Playwright浏览器驱动"
**A**: 这是正常现象，首次运行需要安装浏览器驱动，约300MB，安装完成后会自动启动应用

### Q: 登录成功后，爬虫无法获取数据
**A**: 可能是token获取失败，请检查浏览器是否正常登录到订单列表页面

### Q: 爬取过程中出现"server busy"错误
**A**: 这是API限流导致的，程序会自动重试，无需手动干预

### Q: 点击"停止爬虫"按钮没有反应
**A**: 请等待当前操作完成后，爬虫会自动停止

### Q: 接口推送失败怎么办？
**A**: 检查 `PUSH_API_URL`、鉴权头和网络；失败请求会自动写到 `data/push_failed.jsonl`

## 技术支持
如遇到其他问题，请联系开发者提供技术支持。
