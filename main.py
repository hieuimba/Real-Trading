import logging
import logging.handlers
import os
from bs4 import BeautifulSoup

import requests
from datetime import timedelta

import pandas as pd
import quantstats as qs

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_file_handler = logging.handlers.RotatingFileHandler(
    "status.log",
    maxBytes=1024 * 1024,
    backupCount=1,
    encoding="utf8",
)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger_file_handler.setFormatter(formatter)
logger.addHandler(logger_file_handler)


try:
    JOURNAL_URL = os.environ["JOURNAL_URL"]
    API_KEY = os.environ["JOURNAL_API_KEY"]

except KeyError:
    logger.info("Token not available!")
    raise


def format_journal(journal):
    journal['NetProfit'] = journal['PnL']
    # select date closed and net profit
    journal = journal[['DateClosed', 'NetProfit']]
    # convert to datetime date closed
    journal['DateClosed'] = pd.to_datetime(journal['DateClosed'])
    # get only date from dateclosed
    journal['DateClosed'] = journal['DateClosed'].dt.date
    # group by date closed and sum net profit
    journal = journal.groupby('DateClosed').sum().reset_index()
    # reverse df
    journal = journal.iloc[::-1]
    # create first row
    journal.loc[-1] = [journal['DateClosed'].min() - timedelta(1), 0]
    # sort by date closed
    journal = journal.sort_values('DateClosed')
    # dateclosed index
    journal.index = pd.to_datetime(journal['DateClosed'])
    # cumsum
    journal['NetProfit'] = journal['NetProfit'].cumsum() + 2000

    # convert to returns
    journal['Return'] = journal['NetProfit'].pct_change()

    # select return
    journal = journal['Return']
    return journal


def format_html(file):
    with open(file, 'r+') as f:
        html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        # change title
        soup.title.string.replace_with('Real Trading for a Living')
        # save to file
        f.seek(0)
        f.truncate()
        f.write(str(soup))


if __name__ == "__main__":
    r = requests.get(JOURNAL_URL, headers={'x-api-key': API_KEY})
    if r.status_code == 200:
        data = pd.DataFrame(r.json())
        journal = format_journal(data)

        spy = qs.utils.download_returns('SPY', period='5y')
        spy.index = spy.index.tz_localize(None)

        qs.reports.html(journal, benchmark=spy, download_filename='index.html',
                        output='journal.html', benchmark_title='SPY')

        format_html('index.html')

        logger.info(f'Updated')
    else:
        logger.error(f"Error: {r.status_code}")
