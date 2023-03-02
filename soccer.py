#from selenium import webdriver
#from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import pandas as pd
import re
from time import sleep
from collections import defaultdict
from random import randint
import os
import selenium.webdriver as webdriver
from datetime import datetime, timedelta
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys

class WhoScord:
    def __init__(self):
        self.final = defaultdict(list)
        self.target_atts = ['GF', 'GD', 'Pts', 'W']
        self.base_url = 'https://www.whoscored.com'
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-notifications")
        self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
        # path = os.path.join(os.getcwd(), 'gd', 'geckodriver.exe')
        # options = Options()
        # options.add_argument("--headless")
        # firefox_service = Service(path)
        # self.driver = webdriver.Firefox(service=firefox_service, options=options)
    
    def login(self):
        self.driver.get('https://www.whoscored.com/Accounts/Login')
        username = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                    "input[name='usernameOrEmailAddress']")))
        password = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                                    "input[name='password']")))
        username.clear()
        username.send_keys(os.getenv('USERNAME'))
        password.clear()
        password.send_keys(os.getenv('PASS'))
        button = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                                            "input[type='submit']"))).click()
        print("Logged in")
        sleep(randint(1,4))
        
        
    def extract_games(self):
        live_scores_page = BeautifulSoup(self.driver.page_source, 'lxml')
        container = live_scores_page.find("div", {"class": "divtable-body"})
        table_rows = container.find_all('div', {'class': 'divtable-row'})
        league_name = ""
        results = defaultdict(list)
        for row in table_rows:
            check = row.has_attr("data-group-id")
            if not check:
                league_name = row.text.replace('Detailed coverage', '').strip()
                league_url = self.base_url + row.find('a')['href']
            else:
                for team in row.find_all('a', {'class': 'team-link'})[0:2]:
                    item = {"Team": team.text, "league": league_name,
                           "league_url": league_url}
                    results[league_name].append(item)
        return results
        
    def clean_number(self, text):
        comp = re.compile(r"^\d+")
        match = comp.match(text)
        if match:
            start = match.start()
            end = match.end()
            text = text[:start] + text[end:]
        return text
    
    def extract_year_stats(self, league_page_soup, current_league_matches_df):
        table_container = league_page_soup.find_all('div', {'class': 'tournament-standings-table'})
        standing_tables = [pd.read_html(str(table))[0] for table in table_container]
        
        if len(standing_tables) != 0:
            if len(standing_tables) > 1:
                standing_table_concat = pd.concat(standing_tables).reset_index(drop=True)
            elif len(standing_tables) == 1:
                standing_table_concat = standing_tables[0]    
            
            standing_table_concat['Team'] = standing_table_concat['Team'].apply(lambda x: self.clean_number(x))
            year_df_final = pd.merge(standing_table_concat, current_league_matches_df, how='right', on = 'Team')
            #year_df_final = standing_table_concat.merge(current_league_matches_df, on='Team', how='inner')
            return year_df_final
        else:
            return False
        
    
    def show_l3(self, current_league):
        content = self.driver.find_elements(By.CSS_SELECTOR, 
                                            'div.tournament-standings-table div.option-group ul li')
        form_buttons = content[1::5]
        l3_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a[data-source="three"]')  
        for i in range(len(form_buttons)):
            form_buttons[i].click()
            sleep(randint(1,3))
            l3_buttons[i].click()
            sleep(randint(1,3))
            
        l3_forms = self.driver.find_elements(By.CSS_SELECTOR,
                                            "div[id^='tournament-tables-'] div[id^='forms-'] div.semi-attached-table")
        l3_dfs = [pd.read_html(l3_form.get_attribute('innerHTML'))[0] for l3_form in l3_forms]
        if len(l3_dfs) > 1:
            l3_df_concat = pd.concat(l3_dfs, axis=0, sort=False, join='inner').reset_index(drop=True)
        else:
            l3_df_concat = l3_dfs[0]
            
        l3_df_concat['Team'] = l3_df_concat['Team'].apply(lambda x: self.clean_number(x))
        l3_df_final = l3_df_concat.merge(current_league, on='Team', how='inner')        
        return l3_df_final
    
    def extract_atts(self, target, l3_df_final, year_df_final):
        for index, y_row in year_df_final.iterrows():
            item = {}
            match = l3_df_final[l3_df_final["Team"] == y_row['Team']]
            item['League'] = y_row['league']
            item['Team'] = y_row['Team']
            item['P'] = y_row['P']
            try:
                item['Year'] = round(float(y_row[target]) / float(y_row['P']), 2)
            except:
                item['Year'] = 0
            try:
                item['L3'] = round(float(match[target].values[0]) / float(match['P'].values[0]), 2)
            except:
                item['L3'] = 0

            item['Diff from Year to L3'] = round(item['L3'] - item['Year'], 2)
            self.final[target].append(item)
            if index % 2 == 1:
                empty_item = {"League": "", "Team": "", "P": "", "Year": "", "L3": "",
                               "Diff from Year to L3": ""}
                self.final[target].append(empty_item)
    
    def run(self):
        tomorrow = False
        entered_date = ""

        option = input("\n1. Today\n2. Tomorrow\n3. Custom Date\n")

        if option == "2":
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            date = tomorrow.strftime("%d-%m-%Y")
            tomorrow = True
        elif option == "3":
            while True:
                entered_date = input("Enter in the YYYY-MM-DD format: ")
                if len(entered_date.split("-")) != 3:
                    print("Example: 2022-01-25")
                else:
                    date = datetime.strptime(entered_date, "%Y-%m-%d").strftime("%d-%m-%Y")
                    break

        else:
            today = datetime.now()
            date = today.strftime("%d-%m-%Y")

        #self.login()
        sleep(randint(3, 6))
        self.driver.get('https://www.whoscored.com/LiveScores')
        sleep(randint(4, 6))
        
        popup = self.driver.find_elements(By.CSS_SELECTOR, 
                                        'button[aria-label="Close this dialog"]')

        if len(popup) != 0:
            popup[0].click()
            sleep(randint(1,3))

        webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

        if tomorrow == True:
            next_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                   "a.next.button")))
            next_button.click() 
            sleep(randint(4, 6))
        elif entered_date:
            dates_button = self.driver.find_elements(By.CSS_SELECTOR, 'a#date-config-toggle-button')
            year, month, day = [int(item) for item in entered_date.split("-")]
            if dates_button:
                dates_button[0].click()
                sleep(1)
                self.driver.find_elements(By.CSS_SELECTOR, f'table.years td[data-value="{year}"]')[0].click()
                self.driver.find_elements(By.CSS_SELECTOR, f'table.days td[data-value="{day-1}"]' )[0].click()
                self.driver.find_elements(By.CSS_SELECTOR, f'table.months td[data-value="{month-1}"]' )[0].click()
                sleep(randint(4, 6))

        
        league_matches_results = self.extract_games()
        counter = 1
        leagues_length = len(league_matches_results.keys())
        for k, v in league_matches_results.items():
            url = v[0]['league_url']
            print("{} | {}".format(counter, leagues_length), end=",  ", flush=True)
            print("Getting: {}".format(url), end="\n")
            self.driver.get(url)
            sleep(randint(7, 10))

            popup = self.driver.find_elements(By.CSS_SELECTOR, 
                                'button[aria-label="Close this dialog"]')
            if len(popup) != 0:
                popup[0].click()
                sleep(randint(1,3))

            current_league_matches_df = pd.DataFrame(v)
            league_page_soup = BeautifulSoup(self.driver.page_source, 'lxml')
            year_df_final = self.extract_year_stats(league_page_soup, current_league_matches_df)
            if isinstance(year_df_final, (pd.DataFrame)) == True:
                l3_df_final = self.show_l3(current_league_matches_df)
                for target in self.target_atts:
                    self.extract_atts(target, l3_df_final, year_df_final)
            else:
                print("Nothing to get in {}".format(url))

            counter += 1

        
        for key in self.final.keys():
            if key == 'W':
                filename = 'SW'
            else:
                filename = key

            df = pd.DataFrame(self.final[key])
            df.to_excel("{}".format(filename) + " {}".format(date) + ".xlsx", index=False)
            
        self.driver.close()

ws = WhoScord()
ws.run()

