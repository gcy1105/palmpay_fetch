import hashlib
import hmac
import base64
import json
import time

def generate_sign(pp_token, pp_device_id, pp_device_type, pp_client_ver, appsource, countrycode, post_data, method='POST'):
    """
    生成PP_REQ_SIGN签名
    
    Args:
        pp_token: PP_TOKEN值
        pp_device_id: PP_DEVICE_ID值
        pp_device_type: PP_DEVICE_TYPE值
        pp_client_ver: PP_CLIENT_VER值
        appsource: APPSOURCE值
        countrycode: COUNTRYCODE值
        post_data: POST数据字典或GET参数字典
        method: 请求方法（POST或GET）
        
    Returns:
        tuple: (签名, 时间戳)
    """
    # 1. 获取时间戳（如果post_data中包含timestamp，则使用它）
    if 'timestamp' in post_data:
        timestamp = str(post_data['timestamp'])
    else:
        timestamp = str(int(time.time() * 1000))
    
    # 2. 准备参数
    params = {
        "PP_CLIENT_VER": pp_client_ver,
        "PP_DEVICE_ID": pp_device_id,
        "PP_DEVICE_TYPE": pp_device_type,
        "PP_TIMESTAMP": timestamp,
        "PP_TOKEN": pp_token,
        "appSource": int(appsource),  # 数字类型
        "countryCode": countrycode.upper(),  # 大写
    }
    
    # 根据请求方法处理参数
    if method == 'POST':
        params["param"] = json.dumps(post_data)  # JSON字符串
    elif method == 'GET':
        # 对于GET请求，使用空字符串作为param
        # 分析JS代码发现，GET请求不包含URL参数进行签名
        params["param"] = ""
    
    # 2. 排序参数
    sorted_keys = sorted(params.keys())
    
    # 3. 拼接消息
    message = ""
    for key in sorted_keys:
        if params[key] is not None:
            message += key + str(params[key])
    
    # 4. 计算MD5哈希作为密钥
    md5_hash = hashlib.md5(timestamp.encode("utf-8")).hexdigest()
    
    # 5. 计算HMAC-SHA1签名
    hmac_key = md5_hash.encode("utf-8")
    hmac_message = message.encode("utf-8")
    hmac_obj = hmac.new(hmac_key, hmac_message, hashlib.sha1)
    signature = base64.b64encode(hmac_obj.digest()).decode("utf-8")
    
    return signature, timestamp

def generate_signature_headers(token, device_id, country_code, params, method='POST', merchantid=None):
    """
    生成包含签名的请求头
    """
    # 使用与test_order_list.py相同的签名生成逻辑
    appsource = '30'
    pp_client_ver = '1.0.0_test&508212014'  # 使用与test_order_list.py相同的值
    
    # 如果没有提供merchantid，使用默认值
    if merchantid is None:
        merchantid = '125072409535231'
    
    # 生成签名
    signature, timestamp = generate_sign(
        token, 
        device_id, 
        'WEB', 
        pp_client_ver, 
        appsource, 
        country_code,
        params,
        method
    )
    
    # 构造请求头，与test_order_list.py完全一致
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "appsource": appsource,
        "content-type": "application/json",
        "countrycode": country_code,
        "merchantid": merchantid,
        "origin": "https://business.palmpay.com",
        "pp_client_ver": pp_client_ver,
        "pp_device_id": device_id,
        "pp_device_type": "WEB",
        "pp_req_sign": signature,
        "pp_req_sign_2": signature,
        "pp_timestamp": timestamp,
        "pp_token": token,
        "priority": "u=1, i",
        "referer": "https://business.palmpay.com/",
        "sec-ch-ua": 'Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "macOS",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "tntcode": "palmpayhk",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    }
    
    return headers

