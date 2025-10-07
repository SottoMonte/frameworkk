import application.port.persistence as persistence
import json
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import application.service.flow as flow
import time
import re

class adapter(persistence.port):
    
    def __init__(self,**constants):
        self.config = constants['config']
        self.driver = webdriver.Firefox()
        if 'auth' in self.config:
            self.login()
        self.headers = { 
	'authority': 'httpbin.org', 
	'cache-control': 'max-age=0', 
	'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"', 
	'sec-ch-ua-mobile': '?0', 
	'upgrade-insecure-requests': '1', 
	'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36', 
	'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 
	'sec-fetch-site': 'none', 
	'sec-fetch-mode': 'navigate', 
	'sec-fetch-user': '?1', 
	'sec-fetch-dest': 'document', 
	'accept-language': 'en-US,en;q=0.9', 
}
    def login(self):
        self.driver.get(self.config['url']+self.config['auth'])
        a = WebDriverWait(self.driver, 100).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        time.sleep(1)
        # find username/email field and send the username itself to the input field
        self.driver.find_element("id", "username").send_keys(self.config['username'])
        # find password input field and insert password as well
        self.driver.find_element("id", "password").send_keys(self.config['password'])
        # click login button
        #self.driver.find_element(By.CLASS_NAME,"ax login btn btn-block btn-primary").click()
        self.driver.find_element(By.CSS_SELECTOR ,"button[type='submit']").click(); 

    async def query(self, *services, **constants):
        result = dict()
        soup = services[0]
        field = [x[constants['location']] for x in constants['fields'] if constants['location'] in x]
        
        #print(field)
        for idx,x in  enumerate(field):
            #g = soup.find_all(class_=x)
            tt =[]
            if ':' in x:
                ss = x.split(':')
                id = int(ss[1])
                v = ss[0]
            else:
                id = idx
                v = x
            g = soup.find_all(v)
            clean = re.compile('<.*?>')
            aa = [re.sub(clean, '', str(x)).replace('\n','').strip() for x in g]
            
            #tt = storekeeper.builder('router',{'CPEID': aa[0],'name':aa[3],'state':aa[1]})

            #print(v,aa[id],id)
            result[x] = aa[id]
        return result

    @flow.asyn(ports=('storekeeper',))
    async def read(self, storekeeper, **constants):
        print(self.config,constants)
        self.driver.get(self.config['url']+constants['path'])
        a = WebDriverWait(self.driver, 100).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        #all_title = self.driver.find_element(By.CLASS_NAME, "gFttI f ME Ci H3 _c")
        await asyncio.sleep(2)
        html_source_code = self.driver.page_source
        soup = BeautifulSoup(html_source_code, 'html.parser')
        
        result = await self.query(soup,**constants)
                        
        return storekeeper.builder('transaction',{'state': True,'action':'read','result':result})
        '''async with aiohttp.ClientSession() as session:
            #https://scrapeops.io/python-web-scraping-playbook/python-beautifulsoup-returns-empty-list/
            #https://www.scraperapi.com/blog/10-tips-for-web-scraping/
            async with session.get(self.config['url'], headers=self.headers,ssl=False) as response:
                if response.status != 200:
                    return storekeeper.builder('transaction',{'state': False,'action':'create','remark':'not found data'})
                else:
                    data = await response.text()
                    soup = BeautifulSoup(data, 'html.parser')
                    field = [x[constants['location']] for x in constants['fields'] if constants['location'] in x]
                    result = dict()
                    for x in field:
                        g = soup.find_all(x)
                        result[x] = str(g)
                        
                    return storekeeper.builder('transaction',{'state': True,'action':'read','result':result})'''

    @flow.asyn(ports=('storekeeper',))
    async def create(self, storekeeper, **constants):
        return storekeeper.builder('transaction',{'state': True,'action':'read'})

    @flow.asyn(ports=('storekeeper',))
    async def delete(self, storekeeper, **constants):
        return storekeeper.builder('transaction',{'state': True,'action':'read'})

    @flow.asyn(ports=('storekeeper',))
    async def write(self, storekeeper, **constants):
        return storekeeper.builder('transaction',{'state': True,'action':'read'})

    async def tree(self, *services, **constants):
        pass