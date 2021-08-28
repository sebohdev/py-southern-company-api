import datetime
from .utils import auto_str


@auto_str
class Usage:
    date: datetime.date
    cost: float
    kWH: float

    def __init__(self, date: datetime.date, cost: float, kWH: float) -> None:
        self.date = date
        self.cost = cost
        self.kWH = kWH


@auto_str
class AccountUsage:
    account: str
    data: [Usage]

    def __init__(self, account: str, data: [Usage]) -> None:
        self.account = account
        self.data = data

