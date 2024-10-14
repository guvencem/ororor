from fastapi import FastAPI
import uvicorn
from domainObjects import *
from fastapi import FastAPI
from binance.um_futures import UMFutures
import time

default_price = 5 #dolar
DEFAULT_MULTIPLIER = 11

#Init Binance ##################
BINANCE_APIKEY_1 = "H7hSbRMY4yfPb5v6bt8HsI4lIB5lsh8Gd26tFkL1fZ58XK3BhFaToE9KNbUm7IWr"
BINANCE_APISECRET_1 =  "V46tXLk5Jq4ioaV98Iwui76lW6ltLh9gMExoMazWztfKOepM4gAGCRgdLPda1UYq"

client1 = UMFutures(key=BINANCE_APIKEY_1, secret=BINANCE_APISECRET_1)
#client2 = UMFutures(key=BINANCE_APIKEY_2, secret=BINANCE_APISECRET_2)
clients = [client1]
######################################

exchangeInfo = client1.exchange_info() #exchange info for all coins. 

app = FastAPI()

@app.post("/signal")
def processSignals(indicatorSignal: TradingViewSignal):
    i = 1
    for client in clients:
        print("Doing transactions for client: " + str(i))
        tickerName = indicatorSignal.ticker.replace(".P","")
        nextSide =  "BUY" if indicatorSignal.side == "buy" else "SELL"
        if(indicatorSignal.side == "CLOSE"):
            nextSide = "CLOSE"
        marginTypeChanged = changeMarginTypeToIsolated(tickerName,client)
        if(marginTypeChanged == False):
            print("Error happened. Closing.")
            return
        accountData = client.account()
        print(default_price)
        i+=1
        currentStatus = getCurrentStatusOfCoin(accountData["positions"],tickerName) #TODO: add safety checks
        currentAmount = float(currentStatus["positionAmt"]) 
        
        existingSide = "BOTH"
        if(currentAmount > 0):
            existingSide = "BUY"
        elif (currentAmount < 0):
            existingSide ="SELL"

        if(existingSide == nextSide):
            print("Side is same as before. Returning...")
            return
        if(currentAmount != 0.0):
            print("Closing existing position for coin: " + tickerName)
            closeExistingPosition(tickerName,currentAmount,client)
        if(not (nextSide == "CLOSE")):
            succed = processBuy(tickerName,nextSide,client,default_price)
        else:
            succed = "Closed..."
    return succed

def changeMarginTypeToIsolated(tickerName,client):
    try:
        client.change_leverage(tickerName,DEFAULT_MULTIPLIER)
        client.change_margin_type(tickerName,"ISOLATED")
        return True
    except Exception as e:
        if(e.error_message != "No need to change margin type."):
            print(e.error_message)
            return False
    return True


def closeExistingPosition(tickerName, currentAmount,client):
    side = "BUY" if (currentAmount < 0) else "SELL"
    params = {
        'symbol': tickerName,
        'side': side,
        'type': 'MARKET',
        'quantity': abs(currentAmount),
    }
    try:        
        client.new_order(**params)
        time.sleep(3)
        client.cancel_open_orders(**{'symbol':tickerName})
        print("Position for " + tickerName + " has been closed. Quantity:" + str(currentAmount))
    except Exception as e:
        print("Could not close position " + "SHORT" if (side == "BUY") else "LONG" + " for coin: " +tickerName +"err: " + e.error_message)
        return
    return


def processBuy(tickerName,side,client,default_price):
    print("Buying new coin: " + tickerName + " on side: " + side)
    priceOfCoin = float(client.mark_price(tickerName)["markPrice"])
    quantity = calculateQuantity(priceOfCoin,tickerName,default_price)
    print(side,quantity)
   
    maxPricePrecision =   getPricePrecision(tickerName)

    print(priceOfCoin)

    stopLossAmount = ((3 / 100) * (priceOfCoin)) / DEFAULT_MULTIPLIER
    takeProfitAmount = ((11 / 100) * (priceOfCoin)) / DEFAULT_MULTIPLIER
    print(priceOfCoin + takeProfitAmount)

    paramsForStopLoss = {
        'symbol':tickerName,
        'side':"SELL" if side == "BUY" else "BUY",
        'type': 'STOP_MARKET',
        'stopPrice': float("{:.{}f}".format(priceOfCoin - stopLossAmount ,maxPricePrecision)) if side == "BUY" else float("{:.{}f}".format(priceOfCoin+stopLossAmount,maxPricePrecision)),
        'closePosition':True
    }
    paramsForTakeProfit = {
        'symbol':tickerName,
        'side':"SELL" if side == "BUY" else "BUY",
        'type': 'TAKE_PROFIT_MARKET',
        'stopPrice': float("{:.{}f}".format(priceOfCoin + takeProfitAmount,maxPricePrecision)) if side == "BUY" else float("{:.{}f}".format(priceOfCoin - takeProfitAmount,maxPricePrecision)),
        'closePosition':True
    }

    params = {
        'symbol': tickerName,
        'side': side,
        'type': 'MARKET',
        'quantity': quantity }
    try:
        client.new_order(**params)
        #client.new_order(**paramsForStopLoss)
        client.new_order(**paramsForTakeProfit)
        print("Succesfully bought coin:" + tickerName + " side: " + side + " quantity: " + str(quantity) + " entry price: " + str(priceOfCoin))
    except Exception as e:
        print("Error happened while buying coin: " + tickerName + " side: " + side + " quantity: " + str(quantity))
        print(e.error_message)
        print(e)
        return False
    return True
    

def calculateQuantity(priceOfCoin,tickerName,default_price):
    quantityPrecision = getQuantityPrecision(tickerName)
    if(quantityPrecision == None):
        print("Cannot get quantity precision. Returning...")
        return 0
    print(default_price)
    quantity = round((default_price / priceOfCoin) * DEFAULT_MULTIPLIER,quantityPrecision)
    print(quantity)
    return quantity

def getCurrentStatusOfCoin(json_object, name):
        return [obj for obj in json_object if obj['symbol']==name][0]

def getQuantityPrecision(tickerName):
    try:
        return int([si['quantityPrecision'] for si in exchangeInfo['symbols'] if si['symbol'] == tickerName][0])
    except:
        return None

def getPricePrecision(tickerName):
    try:
        return int([si['pricePrecision'] for si in exchangeInfo['symbols'] if si['symbol'] == tickerName][0])
    except:
        return None
@app.get("/")
def test():
    for client in clients:
        print(client.account())
    return {}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

