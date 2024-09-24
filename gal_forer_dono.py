import click
import json
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Instrument:
    def __init__(self, instrument_number, sender, receiver, record_date, doc_type, image_links):
        self.instrument_number = instrument_number
        self.sender = sender
        self.receiver = receiver
        self.record_date = record_date
        self.doc_type = doc_type
        self.image_links = image_links

    def __str__(self):
        return json.dumps(self.__dict__)


def date_to_timestamp(date_string: str) -> int:
    date_format = "%m/%d/%Y %I:%M:%S %p"
    parsed_date = datetime.strptime(date_string, date_format)
    timestamp = parsed_date.timestamp()

    return int(timestamp * 1000)


def get_data_locations(metadata: list) -> any:
    for idx, row in enumerate(metadata):
        if row.text == 'Instrument:':
            i = metadata[idx + 1].text.split(' ')[0]
        if row.text == 'File Date:':
            d = metadata[idx + 1].text
        if row.text == 'Inst. Type:':
            t = metadata[idx + 1].text
    return i, d, t


def get_entries(tr: list, actions: ActionChains, driver: WebDriver, wait: WebDriverWait) -> list:
    entries = []
    # The relevant tr start from 7 in the tbody
    row = 7
    while row <= len(tr) - 1:
        if row < len(tr) - 1:
            actions.move_to_element(tr[row + 1]).perform()
        else:
            actions.move_to_element(driver.find_element(By.ID, 'grid_pager_label')).perform()
        # wait for the initial table with the records to show and gets it
        element = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable(tr[row]))
        element.click()
        metadata = driver.find_element(By.CLASS_NAME, 'flex-col')
        # wait for the metadata to load
        time.sleep(5)
        # Gets the details for the instrument
        metadata_rows = metadata.find_elements(By.TAG_NAME, 'label')
        actions.move_to_element(metadata_rows[2]).perform()
        # Get the to and from
        wait.until(EC.visibility_of_element_located((By.ID, 'grantors align-top')))
        actions.move_to_element(driver.find_element(By.ID, 'grantors align-top')).perform()
        from_list = driver.find_element(By.ID, 'grantors align-top').find_elements(By.TAG_NAME, 'li')
        to_list = driver.find_element(By.ID, 'grantees align-top').find_elements(By.TAG_NAME, 'li')
        from_list = [e.text for e in from_list if e.text]
        to_list = [e.text for e in to_list if e.text]

        # Get the images for the instrument
        images = [img.get_attribute('src') for img in
                  driver.find_element(By.ID, 'carousel_div').find_elements(By.TAG_NAME, 'img')]

        # Get the metadata for the instrument
        instrument, date, record_type = get_data_locations(metadata_rows)
        row += 1
        if not date:
            continue
        entries.append(Instrument(instrument, from_list, to_list, date_to_timestamp(date), record_type, images))
    return entries


def get_records(first_name: str, last_name: str, from_date: str, thru_date: str, chrome_driver: str) -> str:
    try:
        # Set up Chrome service
        service = Service(chrome_driver)
        service.start()
        # Instantiate Chrome webdriver
        driver = webdriver.Chrome(service=service)
        wait = WebDriverWait(driver, 30)

        # Open the webpage
        driver.get("https://recording.seminoleclerk.org/DuProcessWebInquiry/index.html")

        # Find the button to enter the site and click it
        driver.find_element(By.CLASS_NAME, "btn-success").click()

        # Wait until the page loads after first reroute
        wait.until(EC.visibility_of_element_located((By.ID, 'criteria_full_name')))
        # getting the search text boxes and populating them
        if first_name or last_name:
            driver.find_element(By.ID, 'criteria_full_name').send_keys(f'{first_name} {last_name}')
        # search.send_keys("ben smith")
        if from_date:
            driver.find_element(By.ID, 'criteria_file_date_start').send_keys(from_date)
        if thru_date:
            driver.find_element(By.ID, 'criteria_file_date_end').send_keys(thru_date)
        # Click search button
        driver.find_element(By.LINK_TEXT, 'SEARCH').click()

        has_next_page = True
        entries = []
        # Handle multy page result from query
        while has_next_page:
            # Create actions to scroll, need to recreate when DOM changes
            actions = ActionChains(driver)

            # Wait for search to finish
            wait.until(EC.visibility_of_element_located((By.ID, 'grid_inst_num')))

            # Get the trs with the entries found for search criteria
            tr = driver.find_element(By.CLASS_NAME, "ui-iggrid-record").find_elements(By.XPATH, "//tr")
            actions.move_to_element(driver.find_element(By.ID, 'grid_link_selectcolumns')).perform()
            # Get the records
            entries.extend(get_entries(tr, actions, driver, wait))
            # Check to see if there is a next page in the query results
            has_next_page = has_next(driver, actions)
        return json.dumps([obj.__dict__ for obj in entries], indent=2)
    except Exception as e:
        return f'Unexpected error: {e}'
    finally:
        driver.quit()


def has_next(driver: WebDriver, actions: ActionChains) -> bool:
    # Check if there is a next page, did find_elements to avoid try/catch, there could be only one, so I use index 0
    next_page = driver.find_elements(By.CLASS_NAME, 'ui-iggrid-nextpagelabel')
    if next_page:
        actions.move_to_element(next_page[0])
        next_page[0].click()
        return True
    return False


@click.command()
@click.option('--first-name', default='ben smith', help='Your first name')
@click.option('--last-name', default='', help='Your last name')
@click.option('--from-date', default='', help='From date')
@click.option('--thru-date', default='', help='Thru date')
@click.option('--chrome-driver', required=True, help='The location of the chrome driver executable for Selenium')
def runner(first_name: str, last_name: str, from_date: str, thru_date: str, chrome_driver: str):
    output = get_records(first_name, last_name, from_date, thru_date, chrome_driver)
    print(output)


if __name__ == "__main__":
    runner()


"""
Notes(I would of done a readme but you asked for one file):
I couldn't understand how to calculate the access-key so I could use requests, so I used Selenium for scraping
Selenium - https://www.selenium.dev/documentation/webdriver/getting_started/

to run with one result(change chrome driver path):
python gal_forer_dono.py --first-name "ben" --last-name "smith" --chrome-driver "path\chromedriver.exe"

to run with multiple results and 1 page(change chrome driver path):
python gal_forer_dono.py --first-name "John"  --from-date "04/12/2024" --thru-date "04/19/2024" --chrome-driver "path\chromedriver.exe"

to run with multiple results and multiple page(change chrome driver path):
python gal_forer_dono.py --first-name "John"  --from-date "03/22/2024" --thru-date "04/19/2024" --chrome-driver "path\chromedriver.exe"
"""
