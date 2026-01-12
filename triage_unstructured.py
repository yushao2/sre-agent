import asyncio
from ai_sre_agent.agent.agent import SREAgentSimple

async def main():
    agent = SREAgentSimple()

    text = """
    In #support-prod: users report 504s on /api/orders since ~10:42.
    Someone said they restarted ingress and it helped for 2 mins.
    Error snippet: upstream timed out while reading response header from upstream.
    Grafana shows p95 latency spiking, DB connections near max.
    """

    out = await agent.triage_unstructured(text, source_hint="support_channel")
    print(out)

if __name__ == "__main__":
    asyncio.run(main())