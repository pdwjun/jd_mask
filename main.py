import sys
from jd_mask_spider_requests import Jd_Mask_Spider

if __name__ == '__main__':
    a = """
  ________   __    _ 
 |___  /\ \ / /   | |
    / /  \ V /    | |
   / /    > < _   | |
  / /__  / . \ |__| |1.预约商品
 /_____|/_/ \_\____/ 2.秒杀抢购商品 
    """
    start_tool = Jd_Mask_Spider()

    # start_tool.login()
    # start_tool.request_seckill_url()
    # start_tool.request_seckill_checkout_page()
    # start_tool.submit_seckill_order()

    start_tool.mobile_submit_order()
