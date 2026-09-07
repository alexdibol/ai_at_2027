from .models import CriticReport
class LLMInterface:
 def critique(self,context): raise NotImplementedError
class NullLLM(LLMInterface):
 def critique(self,context): return CriticReport(summary="No external LLM configured; fail-closed.",proposed_actions=[])
