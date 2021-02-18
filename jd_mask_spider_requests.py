import random
import sys
import time
from jdlogger import logger
from timer import Timer
import requests
from util import parse_json, get_session, get_sku_title, send_wechat
from config import global_config


class Jd_Mask_Spider(object):
    def __init__(self):
        # 初始化信息
        self.session = get_session()
        self.sku_id = global_config.getRaw('config', 'sku_id')
        self.seckill_init_info = dict()
        self.seckill_url = dict()
        self.seckill_order_data = dict()
        self.timers = Timer()
        self.default_user_agent = global_config.getRaw('config', 'DEFAULT_USER_AGENT')

    def login(self):
        for flag in range(1, 3):
            try:
                targetURL = 'https://order.jd.com/center/list.action'
                payload = {
                    'rid': str(int(time.time() * 1000)),
                }
                resp = self.session.get(
                    url=targetURL, params=payload, allow_redirects=False)
                if resp.status_code == requests.codes.OK:
                    logger.info('校验是否登录[成功]')
                    logger.info('用户:{}'.format(self.get_username()))
                    return True
                else:
                    logger.info('校验是否登录[失败]')
                    logger.info('请从新输入cookie')
                    time.sleep(1)
                    continue
            except Exception as e:
                logger.info('第【%s】次失败请重新获取cookie', flag)
                time.sleep(1)
                continue
        sys.exit(1)

    def make_reserve(self):
        """商品预约"""
        logger.info('商品名称:{}'.format(get_sku_title()))
        url = 'https://yushou.jd.com/youshouinfo.action?'
        payload = {
            'callback': 'fetchJSON',
            'sku': self.sku_id,
            '_': str(int(time.time() * 1000)),
        }
        headers = {
            'User-Agent': self.default_user_agent,
            'Referer': 'https://item.jd.com/{}.html'.format(self.sku_id),
        }
        resp = self.session.get(url=url, params=payload, headers=headers)
        resp_json = parse_json(resp.text)
        reserve_url = resp_json.get('url')
        self.timers.start()
        while True:
            try:
                self.session.get(url='https:' + reserve_url)
                logger.info('预约成功，已获得抢购资格 / 您已成功预约过了，无需重复预约')
                if global_config.getRaw('messenger', 'enable') == 'true':
                    success_message = "预约成功，已获得抢购资格 / 您已成功预约过了，无需重复预约"
                    send_wechat(success_message)
                break
            except Exception as e:
                logger.error('预约失败正在重试...')

    def get_username(self):
        """获取用户信息"""
        url = 'https://passport.jd.com/user/petName/getUserInfoForMiniJd.action'
        payload = {
            'callback': 'jQuery'.format(random.randint(1000000, 9999999)),
            '_': str(int(time.time() * 1000)),
        }
        headers = {
            'User-Agent': self.default_user_agent,
            'Referer': 'https://order.jd.com/center/list.action',
        }
        try:
            resp = self.session.get(url=url, params=payload, headers=headers)
            resp_json = parse_json(resp.text)
            # 响应中包含了许多用户信息，现在在其中返回昵称
            # jQuery2381773({"imgUrl":"//storage.360buyimg.com/i.imageUpload/xxx.jpg","lastLoginTime":"","nickName":"xxx","plusStatus":"0","realName":"xxx","userLevel":x,"userScoreVO":{"accountScore":xx,"activityScore":xx,"consumptionScore":xxxxx,"default":false,"financeScore":xxx,"pin":"xxx","riskScore":x,"totalScore":xxxxx}})
            return resp_json.get('nickName') or 'jd'
        except Exception:
            return 'jd'

    def get_seckill_url(self):
        """获取商品的抢购链接
        点击"抢购"按钮后，会有两次302跳转，最后到达订单结算页面
        这里返回第一次跳转后的页面url，作为商品的抢购链接
        :return: 商品的抢购链接
        """

        url = 'https://item-soa.jd.com/getWareBusiness'

        payload = {
            'callback': 'jQuery{}'.format(random.randint(1000000, 9999999)),
            'skuId': self.sku_id,
            '_': str(int(time.time() * 1000)),
        }
        headers = {
            'User-Agent': self.default_user_agent,
            # 'Host': 'item-soa.jd.com',
            'Referer': 'https://item.jd.com/',
            'authority': 'item-soa.jd.com',
            'scheme': 'https',
            'method': 'GET',
            'num': '1',
            'path': '/getWareBusiness?callback=' + payload['callback'] + '&skuId=' + self.sku_id,
        }
        tryTime = 0
        while True and tryTime < 20:
            # self.session.mount('https://cart.jd.com/', HTTP20Adapter())
            # 加购物车
            resp = self.session.get(url=url, headers=headers, params=payload)
            resp_json = parse_json(resp.text)
            yuyueInfo = resp_json.get('yuyueInfo')
            if yuyueInfo is not None and yuyueInfo.get('state') == 4:
                cookies = self.session.cookies
                url = 'https://cart.jd.com/gate.action?pcount=1&ptype=1&pid=' + self.sku_id
                resp = requests.get(url, cookies=cookies)
                return resp.url

                # https://divide.jd.com/user_routing?skuId=8654289&sn=c3f4ececd8461f0e4d7267e96a91e0e0&from=pc
                # router_url = 'https:' + resp_json.get('url')
                # # https://marathon.jd.com/captcha.html?skuId=8654289&sn=c3f4ececd8461f0e4d7267e96a91e0e0&from=pc
                # seckill_url = router_url.replace(
                #     'divide', 'marathon').replace(
                #     'user_routing', 'captcha.html')
                # logger.info("抢购链接获取成功: %s", seckill_url)
                # return seckill_url
            else:
                logger.info("抢购链接获取失败，%s不是抢购商品或抢购页面暂未刷新，0.1秒后重试")
                time.sleep(0.2)

            tryTime = tryTime + 1

    def request_seckill_url(self):
        """访问商品的抢购链接（用于设置cookie等"""
        logger.info('用户:{}'.format(self.get_username()))
        logger.info('sku_id:{}'.format(self.sku_id))
        logger.info('商品名称:{}'.format(get_sku_title()))
        self.timers.start()
        self.seckill_url[self.sku_id] = self.get_seckill_url()
        logger.info('访问商品的抢购连接...')
        headers = {
            'User-Agent': self.default_user_agent,
            'Host': 'marathon.jd.com',
            'Referer': 'https://item.jd.com/{}.html'.format(self.sku_id),
        }
        self.session.get(
            url=self.seckill_url.get(
                self.sku_id),
            headers=headers,
            allow_redirects=False)

    def request_seckill_checkout_page(self):
        """访问抢购订单结算页面"""
        url = 'https://trade.jd.com/shopping/dynamic/coupon/getCoupons.action'

        headers = {
            'User-Agent': self.default_user_agent,
            'Host': 'trade.jd.com',
            'Referer': 'https://trade.jd.com/shopping/order/getOrderInfo.action',
            'authority': 'trade.jd.com',
            'scheme': 'https',
            'method': 'POST',
            'path': '/shopping/dynamic/coupon/getCoupons.action',
        }
        self.session.get(url=url, headers=headers)

    def _get_seckill_init_info(self):
        """获取秒杀初始化信息（包括：地址，发票，token）
        :return: 初始化信息组成的dict
        """
        logger.info('获取秒杀初始化信息...')
        url = 'https://marathon.jd.com/seckillnew/orderService/pc/init.action'
        data = {
            'sku': self.sku_id,
            'num': 1,
            'isModifyAddress': 'false',
        }
        headers = {
            'User-Agent': self.default_user_agent,
            'Host': 'marathon.jd.com',
        }
        resp = self.session.post(url=url, data=data, headers=headers)

        logger.info(resp.text)
        return parse_json(resp.text)

    def _get_seckill_order_data(self):
        """生成提交抢购订单所需的请求体参数
        :return: 请求体参数组成的dict
        """
        logger.info('生成提交抢购订单所需参数...')
        # 获取用户秒杀初始化信息
        self.seckill_init_info[self.sku_id] = self._get_seckill_init_info()
        init_info = self.seckill_init_info.get(self.sku_id)
        default_address = init_info['addressList'][0]  # 默认地址dict
        invoice_info = init_info.get('invoiceInfo', {})  # 默认发票信息dict, 有可能不返回
        token = init_info['token']
        data = {
            'skuId': self.sku_id,
            'num': 1,
            'addressId': default_address['id'],
            'yuShou': 'true',
            'isModifyAddress': 'false',
            'name': default_address['name'],
            'provinceId': default_address['provinceId'],
            'cityId': default_address['cityId'],
            'countyId': default_address['countyId'],
            'townId': default_address['townId'],
            'addressDetail': default_address['addressDetail'],
            'mobile': default_address['mobile'],
            'mobileKey': default_address['mobileKey'],
            'email': default_address.get('email', ''),
            'postCode': '',
            'invoiceTitle': invoice_info.get('invoiceTitle', -1),
            'invoiceCompanyName': '',
            'invoiceContent': invoice_info.get('invoiceContentType', 1),
            'invoiceTaxpayerNO': '',
            'invoiceEmail': '',
            'invoicePhone': invoice_info.get('invoicePhone', ''),
            'invoicePhoneKey': invoice_info.get('invoicePhoneKey', ''),
            'invoice': 'true' if invoice_info else 'false',
            'password': '',
            'codTimeType': 3,
            'paymentType': 4,
            'areaCode': '',
            'overseas': 0,
            'phone': '',
            'eid': global_config.getRaw('config', 'eid'),
            'fp': global_config.getRaw('config', 'fp'),
            'token': token,
            'pru': ''
        }
        return data

    def submit_seckill_order(self):
        """提交抢购（秒杀）订单
        :return: 抢购结果 True/False
        """
        # url = 'https://marathon.jd.com/seckillnew/orderService/pc/submitOrder.action'
        url = 'https://trade.jd.com/shopping/order/submitOrder.action'
        payload = {
            'skuId': self.sku_id,
            'submitOrderParam.payPassword': 'u34u36u37u39u31u38',
            'vendorRemarks': '[{"venderId":"715322","remark":""}]',
            'submitOrderParam.sopNotPutInvoice': 'true',
            'submitOrderParam.trackID': 'TestTrackId',
            'submitOrderParam.ignorePriceChange': '0',
            'submitOrderParam.btSupport': '0',
            'submitOrderParam.eid': 'IFFL6KCM7GNWKEF7QYJWY7GV6N5TDO3XY32JXHQYGXVRSU37R7XXMVOGMB55UONBL657M5JEAKFPNLWJVO7MP6RQCI',
            'submitOrderParam.fp': 'f8796ac2de74f27aa2279ebd189d5121',
            'submitOrderParam.jxj': '1',
        }
        sec_kill_order_data = self._get_seckill_order_data(
        )
        # logger.info('提交抢购订单...')
        headers = {
            'User-Agent': self.default_user_agent,
            'Host': 'trade.jd.com',
            'Referer': 'https://trade.jd.com/shopping/order/getOrderInfo.action',
            'authority': 'trade.jd.com',
            'scheme': 'https',
            'method': 'POST',
            'path': '/shopping/order/submitOrder.action?',
            # 'sec-fetch-dest:': 'empty',
            # 'sec-fetch-mode:': 'cors',
            # 'sec-fetch-site:': 'same-origin',
        }
        # self.session.mount('https://trade.jd.com/', HTTP20Adapter())

        # resp = requests.post(url, cookies=self.session.cookies, headers=headers, params=payload, data=.seckill_order_data.get(
        #         self.sku_id))

        resp = self.session.post(
            url=url,
            params=payload,
            data=sec_kill_order_data,
            headers=headers)
        resp_json = parse_json(resp.text)
        # 返回信息
        # 抢购失败：
        # {'errorMessage': '很遗憾没有抢到，再接再厉哦。', 'orderId': 0, 'resultCode': 60074, 'skuId': 0, 'success': False}
        # {'errorMessage': '抱歉，您提交过快，请稍后再提交订单！', 'orderId': 0, 'resultCode': 60017, 'skuId': 0, 'success': False}
        # {'errorMessage': '系统正在开小差，请重试~~', 'orderId': 0, 'resultCode': 90013, 'skuId': 0, 'success': False}
        # 抢购成功：
        # {"appUrl":"xxxxx","orderId":820227xxxxx,"pcUrl":"xxxxx","resultCode":0,"skuId":0,"success":true,"totalMoney":"xxxxx"}
        if resp_json.get('success'):
            order_id = resp_json.get('orderId')
            # total_money = resp_json.get('totalMoney')
            # pay_url = 'https:' + resp_json.get('pcUrl')
            logger.info(
                '抢购成功，需要手动支付，订单号:{}'.format(order_id)
            )
            if global_config.getRaw('messenger', 'enable') == 'true':
                success_message = "抢购成功，需要手动支付，订单号:{}, 商品:{}".format(order_id, get_sku_title())
                send_wechat(success_message)
            return True
        else:
            logger.info('抢购失败，返回信息:{}'.format(resp_json))
            if global_config.getRaw('messenger', 'enable') == 'true':
                error_message = '抢购失败，返回信息:{}'.format(resp_json)
                send_wechat(error_message)
            return False

    def mobile_submit_order(self):
        # 手机端提交订单
        url = 'https://fo.m.jd.com/m/pay/payWithCheckOut'
        payload = {
            'skuId': self.sku_id,
            'skuNum': 1,
            'addressId': 1405661826,
            'type': 2,
            'payType': 1,
        }
        # sec_kill_order_data = self._get_seckill_order_data(
        # )
        # logger.info('提交抢购订单...')
        headers = {
            'User-Agent': self.default_user_agent,
            # 'Host': 'trade.jd.com',
            'Referer': 'https://fo.m.jd.com/m/settlement/payMiddle?skuId=' + self.sku_id + 'subPrice=0&notiPrice=0&expectingPrice=0&expireDate=undefined&type=2',
            'authority': 'fo.m.jd.com',
            'scheme': 'https',
            'method': 'POST',
            'path': '/m/pay/payWithCheckOut',
            # 'sec-fetch-dest:': 'empty',
            # 'sec-fetch-mode:': 'cors',
            # 'sec-fetch-site:': 'same-origin',
        }
        # self.session.mount('https://trade.jd.com/', HTTP20Adapter())

        # resp = requests.post(url, cookies=self.session.cookies, headers=headers, params=payload, data=.seckill_order_data.get(
        #         self.sku_id))

        logger.info('用户:{}'.format(self.get_username()))
        logger.info('sku_id:{}'.format(self.sku_id))
        logger.info('商品名称:{}'.format(get_sku_title()))
        self.timers.start()

        resp = self.session.post(
            url=url,
            params=payload,
            # data=sec_kill_order_data,
            headers=headers)
        logger.info(resp.text)
        resp_json = parse_json(resp.text)
        # 返回信息
        # 抢购失败：
        # {'errorMessage': '很遗憾没有抢到，再接再厉哦。', 'orderId': 0, 'resultCode': 60074, 'skuId': 0, 'success': False}
        # {'errorMessage': '抱歉，您提交过快，请稍后再提交订单！', 'orderId': 0, 'resultCode': 60017, 'skuId': 0, 'success': False}
        # {'errorMessage': '系统正在开小差，请重试~~', 'orderId': 0, 'resultCode': 90013, 'skuId': 0, 'success': False}
        # 抢购成功：
        # {"appUrl":"xxxxx","orderId":820227xxxxx,"pcUrl":"xxxxx","resultCode":0,"skuId":0,"success":true,"totalMoney":"xxxxx"}
        if resp_json.get('success'):
            order_id = resp_json.get('orderId')
            # total_money = resp_json.get('totalMoney')
            # pay_url = 'https:' + resp_json.get('pcUrl')
            logger.info(
                '抢购成功，需要手动支付，订单号:{}'.format(order_id)
            )
            if global_config.getRaw('messenger', 'enable') == 'true':
                success_message = "抢购成功，需要手动支付，订单号:{}, 商品:{}".format(order_id, get_sku_title())
                send_wechat(success_message)
            return True
        else:
            logger.info('抢购失败，返回信息:{}'.format(resp_json))
            if global_config.getRaw('messenger', 'enable') == 'true':
                error_message = '抢购失败，返回信息:{}'.format(resp_json)
                send_wechat(error_message)
            return False
