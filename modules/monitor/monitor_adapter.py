from typing import Any, Dict

from data_workflows import DataSourcingWorkflow, MonitorWorkflow
from workflow_settings import (
    sourcing_settings,
    quantum_settings,
    hpc_settings,
    ai_settings,
    cybersecurity_settings,
)


TOPIC_SETTINGS = {
    "quantum": quantum_settings,
    "hpc": hpc_settings,
    "ai": ai_settings,
    "cybersecurity": cybersecurity_settings,
}


def run_monitor_from_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal adapter for the monitor module.

    Expects a MonitorRunRequest-like dict:

        {
          "workflow": "sourcing" | "monitor",
          "topic": "quantum" | "hpc" | "ai" | "cybersecurity",
          "mode": "full" | "no_llm",
          "suppress_ft_crawl": bool,
          "import_manual_data": bool,
          "send_deliverable": bool,
          "send_newsletter": bool
        }
    """

    workflow = req["workflow"]
    topic = req.get("topic")
    mode = req.get("mode", "full")

    if workflow == "sourcing":
        # Allow orchestrator to override suppress_ft_crawl if needed
        sourcing_settings.suppress_ft_crawl = bool(req.get("suppress_ft_crawl", False))

        wf = DataSourcingWorkflow("sourcing", sourcing_settings)
        wf.run()

        return {
            "status": "completed",
            "workflow": "sourcing",
            "topic": None,
            "artifacts": [],
        }

    if workflow == "monitor":
        if topic not in TOPIC_SETTINGS:
            raise ValueError(f"Unsupported topic: {topic}")

        settings_cls = TOPIC_SETTINGS[topic]

        # Mutate settings based on request (simple, explicit knobs)
        settings_cls.suppress_llm_categorization = mode != "no_llm"
        settings_cls.import_manual_data = bool(req.get("import_manual_data", False))
        settings_cls.send_deliverable = bool(req.get("send_deliverable", False))
        settings_cls.send_newsletter = bool(req.get("send_newsletter", False))

        wf = MonitorWorkflow(topic, settings_cls)
        wf.run()

        return {
            "status": "completed",
            "workflow": "monitor",
            "topic": topic,
            "mode": mode,
            "outputs": {
                "db_path": f"modules/monitor/deliverables/{topic}/{topic}.db",
                "data_dir": f"modules/monitor/data/{topic}/",
            },
        }

    raise ValueError(f"Unsupported workflow: {workflow}")


