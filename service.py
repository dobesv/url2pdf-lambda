#!/usr/bin/env python
from tempfile import NamedTemporaryFile

import httplib2
import datetime
import time
import os
import selenium
import json
import boto3
import requests
from dateutil.parser import parse
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials
import base64

import logging

log = logging.getLogger('url2pdf')
logging.getLogger().setLevel(logging.INFO)
log.setLevel(logging.DEBUG)

user_agent = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36")
dcap = dict(DesiredCapabilities.PHANTOMJS)
dcap["phantomjs.page.settings.userAgent"] = user_agent
dcap["phantomjs.page.settings.javascriptEnabled"] = False

logfile = NamedTemporaryFile(suffix='.log')
driver = webdriver.PhantomJS(
    service_log_path=logfile.name,
    executable_path="/var/task/phantomjs",
    service_args=['--ignore-ssl-errors=true'],
    desired_capabilities=dcap)


def url2pdf(url):
    """
    Render HTML to PDF using PhantomJS

    Args:
        html_source: HTML source code

    Returns:
        bytes: PDF blob
    """
    start = time.time()
    with NamedTemporaryFile(mode='r+b', suffix='.pdf') as outfile:
        logfile_pos = logfile.tell()
        driver.set_window_size(1024, 768)  # optional
        driver.get(url)

        def execute(script, args=None):
            driver.execute('executePhantomScript', {'script': script, 'args': args or []})

        driver.command_executor._commands['executePhantomScript'] = ('POST', '/session/$sessionId/phantom/execute')

        # set page format
        # inside the execution script, webpage is "this"
        execute('this.paperSize = {format: "Letter", orientation: "portrait", margin: { top: 0, right: 0, bottom: 0, left: 0 } };')

        # render current page
        execute('this.render("%s", {"format":"pdf"});' % outfile.name)

        driver.get('about:blank')

        # Output any log messages from phantomjs somewhere we might see them
        phantomjs_logger = logging.getLogger('phantomjs')
        logfile.seek(logfile_pos)
        for line in logfile:
            line = line.strip()
            if line:
                level = logging.DEBUG
                if line.startswith('['):
                    level_name = line[1:].split(' ', 1)[0]
                    level = dict(
                        WARNING=logging.WARNING,
                        WARN=logging.WARN,
                        INFO=logging.INFO,
                        ERROR=logging.ERROR,
                        CRITICAL=logging.CRITICAL,
                        FATAL=logging.FATAL,
                    ).get(level_name, level)
                phantomjs_logger.log(level, line)

        outfile.seek(0)

        log.info('PDF generation took %.3fs' % (time.time() - start))
        return outfile.read()


def handler(event, context):
    query = event.get("queryStringParameters")
    url = query and query.get('url')
    if not url:
        return dict(statusCode=400, body="Must specify url");

    body = url2pdf(url)

    return {
        "statusCode": 200,
        "body": base64.b64encode(body),
        "headers": {
            "Content-Type": "application/pdf",
            "Content-Length": len(body),
            "Cache-Control": "max-age=86400"
        },
        "isBase64Encoded": True
    }

# dcap = dict(DesiredCapabilities.PHANTOMJS)
# dcap["phantomjs.page.settings.userAgent"] = user_agent
# dcap["phantomjs.page.settings.javascriptEnabled"] = True
#
# browser = webdriver.PhantomJS(service_log_path=os.path.devnull, executable_path="/var/task/phantomjs", service_args=['--ignore-ssl-errors=true'], desired_capabilities=dcap)
# browser.get('https://en.wikipedia.org/wiki/Special:Random')
# line = browser.find_element_by_class_name('firstHeading').text
# print(line)
# return line
