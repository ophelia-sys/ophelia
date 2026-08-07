from exchange.bingx_client import BingXClient

client = BingXClient()

positions = client.get_positions()

print(positions)
