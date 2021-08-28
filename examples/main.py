import datetime
import os

from dotenv import load_dotenv
import southern_company

load_dotenv()

if __name__ == '__main__':
    api = southern_company.Api(os.environ.get("user"), os.environ.get("password"))
    usage = api.get_daily_data(datetime.datetime(2021, 8, 1), datetime.datetime(2021, 8, 5))
    print(usage)