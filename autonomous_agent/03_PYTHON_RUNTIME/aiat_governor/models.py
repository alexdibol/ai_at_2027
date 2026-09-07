from typing import Any,Dict,List,Optional,Literal
from pydantic import BaseModel,Field
class MissionSpec(BaseModel):
 objective:str; asset_class:str="equities"; universe:Optional[str]=None
 research_period:Optional[str]=None; prediction_horizon:Optional[str]=None
 rebalance:Optional[str]=None; constraints:Dict[str,Any]=Field(default_factory=dict)
 required_output:List[str]=Field(default_factory=lambda:["research"]); live_authority:bool=False
class GovernanceEnvelope(BaseModel):
 research_only:bool=True; fail_closed:bool=True; human_review_required:bool=True
class DataManifest(BaseModel):
 sources:List[str]=Field(default_factory=list); point_in_time_checked:bool=False
 survivorship_handled:bool=False; corporate_actions_handled:bool=False
class ExperimentRecord(BaseModel):
 name:str; family:str; params:Dict[str,Any]=Field(default_factory=dict)
 diagnostics:Dict[str,Any]=Field(default_factory=dict); status:str="PLANNED"
class StrategySpec(BaseModel):
 name:str; signal_rule:str; rebalance_frequency:Optional[str]=None; signal_lag:Optional[str]=None
class PortfolioSpec(BaseModel):
 method:str; constraints:Dict[str,Any]=Field(default_factory=dict)
class BacktestEvidence(BaseModel):
 metrics:Dict[str,float]=Field(default_factory=dict); stress_results:Dict[str,Any]=Field(default_factory=dict)
class IndependentRiskReport(BaseModel):
 status:Literal["PASS","MORE_RESEARCH","REJECT","ESCALATE"]; findings:List[str]=Field(default_factory=list)
class CriticReport(BaseModel):
 summary:str; proposed_actions:List[str]=Field(default_factory=list)
class LEANPackage(BaseModel):
 files:Dict[str,str]=Field(default_factory=dict); mapping_notes:List[str]=Field(default_factory=list)
class ReconciliationReport(BaseModel):
 passed:bool=False; differences:List[str]=Field(default_factory=list)
class AgentResult(BaseModel):
 mission_id:str; status:str; current_state:str; artifacts:Dict[str,Any]=Field(default_factory=dict)
 risk_findings:List[str]=Field(default_factory=list); unresolved_issues:List[str]=Field(default_factory=list)
 lean_package:Optional[LEANPackage]=None; reconciliation:Optional[ReconciliationReport]=None
 live_authority:str="DENIED"
