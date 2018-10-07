import calendar
from multiprocessing.pool import ThreadPool
from itertools import repeat
from typing import List

import requests
from lxml import html
from lxml.etree import tostring
from datetime import date, datetime
import time
from urllib.parse import urljoin
from dateutil.rrule import rrule, DAILY, MONTHLY

from inkedNewsCrawler.custom_crawler.news_event_crawler.event_model import StockCalendarEventModel
from inkedNewsCrawler.custom_crawler.news_event_crawler.event_register_service import \
    register_calendar_event_to_server

BASE_URL = "http://everystocks.com/"


def build_url(year, month):
    url = BASE_URL + "index.php?mid=calendar&pYear=%s&pMonth=%s" % (
        str(year), str(month))
    return url


def main():
    all_data_list = get_all_events()
    total = len(all_data_list)
    index = 0
    for event_data in all_data_list:
        print("Current: ", index, "  Total: ", total)
        register_calendar_event_to_server(event_data, isTest=False)
        time.sleep(0.1)
        index += 1
    # 1. Get all calendar events
    # 2. Loop each events, send to server


def get_all_events() -> List[StockCalendarEventModel]:
    all_event_data_list = []

    start_date = datetime(2017, 8, 1)
    # end_date = datetime(2020, 1, 1)
    end_date = datetime(2019, 1, 1)
    months = rrule(MONTHLY, dtstart=start_date, until=end_date)
    for month in months:
        print(month)
        month_events = parse_month(month.year, month.month)
        all_event_data_list.extend(month_events)

    return all_event_data_list


def request_with_retries(url):
    try:
        return requests.get(url)
    except Exception:
        print("OVERHEAD:: sleep")
        time.sleep(0.5)
        return request_with_retries(url)


def parse_month(year, month) -> List[StockCalendarEventModel]:
    eventDataList = []
    url = build_url(year, month)
    r = request_with_retries(url)
    tree = html.fromstring(r.text)

    month_range = calendar.monthrange(year, month)
    index = 0
    day_count_in_month = month_range[1]
    for day in range(1, day_count_in_month + 1):
        xpath = "//div[@id='day_schedule_container_{}-{}-{}']".format(year, month, day)
        date_events_root = tree.xpath(xpath)[0]

        event_items = date_events_root.xpath("//div[@class='drag']")

        pool = ThreadPool(len(event_items))
        result = pool.starmap(parse_single_event,
                              zip(event_items, repeat(datetime(year, month, day))))
        eventDataList.extend(result)
        # close the pool and wait for the work to finish
        pool.close()
        pool.join()
        index += 1

        # # FIXME For debug
        # if index == 2:
        #     print("BREAK")
        #     break

    return eventDataList


def parse_single_event(event_item_node: html.HtmlElement, datetime):
    blog_url = event_item_node.xpath('./a/@href')[0]
    blog_url = urljoin(BASE_URL, blog_url)
    event_name = event_item_node.text_content()
    content = parse_blog_content(blog_url)
    event_date = datetime
    print("event_name", event_name)
    print("blog_url", blog_url)
    print("event_date", event_date)
    # print("content", content)
    print("\n")
    # region Create model
    data = StockCalendarEventModel()
    data.eventName = event_name
    data.eventContent = content
    data.eventTime = event_date
    data.links = [blog_url]
    data.extraFields = {"source": "everystocks.com", "version": "0.0.1", "production": True}
    # endregion
    return data


def parse_blog_content(blog_url) -> str:
    # EX. http://everystocks.com/index.php?mid=calendar&pYear=2017&pMonth=8&document_srl=731

    r = request_with_retries(blog_url)
    tree = html.fromstring(r.text)

    # remove unused element
    remove_target = tree.xpath('//div[@class="document_popup_menu"]')[0]
    remove_target.getparent().remove(remove_target)

    p = tree.xpath('//*[@id="content"]/div/div[3]/div/div[2]/div')[0]
    content = str(p.text_content())
    return content


if __name__ == '__main__':
    main()
