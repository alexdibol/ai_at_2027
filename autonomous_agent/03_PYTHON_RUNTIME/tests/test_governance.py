from aiat_governor.runtime import run_mission
from aiat_governor.tools import build_default_registry
from aiat_governor.llm import NullLLM
from aiat_governor.audit import InMemoryAuditStore
def test_denied():
 r=run_mission({"objective":"Test momentum."},build_default_registry(),NullLLM(),InMemoryAuditStore())
 assert r.live_authority=="DENIED"
 assert r.status=="MORE_RESEARCH_REQUIRED"
