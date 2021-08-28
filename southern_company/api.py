import datetime

import requests
import re

from southern_company.models import Usage, AccountUsage
from southern_company.utils import format_date


class Api(object):

    def __init__(self, username: str, password: str):

        self._password = password
        self._username = username
        self._session: requests.Session = requests.Session()

        self._jwt = None
        self._accounts = None

        self.login()

    def login(self):
        # Request token
        login_token = self.request_verification_token()
        sc_web_token = self.get_sc_web_token(login_token, self._username, self._password)

        self._jwt = self.get_jwt(sc_web_token)

        self._session.headers["Authorization"] = f"Bearer {self._jwt}"
        self._session.headers["Content-Type"] = "application/json"

        self._accounts = self.get_all_accounts()

        return self._accounts

    @staticmethod
    def request_verification_token() -> str:
        response = requests.get("https://webauth.southernco.com/account/login")

        if not response.ok:
            raise Exception("Failed to request the verification token")

        login_page = response.text

        match = re.findall(r'.*data-aft="(\S+)".*', login_page)

        if not match:
            raise Exception("Failed to extract verification token")

        return match[0]

    @staticmethod
    def get_sc_web_token(verification_token: str, username: str, password: str) -> str:
        response = requests.post("https://webauth.southernco.com/api/login",
                                 headers={'Content-Type': 'application/json',
                                          'RequestVerificationToken': verification_token},
                                 json={'username': username,
                                       'password': password,
                                       'targetPage': 1,
                                       'params': {'ReturnUrl': "null"}})

        if not response.ok:
            raise Exception("Failed to request sc web token")

        html_data = response.json()['data']['html']
        match = re.findall(r'NAME=\'ScWebToken\' value=\'(\S+\.\S+\.\S+)\'', html_data)

        if not match:
            raise Exception("Could not find ScWebToken")

        return match[0]

    @staticmethod
    def get_jwt(sc_web_token: str) -> str:
        swt_response = requests.post(
            "https://customerservice2.southerncompany.com/Account/LoginComplete?ReturnUrl=null",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            params={"ScWebToken": sc_web_token})

        if not swt_response.ok:
            raise Exception(f"Failed to get secondary ScWebToken: {swt_response.text}")

        swt_cookies = swt_response.headers["set-cookie"]
        if not swt_cookies:
            raise Exception("Failed to get secondary ScWebToken: No cookies were sent back")

        match = re.findall(r'ScWebToken=(\S*);', swt_cookies)
        if not match:
            raise Exception("Failed to get secondary ScWebToken: Could not find any token matches in headers")

        sw_token = match[0]

        response = requests.post("https://customerservice2.southerncompany.com/Account/LoginValidated/JwtToken",
                                 headers={"Cookie": f"ScWebToken={sw_token}"})

        if not response.ok:
            raise Exception(f"Failed to get JWT: {response.text}")

        cookies = response.headers["set-cookie"]
        if not cookies:
            raise Exception("Failed to get JWT: No Cookies were sent back")

        match = re.findall(r'ScJwtToken=(\S*);', cookies)
        if not match:
            raise Exception("Failed to get JWT:  Could not find Token")

        return match[0]

    def get_all_accounts(self):

        if not self._jwt:
            raise Exception("Not logged yet")

        response = self._session.get("https://customerservice2api.southerncompany.com/api/account/getAllAccounts")

        if not response.ok:
            raise Exception(f"Failed to get accounts: {response.text}")

        def account_mapper(a):
            return {'name': a["Description"],
                    'primary': a["PrimaryAccount"],
                    'number': a["AccountNumber"],
                    'company': a["Company"]}

        accounts = [account_mapper(a) for a in response.json()['Data']]
        return accounts

    def get_daily_data(self, start_date: datetime.date, end_date: datetime.date) -> [AccountUsage]:

        if not self._jwt:
            raise Exception("Not logged in yet")

        if end_date < start_date:
            raise Exception("Invalid Dates")

        def request_data(account_number):
            cost_response = self._session.post(
                "https://customerservice2api.southerncompany.com/api/MyPowerUsage/DailyGraph",
                json={
                    'accountNumber': account_number,
                    'StartDate': format_date(start_date),
                    'EndDate': format_date(end_date),
                    'DataType': 'Cost',
                    'OPCO': 'GPC',
                    'intervalBehavior': 'Automatic'}
            )

            if not cost_response.ok:
                raise Exception("Could not request daily usage data")

            usage_response = self._session.post(
                "https://customerservice2api.southerncompany.com/api/MyPowerUsage/DailyGraph",
                json={
                    'accountNumber': account_number,
                    'StartDate': format_date(start_date),
                    'EndDate': format_date(end_date),
                    'DataType': 'Usage',
                    'OPCO': 'GPC',
                    'intervalBehavior': 'Automatic'}
            )

            if not usage_response.ok:
                raise Exception("Could not request daily usage data")

            cost = cost_response.json()['Data']['UsageTable']['UsageDataList']
            usage = usage_response.json()['Data']['UsageTable']['UsageDataList']

            data: [Usage] = []
            for k, v in zip(cost, usage):
                if k['UsageDate'] == v['UsageDate']:
                    date = Usage(datetime.datetime.strptime(k['UsageDate'], "%m/%d/%Y"),
                                 float(k['DailyUsage']),
                                 float(v['DailyUsage']))
                    data.append(date)

            return data

        usage_per_account: [AccountUsage] = []
        for a in self._accounts:
            usage_per_account.append(
                AccountUsage(a['number'], request_data(a['number'])))

        return usage_per_account