if __name__ == '__main__':
    # 测试用例：使用curl请求中的参数
    test_params = {
        'PP_TOKEN': '66a4aaf9-2dce-459e-8ca5-685a9ef62308',
        'PP_TIMESTAMP': '1769656387097',
        'PP_DEVICE_TYPE': 'WEB',
        'countryCode': 'gsa',
        'PP_DEVICE_ID': '8db6b9f4907b241696062774623cb93d',
        'appSource': '30',
        'PP_CLIENT_VER': '1.0.0_test&508212014',
        'merchantid': '125060602371651',
        'param': '{"current":1,"pageSize":20,"orderTypes":[],"pageIndex":1,"createStartTime":1764630000000,"createEndTime":1769727599999,"countryCodes":["GH"],"startOrderAmount":null,"endOrderAmount":null}'
    }
    
    # 测试不带merchantid的情况（根据JavaScript代码，可能不需要这个参数）
    test_params_no_merchant = {
        'PP_TOKEN': '66a4aaf9-2dce-459e-8ca5-685a9ef62308',
        'PP_TIMESTAMP': '1769656387097',
        'PP_DEVICE_TYPE': 'WEB',
        'countryCode': 'gsa',
        'PP_DEVICE_ID': '8db6b9f4907b241696062774623cb93d',
        'appSource': '30',
        'PP_CLIENT_VER': '1.0.0_test&508212014',
        'param': '{"current":1,"pageSize":20,"orderTypes":[],"pageIndex":1,"createStartTime":1764630000000,"createEndTime":1769727599999,"countryCodes":["GH"],"startOrderAmount":null,"endOrderAmount":null}'
    }
    
    # 测试带merchantid的情况
    print("=== 测试带merchantid的情况 ===")
    sorted_keys = sorted(test_params.keys())
    print("排序后的参数键:")
    for key in sorted_keys:
        print(f"  {key}: {test_params[key][:50]}..." if len(str(test_params[key])) > 50 else f"  {key}: {test_params[key]}")
    
    # 打印拼接后的消息
    message_parts = []
    for key in sorted_keys:
        message_parts.append(f"{key}{test_params[key]}")
    message = ''.join(message_parts)
    print(f"\n拼接后的消息长度: {len(message)}")
    print(f"拼接后的消息: {message[:100]}...")
    
    # 生成签名
    signature = generate_sign(test_params)
    
    print("\n生成的签名:")
    print(signature)
    print("\n期望的签名:")
    print("SNAiyimGxALVpr2YQb68tqnT038=")
    
    if signature == "SNAiyimGxALVpr2YQb68tqnT038=":
        print("\n✓ 签名匹配！")
    else:
        print("\n✗ 签名不匹配")
    
    # 测试不带merchantid的情况
    print("\n=== 测试不带merchantid的情况 ===")
    sorted_keys_no_merchant = sorted(test_params_no_merchant.keys())
    print("排序后的参数键:")
    for key in sorted_keys_no_merchant:
        print(f"  {key}: {test_params_no_merchant[key][:50]}..." if len(str(test_params_no_merchant[key])) > 50 else f"  {key}: {test_params_no_merchant[key]}")
    
    # 打印拼接后的消息
    message_parts_no_merchant = []
    for key in sorted_keys_no_merchant:
        message_parts_no_merchant.append(f"{key}{test_params_no_merchant[key]}")
    message_no_merchant = ''.join(message_parts_no_merchant)
    print(f"\n拼接后的消息长度: {len(message_no_merchant)}")
    print(f"拼接后的消息: {message_no_merchant[:100]}...")
    
    # 生成签名
    signature_no_merchant = generate_sign(test_params_no_merchant)
    
    print("\n生成的签名:")
    print(signature_no_merchant)
    print("\n期望的签名:")
    print("SNAiyimGxALVpr2YQb68tqnT038=")
    
    if signature_no_merchant == "SNAiyimGxALVpr2YQb68tqnT038=":
        print("\n✓ 签名匹配！")
    else:
        print("\n✗ 签名不匹配")
