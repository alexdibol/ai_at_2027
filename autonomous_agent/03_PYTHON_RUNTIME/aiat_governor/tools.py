from dataclasses import dataclass
from typing import Callable,List,Dict,Any
@dataclass
class ToolSpec:
 name:str; version:str; purpose:str; handler:Callable[...,Any]; permissions:List[str]
class ToolRegistry:
 def __init__(self): self.tools:Dict[str,ToolSpec]={}
 def register(self,spec): self.tools[spec.name]=spec
 def list(self): return sorted(self.tools)
def _placeholder(name):
 def f(**kwargs): return {"tool":name,"status":"PLACEHOLDER","inputs":kwargs}
 return f
def build_default_registry():
 r=ToolRegistry()
 for n in ["validate_mission","validate_data_manifest","build_features","fit_logistic","fit_knn",
           "fit_random_forest","fit_mlp","run_rule_baseline","build_portfolio","run_backtest",
           "run_stress_tests","independent_risk_review","generate_lean","reconcile_lean"]:
  r.register(ToolSpec(n,"0.2.0",n.replace("_"," "),_placeholder(n),["research"]))
 return r
