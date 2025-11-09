# Scheduler


The scheduler in the ```scheduler.py``` is the EFMO's manager which decides when which workflow is executed. 

It defines each workflow by loading the corresponding class from the ```data_workflows.py``` file, e.g:

```
quantum_workflow = MonitorWorkflow("quantum", quantum_settings)
```

and schedules it to run at a certain day and time, e.g.:

```
schedule.every().friday.at("06:35").do(lambda: quantum_workflow.run())
```


The scheduler is started automatically in a temux environment at boot, as documented [here](hardware.md). 


For scheduling the workflows, the following points should be kept in mind:
- Do not schedule two workflows involving LLMs at the same time, if the limits of the API are low.
- Note that the protoype server is up only up between 7:30am and 10:30pm
- Note that the times are UTC, not CET. 
- Not that each workflow may take many hours to complete. 

All output is saved to the ```scheduler.log``` file. 
