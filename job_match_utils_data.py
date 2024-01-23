from selenium import webdriver
from selenium.webdriver.common.by import By

from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime, timedelta
import time
from tqdm import tqdm

class JobMatch:
    # Define global link to the saved jobs
    global JOBS_URL
    JOBS_URL = 'https://www.linkedin.com/my-items/saved-jobs/?cardType=SAVED'

    def __init__(self, username, password):

        self.username = username
        self.password = password


    def login(self):

        print('JobMatch: Logging to linked-in, please wait...')
    
        self.driver = webdriver.Chrome()
        time.sleep(2)
        # Navigate to the LinkedIn login page
        self.driver.get('https://www.linkedin.com/login')
        # Wait unti lthe page loads
        time.sleep(5)
        # Enter your email address and password
        self.driver.find_element(By.ID, 'username').send_keys(self.username)
        time.sleep(1)
        self.driver.find_element(By.ID, 'password').send_keys(self.password)
        time.sleep(1)

        # Submit the login form
        self.driver.find_element(By.CSS_SELECTOR, '.login__form_action_container button').click()

        ###TODO: Please add handling of the incorect log-in scenario
        print('JobMatch: Log-in completed!')

    def get_page_soup(self, page_url):

        self.driver.get(page_url)
        # Wait until the page is loaded properly
        time.sleep(5)
        # Get the page source
        page_source = self.driver.page_source
        # Parse the HTML using Beautiful Soup
        soup = BeautifulSoup(page_source, 'html.parser')

        return soup

    def get_n_job_pages(self):
        
        # Get the soup source of tha base page of saved jobs
        base_soup = self.get_page_soup(JOBS_URL)
        # Scan the source for pages index placeholder
        pages_idx_obj = base_soup.find('ul', {'class' : 'artdeco-pagination__pages artdeco-pagination__pages--number'})
        last_page_str = str(pages_idx_obj.find_all('li')[-1].find('span')) # Find the number of last saved jobs page
        # Check how many jobs pages are there
        n_job_pages = int(re.findall(r'\d+', last_page_str)[0])

        return int(n_job_pages)

    def get_saved_pages_urls(self):

        n_job_pages = self.get_n_job_pages()

        pages_urls = []

        for i in range(n_job_pages):
            p_url = JOBS_URL + f'&start={i*10}'
            pages_urls.append(p_url)

        return pages_urls

    def jobmatch_get_job_details(self, job_html):

        # Fetch only text from the job html code
        job_text = job_html.get_text()
        # Replace '\n' tag with ';' so it's easier to return instances of proper text (; is not expected to be used anywere in job parameters)
        job_text = job_text.replace('\n', ';')
        # Compile regex pattern to filter out '-' symbols
        pattern = r'(?<=;)([^;]+)(?=;)'
        job_pars = re.findall(pattern, job_text)
        # Remove reduntant whitespaves left after treating bs4.Tag
        out = [i for i in job_pars if not i.isspace()]
        
        # Sometimes jobs don't have info on status, so we'll have to handle that as well
        if len(out) == 5:
            return {'Position' : out[0], 'Company' : out[1], 'Location' : out[2], 'Status' : out[3], 'Posted' : out[4].replace('Posted ', '')}
        else:
            return {'Position' : out[0], 'Company' : out[1], 'Location' : out[2], 'Status' : 'N/A', 'Posted' : out[3].replace('Posted ', '')}

    def convert_time_lag(self, row):
        # Compile pattern to search for 'Nd/h ago' patter in Posted column
        match = re.match(r'(\d+)([dhwmo]{1,2})\sago', row['Posted'])
        # If matched
        if match:
            # Split the results to two groups - number of days/hours and time unit
            value, unit = int(match.group(1)), match.group(2)
            # If number of days specified
            if unit == 'd':
                return pd.to_datetime(datetime.now() - timedelta(days=value))
            # If number of hours specified
            elif unit == 'h':
                return pd.to_datetime(datetime.now() - timedelta(hours=value))
            # If number of weeks given
            elif unit == 'w':
                return pd.to_datetime(datetime.now() - timedelta(days=(value*7)))
            # If number of months given
            elif unit == 'mo':
                return pd.to_datetime(datetime.now() - timedelta(days=(value*30)))
        # If the pattern wasn't matched at all return NaN
        return pd.NaT

    def get_job_link(self, job_html):
        return job_html.find('a', {'class': 'app-aware-link scale-down'}, href=True)['href']
    
    def get_job_desc(self, url):
        
        # Navigate to job url
        self.driver.get(url)
        # Get the page source
        time.sleep(1)
        page_source = self.driver.page_source
        # Parse the HTML using Beautiful Soup
        soup = BeautifulSoup(page_source, 'html.parser')
        # Return job description
        return soup.find('div', id = 'job-details').get_text().replace('\n', '')

    def jobmatch_page_tab(self, page):

        # Read basic details of each job on current page
        job_details = [self.jobmatch_get_job_details(i) for i in page]
        job_details = pd.DataFrame.from_dict(job_details)

        # Convert posted time lag to TimeStamp
        job_details['Date Posted'] = job_details.apply(self.convert_time_lag, axis=1)
    
        # Attach page URLs
        job_details['URL'] = [self.get_job_link(i) for i in page]

        return job_details

    def compile_jobs_dataframe(self):
        print('JobMatch: Compiling DataFrame with all saved Linke-in jobs, please wait..')

        frames = []

        saved_pages_urls = self.get_saved_pages_urls()
        # For each pages of saved jobs in linkedin
        for page_url in tqdm(saved_pages_urls, desc='Process'):
            #print(f'Scanning job page no.{page_idx}..')
            page_soup = self.get_page_soup(page_url)
            job_page = page_soup.find_all('li', {'class': 'reusable-search__result-container'})
            # Get the full data table for current page
            frames.append(self.jobmatch_page_tab(job_page))

        # Exit chrome session once all done
        self.driver.quit()

        print('JobMatch: DataFrame completed!')
        # Concatenate the tables to one table and return it
        return pd.concat(frames).reset_index(drop=True)