from pydantic import BaseModel

class TradingViewSignal(BaseModel):
    ticker: str
    side: str

class transactionObject(BaseModel):
    ticker: str
    side: str
    quantity: float