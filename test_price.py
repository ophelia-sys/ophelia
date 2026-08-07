from exchange.bingx_client import BingXClient

client = BingXClient()

price = client.get_latest_price("SOL-USD")

print(price)