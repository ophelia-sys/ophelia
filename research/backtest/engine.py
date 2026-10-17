import os
from .data_loader import ParquetDataLoader
from .portfolio import PortfolioSimulation
from .cost_models import CostModels

class OpheliaBacktest:
    """
    Permanent Historical Backtest Engine for Ophelia.
    Requires an explicit, pre-existing dataset_id.
    """
    def __init__(self, dataset_id: str, start_ts: int = None, end_ts: int = None, cost_config=CostModels.REALISTIC):
        self.dataset_id = dataset_id
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.cost_config = cost_config
        
        self.loader = ParquetDataLoader()
        self.portfolio = PortfolioSimulation()
        
        # Verify dataset exists immediately and load manifest
        self.manifest = self.loader.load_dataset(self.dataset_id)
        
    def run(self, strategy_adapter):
        """
        Executes the backtest chronologically, chunk by chunk.
        """
        iterator = self.loader.get_chronological_iterator(
            self.dataset_id, 
            self.start_ts, 
            self.end_ts
        )
        
        # In a real environment we would iterate chunks here:
        # for chunk in iterator.fetch_arrow_table().to_batches():
        #     df = chunk.to_pandas()
        #     for row in df.itertuples():
        #         signal = strategy_adapter.on_bar(row)
        #         if signal:
        #            self.portfolio.execute_trade(...)
        
        # We mock the structure here as DuckDB is fully mocked in memory right now.
        return {
            "dataset_id": self.dataset_id,
            "manifest_version": self.manifest.get("schema_version"),
            "final_capital": self.portfolio.capital,
            "realized_pnl": self.portfolio.realized_pnl,
            "total_fees": self.portfolio.total_fees,
            "total_slippage": self.portfolio.total_slippage,
            "trades_count": len(self.portfolio.trade_history)
        }
