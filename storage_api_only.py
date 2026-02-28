# storage_api_only.py
import os
import json
import time
import requests
from colorama import Fore

class StorageApiOnly:
    """
    只支持 API 推送：
    - append()：追加一条，达到 batch_size 立刻推
    - flush()：把 pending 全部推完（分批）
    - 推送失败写 data/push_failed.jsonl
    """

    def __init__(self, gui_server=None):
        self.gui_server = gui_server

        self.push_api_url = os.getenv("PUSH_API_URL", "").strip()
        self.timeout = int(os.getenv("PUSH_API_TIMEOUT", "30"))
        self.batch_size = int(os.getenv("PUSH_API_BATCH_SIZE", "1000"))
        self.retry = int(os.getenv("PUSH_API_RETRY", "5"))
        self.backoff = float(os.getenv("PUSH_API_RETRY_BACKOFF", "1.5"))
        self.save_failed = os.getenv("PUSH_SAVE_FAILED", "true").lower() == "true"

        # 是否“爬到就推”（建议 true）
        self.push_on_append = os.getenv("PUSH_ON_APPEND", "true").lower() == "true"

        if not self.push_api_url:
            raise RuntimeError("PUSH_API_URL 未配置，无法推送")

        self.pending = []

        os.makedirs("data", exist_ok=True)
        self.failed_file = os.path.join("data", "push_failed.jsonl")

        print(Fore.GREEN + f"[Storage] API-only 模式启用：{self.push_api_url}")

    def append_single_to_db(self, order: dict, auth_info=None):
        # 兼容你原项目调用：api_crawler.py 里就是 append_single_to_db(order)
        if not order:
            return

        # ✅ 这里你可以补充字段映射/清洗（可选）
        # order = self._normalize(order, auth_info)

        self.pending.append(order)

        if self.push_on_append and len(self.pending) >= self.batch_size:
            self.flush_pending(reason="batch_full")

    def flush_pending(self, reason="manual"):
        if not self.pending:
            print(Fore.CYAN + f"[Push] flush_pending({reason}): pending=0 skip")
            return

        total = len(self.pending)
        print(Fore.CYAN + f"[Push] flush_pending({reason}): pending={total} start...")

        while self.pending:
            chunk = self.pending[:self.batch_size]
            self.pending = self.pending[self.batch_size:]
            ok = self._send_orders_to_api(chunk)
            # 如果你想“失败就阻塞不往下推”，把下面注释取消即可：
            # if not ok:
            #     self.pending = chunk + self.pending
            #     break

    def _send_orders_to_api(self, items: list) -> bool:
        # 你 Laravel 接口需要 {"channel": "...", "items":[...]}
        # 如果每条里都有 channel，取第一条；否则你也可以用 env 固定 channel
        channel = items[0].get("channel", "") if isinstance(items[0], dict) else ""
        payload = {"channel": channel, "items": items}

        for attempt in range(1, self.retry + 1):
            try:
                t0 = time.time()
                resp = requests.post(self.push_api_url, json=payload, timeout=self.timeout)
                cost_ms = int((time.time() - t0) * 1000)

                body = (resp.text or "")
                preview = body[:500]

                # ✅ 不管成功失败，都打印
                print(Fore.YELLOW + f"[Push] {len(items)} -> {self.push_api_url} "
                      f"status={resp.status_code} cost={cost_ms}ms attempt={attempt}")
                print(Fore.YELLOW + f"[Push] resp_body(0~500): {preview}")

                if 200 <= resp.status_code < 300:
                    return True

                time.sleep(self.backoff ** attempt)

            except Exception as e:
                print(Fore.RED + f"[Push] Exception attempt={attempt}: {e}")
                time.sleep(self.backoff ** attempt)

        # ✅ 最终失败：落盘，保证“爬到的数据不会无声消失”
        if self.save_failed:
            with open(self.failed_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": int(time.time()),
                    "url": self.push_api_url,
                    "count": len(items),
                    "payload": payload
                }, ensure_ascii=False) + "\n")
            print(Fore.RED + f"[Push] FAILED saved -> {self.failed_file}")

        return False