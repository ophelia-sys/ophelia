from exchange.bingx_client import BingXClient

client = BingXClient()

print(client.get_leverage("SOL-USD"))