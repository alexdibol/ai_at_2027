from .models import LEANPackage
def generate_minimal_lean():
 code="""from AlgorithmImports import *
class AIATGovernedAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020,1,1)
        self.SetCash(100000)
        self.symbol=self.AddEquity("SPY",Resolution.Daily).Symbol
        self.SetWarmUp(30,Resolution.Daily)
    def OnData(self,data):
        if self.IsWarmingUp: return
        # FAIL-CLOSED: insert only validated research translation.
        pass
"""
 return LEANPackage(files={"main.py":code},mapping_notes=["Research/backtest only.","Live authority DENIED."])
