from exchange.bingx_client import BingXClient

client = BingXClient()

print("\nFetching Futures Balance...\n")

response = client.get_balance()

print(response)