import csv
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone, timedelta

import requests
from colorama import Fore, init
from dotenv import load_dotenv

init(autoreset=True)
WAT_TZ = timezone(timedelta(hours=1))


class Storage:
    def __init__(self):
        self._load_env_file()

        self.data_dir = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(Fore.GREEN + f"创建数据存储目录: {self.data_dir}")

        self.write_lock = threading.Lock()
        self.session = requests.Session()
        self.conn = None
        self.pymysql = None
        self._last_account_info_api = None
        self._current_csv_file_path = ''
        self._current_csv_headers = []
        self._last_pushed_csv_file_path = ''
        self.storage_mode = 'api'
        self._load_api_config()
        if self.api_enabled:
            if self.push_save_failed:
                print(Fore.GREEN + f"接口推送模式已启用: {self.push_api_url}（失败会落地到 {self.push_failed_file}）")
            else:
                print(Fore.GREEN + f"接口推送模式已启用: {self.push_api_url}（失败不落本地）")
        else:
            print(Fore.RED + "❌ 未配置 PUSH_API_URL：无法推送，请检查 .env")

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
            else:
                print(Fore.YELLOW + f"未找到环境配置文件: {env_file}")
        except Exception as e:
            print(Fore.RED + f"加载环境配置文件失败: {str(e)}")

    def _parse_bool(self, value, default=False):
        if value is None:
            return default
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    def _safe_identifier(self, value, default_value):
        candidate = (value or default_value or '').strip()
        if not candidate:
            candidate = default_value
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', candidate):
            return default_value
        return candidate

    def _to_text(self, value):
        if value is None:
            return ''
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _pick_first(self, data_item, keys):
        for key in keys:
            value = data_item.get(key)
            if value is not None and value != '':
                return value
        return ''

    def _format_timestamp_to_wat(self, value):
        """将秒/毫秒时间戳格式化为西非时间字符串（UTC+1）。"""
        if not (isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit())):
            return self._to_text(value)

        timestamp = int(value)
        if timestamp > 10000000000:
            timestamp = timestamp / 1000
        dt = datetime.fromtimestamp(timestamp, WAT_TZ)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _extract_order_date(self, value):
        """从订单创建时间提取YYYY-MM-DD。"""
        today = datetime.now(WAT_TZ).strftime('%Y-%m-%d')
        if value is None or value == '':
            return today

        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            try:
                timestamp = int(value)
                if timestamp > 10000000000:
                    timestamp = timestamp / 1000
                return datetime.fromtimestamp(timestamp, WAT_TZ).strftime('%Y-%m-%d')
            except Exception:
                return today

        text_value = self._to_text(value).strip()
        match = re.match(r'^(\d{4}-\d{2}-\d{2})', text_value)
        if match:
            return match.group(1)
        return today

    def resolve_account_info(self, auth_info=None):
        auth_info = auth_info or {}

        merchant_id = self._to_text(auth_info.get('merchantid') or auth_info.get('merchantId')).strip()
        device_id = self._to_text(auth_info.get('deviceId') or auth_info.get('pp_device_id')).strip()
        account_name = (os.getenv('ACCOUNT_NAME') or '').strip()

        if merchant_id:
            account_id = merchant_id
        elif account_name:
            account_id = account_name
        elif device_id:
            account_id = f"device_{device_id[:12]}"
        else:
            account_id = 'unknown_account'

        token = self._to_text(auth_info.get('token') or auth_info.get('pp_token')).strip()
        token_preview = token[:12] if token else ''

        return {
            'account_id': account_id,
            'account_name': account_name,
            'merchant_id': merchant_id,
            'device_id': device_id,
            'token_preview': token_preview,
        }

    def get_sink_label(self):
        return 'CSV' if self.storage_mode == 'api' else '数据库'

    # -------------------- API mode --------------------
    def _load_api_config(self):
        self.push_api_url = (os.getenv('PUSH_API_URL') or '').strip()
        self.push_api_method = (os.getenv('PUSH_API_METHOD') or 'POST').strip().upper()
        if self.push_api_method not in ('POST', 'PUT'):
            self.push_api_method = 'POST'

        try:
            self.push_api_timeout = float((os.getenv('PUSH_API_TIMEOUT') or '15').strip())
        except ValueError:
            self.push_api_timeout = 15.0

        try:
            self.push_api_batch_size = int((os.getenv('PUSH_API_BATCH_SIZE') or '1000').strip())
        except ValueError:
            self.push_api_batch_size = 1000
        self.push_api_batch_size = max(1, self.push_api_batch_size)
        self.push_channel = (os.getenv('PUSH_CHANNEL') or '').strip()

        self.push_verify_ssl = self._parse_bool(os.getenv('PUSH_VERIFY_SSL'), True)
        self.push_api_auth_token = (os.getenv('PUSH_API_AUTH_TOKEN') or '').strip()
        self.push_save_failed = self._parse_bool(os.getenv('PUSH_SAVE_FAILED'), False)

        headers_raw = (os.getenv('PUSH_API_HEADERS_JSON') or '').strip()
        self.push_api_headers = {}
        if headers_raw:
            try:
                parsed_headers = json.loads(headers_raw)
                if isinstance(parsed_headers, dict):
                    self.push_api_headers = {str(k): str(v) for k, v in parsed_headers.items()}
            except Exception:
                print(Fore.YELLOW + 'PUSH_API_HEADERS_JSON 解析失败，已忽略自定义请求头')

        failed_file = (os.getenv('PUSH_FAILED_FILE') or 'data/push_failed.jsonl').strip()
        if os.path.isabs(failed_file):
            self.push_failed_file = failed_file
        else:
            self.push_failed_file = os.path.join(os.getcwd(), failed_file)

        if self.push_save_failed:
            failed_dir = os.path.dirname(self.push_failed_file)
            if failed_dir and not os.path.exists(failed_dir):
                os.makedirs(failed_dir, exist_ok=True)

        self.api_enabled = bool(self.push_api_url)

    def _build_api_headers(self):
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'palmpay-fetch/1.0',
        }
        headers.update(self.push_api_headers)
        if self.push_api_auth_token and 'Authorization' not in headers:
            headers['Authorization'] = f"Bearer {self.push_api_auth_token}"
        return headers

    def _parse_datetime_for_api(self, value):
        if value is None or value == '':
            return ''

        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            return self._format_timestamp_to_wat(value)

        text = self._to_text(value).strip()
        if not text:
            return ''
        text = text.replace('T', ' ')
        datetime_match = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', text)
        if datetime_match:
            return f"{datetime_match.group(1)} {datetime_match.group(2)}"
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            return f"{text} 00:00:00"
        return text

    def _parse_json_for_api(self, value):
        if value is None or value == '':
            return []
        if isinstance(value, (dict, list)):
            return value
        text = self._to_text(value).strip()
        if not text:
            return []
        try:
            return json.loads(text)
        except Exception:
            return [text]

    def _build_order_payload_for_api(self, order, account_info):
        row = dict(order)
        merchant_channel = self._to_text(row.get('Order Information_Merchant ID')).strip()
        channel_value = merchant_channel or self.push_channel or account_info.get('account_id') or 'palmpay'

        # 按约定：order_create_time 仅使用文件字段 Order Information_Create Time
        create_time_raw = self._to_text(row.get('Order Information_Create Time')).strip()
        settlement_time_raw = self._to_text(row.get('Settlement Information_Settlement Time')).strip()
        update_time_raw = self._to_text(row.get('Order Information_Update Time')).strip()

        order_order_no = self._to_text(row.get('Order Information_Order No')).strip()
        order_no = self._to_text(self._pick_first(row, ['order_no', 'Order Information_Order No'])).strip()
        if not order_order_no:
            order_order_no = order_no

        other_user_mobile_no = self._to_text(
            self._pick_first(row, ['Other Information_User Mobile No', 'user_mobile_no'])
        ).strip()
        user_mobile_no = self._to_text(self._pick_first(row, ['user_mobile_no'])).strip()
        if not other_user_mobile_no:
            other_user_mobile_no = user_mobile_no

        order_status = self._to_text(
            self._pick_first(row, ['Order Information_Status', 'order_status', 'Status'])
        ).strip()

        mapped = {
            'order_order_no': order_order_no,
            'other_user_mobile_no': other_user_mobile_no,
            'order_status': order_status,
            'order_create_time': self._parse_datetime_for_api(create_time_raw),
            'order_merchant_order_no': self._to_text(
                self._pick_first(row, ['Order Information_Merchant Order No', 'out_order_no', 'merchant_order_no'])
            ).strip(),
            'order_merchant_id': self._to_text(
                self._pick_first(row, ['Order Information_Merchant ID', 'merchant_id', 'merchantId'])
            ).strip(),
            'order_order_type': self._to_text(
                self._pick_first(row, ['Order Information_Order Type', 'order_type', 'Order Type'])
            ).strip(),
            'order_order_amount': self._to_text(
                self._pick_first(row, ['Order Information_Order Amount', 'order_amount', 'Order Amount'])
            ).strip(),
            'order_order_currency': self._to_text(
                self._pick_first(row, ['Order Information_Order Currency', 'order_currency', 'Order Currency'])
            ).strip(),
            'order_net_amount': self._to_text(
                self._pick_first(row, ['Order Information_Net Amount', 'net_amount', 'Net Amount'])
            ).strip(),
            'order_product': self._to_text(
                self._pick_first(row, ['Order Information_Product', 'product', 'Product'])
            ).strip(),
            'order_pay_id': self._to_text(
                self._pick_first(row, ['Order Information_Pay ID', 'pay_id', 'Pay ID'])
            ).strip(),
            'order_update_time': self._parse_datetime_for_api(update_time_raw),
            'payer_payer_bank_name': self._to_text(
                self._pick_first(row, ['Payer Information_Payer Bank Name'])
            ).strip(),
            'payer_payer_account_number': self._to_text(
                self._pick_first(row, ['Payer Information_Payer Account Number'])
            ).strip(),
            'payee_payee_bank_name': self._to_text(
                self._pick_first(row, ['Payee Information_Payee Bank Name'])
            ).strip(),
            'payee_payee_account_name': self._to_text(
                self._pick_first(row, ['Payee Information_Payee Account Name'])
            ).strip(),
            'paytool_payment_method': self._to_text(
                self._pick_first(row, ['Payment Tool Information_Payment Method'])
            ).strip(),
            'settle_settlement_time': self._parse_datetime_for_api(settlement_time_raw),
            'settle_settlement_status': self._to_text(
                self._pick_first(row, ['Settlement Information_Settlement Status', 'settlement_status', 'Settlement Status'])
            ).strip(),
            'settle_settlement_batch_no': self._to_text(
                self._pick_first(row, ['Settlement Information_Settlement Batch No'])
            ).strip(),
            'settle_settlement_amount': self._to_text(
                self._pick_first(row, ['Settlement Information_Settlement Amount', 'settlement_amount'])
            ).strip(),
            'settle_settlement_fee': self._to_text(
                self._pick_first(row, ['Settlement Information_Settlement Fee', 'settlement_fee'])
            ).strip(),
            'user_mobile_no': user_mobile_no,
            'refund_refund_status': self._to_text(
                self._pick_first(row, ['Refund Information_Refund Status'])
            ).strip(),
            'refund_refund_items': self._parse_json_for_api(
                self._pick_first(row, ['Refund Information_Refund Items'])
            ),
            'order_no': order_no,
            'other_title': self._to_text(self._pick_first(row, ['Other Information_Title'])).strip(),
            'order_reference': self._to_text(self._pick_first(row, ['Order Information_Reference'])).strip(),
            'other_remark': self._to_text(self._pick_first(row, ['Other Information_Remark'])).strip(),
            'date': self._to_text(row.get('date') or self._extract_order_date(create_time_raw)).strip(),
            'channel': channel_value,
        }

        # 按你的“都必填”要求，缺失字段统一补空字符串；json字段默认空数组
        mapped['order_order_no'] = mapped['order_order_no'] or ''
        mapped['other_user_mobile_no'] = mapped['other_user_mobile_no'] or ''
        mapped['order_status'] = mapped['order_status'] or ''
        mapped['order_create_time'] = mapped['order_create_time'] or ''
        mapped['refund_refund_items'] = mapped['refund_refund_items'] if mapped['refund_refund_items'] is not None else []
        mapped['channel'] = mapped['channel'] or channel_value

        return mapped

    def _new_csv_filename(self):
        timestamp = datetime.now(WAT_TZ).strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_order_details.csv"
        candidate = os.path.join(self.data_dir, filename)
        if not os.path.exists(candidate):
            return candidate

        index = 1
        while True:
            filename = f"{timestamp}_{index:02d}_order_details.csv"
            candidate = os.path.join(self.data_dir, filename)
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def _start_new_csv_session_locked(self):
        self._current_csv_file_path = self._new_csv_filename()
        self._current_csv_headers = []
        self._last_pushed_csv_file_path = ''
        return self._current_csv_file_path

    def start_csv_session(self, auth_info=None, force_new=False):
        with self.write_lock:
            if self.storage_mode != 'api':
                return ''

            account_info = self.resolve_account_info(auth_info)
            self._last_account_info_api = account_info
            if force_new or not self._current_csv_file_path:
                csv_path = self._start_new_csv_session_locked()
                print(Fore.GREEN + f"已创建CSV文件: {csv_path}")
            return self._current_csv_file_path

    def _expand_current_csv_headers_locked(self, extra_headers):
        if not extra_headers:
            return
        if not self._current_csv_file_path or not os.path.exists(self._current_csv_file_path):
            self._current_csv_headers.extend(extra_headers)
            return

        new_headers = self._current_csv_headers + extra_headers
        temp_path = f"{self._current_csv_file_path}.tmp"
        with open(self._current_csv_file_path, 'r', encoding='utf-8-sig', newline='') as src:
            reader = csv.DictReader(src)
            old_rows = list(reader)

        with open(temp_path, 'w', encoding='utf-8-sig', newline='') as dst:
            writer = csv.DictWriter(dst, fieldnames=new_headers)
            writer.writeheader()
            for row in old_rows:
                writer.writerow({h: self._to_text(row.get(h, '')) for h in new_headers})

        os.replace(temp_path, self._current_csv_file_path)
        self._current_csv_headers = new_headers

    def _append_rows_to_current_csv_locked(self, data_list):
        rows = [dict(item) for item in data_list if item]
        if not rows:
            return 0

        if not self._current_csv_file_path:
            self._start_new_csv_session_locked()

        if not self._current_csv_headers:
            self._current_csv_headers = list(rows[0].keys())

        known = set(self._current_csv_headers)
        extra_headers = []
        for row in rows:
            for key in row.keys():
                if key not in known:
                    known.add(key)
                    extra_headers.append(key)

        if extra_headers:
            self._expand_current_csv_headers_locked(extra_headers)

        file_exists = os.path.exists(self._current_csv_file_path)
        needs_header = (not file_exists) or os.path.getsize(self._current_csv_file_path) == 0
        with open(self._current_csv_file_path, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self._current_csv_headers)
            if needs_header:
                writer.writeheader()
            for row in rows:
                writer.writerow({h: self._to_text(row.get(h, '')) for h in self._current_csv_headers})

        return len(rows)

    def _persist_failed_payload(self, payload, error_message):
        print(Fore.RED + f"接口推送失败: {error_message}")
        if not self.push_save_failed:
            return
        record = {
            'failed_at': datetime.now(WAT_TZ).strftime('%Y-%m-%d %H:%M:%S'),
            'error': error_message,
            'target_url': self.push_api_url,
            'payload': payload,
        }
        with open(self.push_failed_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')

    def _send_orders_to_api(self, orders, account_info):
        channel_value = ''
        if orders and isinstance(orders[0], dict):
            channel_value = self._to_text(orders[0].get('channel')).strip()
        if not channel_value:
            channel_value = self.push_channel or account_info.get('account_id') or 'palmpay'
        body = {
            'channel': channel_value,
            'items': orders,
        }

        if not self.api_enabled:
            self._persist_failed_payload(body, 'PUSH_API_URL 未配置')
            return False

        try:
            headers = self._build_api_headers()
            response = self.session.request(
                method=self.push_api_method,
                url=self.push_api_url,
                json=body,
                headers=headers,
                timeout=self.push_api_timeout,
                verify=self.push_verify_ssl,
            )
            preview = (response.text or "")[:800]
            print(Fore.CYAN + f"[Push] -> {self.push_api_url} items={len(orders)} http={response.status_code}")
            print(Fore.CYAN + f"[Push] resp(0~800): {preview}")

            # 1) HTTP 必须 2xx
            if not (200 <= response.status_code < 300):
                raise RuntimeError(f"HTTP {response.status_code}: {preview}")

            # 2) JSON 必须能解析，且 code==0
            try:
                data = response.json()
            except Exception:
                raise RuntimeError(f"Response is not JSON: {preview}")

            code = data.get("code", None)
            if code != 0:
                msg = data.get("message") or data.get("msg") or data.get("error") or ""
                raise RuntimeError(f"API failed: code={code}, message={msg}, resp={preview}")

            return True
        except Exception as e:
            self._persist_failed_payload(body, str(e))
            return False

    def _push_csv_to_api_locked(self, csv_file_path, account_info):
        if not csv_file_path or not os.path.exists(csv_file_path):
            print(Fore.YELLOW + f"CSV文件不存在，跳过推送: {csv_file_path}")
            return False, 0

        with open(csv_file_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader]

        if not rows:
            print(Fore.YELLOW + f"CSV没有可推送数据: {csv_file_path}")
            return True, 0

        prepared_orders = [self._build_order_payload_for_api(row, account_info) for row in rows]
        total_sent = 0
        for i in range(0, len(prepared_orders), self.push_api_batch_size):
            batch = prepared_orders[i:i + self.push_api_batch_size]
            ok = self._send_orders_to_api(batch, account_info)
            if not ok:
                return False, total_sent
            total_sent += len(batch)

        self._last_pushed_csv_file_path = csv_file_path
        return True, total_sent

    def flush_pending(self, auth_info=None):
        with self.write_lock:
            if self.storage_mode != 'api':
                return True

            if not self._current_csv_file_path:
                return True

            if self._last_pushed_csv_file_path == self._current_csv_file_path:
                return True

            account_info = self.resolve_account_info(auth_info) if auth_info else (
                self._last_account_info_api or {'account_id': self.push_channel or 'palmpay'}
            )
            ok, sent = self._push_csv_to_api_locked(self._current_csv_file_path, account_info)
            if ok and sent > 0:
                print(Fore.GREEN + f"CSV推送完成: file={self._current_csv_file_path} count={sent}")
            return ok

    # -------------------- MySQL mode --------------------
    def _load_mysql_config(self):
        self.mysql_host = (os.getenv('MYSQL_HOST') or '127.0.0.1').strip()
        try:
            self.mysql_port = int((os.getenv('MYSQL_PORT') or '3306').strip())
        except ValueError:
            self.mysql_port = 3306
        self.mysql_user = (os.getenv('MYSQL_USER') or 'root').strip()
        self.mysql_password = os.getenv('MYSQL_PASSWORD') or ''
        self.mysql_database = self._safe_identifier(os.getenv('MYSQL_DATABASE'), 'palmpay_fetch')
        self.mysql_charset = (os.getenv('MYSQL_CHARSET') or 'utf8mb4').strip()
        if not re.fullmatch(r'[A-Za-z0-9_]+', self.mysql_charset):
            self.mysql_charset = 'utf8mb4'
        self.accounts_table = self._safe_identifier(os.getenv('MYSQL_ACCOUNTS_TABLE'), 'accounts')
        self.orders_table = self._safe_identifier(os.getenv('MYSQL_ORDERS_TABLE'), 'orders')

    def _load_mysql_driver(self):
        try:
            import pymysql
            return pymysql
        except ImportError as e:
            raise RuntimeError('缺少 MySQL 依赖，请执行: pip install PyMySQL') from e

    def _connect_and_init_db(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass

        server_conn = self.pymysql.connect(
            host=self.mysql_host,
            port=self.mysql_port,
            user=self.mysql_user,
            password=self.mysql_password,
            charset=self.mysql_charset,
            autocommit=True,
        )
        try:
            with server_conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.mysql_database}` "
                    f"DEFAULT CHARACTER SET {self.mysql_charset}"
                )
        finally:
            server_conn.close()

        self.conn = self.pymysql.connect(
            host=self.mysql_host,
            port=self.mysql_port,
            user=self.mysql_user,
            password=self.mysql_password,
            database=self.mysql_database,
            charset=self.mysql_charset,
            autocommit=False,
        )

        self._init_db()

    def _ensure_mysql_connection(self):
        if self.conn is None:
            self._connect_and_init_db()
            return
        try:
            self.conn.ping(reconnect=True)
        except Exception:
            self._connect_and_init_db()

    def _init_db(self):
        self._ensure_mysql_connection()

        create_accounts_sql = f'''
            CREATE TABLE IF NOT EXISTS `{self.accounts_table}` (
                account_id VARCHAR(128) NOT NULL,
                account_name VARCHAR(255) NULL,
                merchant_id VARCHAR(128) NULL,
                device_id VARCHAR(128) NULL,
                token_preview VARCHAR(64) NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id)
            ) ENGINE=InnoDB DEFAULT CHARSET={self.mysql_charset}
        '''

        create_orders_sql = f'''
            CREATE TABLE IF NOT EXISTS `{self.orders_table}` (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                account_id VARCHAR(128) NOT NULL,
                order_no VARCHAR(128) NOT NULL,
                order_type VARCHAR(64) NULL,
                order_status VARCHAR(64) NULL,
                order_amount VARCHAR(128) NULL,
                create_time VARCHAR(32) NULL,
                settlement_time VARCHAR(32) NULL,
                payload_json LONGTEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `date` DATE NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uniq_account_order (account_id, order_no),
                KEY idx_orders_account_id (account_id),
                KEY idx_orders_created_at (created_at),
                KEY idx_orders_date (`date`),
                CONSTRAINT fk_orders_account
                    FOREIGN KEY (account_id) REFERENCES `{self.accounts_table}` (account_id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET={self.mysql_charset}
        '''

        with self.conn.cursor() as cur:
            cur.execute(create_accounts_sql)
            cur.execute(create_orders_sql)
        self._migrate_orders_table()
        self.conn.commit()

    def _migrate_orders_table(self):
        with self.conn.cursor() as cur:
            cur.execute(
                '''
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                ''',
                (self.mysql_database, self.orders_table),
            )
            columns = {row[0] for row in cur.fetchall()}

            if 'crawled_at' in columns and 'created_at' not in columns:
                cur.execute(
                    f'''
                    ALTER TABLE `{self.orders_table}`
                    CHANGE COLUMN `crawled_at` `created_at`
                    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    '''
                )
                columns.remove('crawled_at')
                columns.add('created_at')

            if 'created_at' not in columns:
                cur.execute(
                    f'''
                    ALTER TABLE `{self.orders_table}`
                    ADD COLUMN `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    '''
                )
                columns.add('created_at')

            if 'date' not in columns:
                cur.execute(
                    f'''
                    ALTER TABLE `{self.orders_table}`
                    ADD COLUMN `date` DATE NULL
                    '''
                )
                columns.add('date')

            cur.execute(
                '''
                SELECT INDEX_NAME
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                ''',
                (self.mysql_database, self.orders_table),
            )
            indexes = {row[0] for row in cur.fetchall()}

            if 'idx_orders_created_at' not in indexes:
                cur.execute(
                    f'''
                    ALTER TABLE `{self.orders_table}`
                    ADD INDEX idx_orders_created_at (created_at)
                    '''
                )

            if 'idx_orders_date' not in indexes:
                cur.execute(
                    f'''
                    ALTER TABLE `{self.orders_table}`
                    ADD INDEX idx_orders_date (`date`)
                    '''
                )

            if 'idx_orders_crawled_at' in indexes and 'created_at' in columns:
                cur.execute(
                    f'''
                    ALTER TABLE `{self.orders_table}`
                    DROP INDEX idx_orders_crawled_at
                    '''
                )

    def _upsert_account(self, account_info):
        sql = f'''
            INSERT INTO `{self.accounts_table}`
                (account_id, account_name, merchant_id, device_id, token_preview)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                account_name=VALUES(account_name),
                merchant_id=VALUES(merchant_id),
                device_id=VALUES(device_id),
                token_preview=VALUES(token_preview),
                updated_at=CURRENT_TIMESTAMP
        '''

        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    account_info['account_id'],
                    account_info['account_name'],
                    account_info['merchant_id'],
                    account_info['device_id'],
                    account_info['token_preview'],
                ),
            )

    def _upsert_order(self, account_id, data_item):
        order_no = self._to_text(
            self._pick_first(
                data_item,
                ['order_no', 'Order No', 'Order Information_Order No', 'Merchant Order No'],
            )
        ).strip()

        if not order_no:
            order_no = f"unknown_{int(datetime.now().timestamp() * 1000)}_{threading.get_ident()}"

        order_type = self._to_text(
            self._pick_first(data_item, ['order_type', 'Order Type', 'Order Information_Order Type'])
        )
        order_status = self._to_text(
            self._pick_first(data_item, ['order_status', 'Status', 'Order Information_Status'])
        )
        order_amount = self._to_text(
            self._pick_first(data_item, ['order_amount', 'Order Amount', 'Order Information_Order Amount'])
        )

        create_time_raw = self._pick_first(data_item, ['create_time', 'Create Time', 'Order Information_Create Time'])
        settlement_time_raw = self._pick_first(
            data_item,
            ['settlement_time', 'Settlement Time', 'Settlement Information_Settlement Time'],
        )

        create_time = self._format_timestamp_to_wat(create_time_raw) if create_time_raw != '' else ''
        settlement_time = self._format_timestamp_to_wat(settlement_time_raw) if settlement_time_raw != '' else ''
        order_date = self._extract_order_date(create_time_raw if create_time_raw != '' else create_time)

        payload_json = json.dumps(data_item, ensure_ascii=False, default=str)

        sql = f'''
            INSERT INTO `{self.orders_table}` (
                account_id,
                order_no,
                order_type,
                order_status,
                order_amount,
                create_time,
                settlement_time,
                payload_json,
                created_at,
                `date`,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                order_type=VALUES(order_type),
                order_status=VALUES(order_status),
                order_amount=VALUES(order_amount),
                create_time=VALUES(create_time),
                settlement_time=VALUES(settlement_time),
                payload_json=VALUES(payload_json),
                created_at=CURRENT_TIMESTAMP,
                `date`=VALUES(`date`),
                updated_at=CURRENT_TIMESTAMP
        '''

        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    account_id,
                    order_no,
                    order_type,
                    order_status,
                    order_amount,
                    create_time,
                    settlement_time,
                    payload_json,
                    order_date,
                ),
            )

        return order_no

    # -------------------- unified write API --------------------
    def append_single_to_db(self, data_item, auth_info=None):
        """实时写入单条订单到CSV或数据库"""
        if not data_item:
            print(Fore.RED + '没有数据需要写入')
            return False

        with self.write_lock:
            account_info = self.resolve_account_info(auth_info)

            if self.storage_mode == 'api':
                self._last_account_info_api = account_info
                written = self._append_rows_to_current_csv_locked([data_item])

                # ✅ 新增：攒够 batch 就推一次（不等爬完）
                self._api_rows_since_last_flush = getattr(self, "_api_rows_since_last_flush", 0) + 1
                if self._api_rows_since_last_flush >= self.push_api_batch_size:
                    self._api_rows_since_last_flush = 0
                    self.flush_pending(auth_info=auth_info)

                return written == 1

            try:
                self._ensure_mysql_connection()
                self._upsert_account(account_info)
                order_no = self._upsert_order(account_info['account_id'], data_item)
                self.conn.commit()
                print(
                    Fore.GREEN
                    + f"订单已写入数据库: account={account_info['account_id']} order_no={order_no}"
                )
                return True
            except Exception as e:
                if self.conn:
                    self.conn.rollback()
                print(Fore.RED + f"写入数据库失败: {str(e)}")
                return True

    def save_to_db(self, data_list, auth_info=None):
        """批量写入订单到CSV或数据库"""
        if not data_list:
            print(Fore.RED + '没有数据需要写入')
            return False

        with self.write_lock:
            account_info = self.resolve_account_info(auth_info)

            if self.storage_mode == 'api':
                self._last_account_info_api = account_info
                csv_path = self._start_new_csv_session_locked()
                saved_count = self._append_rows_to_current_csv_locked(data_list)
                if saved_count <= 0:
                    return False
                ok, sent = self._push_csv_to_api_locked(csv_path, account_info)
                if ok:
                    print(Fore.GREEN + f"批量写入CSV并推送完成: file={csv_path} count={sent}")
                return ok

            try:
                self._ensure_mysql_connection()
                self._upsert_account(account_info)

                saved_count = 0
                for item in data_list:
                    if not item:
                        continue
                    self._upsert_order(account_info['account_id'], item)
                    saved_count += 1

                self.conn.commit()
                print(
                    Fore.GREEN
                    + (
                        f"批量写入数据库完成: account={account_info['account_id']} "
                        f"count={saved_count} db={self.get_database_path()}"
                    )
                )
                return True
            except Exception as e:
                if self.conn:
                    self.conn.rollback()
                print(Fore.RED + f"批量写入数据库失败: {str(e)}")
                return False

    # 兼容旧调用：统一切到当前存储模式
    def append_single_to_csv(self, data_item, auth_info=None):
        return self.append_single_to_db(data_item, auth_info=auth_info)

    def save_to_csv(self, data_list, auth_info=None):
        return self.save_to_db(data_list, auth_info=auth_info)

    def append_to_csv(self, data_list, auth_info=None):
        return self.save_to_db(data_list, auth_info=auth_info)

    def save_to_excel(self, data_list, auth_info=None):
        return self.save_to_db(data_list, auth_info=auth_info)

    def append_to_excel(self, data_list, auth_info=None):
        return self.save_to_db(data_list, auth_info=auth_info)

    def get_data_dir(self):
        return self.data_dir

    def get_database_path(self):
        if self.storage_mode == 'api':
            return self.push_api_url or 'PUSH_API_URL_NOT_SET'

        masked_pwd = '***' if self.mysql_password else ''
        auth_part = self.mysql_user
        if masked_pwd:
            auth_part = f"{self.mysql_user}:{masked_pwd}"
        return f"mysql://{auth_part}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    def close(self):
        try:
            self.flush_pending()
        except Exception:
            pass

        try:
            self.session.close()
        except Exception:
            pass

        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
