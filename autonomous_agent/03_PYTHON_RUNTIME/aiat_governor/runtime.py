import uuid
from .models import *
from .lean import generate_minimal_lean
def run_mission(mission_request,registry,llm,store):
 mid=str(uuid.uuid4()); mission=MissionSpec.model_validate(mission_request)
 artifacts={"mission":mission.model_dump(),"governance":GovernanceEnvelope().model_dump(),"data_manifest":DataManifest().model_dump()}
 unresolved=["Point-in-time data validation not yet satisfied.","Wire actual NB00-NB10 quantitative handlers before empirical acceptance."]
 risk=IndependentRiskReport(status="MORE_RESEARCH",findings=["Evidence layer not fully connected."])
 artifacts["risk_report"]=risk.model_dump(); artifacts["critic_report"]=llm.critique(artifacts).model_dump()
 lean_package=generate_minimal_lean() if "quantconnect" in [x.lower() for x in mission.required_output] else None
 recon=ReconciliationReport(passed=False,differences=["Research engine not fully wired."]) if lean_package else None
 return AgentResult(mission_id=mid,status="MORE_RESEARCH_REQUIRED",current_state="CLOSED",artifacts=artifacts,
                    risk_findings=risk.findings,unresolved_issues=unresolved,lean_package=lean_package,
                    reconciliation=recon,live_authority="DENIED")
